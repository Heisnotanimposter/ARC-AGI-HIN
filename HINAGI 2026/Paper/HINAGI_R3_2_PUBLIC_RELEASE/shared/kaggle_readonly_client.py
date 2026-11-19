#!/usr/bin/env python3
"""
ARC-AGI-3 Red Team Governance: Deny-by-Default Read-Only Kaggle Client.

Permitted subcommands:
  1. kaggle competitions submissions ...
  2. kaggle kernels status ...
  3. kaggle kernels output ...

All other subcommands (including 'kernels push', 'competitions submit')
are strictly blocked and raise PermissionError.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PERMITTED_READONLY_COMMANDS = {
    ("competitions", "submissions"),
    ("kernels", "status"),
    ("kernels", "output"),
}

BLOCKED_MUTATING_COMMANDS = {
    ("competitions", "submit"),
    ("kernels", "push"),
    ("kernels", "pull"),
    ("datasets", "create"),
    ("datasets", "version"),
    ("models", "create"),
}


class KaggleReadonlyClient:
    def __init__(self, kaggle_bin: Optional[Path] = None):
        if kaggle_bin is not None:
            self.kaggle_bin = kaggle_bin
        else:
            local_bin = Path(".venv/bin/kaggle")
            self.kaggle_bin = local_bin if local_bin.exists() else Path("kaggle")

    def execute_readonly(self, args: List[str]) -> Dict[str, Any]:
        """
        Executes a strictly read-only Kaggle command.
        Raises PermissionError if mutating or unrecognized.
        Raises RuntimeError if the underlying CLI returns a non-zero exit code.
        """
        if len(args) < 2:
            raise PermissionError(
                f"DENIED: Too few arguments for Kaggle CLI: {args}. Must match permitted read-only commands."
            )

        cmd_tuple = (args[0].lower(), args[1].lower())

        if cmd_tuple not in PERMITTED_READONLY_COMMANDS:
            raise PermissionError(
                f"MUTATION_BLOCKED: Kaggle command '{' '.join(args[:2])}' is strictly prohibited "
                f"under Red Team Governance Policy. Permitted: {sorted(list(PERMITTED_READONLY_COMMANDS))}"
            )

        full_cmd = [str(self.kaggle_bin), *args]
        timestamp = datetime.now(timezone.utc).isoformat()

        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        record = {
            "timestamp_utc": timestamp,
            "command": full_cmd,
            "subcommand_tuple": list(cmd_tuple),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

        if proc.returncode != 0:
            raise RuntimeError(
                f"Kaggle CLI command failed with returncode {proc.returncode}:\n"
                f"Command: {' '.join(full_cmd)}\n"
                f"Stderr: {proc.stderr}\n"
                f"Stdout: {proc.stdout}"
            )

        return record

    def get_kernel_status(self, kernel_slug: str) -> Dict[str, Any]:
        """Strictly parses kernel status into one of: QUEUED, RUNNING, COMPLETE, ERROR, UNKNOWN."""
        rec = self.execute_readonly(["kernels", "status", kernel_slug])
        out = rec["stdout"].strip()

        # Exact matching patterns
        parsed_status = "UNKNOWN"
        for line in out.splitlines():
            if "status" in line.lower():
                line_clean = line.strip().replace('"', "").replace("'", "")
                for candidate in ["QUEUED", "RUNNING", "COMPLETE", "ERROR", "CANCELLED"]:
                    if f"KernelWorkerStatus.{candidate}" in line_clean:
                        parsed_status = candidate
                        break
                    if line_clean.endswith(f"status {candidate}") or line_clean.endswith(f"status: {candidate}"):
                        parsed_status = candidate
                        break

        rec["parsed_status"] = parsed_status
        return rec

    def get_competition_submissions(self, competition: str) -> Dict[str, Any]:
        """Fetches submissions table and parses records strictly."""
        rec = self.execute_readonly(["competitions", "submissions", "-c", competition])
        lines = rec["stdout"].splitlines()
        parsed_records = []
        headers = []

        for line in lines:
            if not line.strip():
                continue
            if "ref" in line.lower() and "filename" in line.lower():
                headers = [h.strip() for h in re.split(r"\s{2,}", line)]
                continue
            if line.startswith("---") or line.startswith("==="):
                continue

            parts = [p.strip() for p in re.split(r"\s{2,}", line)]
            if len(parts) >= 4 and parts[0].isdigit():
                ref = parts[0]
                filename = parts[1]
                # Date and status parsing
                date_str = parts[2]
                status_raw = "UNKNOWN"
                exact_status = "UNKNOWN"
                pub_score = None
                priv_score = None

                for p in parts[3:]:
                    p_upper = p.upper()
                    if "SUBMISSIONSTATUS." in p_upper or p_upper in {"PENDING", "COMPLETE", "ERROR", "FAILED"}:
                        status_raw = p
                        for st in ["PENDING", "COMPLETE", "ERROR", "FAILED"]:
                            if st in p_upper:
                                exact_status = st
                                break
                    else:
                        try:
                            score_val = float(p)
                            if pub_score is None:
                                pub_score = score_val
                            else:
                                priv_score = score_val
                        except ValueError:
                            pass

                parsed_records.append({
                    "ref": ref,
                    "filename": filename,
                    "date": date_str,
                    "raw_status": status_raw,
                    "exact_status": exact_status,
                    "public_score": pub_score,
                    "private_score": priv_score,
                    "raw_line": line,
                })

        rec["parsed_submissions"] = parsed_records
        return rec

    def pull_kernel_output(self, kernel_slug: str, output_dir: Path) -> Dict[str, Any]:
        """Pulls output files from a completed or errored kernel into output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        rec = self.execute_readonly(["kernels", "output", kernel_slug, "-p", str(output_dir)])
        downloaded = [str(p.relative_to(output_dir)) for p in output_dir.glob("**/*") if p.is_file()]
        rec["downloaded_files"] = downloaded
        return rec
