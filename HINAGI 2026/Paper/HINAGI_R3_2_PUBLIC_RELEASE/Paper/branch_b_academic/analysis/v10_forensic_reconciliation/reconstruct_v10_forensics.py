#!/usr/bin/env python3
"""Deterministic V10 forensic reconstruction and reconciliation generator.

Reads strictly READ-ONLY from canonical artifacts under ``HINAGI 2026/`` and writes
all reconstructed machine-readable tables and manifests strictly inside
``HINAGI 2026/Paper/branch_b_academic/analysis/v10_forensic_reconciliation/``.
"""

from __future__ import annotations

import base64
import csv
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("R1_PACKAGE_ROOT", Path(__file__).resolve().parents[4]))
V10_DIR = Path(os.environ.get("R1_V10_DIR", REPO_ROOT / "submissions/arc3_v10_verified"))
OUT_DIR = Path(os.environ.get("R1_REC_OUT_DIR", REPO_ROOT / "replay_out/v10_forensic_reconciliation"))

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYSIS_DIR))
import build_v10_eviction_token_tables as b  # read-only reuse of canonical parsers

REQTIME_RE = re.compile(
    r"^\[([^\]]+)\]\s+ReqTimeStats\(rid=([^,]+),\s+input_len=(\d+),\s+"
    r"cached_input_len=(\d+),\s+output_len=(\d+),\s+attempts=(\d+),\s+"
    r"type=([^)]+)\):\s+queue_duration=([0-9.]+)ms,\s+"
    r"initial_prefill_elapsed=([0-9.]+)ms,\s+post_prefill_elapsed=([0-9.]+)ms,\s+"
    r"forward_duration=([0-9.]+)ms,\s+entry_time=([0-9.]+)"
)
POST_HTTP_RE = re.compile(
    r'^\[([^\]]+)\]\s+INFO:\s+127\.0\.0\.1:\d+\s+-\s+"(GET|POST)\s+(\S+)\s+HTTP/1\.1"\s+(\d+)'
)
SOTA_TIMEOUT_RE = re.compile(
    r"analyzer request timed out at action (\d+);.*read timeout=([0-9.]+)"
)
CAL_EVENT_RE = re.compile(
    r"text_token_calibration: ([0-9.]+) chars/token(?: \(clamped from ([0-9.]+)\))? "
    r"\[prompt_tokens (\d+), images (\d+), text chars (\d+)\]"
)

_VISION_PATCH_PIXELS = 32
_VISION_SENTINEL_TOKENS = 2
_IMAGE_TOKENS_FALLBACK = 402
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CONTEXT_BUDGET_TOKENS = 44544
_CONTEXT_DRAIN_TOKENS = 16384
_CONTEXT_TARGET_TOKENS = _CONTEXT_BUDGET_TOKENS - _CONTEXT_DRAIN_TOKENS  # 28160


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _png_dimensions(data_url: str) -> tuple[int, int] | None:
    marker = "base64,"
    idx = data_url.find(marker)
    if idx < 0:
        return None
    head = data_url[idx + len(marker) : idx + len(marker) + 32]
    if len(head) < 32:
        return None
    try:
        raw = base64.b64decode(head, validate=True)
    except Exception:
        return None
    if len(raw) < 24 or not raw.startswith(_PNG_SIGNATURE) or raw[12:16] != b"IHDR":
        return None
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    if w <= 0 or h <= 0:
        return None
    return w, h


def _image_part_tokens(part: dict[str, Any]) -> int:
    url = ""
    img_url = part.get("image_url")
    if isinstance(img_url, dict):
        url = str(img_url.get("url") or "")
    dims = _png_dimensions(url) if url else None
    if dims is None:
        return _IMAGE_TOKENS_FALLBACK
    w, h = dims
    cells = (-(-w // _VISION_PATCH_PIXELS)) * (-(-h // _VISION_PATCH_PIXELS))
    return cells + _VISION_SENTINEL_TOKENS


def _split_messages_for_estimate(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Mirror tool_agent._split_messages_for_estimate and also count image parts."""
    image_tokens = 0
    image_count = 0
    rewritten: list[dict[str, Any]] = []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            rewritten.append(m)
            continue
        parts: list[Any] = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "image_url":
                image_tokens += _image_part_tokens(p)
                image_count += 1
                parts.append({"type": "image_url", "image_url": {"url": "<image>"}})
            else:
                parts.append(p)
        rewritten.append({**m, "content": parts})
    return rewritten, image_tokens, image_count


def _estimate_payload_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_choice: str | None,
    chars_per_token: float,
) -> tuple[int, int, int, int]:
    """Return (est_tokens, image_tokens, image_count, rendered_chars)."""
    scrubbed, img_toks, img_cnt = _split_messages_for_estimate(messages)
    payload: dict[str, Any] = {"messages": scrubbed}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    text_est = max(
        1,
        int(len(rendered) / chars_per_token)
        + (1 if len(rendered) % chars_per_token else 0),
    )
    return text_est + img_toks, img_toks, img_cnt, len(rendered)


def _find_missing_tool_call_ids(messages: list[dict[str, Any]]) -> list[str]:
    """Verify whether any assistant tool_call ID lacks a following role='tool' reply."""
    expected: dict[str, str] = {}
    for idx, msg in enumerate(messages):
        role = str(msg.get("role", "")).strip()
        if role == "assistant":
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict) and tc.get("id"):
                    expected[str(tc["id"])] = f"msg[{idx}]"
        elif role == "tool":
            tcid = msg.get("tool_call_id")
            if tcid and str(tcid) in expected:
                del expected[str(tcid)]
    return [f"{k}@{v}" for k, v in expected.items()]


def _file_role(rel: str) -> str:
    if rel == "benchmark.json":
        return "harness_benchmark_json"
    if rel == "summary.txt":
        return "harness_summary_txt"
    if rel == "requests.jsonl":
        return "detached_final_response_log"
    if rel == "serve.log":
        return "sglang_server_log"
    if rel == "arc-agi-3-sota.log":
        return "kaggle_notebook_stdout_stderr_log"
    if rel == "submission.parquet":
        return "kaggle_submission_parquet"
    if rel == "diagnostics.html":
        return "harness_diagnostics_html"
    if rel == "games.pkl":
        return "serialized_game_catalog_pickle"
    if rel.endswith("_p0_requests.jsonl"):
        return "per_game_llm_request_response_log"
    if rel.startswith("artifacts/") and rel.endswith("_p0_events.jsonl"):
        return "per_game_execution_events_log"
    if rel.startswith("prompts/") and rel.endswith("_p0.log"):
        return "per_game_rendered_prompt_log"
    if rel.startswith("movies/") and rel.endswith("_p0.html"):
        return "per_game_replay_movie_html"
    if rel.endswith(".txt") or rel.endswith(".json") or rel.endswith(".html"):
        return "run_metadata_or_report"
    return "auxiliary_run_file"


def _record_count(path: Path) -> str:
    name = path.name
    if name == "benchmark.json":
        try:
            return str(len(json.loads(path.read_text(encoding="utf-8")).get("game_runs", [])))
        except Exception:
            return ""
    if path.suffix in {".jsonl", ".txt", ".log", ".csv"}:
        # Count LF newlines without splitting on CR
        return str(path.read_bytes().count(b"\n"))
    return ""


def build_artifact_inventory(*, r1_portable: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build inventory over Tier R1 files on disk plus GA-04 excluded binary metadata pointers."""
    meta_path = REPO_ROOT / "excluded_artifacts_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if (r1_portable and meta_path.exists()) else {}

    siblings = {
        "pulled_arc3_output": REPO_ROOT / "submissions/pulled_from_kaggle/arc3_output",
        "arc3_output": REPO_ROOT / "submissions/arc3_output",
        "v6_smoke": REPO_ROOT / "submissions/arc3_v6_smoke_verified",
        "v8_smoke": REPO_ROOT / "submissions/arc3_v8_smoke_verified",
        "v9_smoke": REPO_ROOT / "submissions/arc3_v9_smoke_verified",
    }
    sib_hashes: dict[str, dict[str, str]] = {}
    sib_counts: dict[str, dict[str, int]] = {}
    for key, sroot in siblings.items():
        if not sroot.exists():
            sib_hashes[key] = {}
            sib_counts[key] = meta.get("siblings_summary", {}).get(key, {"files": 0, "bytes": 0})
            continue
        hmap: dict[str, str] = {}
        total_b = 0
        for p in sorted(sroot.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(sroot))
                raw = p.read_bytes()
                hmap[rel] = sha256_bytes(raw)
                total_b += len(raw)
        sib_hashes[key] = hmap
        sib_counts[key] = {"files": len(hmap), "bytes": total_b}

    rows: list[dict[str, Any]] = []
    v10_hashes: dict[str, str] = {}
    v10_bytes = 0
    for p in sorted(V10_DIR.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(V10_DIR))
        raw = p.read_bytes()
        h = sha256_bytes(raw)
        st = p.stat()
        v10_hashes[rel] = h
        v10_bytes += len(raw)
        mtime = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat()
        rows.append(
            {
                "scope": "v10_r1_bundled_sanitized" if rel == "arc-agi-3-sota.log" else "v10_r1_bundled_verified",
                "relative_path": f"submissions/arc3_v10_verified/{rel}",
                "size_bytes": len(raw),
                "sha256": h,
                "mtime_utc": mtime,
                "record_count": _record_count(p),
                "file_role": _file_role(rel),
                "identical_in_pulled_arc3_output": "METADATA_ONLY_IN_R1",
                "v8_smoke_match": "EXCLUDED_IN_R1",
                "v6_smoke_match": "SAME_HASH" if sib_hashes["v6_smoke"].get(rel) == h else ("DIFF_HASH" if rel in sib_hashes["v6_smoke"] else "ABSENT"),
                "arc3_output_match": "EXCLUDED_IN_R1",
            }
        )

    for item in meta.get("excluded_v10_artifacts", []):
        rows.append(
            {
                "scope": f"v10_excluded_in_r1_{item['exclusion_reason']}",
                "relative_path": item["relative_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
                "mtime_utc": "EXCLUDED_BINARY_METADATA_ONLY",
                "record_count": "",
                "file_role": _file_role(item["relative_path"].replace("submissions/arc3_v10_verified/", "")),
                "identical_in_pulled_arc3_output": "EXCLUDED_IN_R1",
                "v8_smoke_match": "EXCLUDED_IN_R1",
                "v6_smoke_match": "EXCLUDED_IN_R1",
                "arc3_output_match": "EXCLUDED_IN_R1",
            }
        )

    comparators = [
        ("artifacts/phase6_5/reference_snapshots/v6_reference.ipynb", "reference_notebook_v6"),
        ("artifacts/phase6_5/reference_snapshots/v10_reference.ipynb", "reference_notebook_v10"),
        ("Paper/ARC3_V13_Followup_Artifact_57912660.ipynb", "reference_notebook_v13"),
        ("artifacts/phase6_5/reference_snapshots/phase6_3_candidate.ipynb", "reference_notebook_phase6_3"),
        ("artifacts/phase5_4/submission_57827259_status.json", "kaggle_cli_status_snapshot_pending"),
        ("Paper/ARC3_Version_History_Evidence_Ledger.md", "version_history_evidence_ledger"),
        ("reference/arc3_franzen_m2/ARC3-Inference/inference/agent/tool_agent.py", "source_tool_agent_py"),
        ("reference/arc3_franzen_m2/ARC3-Inference/inference/framework/solver.py", "source_solver_py"),
        ("Paper/branch_b_academic/analysis/build_v10_eviction_token_tables.py", "portable_v10_analysis_script"),
        ("Paper/branch_b_academic/analysis/test_v10_eviction_token_tables.py", "existing_v10_analysis_test"),
        ("submissions/arc3_v6_smoke_verified/benchmark.json", "v6_smoke_benchmark_json"),
        ("submissions/arc3_v6_smoke_verified/arc-agi-3-sota.log", "v6_smoke_sota_log_sanitized"),
    ]
    for rel, role in comparators:
        p = REPO_ROOT / rel
        raw = p.read_bytes()
        st = p.stat()
        rows.append(
            {
                "scope": "comparator_or_canonical_source",
                "relative_path": rel,
                "size_bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "mtime_utc": dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat(),
                "record_count": _record_count(p),
                "file_role": role,
                "identical_in_pulled_arc3_output": "N/A",
                "v8_smoke_match": "N/A",
                "v6_smoke_match": "N/A",
                "arc3_output_match": "N/A",
            }
        )

    cross_summary = {
        "r1_portable_mode": r1_portable,
        "v10_bundled_files": len(v10_hashes),
        "v10_bundled_bytes": v10_bytes,
        "v10_excluded_files": len(meta.get("excluded_v10_artifacts", [])),
        "v10_excluded_bytes": meta.get("v10_raw_totals", {}).get("excluded_v10_bytes", 0),
        "siblings": meta.get("siblings_summary", sib_counts),
        "sanitized_log_hashes": meta.get("sanitized_files", {}),
    }
    return rows, cross_summary


def parse_serve_log_exact() -> list[dict[str, Any]]:
    """Parse all 360 ReqTimeStats records using LF-only line numbering matching read_file/wc -l."""
    raw_lines = (V10_DIR / "serve.log").read_bytes().decode("utf-8", errors="replace").split("\n")
    rows: list[dict[str, Any]] = []
    for ln_no, ln in enumerate(raw_lines, 1):
        m = REQTIME_RE.search(ln)
        if not m:
            continue
        ts, rid, in_len, cached_len, out_len, attempts, typ, q_ms, init_ms, post_ms, fwd_ms, entry = m.groups()
        next_ln = raw_lines[ln_no] if ln_no < len(raw_lines) else ""
        http_m = POST_HTTP_RE.search(next_ln)
        http_logged = f"{http_m.group(2)} {http_m.group(3)} {http_m.group(4)}" if http_m else "NONE_IMMEDIATE"
        rows.append(
            {
                "serve_line_nl": ln_no,
                "serve_ts_utc": ts,
                "serve_rid": rid,
                "serve_input_len": int(in_len),
                "serve_cached_len": int(cached_len),
                "serve_output_len": int(out_len),
                "serve_attempts": int(attempts),
                "serve_queue_ms": float(q_ms),
                "serve_forward_ms": float(fwd_ms),
                "serve_entry_time": float(entry),
                "serve_http_logged": http_logged,
            }
        )
    return rows


def parse_sota_game_timings() -> dict[str, dict[str, Any]]:
    """Extract [finished] and timeout wallclock lines per game from arc-agi-3-sota.log."""
    raw = (V10_DIR / "arc-agi-3-sota.log").read_text(encoding="utf-8").splitlines()
    fin_re = re.compile(r"\[finished\]\s+(\S+)\s+state=(\S+)")
    to_events: list[tuple[float, int, float]] = []
    out: dict[str, dict[str, Any]] = {}
    for ln in raw:
        if '"time"' not in ln:
            continue
        try:
            obj = json.loads(ln.lstrip(","))
        except Exception:
            continue
        t = float(obj.get("time", 0.0))
        data = str(obj.get("data", ""))
        tm = SOTA_TIMEOUT_RE.search(data)
        if tm:
            to_events.append((t, int(tm.group(1)), float(tm.group(2))))
        fm = fin_re.search(data)
        if fm:
            gid = fm.group(1)
            out[gid] = {"sota_finish_t": t, "sota_state": fm.group(2)}
    # Attach closest immediately preceding timeout event (<2s before finish)
    for gid, info in out.items():
        ft = info["sota_finish_t"]
        matched_to = [ev for ev in to_events if 0.0 <= ft - ev[0] <= 2.0]
        if matched_to:
            ev = matched_to[-1]
            info["timeout_sota_t"] = ev[0]
            info["timeout_action_num"] = ev[1]
            info["timeout_seconds"] = ev[2]
        else:
            info["timeout_sota_t"] = None
            info["timeout_action_num"] = None
            info["timeout_seconds"] = None
    return out


def reconstruct_all(*, r1_portable: bool = True) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bm = json.loads((V10_DIR / "benchmark.json").read_text(encoding="utf-8"))
    bm_by_gid = {gr["game_id"]: gr for gr in bm["game_runs"]}
    _, sum_per_game = b.parse_summary_txt(V10_DIR / "summary.txt")
    sota_parsed = b.parse_sota_log(V10_DIR / "arc-agi-3-sota.log")
    sota_timings = parse_sota_game_timings()
    serve_rows = parse_serve_log_exact()

    # Verify root requests.jsonl detached record matches g50t idx=15
    root_lines = [
        json.loads(ln)
        for ln in (V10_DIR / "requests.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(root_lines) == 1 and root_lines[0]["event"] == "response"
    root_resp = root_lines[0]

    # Pre-benchmark warmup/health rows in serve_rows
    warmup_rows = serve_rows[:3]
    agent_serve_rows = serve_rows[3:]
    assert len(warmup_rows) == 3
    assert len(agent_serve_rows) == 357

    # Partition agent_serve_rows into 353 HTTP-completed and 4 timeout candidates
    # Wait: let's match by exact (input_len, cached_input_len) first, then disambiguate collisions via
    # (output_len >= completion_tokens and output_len - completion_tokens <= 3) + chronological completion vs game finish!
    serve_pool: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for sr in agent_serve_rows:
        serve_pool[(sr["serve_input_len"], sr["serve_cached_len"])].append(sr)

    req_rows: list[dict[str, Any]] = []
    game_rows_352: list[dict[str, Any]] = []
    cal_matches = 0
    cal_total = 0

    # Gather live calibration transcripts from events
    live_cals: dict[str, dict[int, tuple[float, int, int]]] = defaultdict(dict)
    event_counts: dict[str, Counter[str]] = {}
    for gid in sorted(bm_by_gid):
        ep = V10_DIR / "artifacts" / f"{gid}_p0_events.jsonl"
        c: Counter[str] = Counter()
        for ln in ep.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            rec = json.loads(ln)
            c[rec.get("type", "unknown")] += 1
            for m in CAL_EVENT_RE.finditer(rec.get("transcript", "")):
                cal_total += 1
                live_cals[gid][int(m.group(3))] = (float(m.group(1)), int(m.group(4)), int(m.group(5)))
        event_counts[gid] = c

    # Benchmark clock origin epoch from benchmark.end_time - sota max finish / end
    # Using sota t=2102.01 ~= 2026-10-30 05:30:19 UTC -> offset for time ordering
    end_epoch = dt.datetime.fromisoformat(bm["end_time"]).replace(tzinfo=dt.timezone.utc).timestamp()
    sota_origin_epoch = end_epoch - 2102.00838

    all_client_reqs: list[dict[str, Any]] = []
    game_pre_summaries: dict[str, dict[str, Any]] = {}

    for gid in sorted(bm_by_gid):
        rp = V10_DIR / f"{gid}_p0_requests.jsonl"
        pairs = b.pair_requests_and_responses(rp)
        gr = bm_by_gid[gid]
        n_hist = len(gr.get("history", []))
        cal = 3.0
        fifo_info: dict[str, Any] | None = None

        # Pre-compute game stats under both per-game-only (352) and full-client (+root = 353)
        pairs_with_root = list(pairs)
        root_attached_idx = None
        if gid == "g50t-5849a774":
            last_i, last_req, last_resp = pairs_with_root[-1]
            assert last_resp is None
            for k in ("messages", "tools", "chat_template_kwargs", "tool_choice", "analysis_step", "action", "request_index_within_turn"):
                assert root_resp[k] == last_req[k], f"g50t root mismatch on {k}"
            pairs_with_root[-1] = (last_i, last_req, root_resp)
            root_attached_idx = last_i

        for idx, req, resp in pairs:
            trans, div_idx = b.classify_prefix_transition(idx, pairs)
            msgs = req.get("messages") or []
            tools = req.get("tools") or []
            tc = req.get("tool_choice")
            est_tok, img_tok_est, img_cnt, rend_chars = _estimate_payload_tokens(msgs, tools, tc, cal)
            missing_tc = _find_missing_tool_call_ids(msgs)

            # Check eviction pre-trim estimate at FIFO boundary using prior request + block boundary
            if trans == "fifo_eviction":
                _, prev_req, _ = pairs[idx - 1]
                pm = prev_req.get("messages") or []
                # Estimate without opener vs full
                post_no_open, _, _, _ = _estimate_payload_tokens(msgs[:-1], tools, tc, cal)

                def _txt(m: dict[str, Any]) -> str:
                    c = m.get("content")
                    if isinstance(c, list):
                        return "".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
                    return str(c or "")

                sig1 = _txt(msgs[1]).replace("[grid image omitted from history]", "")
                match_k = next((k for k in range(1, len(pm)) if _txt(pm[k]).replace("[grid image omitted from history]", "") == sig1), None)
                pre_raw_est = None
                pre_win4_eos_est = None
                if match_k is not None:
                    overlap_len = len(pm) - match_k
                    new_tail = msgs[1 + overlap_len :]
                    raw_pre = [msgs[0], *pm[1:], *new_tail]
                    pre_raw_est, _, _, _ = _estimate_payload_tokens(raw_pre, tools, tc, cal)
                    img_user_idxs = [
                        mi
                        for mi, m in enumerate(raw_pre[:-1])
                        if m.get("role") == "user"
                        and isinstance(m.get("content"), list)
                        and any(isinstance(p, dict) and p.get("type") == "image_url" for p in m["content"])
                    ]
                    keep_set = set(img_user_idxs[-4:])
                    win4_eos = []
                    for mi, m in enumerate(raw_pre[:-1]):
                        if mi not in img_user_idxs or mi in keep_set:
                            win4_eos.append(m)
                        else:
                            win4_eos.append(
                                {
                                    **m,
                                    "content": [
                                        {"type": "text", "text": "[grid image omitted from history]"}
                                        if isinstance(p, dict) and p.get("type") == "image_url"
                                        else p
                                        for p in m["content"]
                                    ],
                                }
                            )
                    pre_win4_eos_est, _, _, _ = _estimate_payload_tokens(win4_eos, tools, tc, cal)
                trim_site = (
                    "L6323_end_of_step"
                    if (est_tok > _CONTEXT_TARGET_TOKENS or (pre_win4_eos_est is not None and pre_win4_eos_est > _CONTEXT_BUDGET_TOKENS))
                    else "L6699_start_of_step_or_resume"
                )
                fifo_info = {
                    "idx": idx,
                    "cal": round(cal, 4),
                    "pre_raw_est": pre_raw_est,
                    "pre_win4_eos_est": pre_win4_eos_est,
                    "post_est_full": est_tok,
                    "post_est_no_opener": post_no_open,
                    "prev_msgs": len(pm),
                    "cur_msgs": len(msgs),
                    "matched_prev_pos": match_k,
                    "trim_site": trim_site,
                }

            eff_resp = root_resp if (gid == "g50t-5849a774" and idx == root_attached_idx) else resp
            req_action = int(req.get("action") or 0)
            attr_here = req_action <= n_hist
            resp_loc = "root_requests_jsonl" if idx == root_attached_idx else ("per_game_requests_jsonl" if resp is not None else "TIMEOUT_NO_RESPONSE")

            row: dict[str, Any] = {
                "row_type": "client_request",
                "game_id": gid,
                "client_req_idx": idx,
                "source_file": f"submissions/arc3_v10_verified/{gid}_p0_requests.jsonl",
                "request_logged": "True",
                "response_logged": str(eff_resp is not None),
                "response_location": resp_loc,
                "analysis_step": req.get("analysis_step"),
                "action": req_action,
                "request_index_within_turn": req.get("request_index_within_turn"),
                "prefix_transition": trans,
                "divergent_idx": div_idx,
                "message_count": len(msgs),
                "image_count_client": img_cnt,
                "est_tokens_calibrated": est_tok,
                "cal_chars_per_token": round(cal, 4),
                "prompt_tokens": "",
                "cached_tokens": "",
                "uncached_prompt_tokens": "",
                "cache_hit_pct": "",
                "image_tokens_usage": "",
                "completion_tokens": "",
                "reasoning_tokens": "",
                "output_non_reasoning_tokens": "",
                "total_tokens": "",
                "finish_reason": "",
                "action_bucket": "action_attributed" if attr_here else "trailing_post_action",
                "action_attributed_here": str(attr_here),
                "post_final_action_flag": str(not attr_here),
                "missing_tool_call_ids": ";".join(missing_tc),
            }
            if eff_resp is not None:
                u = eff_resp["usage"]
                pt = int(u["prompt_tokens"])
                ct = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
                comp = int(u["completion_tokens"])
                reas = int(u.get("reasoning_tokens") or 0)
                img_u = int((u.get("prompt_tokens_details") or {}).get("image_tokens") or 0)
                row.update(
                    {
                        "prompt_tokens": pt,
                        "cached_tokens": ct,
                        "uncached_prompt_tokens": pt - ct,
                        "cache_hit_pct": round(100.0 * ct / pt, 4) if pt else 0.0,
                        "image_tokens_usage": img_u,
                        "completion_tokens": comp,
                        "reasoning_tokens": reas,
                        "output_non_reasoning_tokens": comp - reas,
                        "total_tokens": int(u.get("total_tokens") or (pt + comp)),
                        "finish_reason": eff_resp.get("finish_reason", ""),
                    }
                )
                # Verify live calibration transcript if logged on this pt
                text_tokens = pt - img_tok_est
                if text_tokens > 0 and rend_chars > 0:
                    measured = rend_chars / text_tokens
                    clamped = min(3.3, max(1.0, measured))
                    if pt in live_cals[gid]:
                        lc, li, lch = live_cals[gid][pt]
                        assert round(clamped, 2) == round(lc, 2) and img_tok_est == li and rend_chars == lch
                        cal_matches += 1
                    cal = clamped

            all_client_reqs.append(row)

        u352 = b.sum_response_usage(pairs)
        u353 = b.sum_response_usage(pairs_with_root)
        game_pre_summaries[gid] = {
            "pairs": pairs,
            "pairs_with_root": pairs_with_root,
            "u352": u352,
            "u353": u353,
            "fifo_info": fifo_info,
        }

    assert cal_matches == cal_total, f"Live calibration mismatch: {cal_matches} != {cal_total}"

    # Match client responses to serve_log ReqTimeStats!
    used_rids: set[str] = set()
    for r in all_client_reqs:
        if r["response_logged"] != "True":
            continue
        k = (int(r["prompt_tokens"]), int(r["cached_tokens"]))
        cands = [s for s in serve_pool.get(k, []) if s["serve_rid"] not in used_rids]
        comp = int(r["completion_tokens"])
        # Filter by 0 <= output_len - completion_tokens <= 3
        valid = [s for s in cands if 0 <= (s["serve_output_len"] - comp) <= 3]
        assert valid, f"No valid serve match for {r['game_id']} idx={r['client_req_idx']} {k} comp={comp}"
        if len(valid) == 1:
            chosen = valid[0]
            match_status = "EXACT_UNIQUE_1TO1"
        else:
            # Disambiguate colliding (in_len, cached_len, ~out_len) by comparing server timestamp against
            # game finish epoch (sota_finish_t + sota_origin_epoch): choose latest candidate that finished BEFORE game's finish epoch
            fin_epoch = sota_origin_epoch + sota_timings[r["game_id"]]["sota_finish_t"]
            before_fin = []
            for s in valid:
                se = dt.datetime.strptime(s["serve_ts_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
                if se <= fin_epoch + 5.0:
                    before_fin.append((abs(fin_epoch - se), se, s))
            if r["client_req_idx"] == 0:
                # For index 0 requests, pick closest to game started_at + forward latency!
                st_epoch = dt.datetime.fromisoformat(bm_by_gid[r["game_id"]]["started_at"]).replace(tzinfo=dt.timezone.utc).timestamp()
                valid_sorted = sorted(
                    valid,
                    key=lambda s: abs(
                        s["serve_entry_time"] - st_epoch
                    ),
                )
                chosen = valid_sorted[0]
            else:
                before_fin.sort(key=lambda x: x[0])
                chosen = before_fin[0][2]
            match_status = "COLLIDING_KEY_TIME_DISAMBIGUATED"
        used_rids.add(chosen["serve_rid"])
        r.update({**chosen, "serve_match_status": match_status})

    # Remaining 4 serve rows MUST correspond to the 4 timeout requests!
    leftover_serve = [s for s in agent_serve_rows if s["serve_rid"] not in used_rids]
    assert len(leftover_serve) == 4
    timeout_reqs = [r for r in all_client_reqs if r["response_logged"] == "False"]
    assert len(timeout_reqs) == 4

    # Match each timeout request deterministically by game timeout timestamp + cached pattern
    # Build mapping checking serve_ts proximity & cached_input_len compatibility
    leftover_by_rid = {s["serve_rid"]: s for s in leftover_serve}
    for r in timeout_reqs:
        gid = r["game_id"]
        fin_epoch = sota_origin_epoch + sota_timings[gid]["sota_finish_t"]
        # Match closest remaining serve row finishing within [-2s, +15s] of client timeout finish!
        cands = []
        for s in leftover_serve:
            if s["serve_rid"] in used_rids:
                continue
            se = dt.datetime.strptime(s["serve_ts_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
            # cn04 is pure_append so cached_input_len > 5056; other 3 are mutation/eviction so cached=5056
            if abs(se - fin_epoch) < 15.0:
                cands.append((abs(se - fin_epoch), s))
        assert len(cands) == 1, f"Ambiguous timeout serve match for {gid}: {cands}"
        chosen = cands[0][1]
        used_rids.add(chosen["serve_rid"])
        r.update({**chosen, "serve_match_status": "SERVER_COMPLETED_AFTER_CLIENT_TIMEOUT"})

    assert len(used_rids) == len(agent_serve_rows)

    # Prepend 3 pre-benchmark warmup/health rows
    for wi, w in enumerate(warmup_rows):
        role = ["sglang_structured_output_warmup", "kaggle_notebook_http_warmup", "harness_health_check"][wi]
        req_rows.append(
            {
                "row_type": role,
                "game_id": "__PRE_BENCHMARK__",
                "client_req_idx": "",
                "source_file": "submissions/arc3_v10_verified/serve.log",
                "request_logged": "False",
                "response_logged": "False",
                "response_location": "SERVE_LOG_ONLY",
                "analysis_step": "",
                "action": "",
                "request_index_within_turn": "",
                "prefix_transition": "pre_benchmark",
                "divergent_idx": "",
                "message_count": "",
                "image_count_client": "",
                "est_tokens_calibrated": "",
                "cal_chars_per_token": "",
                "prompt_tokens": "",
                "cached_tokens": "",
                "uncached_prompt_tokens": "",
                "cache_hit_pct": "",
                "image_tokens_usage": "",
                "completion_tokens": "",
                "reasoning_tokens": "",
                "output_non_reasoning_tokens": "",
                "total_tokens": "",
                "finish_reason": "",
                "action_bucket": "pre_benchmark_warmup_health",
                "action_attributed_here": "False",
                "post_final_action_flag": "False",
                **w,
                "serve_match_status": "SERVE_ONLY_WARMUP_OR_HEALTH",
                "missing_tool_call_ids": "",
            }
        )
    req_rows.extend(all_client_reqs)

    # Build 03_TOKEN_ACCOUNTING_RECONCILIATION.csv rows
    tok_rows: list[dict[str, Any]] = []
    evicted_gids: list[str] = []
    non_evicted_gids: list[str] = []

    for gid in sorted(bm_by_gid):
        gr = bm_by_gid[gid]
        hist = gr.get("history", [])
        n_hist = len(hist)
        h_gen = sum(int(h.get("generated_tokens", 0)) for h in hist)
        h_unc = sum(int(h.get("uncached_input_tokens", 0)) for h in hist)
        note_m = re.search(r"tokens=(\d+)", gr.get("solver_note") or "")
        note_tok = int(note_m.group(1))
        sum_row = sum_per_game[gid]
        assert h_gen == sum_row["tokens"]
        assert n_hist == sum_row["actions"]
        assert h_unc == 0
        assert int(gr.get("final_generated_tokens", 0)) == 0

        gs = game_pre_summaries[gid]
        pairs = gs["pairs"]
        pairs_wr = gs["pairs_with_root"]
        u352 = gs["u352"]
        u353 = gs["u353"]
        fifo = gs["fifo_info"]
        is_ev = fifo is not None
        if is_ev:
            evicted_gids.append(gid)
        else:
            non_evicted_gids.append(gid)

        act_comp_352 = sum(
            int((resp.get("usage") or {}).get("completion_tokens") or 0)
            for _, req, resp in pairs
            if resp is not None and int(req.get("action") or 0) <= n_hist
        )
        act_comp_353 = sum(
            int((resp.get("usage") or {}).get("completion_tokens") or 0)
            for _, req, resp in pairs_wr
            if resp is not None and int(req.get("action") or 0) <= n_hist
        )
        assert act_comp_352 == h_gen and act_comp_353 == h_gen, f"Action comp mismatch on {gid}"
        trail_352 = u352["completion_tokens"] - act_comp_352
        trail_353 = u353["completion_tokens"] - act_comp_353
        assert note_tok == u353["completion_tokens"], f"solver_note != comp353 on {gid}"

        to_req = [r for r in all_client_reqs if r["game_id"] == gid and r["response_logged"] == "False"]
        to_in = to_req[0]["serve_input_len"] if to_req else 0
        to_ca = to_req[0]["serve_cached_len"] if to_req else 0
        to_out = to_req[0]["serve_output_len"] if to_req else 0
        to_sec = sota_timings[gid]["timeout_seconds"]
        term_status = f"http_read_timeout_{to_sec:.2f}s" if to_sec is not None else "graceful_exit_pre_limit"

        ec = event_counts[gid]
        tok_rows.append(
            {
                "row_kind": "game",
                "game_id": gid,
                "is_evicted": str(is_ev),
                "terminal_status": term_status,
                "timeout_seconds": f"{to_sec:.2f}" if to_sec is not None else "",
                "score_final": round(float(gr["final_score"]), 8),
                "levels_completed": int(gr["levels_completed"]),
                "total_levels": int(gr["number_of_levels"]),
                "actions_executed": n_hist,
                "client_requests": len(pairs),
                "per_game_responses": sum(1 for _, _, resp in pairs if resp is not None),
                "root_responses": 1 if gid == "g50t-5849a774" else 0,
                "timeout_requests": len(to_req),
                "prompt_tokens_352": u352["prompt_tokens"],
                "cached_tokens_352": u352["cached_tokens"],
                "uncached_tokens_352": u352["uncached_prefill_tokens"],
                "cache_hit_pct_352": round(100.0 * u352["cached_tokens"] / u352["prompt_tokens"], 4),
                "comp_tokens_352": u352["completion_tokens"],
                "reason_tokens_352": u352["reasoning_tokens"],
                "image_tokens_352": u352["image_tokens"],
                "prompt_tokens_353": u353["prompt_tokens"],
                "cached_tokens_353": u353["cached_tokens"],
                "uncached_tokens_353": u353["uncached_prefill_tokens"],
                "cache_hit_pct_353": round(100.0 * u353["cached_tokens"] / u353["prompt_tokens"], 4),
                "comp_tokens_353": u353["completion_tokens"],
                "reason_tokens_353": u353["reasoning_tokens"],
                "image_tokens_353": u353["image_tokens"],
                "history_generated_tokens": h_gen,
                "history_uncached_input_tokens": h_unc,
                "summary_txt_tokens": sum_row["tokens"],
                "action_attributed_comp_tokens": act_comp_353,
                "trailing_post_action_comp_352": trail_352,
                "trailing_post_action_comp_353": trail_353,
                "solver_note_tokens": note_tok,
                "final_generated_tokens": int(gr.get("final_generated_tokens", 0)),
                "final_uncached_input_tokens": int(gr.get("final_uncached_input_tokens", 0)),
                "final_wallclock_s": round(float(gr.get("final_wallclock_seconds", 0.0)), 2),
                "diff_hist_vs_action_comp": h_gen - act_comp_353,
                "diff_note_vs_comp352": note_tok - u352["completion_tokens"],
                "diff_note_vs_comp353": note_tok - u353["completion_tokens"],
                "serve_timeout_input_len": to_in,
                "serve_timeout_cached_len": to_ca,
                "serve_timeout_output_len": to_out,
                "events_total": sum(ec.values()),
                "events_initial": ec["initial"],
                "events_action": ec["action"],
                "events_analysis": ec["analysis"],
                "fifo_boundary_idx": fifo["idx"] if fifo else "",
                "fifo_trim_site": fifo["trim_site"] if fifo else "",
                "fifo_pre_trim_raw_est_tokens": fifo["pre_raw_est"] if fifo and fifo["pre_raw_est"] is not None else "",
                "fifo_pre_trim_win4_eos_est_tokens": fifo["pre_win4_eos_est"] if fifo and fifo["pre_win4_eos_est"] is not None else "",
                "fifo_post_trim_no_opener_est_tokens": fifo["post_est_no_opener"] if fifo else "",
                "fifo_post_trim_full_est_tokens": fifo["post_est_full"] if fifo else "",
            }
        )

    def _agg_row(kind: str, label: str, subset: list[dict[str, Any]]) -> dict[str, Any]:
        sum_fields = [
            "levels_completed", "total_levels", "actions_executed", "client_requests",
            "per_game_responses", "root_responses", "timeout_requests",
            "prompt_tokens_352", "cached_tokens_352", "uncached_tokens_352",
            "comp_tokens_352", "reason_tokens_352", "image_tokens_352",
            "prompt_tokens_353", "cached_tokens_353", "uncached_tokens_353",
            "comp_tokens_353", "reason_tokens_353", "image_tokens_353",
            "history_generated_tokens", "history_uncached_input_tokens",
            "summary_txt_tokens", "action_attributed_comp_tokens",
            "trailing_post_action_comp_352", "trailing_post_action_comp_353",
            "solver_note_tokens", "final_generated_tokens", "final_uncached_input_tokens",
            "diff_hist_vs_action_comp", "diff_note_vs_comp352", "diff_note_vs_comp353",
            "serve_timeout_input_len", "serve_timeout_cached_len", "serve_timeout_output_len",
            "events_total", "events_initial", "events_action", "events_analysis",
        ]
        agg: dict[str, Any] = {
            "row_kind": kind,
            "game_id": label,
            "is_evicted": "True" if kind == "cohort_evicted_9" else ("False" if kind == "cohort_non_evicted_16" else "MIXED_25"),
            "terminal_status": "",
            "timeout_seconds": "",
            "score_final": round(sum(float(bm_by_gid[r["game_id"]]["final_score"]) for r in subset), 8),
        }
        for f in sum_fields:
            agg[f] = sum(int(r[f]) for r in subset)
        agg["cache_hit_pct_352"] = round(100.0 * agg["cached_tokens_352"] / agg["prompt_tokens_352"], 4)
        agg["cache_hit_pct_353"] = round(100.0 * agg["cached_tokens_353"] / agg["prompt_tokens_353"], 4)
        agg["final_wallclock_s"] = round(sum(float(r["final_wallclock_s"]) for r in subset), 2)
        agg["fifo_boundary_idx"] = ""
        agg["fifo_trim_site"] = ""
        agg["fifo_pre_trim_raw_est_tokens"] = ""
        agg["fifo_pre_trim_win4_eos_est_tokens"] = ""
        agg["fifo_post_trim_no_opener_est_tokens"] = ""
        agg["fifo_post_trim_full_est_tokens"] = ""
        return agg

    ev_rows = [r for r in tok_rows if r["is_evicted"] == "True"]
    nev_rows = [r for r in tok_rows if r["is_evicted"] == "False"]
    tok_rows.append(_agg_row("cohort_evicted_9", "COHORT_EVICTED_N9", ev_rows))
    tok_rows.append(_agg_row("cohort_non_evicted_16", "COHORT_NON_EVICTED_N16", nev_rows))
    tok_rows.append(_agg_row("total_all_25", "ALL_25_GAMES_RECONCILED", [r for r in tok_rows if r["row_kind"] == "game"]))

    # Compute prefix transition breakdowns for BOTH 352 and 353 views
    def _prefix_breakdown(use_root: bool) -> dict[str, dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"responses": 0, "prompt": 0, "cached": 0, "uncached": 0, "comp": 0, "reason": 0, "cached_hist": Counter()}
        )
        for r in all_client_reqs:
            is_resp = (r["response_logged"] == "True") if use_root else (r["response_location"] == "per_game_requests_jsonl")
            if not is_resp:
                continue
            tr = r["prefix_transition"]
            bk = buckets[tr]
            bk["responses"] += 1
            bk["prompt"] += int(r["prompt_tokens"])
            bk["cached"] += int(r["cached_tokens"])
            bk["uncached"] += int(r["uncached_prompt_tokens"])
            bk["comp"] += int(r["completion_tokens"])
            bk["reason"] += int(r["reasoning_tokens"])
            bk["cached_hist"][int(r["cached_tokens"])] += 1
        out_b: dict[str, Any] = {}
        tot_unc = sum(v["uncached"] for v in buckets.values())
        tot_pr = sum(v["prompt"] for v in buckets.values())
        tot_ca = sum(v["cached"] for v in buckets.values())
        for k, v in buckets.items():
            out_b[k] = {
                "responses": v["responses"],
                "prompt": v["prompt"],
                "cached": v["cached"],
                "uncached": v["uncached"],
                "hit_pct": round(100.0 * v["cached"] / v["prompt"], 4) if v["prompt"] else 0.0,
                "uncached_share_pct": round(100.0 * v["uncached"] / tot_unc, 4) if tot_unc else 0.0,
                "comp": v["comp"],
                "reason": v["reason"],
                "cached_histogram": dict(sorted(v["cached_hist"].items())),
            }
        out_b["_TOTAL_"] = {
            "responses": sum(v["responses"] for v in buckets.values()),
            "prompt": tot_pr,
            "cached": tot_ca,
            "uncached": tot_unc,
            "hit_pct": round(100.0 * tot_ca / tot_pr, 4),
            "comp": sum(v["comp"] for v in buckets.values()),
            "reason": sum(v["reason"] for v in buckets.values()),
        }
        return out_b

    pb352 = _prefix_breakdown(use_root=False)
    pb353 = _prefix_breakdown(use_root=True)

    # Assert exact headline invariants
    tot25 = tok_rows[-1]
    assert tot25["prompt_tokens_352"] == 7078878
    assert tot25["cached_tokens_352"] == 4480704
    assert tot25["comp_tokens_352"] == 468510
    assert tot25["reason_tokens_352"] == 404005
    assert tot25["prompt_tokens_353"] == 7098316
    assert tot25["cached_tokens_353"] == 4496768
    assert tot25["comp_tokens_353"] == 471288
    assert tot25["reason_tokens_353"] == 406396
    assert tot25["history_generated_tokens"] == 378304
    assert tot25["solver_note_tokens"] == 471288
    assert tot25["trailing_post_action_comp_352"] == 90206
    assert tot25["trailing_post_action_comp_353"] == 92984
    assert tot25["events_total"] == 613
    assert tot25["events_initial"] == 25
    assert tot25["events_action"] == 386
    assert tot25["events_analysis"] == 202

    inv_rows, cross_summary = build_artifact_inventory(r1_portable=r1_portable)

    def _write_csv(path: Path, data: list[dict[str, Any]]) -> None:
        assert data
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)

    _write_csv(OUT_DIR / "01_ARTIFACT_INVENTORY.csv", inv_rows)
    _write_csv(OUT_DIR / "02_REQUEST_RESPONSE_RECONSTRUCTION.csv", req_rows)
    _write_csv(OUT_DIR / "03_TOKEN_ACCOUNTING_RECONCILIATION.csv", tok_rows)

    manifest = {
        "schema_version": "1.0",
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "mission": "ARC-AGI-3 HINAGI V10 Forensic Evidence Reconstruction & Manuscript Integrity Audit",
        "read_only_policy": "Zero mutations performed on submissions/*, artifacts/*, reference/*, Paper/branch_b_academic/paper/*, or Paper/branch_b_academic/analysis/*.py|md|csv|json",
        "reconstructor_script_sha256": sha256_file(Path(__file__)),
        "canonical_inputs": {
            r["relative_path"]: {"size_bytes": r["size_bytes"], "sha256": r["sha256"]}
            for r in inv_rows
            if r["scope"] == "comparator_or_canonical_source"
            or r["relative_path"] in {
                "submissions/arc3_v10_verified/benchmark.json",
                "submissions/arc3_v10_verified/summary.txt",
                "submissions/arc3_v10_verified/requests.jsonl",
                "submissions/arc3_v10_verified/serve.log",
                "submissions/arc3_v10_verified/arc-agi-3-sota.log",
            }
        },
        "cross_run_summary": cross_summary,
        "reconciled_totals": {
            "games_total": 25,
            "score_sum": round(sum(float(bm_by_gid[g]["final_score"]) for g in bm_by_gid), 6),
            "score_mean": round(sum(float(bm_by_gid[g]["final_score"]) for g in bm_by_gid) / 25.0, 6),
            "actions_executed": 386,
            "client_requests": 357,
            "per_game_responses": 352,
            "root_detached_responses": 1,
            "total_client_responses": 353,
            "true_http_read_timeouts": 4,
            "serve_log_reqtimestats_total": 360,
            "serve_log_warmup_and_health": 3,
            "serve_log_agent_total": 357,
            "history_generated_tokens": 378304,
            "trailing_post_action_comp_352": 90206,
            "trailing_post_action_comp_353": 92984,
            "comp_tokens_352": 468510,
            "comp_tokens_353_exact_solver_note": 471288,
            "serve_timeout_input_len_sum": tot25["serve_timeout_input_len"],
            "serve_timeout_cached_len_sum": tot25["serve_timeout_cached_len"],
            "serve_timeout_output_len_sum": tot25["serve_timeout_output_len"],
            "live_calibration_matches": f"{cal_matches}/{cal_total}",
        },
        "prefix_breakdown_352": pb352,
        "prefix_breakdown_353": pb353,
        "fifo_boundary_details": {
            gid: game_pre_summaries[gid]["fifo_info"]
            for gid in sorted(evicted_gids)
        },
        "deliverables_sha256": {},
    }

    # Include hashes of any deliverables already present in OUT_DIR
    for fname in sorted(p.name for p in OUT_DIR.iterdir() if p.is_file() and p.name != "08_REPRODUCIBILITY_MANIFEST.json"):
        p = OUT_DIR / fname
        manifest["deliverables_sha256"][fname] = {"size_bytes": p.stat().st_size, "sha256": sha256_file(p)}

    (OUT_DIR / "08_REPRODUCIBILITY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--r1-portable", action="store_true", default=True)
    args = ap.parse_args()
    res = reconstruct_all(r1_portable=args.r1_portable)
    print(json.dumps({"reconciled_totals": res["reconciled_totals"], "pb352": res["prefix_breakdown_352"], "pb353": res["prefix_breakdown_353"]}, indent=2))
