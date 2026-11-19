"""ARC-AGI-3 Runtime Reliability, Monotonic Timing & Readiness Guards.

Implements M2 Workstream specifications:
- Global monotonic clock initialized before any executable workload.
- Immutable 9-hour global deadline with dedicated shutdown buffer (600s).
- Strict fail-closed SGLang server readiness (/health == 200 required).
- Separate diagnostic error taxonomy (SERVER_NOT_READY, SERVER_HTTP_ERROR,
  SERVER_PROCESS_EXITED, INFERENCE_TIMEOUT, GLOBAL_BUDGET_EXHAUSTED).
- Active game session guard protecting against duplicate action dispatch and
  guaranteeing clean telemetry / Parquet flush on mid-game server crash.
- Path auto-discovery with strict FileNotFoundError on missing mounts.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

logger = logging.getLogger("RuntimeGuards")


class DiagnosticErrorCode:
    SERVER_NOT_READY = "SERVER_NOT_READY"
    SERVER_HTTP_ERROR = "SERVER_HTTP_ERROR"
    SERVER_PROCESS_EXITED = "SERVER_PROCESS_EXITED"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    GLOBAL_BUDGET_EXHAUSTED = "GLOBAL_BUDGET_EXHAUSTED"


class RuntimeGuardError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class ServerNotReadyError(RuntimeGuardError):
    def __init__(self, message: str):
        super().__init__(message, DiagnosticErrorCode.SERVER_NOT_READY)


class ServerHTTPError(RuntimeGuardError):
    def __init__(self, message: str, status_code: int):
        super().__init__(f"HTTP {status_code}: {message}", DiagnosticErrorCode.SERVER_HTTP_ERROR)
        self.status_code = status_code


class ServerProcessExitedError(RuntimeGuardError):
    def __init__(self, message: str, exit_code: int):
        super().__init__(f"Exit code {exit_code}: {message}", DiagnosticErrorCode.SERVER_PROCESS_EXITED)
        self.exit_code = exit_code


class InferenceTimeoutError(RuntimeGuardError):
    def __init__(self, message: str):
        super().__init__(message, DiagnosticErrorCode.INFERENCE_TIMEOUT)


class GlobalBudgetExhaustedError(RuntimeGuardError):
    def __init__(self, message: str):
        super().__init__(message, DiagnosticErrorCode.GLOBAL_BUDGET_EXHAUSTED)


class GlobalMonotonicClock:
    """Immutable global monotonic execution clock for Kaggle container budget management."""

    def __init__(
        self,
        total_budget_s: float = 32400.0,    # 9 hours total container limit
        shutdown_buffer_s: float = 600.0,   # 10 minutes reserved for graceful exit & artifact flush
    ):
        self.start_ns: int = time.monotonic_ns()
        self.start_time: float = time.time()
        self.total_budget_s: float = total_budget_s
        self.shutdown_buffer_s: float = shutdown_buffer_s
        self.usable_budget_s: float = max(0.0, total_budget_s - shutdown_buffer_s)
        self.deadline_ns: int = self.start_ns + int(self.usable_budget_s * 1e9)
        self.hard_limit_ns: int = self.start_ns + int(total_budget_s * 1e9)

    def elapsed_s(self) -> float:
        """Seconds elapsed since global container clock initialization."""
        return (time.monotonic_ns() - self.start_ns) / 1e9

    def get_remaining_usable_budget_s(self) -> float:
        """Seconds remaining before graceful shutdown and artifact flush must begin."""
        rem_ns = self.deadline_ns - time.monotonic_ns()
        return max(0.0, rem_ns / 1e9)

    def is_deadline_exceeded(self) -> bool:
        """True if the usable budget has expired (container entered shutdown buffer)."""
        return time.monotonic_ns() >= self.deadline_ns

    def is_hard_limit_exceeded(self) -> bool:
        """True if total container 9-hour limit has expired."""
        return time.monotonic_ns() >= self.hard_limit_ns


class ServerReadinessGuard:
    """Strict fail-closed SGLang server readiness guard.

    Eliminates all fail-open loops and distinguishes error types:
    - proc.poll() != None -> ServerProcessExitedError
    - Health check != 200 -> ServerHTTPError
    - Global budget expired -> GlobalBudgetExhaustedError
    - Timeout -> ServerNotReadyError
    """

    def __init__(
        self,
        port: int = 8001,
        host: str = "127.0.0.1",
        startup_timeout_s: float = 720.0,
        clock: Optional[GlobalMonotonicClock] = None,
        poll_interval_s: float = 2.0,
    ):
        self.port = port
        self.host = host
        self.startup_timeout_s = startup_timeout_s
        self.clock = clock or GlobalMonotonicClock()
        self.poll_interval_s = poll_interval_s
        self.health_url = f"http://{self.host}:{self.port}/health"
        self.is_ready = False
        self.last_error_code: Optional[str] = None

    def wait_for_ready(
        self,
        proc: Optional[Any] = None,
        log_tail_fn: Optional[Callable[[], None]] = None,
    ) -> bool:
        t0 = time.monotonic()
        last_report = -30.0
        last_status_code = None

        while True:
            # 1. Process termination check
            if proc is not None and proc.poll() is not None:
                if log_tail_fn:
                    log_tail_fn()
                self.is_ready = False
                self.last_error_code = DiagnosticErrorCode.SERVER_PROCESS_EXITED
                raise ServerProcessExitedError(
                    "SGLang server process terminated prematurely before becoming ready.",
                    exit_code=proc.returncode,
                )

            # 2. Global budget check
            if self.clock.is_deadline_exceeded():
                if log_tail_fn:
                    log_tail_fn()
                self.is_ready = False
                self.last_error_code = DiagnosticErrorCode.GLOBAL_BUDGET_EXHAUSTED
                raise GlobalBudgetExhaustedError(
                    f"Global container budget expired ({self.clock.usable_budget_s:.1f}s) while awaiting server readiness."
                )

            # 3. Startup timeout check
            elapsed = time.monotonic() - t0
            if elapsed >= self.startup_timeout_s:
                if log_tail_fn:
                    log_tail_fn()
                self.is_ready = False
                if last_status_code is not None and last_status_code >= 500:
                    self.last_error_code = DiagnosticErrorCode.SERVER_HTTP_ERROR
                    raise ServerHTTPError(
                        f"Server repeatedly returned HTTP error {last_status_code} during startup.",
                        status_code=last_status_code,
                    )
                self.last_error_code = DiagnosticErrorCode.SERVER_NOT_READY
                raise ServerNotReadyError(
                    f"SGLang server readiness timed out after {elapsed:.1f}s (configured limit: {self.startup_timeout_s:.1f}s)."
                )

            # 4. HTTP health check
            try:
                with urlopen(self.health_url, timeout=min(5.0, self.startup_timeout_s)) as resp:
                    last_status_code = resp.status
                    if resp.status == 200:
                        self.is_ready = True
                        logger.info(f"SGLang server ready after {elapsed:.1f}s on {self.health_url}")
                        return True
                    else:
                        last_status_code = resp.status
            except HTTPError as http_err:
                last_status_code = http_err.code
            except Exception:
                pass

            if elapsed - last_report >= 30.0:
                logger.info(
                    f"Awaiting server readiness: {int(elapsed)}s elapsed, "
                    f"remaining global budget: {self.clock.get_remaining_usable_budget_s():.1f}s"
                )
                last_report = elapsed

            time.sleep(self.poll_interval_s)

    def verify_health_before_game(self, timeout_s: float = 3.0) -> bool:
        """Pre-game health assertion called by the solver before dispatching gameplay actions."""
        if self.clock.is_deadline_exceeded():
            self.last_error_code = DiagnosticErrorCode.GLOBAL_BUDGET_EXHAUSTED
            raise GlobalBudgetExhaustedError("Global container budget exceeded before game execution.")

        try:
            with urlopen(self.health_url, timeout=timeout_s) as resp:
                if resp.status == 200:
                    return True
                self.last_error_code = DiagnosticErrorCode.SERVER_HTTP_ERROR
                raise ServerHTTPError("SGLang /health returned non-200 status code", resp.status)
        except Exception as exc:
            self.is_ready = False
            self.last_error_code = DiagnosticErrorCode.SERVER_NOT_READY
            raise ServerNotReadyError(f"SGLang server is not ready before game dispatch: {exc!r}") from exc


class ActiveGameSessionGuard:
    """Guards an in-flight game session against mid-request crashes and duplicate action dispatch."""

    def __init__(self, game_id: str, working_dir: Path):
        self.game_id = game_id
        self.working_dir = working_dir
        self.dispatched_actions: List[Dict[str, Any]] = []
        self.in_flight_request: bool = False
        self.is_terminated: bool = False
        self.termination_reason: Optional[str] = None
        self.diagnostic_code: Optional[str] = None

    def begin_inference_request(self) -> None:
        if self.is_terminated:
            raise RuntimeError(f"Cannot begin inference: game {self.game_id} is already terminated.")
        self.in_flight_request = True

    def end_inference_request(self) -> None:
        self.in_flight_request = False

    def dispatch_action(self, action_name: str, action_data: Optional[Dict[str, Any]] = None) -> int:
        """Dispatches an environment action only after inference completes successfully."""
        if self.in_flight_request:
            raise RuntimeError(
                f"Safety Violation: Cannot dispatch action '{action_name}' while an inference request is in-flight! "
                "Actions must only be dispatched after inference response is validated."
            )
        action_idx = len(self.dispatched_actions)
        record = {
            "action_index": action_idx,
            "action_name": action_name,
            "action_data": action_data or {},
            "timestamp": time.time(),
        }
        self.dispatched_actions.append(record)
        return action_idx

    def handle_inference_failure(self, error: Exception) -> Dict[str, Any]:
        """Safely terminates the game on mid-request inference failure without duplicate action dispatch."""
        self.in_flight_request = False
        self.is_terminated = True
        self.termination_reason = str(error)

        if isinstance(error, RuntimeGuardError):
            self.diagnostic_code = error.code
        elif "timeout" in str(error).lower():
            self.diagnostic_code = DiagnosticErrorCode.INFERENCE_TIMEOUT
        else:
            self.diagnostic_code = DiagnosticErrorCode.SERVER_PROCESS_EXITED

        # Build consistent incomplete-game diagnostic record
        flush_record = {
            "game_id": self.game_id,
            "state": "gave_up",
            "error": self.termination_reason,
            "diagnostic_code": self.diagnostic_code,
            "total_actions_dispatched": len(self.dispatched_actions),
            "final_score": 0.0,
            "levels_completed": 0,
        }

        # Flush diagnostic JSONL
        self.working_dir.mkdir(parents=True, exist_ok=True)
        diag_path = self.working_dir / f"{self.game_id}_failure_record.json"
        with open(diag_path, "w", encoding="utf-8") as f:
            json.dump(flush_record, f, indent=2)

        logger.warning(
            f"Game {self.game_id} safely aborted due to {self.diagnostic_code}. "
            f"Actions dispatched: {len(self.dispatched_actions)}. In-flight request cleared."
        )
        return flush_record


def discover_mount(
    default_path: str,
    marker_filename: str,
    path_keyword: str = "",
    search_root: Path = Path("/kaggle/input"),
) -> str:
    """Strict discovery helper: searches search_root for marker_filename.
    
    Raises FileNotFoundError if marker is not found.
    """
    if Path(default_path).exists():
        return str(default_path)

    kw = path_keyword.lower()
    if search_root.exists():
        for hit in sorted(search_root.rglob(marker_filename)):
            if not kw or kw in str(hit).lower():
                return str(hit.parent)

    raise FileNotFoundError(
        f"Could not find required mount marker '{marker_filename}' (keyword={path_keyword!r}) under {search_root}"
    )
