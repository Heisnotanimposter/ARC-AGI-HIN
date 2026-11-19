#!/usr/bin/env python3
"""Independent red-team arithmetic & forensic verification script for V10 artifacts.

Strictly standalone (Python stdlib only). Does NOT import or reuse
reconstruct_v10_forensics.py or build_v10_eviction_token_tables.py.
Reads canonical raw files directly in read-only mode and writes only
12_INDEPENDENT_ARITHMETIC_RESULTS.json inside v10_forensic_reconciliation/.
"""

from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
BRANCH_DIR = THIS_DIR.parent.parent
PAPER_DIR = BRANCH_DIR.parent
HINAGI_ROOT = PAPER_DIR.parent

V10_DIR = HINAGI_ROOT / "submissions/arc3_v10_verified"
V6_DIR = HINAGI_ROOT / "submissions/arc3_v6_smoke_verified"
TOOL_AGENT_PATH = HINAGI_ROOT / "reference/arc3_franzen_m2/ARC3-Inference/inference/agent/tool_agent.py"
V6_NB_PATH = HINAGI_ROOT / "artifacts/phase6_5/reference_snapshots/v6_reference.ipynb"
V10_NB_PATH = HINAGI_ROOT / "artifacts/phase6_5/reference_snapshots/v10_reference.ipynb"
V10_STATUS_PATH = HINAGI_ROOT / "artifacts/phase5_4/submission_57827259_status.json"
PHASE6_0_JSON = HINAGI_ROOT / "artifacts/phase6_0/vc33_context_ablation_results.json"
import os
OUT_JSON_PATH = Path(os.environ.get("R1_REC_OUT_DIR", str(HINAGI_ROOT / "replay_out/v10_forensic_reconciliation"))) / "12_INDEPENDENT_ARITHMETIC_RESULTS.json"

# Canonical constants read directly from tool_agent.py and V10 Cell 4
VISION_PATCH_PIXELS = 32
VISION_SENTINEL_TOKENS = 2
IMAGE_TOKENS_FALLBACK = 402
PNG_SIG = b"\x89PNG\r\n\x1a\n"
TEXT_TOKEN_SEED = 3.0
TEXT_TOKEN_MIN = 1.0
TEXT_TOKEN_MAX = 3.3
CALIBRATE_LOG_DELTA = 0.05
HISTORY_IMAGE_KEEP = 4
HISTORY_IMAGE_PLACEHOLDER = "[grid image omitted from history]"
CONTROL_MESSAGE_KEY = "_arc3_control"

W_CTX = (44 + 12) * 1024  # 57,344
R_REPLY = 12 * 1024       # 12,288
M_SAFE = 512
B_TOK = max(1024, W_CTX - R_REPLY - M_SAFE)  # 44,544
DRAIN_TOKENS_RAW = 16 * 1024  # 16,384
DRAIN_TOKENS = min(DRAIN_TOKENS_RAW, B_TOK // 2)
B_TARGET = max(1, B_TOK - DRAIN_TOKENS)  # 28,160

REQTIME_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+ReqTimeStats\(rid=(?P<rid>[^,]+),\s+"
    r"input_len=(?P<in_len>\d+),\s+cached_input_len=(?P<cached_len>\d+),\s+"
    r"output_len=(?P<out_len>\d+),\s+attempts=(?P<attempts>\d+),\s+type=(?P<rtype>[^)]+)\):\s+"
    r"queue_duration=(?P<queue>[0-9.]+)ms,\s+(?P<rest>.+)$"
)
HTTP_POST_RE = re.compile(
    r'^\[(?P<ts>[^\]]+)\]\s+INFO:\s+(?P<ip>\S+)\s+-\s+"POST /v1/chat/completions HTTP/1\.1"\s+(?P<code>\d+)'
)
CALIB_RE = re.compile(
    r"text_token_calibration:\s+(?P<val>[0-9.]+)\s+chars/token"
    r"(?:\s+\(clamped from (?P<raw>[0-9.]+)\))?\s+\[prompt_tokens\s+(?P<pt>\d+),\s+"
    r"images\s+(?P<img>\d+),\s+text chars\s+(?P<chars>\d+)\]"
)
SUMMARY_GAME_RE = re.compile(
    r"^\s*(?P<gid>[a-z0-9]+-[0-9a-f]+):\s+score=(?P<score>[0-9.]+),\s+"
    r"levels=(?P<lvls>[0-9.]+)/(?P<tot_lvls>\d+),\s+actions=(?P<acts>\d+),\s+tokens=(?P<toks>\d+)$"
)
SOTA_BENCH_LINE_RE = re.compile(
    r"^\s*(?P<gid>[a-z0-9]+-[0-9a-f]+):\s+score=(?P<score>[0-9.]+),\s+"
    r"levels=(?P<lvls>[0-9.]+)/(?P<tot_lvls>\d+),\s+actions=(?P<acts>\d+),\s+tokens=(?P<toks>\d+)"
)
TIMEOUT_NUM_RE = re.compile(r"timeout=([0-9.]+)\)?")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_summary_txt(path: Path) -> dict[str, dict[str, Any]]:
    per_game: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = SUMMARY_GAME_RE.match(line)
        if m:
            gid = m.group("gid")
            per_game[gid] = {
                "score": float(m.group("score")),
                "levels": float(m.group("lvls")),
                "total_levels": int(m.group("tot_lvls")),
                "actions": int(m.group("acts")),
                "tokens": int(m.group("toks")),
            }
    return per_game


def parse_sota_log(path: Path) -> dict[str, Any]:
    """Parse Kaggle wrapper JSON-array stdout events from arc-agi-3-sota.log."""
    events: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    summary_games: dict[str, dict[str, Any]] = {}
    start_finish: dict[str, dict[str, Any]] = {}
    read_timeouts: list[dict[str, Any]] = []
    other_lines: list[dict[str, Any]] = []
    for idx, ev in enumerate(events, 1):
        data = ev.get("data", "")
        t = ev.get("time")
        for subline in data.splitlines():
            m = SOTA_BENCH_LINE_RE.match(subline)
            if m:
                summary_games[m.group("gid")] = {
                    "score": float(m.group("score")),
                    "levels": float(m.group("lvls")),
                    "total_levels": int(m.group("tot_lvls")),
                    "actions": int(m.group("acts")),
                    "tokens": int(m.group("toks")),
                }
            if "[BENCHMARK] Done" in subline:
                dm = re.search(r"Done\s+([a-z0-9]+-[0-9a-f]+):.*elapsed=([0-9.]+)s", subline)
                if dm:
                    start_finish[dm.group(1)] = {"line": idx, "time_s": t, "text": subline.strip()}
            if "Read timed out" in subline or "request timed out" in subline:
                m_to = re.search(r"at action (\d+);.*read timeout=([0-9.]+)\)", subline)
                read_timeouts.append(
                    {
                        "line": idx,
                        "time_s": t,
                        "action": int(m_to.group(1)) if m_to else None,
                        "timeout_s": float(m_to.group(2)) if m_to else None,
                        "text": subline.strip(),
                    }
                )
            if "rep_tokens" in subline or "tokens=" in subline:
                other_lines.append({"line": idx, "time_s": t, "text": subline.strip()})
            if subline.startswith("ended:"):
                other_lines.append({"line": idx, "time_s": t, "text": subline.strip()})
    return {
        "events_count": len(events),
        "summary_games": summary_games,
        "done_events": start_finish,
        "read_timeouts": read_timeouts,
        "token_mentions": other_lines,
    }


def load_pairs(req_path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in req_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs: list[dict[str, Any]] = []
    pending_req: dict[str, Any] | None = None
    for idx, rec in enumerate(records):
        ev = rec.get("event")
        if ev == "request":
            if pending_req is not None:
                pairs.append({"pair_index": len(pairs), "request": pending_req, "response": None})
            pending_req = rec
        elif ev == "response":
            if pending_req is None:
                raise AssertionError(f"Unmatched response at {req_path}:{idx}")
            pairs.append({"pair_index": len(pairs), "request": pending_req, "response": rec})
            pending_req = None
        else:
            raise AssertionError(f"Unexpected event {ev!r} in {req_path}:{idx}")
    if pending_req is not None:
        pairs.append({"pair_index": len(pairs), "request": pending_req, "response": None})
    return pairs


def png_dimensions(data_url: str) -> tuple[int, int] | None:
    marker = "base64,"
    pos = data_url.find(marker)
    if pos < 0:
        return None
    head = data_url[pos + len(marker) : pos + len(marker) + 32]
    if len(head) < 32:
        return None
    try:
        raw = base64.b64decode(head, validate=True)
    except Exception:
        return None
    if len(raw) < 24 or not raw.startswith(PNG_SIG) or raw[12:16] != b"IHDR":
        return None
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    return (w, h) if (w > 0 and h > 0) else None


def image_part_tokens(part: dict[str, Any]) -> int:
    url = ""
    img_obj = part.get("image_url")
    if isinstance(img_obj, dict):
        url = str(img_obj.get("url") or "")
    dims = png_dimensions(url) if url else None
    if dims is None:
        return IMAGE_TOKENS_FALLBACK
    w, h = dims
    cells = -(-w // VISION_PATCH_PIXELS) * -(-h // VISION_PATCH_PIXELS)
    return cells + VISION_SENTINEL_TOKENS


def split_messages_for_estimate(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    img_tok = 0
    out: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue
        parts: list[Any] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                img_tok += image_part_tokens(part)
                parts.append({"type": "image_url", "image_url": {"url": "<image>"}})
            else:
                parts.append(part)
        out.append({**msg, "content": parts})
    return out, img_tok


def estimate_tokens(value: Any, chars_per_token: float | None = None) -> int:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    chars = chars_per_token or TEXT_TOKEN_SEED
    return max(1, int(len(rendered) / chars) + (1 if len(rendered) % chars else 0))


def estimate_request_input_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    chars_per_token: float | None,
    tool_choice: str | None = None,
) -> int:
    scrubbed, img_tok = split_messages_for_estimate(messages)
    payload: dict[str, Any] = {"messages": scrubbed}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    return estimate_tokens(payload, chars_per_token) + img_tok


def calibrate_from_usage(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    prompt_tokens: int,
    prev_cal: float | None,
    tool_choice: str | None = None,
) -> tuple[float, bool, str]:
    scrubbed, img_tok = split_messages_for_estimate(messages)
    payload: dict[str, Any] = {"messages": scrubbed}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    text_tokens = prompt_tokens - img_tok
    if text_tokens <= 0 or not rendered:
        raise AssertionError(f"Invalid calibration denominator: {text_tokens}")
    measured = len(rendered) / text_tokens
    clamped = min(TEXT_TOKEN_MAX, max(TEXT_TOKEN_MIN, measured))
    emitted = prev_cal is None or abs(clamped - prev_cal) >= CALIBRATE_LOG_DELTA
    note = "" if clamped == measured else f" (clamped from {measured:.2f})"
    msg = (
        f"text_token_calibration: {clamped:.2f} chars/token{note} "
        f"[prompt_tokens {prompt_tokens}, images {img_tok}, text chars {len(rendered)}]"
    )
    return clamped, emitted, msg


def apply_history_image_window(messages: list[dict[str, Any]], keep: int = HISTORY_IMAGE_KEEP) -> list[dict[str, Any]]:
    def has_img(m: dict[str, Any]) -> bool:
        c = m.get("content")
        return isinstance(c, list) and any(isinstance(p, dict) and p.get("type") == "image_url" for p in c)

    seen = 0
    out: list[dict[str, Any]] = []
    for msg in reversed(messages):
        if has_img(msg):
            seen += 1
            if seen > keep:
                new_parts = [
                    {"type": "text", "text": HISTORY_IMAGE_PLACEHOLDER}
                    if (isinstance(p, dict) and p.get("type") == "image_url")
                    else p
                    for p in msg["content"]
                ]
                msg = {**msg, "content": new_parts}
        out.append(msg)
    out.reverse()
    return out


def drop_oldest_history_block(history: list[dict[str, Any]], *, preserve_recent: int = 0) -> bool:
    if len(history) - preserve_recent <= 0:
        return False
    if not any(str(m.get("role", "")).strip() == "user" for m in history[1:]):
        return False
    first = history.pop(0)
    first_role = str(first.get("role", "")).strip()
    while history and history[0].get("role") == "tool" and len(history) > preserve_recent:
        history.pop(0)
    if first_role not in {"assistant", "tool"}:
        while history and history[0].get("role") != "user" and len(history) > preserve_recent:
            history.pop(0)
    return True


def trim_messages_for_context(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    chars_per_token: float | None,
    *,
    preserve_recent: int = 0,
    tool_choice: str | None = None,
) -> list[dict[str, Any]]:
    sys_msg = messages[0]
    history = list(messages[1:])
    draining = False
    while history:
        used = estimate_request_input_tokens([sys_msg, *history], tools, chars_per_token, tool_choice=tool_choice)
        if not draining and used <= B_TOK:
            break
        if used <= (B_TARGET if draining else B_TOK):
            break
        draining = True
        if not drop_oldest_history_block(history, preserve_recent=preserve_recent):
            break
    while history and str(history[0].get("role", "")).strip() != "user":
        history.pop(0)
    return [sys_msg, *history]


def strip_images_for_matching(msg: dict[str, Any]) -> Any:
    """Compare messages ignoring binary image replacement placeholder differences."""
    m = dict(msg)
    c = m.get("content")
    if isinstance(c, list):
        norm = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "image_url":
                norm.append({"type": "IMG"})
            elif isinstance(p, dict) and p.get("type") == "text" and p.get("text") == HISTORY_IMAGE_PLACEHOLDER:
                norm.append({"type": "IMG"})
            else:
                norm.append(p)
        m["content"] = norm
    return json.dumps(m, sort_keys=True, ensure_ascii=False)


def tool_call_ids(messages: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for m in messages:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                if tc.get("id"):
                    out.append(tc["id"])
    return out


def classify_transition(idx: int, pairs: list[dict[str, Any]]) -> str:
    if idx == 0:
        return "initial"
    prev_m = pairs[idx - 1]["request"]["messages"]
    curr_m = pairs[idx]["request"]["messages"]
    prev_tc = tool_call_ids(prev_m)
    curr_tc_set = set(tool_call_ids(curr_m))
    if any(t not in curr_tc_set for t in prev_tc) or len(curr_m) < len(prev_m):
        return "fifo_eviction"
    for a, b in zip(prev_m, curr_m):
        if a != b:
            return "image_omit_mutation"
    return "pure_append"


def parse_serve_log(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    cr_count = raw_bytes.count(b"\r")
    lines = raw_bytes.decode("utf-8", errors="replace").split("\n")
    http_posts: list[dict[str, Any]] = []
    req_stats: list[dict[str, Any]] = []
    raw_http_post_mentions = 0
    for lf_no, line in enumerate(lines, 1):
        clean_line = line.split("\r")[-1]
        if "POST /v1/chat/completions" in line:
            raw_http_post_mentions += 1
        m_http = HTTP_POST_RE.match(clean_line)
        if m_http:
            http_posts.append({"lf_line": lf_no, "ts": m_http.group("ts"), "code": int(m_http.group("code"))})
        m_req = REQTIME_RE.match(clean_line)
        if m_req:
            req_stats.append(
                {
                    "lf_line": lf_no,
                    "ts": m_req.group("ts"),
                    "rid": m_req.group("rid"),
                    "in_len": int(m_req.group("in_len")),
                    "cached_len": int(m_req.group("cached_len")),
                    "out_len": int(m_req.group("out_len")),
                    "attempts": int(m_req.group("attempts")),
                    "rtype": m_req.group("rtype"),
                    "queue_ms": float(m_req.group("queue")),
                    "rest": m_req.group("rest"),
                    "raw": clean_line,
                }
            )
    assert raw_http_post_mentions == len(http_posts), f"Unparsed POST lines: {raw_http_post_mentions} vs {len(http_posts)}"
    return {
        "cr_byte_count": cr_count,
        "lf_line_count": len(lines),
        "splitlines_line_count": len(raw_bytes.decode("utf-8", errors="replace").splitlines()),
        "http_posts": http_posts,
        "req_stats": req_stats,
    }


def main() -> int:
    # -------------------------------------------------------------------------
    # SECTION 1: Independent Arithmetic Audit & All 25 Game Reconciliation
    # -------------------------------------------------------------------------
    bench = json.loads((V10_DIR / "benchmark.json").read_text(encoding="utf-8"))
    summary_map = parse_summary_txt(V10_DIR / "summary.txt")
    sota_info = parse_sota_log(V10_DIR / "arc-agi-3-sota.log")
    root_reqs = [json.loads(l) for l in (V10_DIR / "requests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(root_reqs) == 1, f"Expected 1 root record in requests.jsonl, got {len(root_reqs)}"
    root_rec = root_reqs[0]

    req_files = sorted(V10_DIR.glob("*_p0_requests.jsonl"))
    ev_files = sorted((V10_DIR / "artifacts").glob("*_p0_events.jsonl"))
    prompt_files = sorted((V10_DIR / "prompts").glob("*_p0.log"))
    assert len(bench["game_runs"]) == 25 and len(req_files) == 25 and len(ev_files) == 25 and len(prompt_files) == 25

    per_game_rows: list[dict[str, Any]] = []
    all_pairs_by_gid: dict[str, list[dict[str, Any]]] = {}
    all_events_by_gid: dict[str, list[dict[str, Any]]] = {}

    sum_history_gen = 0
    sum_summary_tok = 0
    sum_sota_tok = 0
    sum_solver_note = 0
    sum_per_game_comp = 0
    sum_per_game_prompt = 0
    sum_per_game_cached = 0
    sum_per_game_image = 0
    sum_per_game_reason = 0
    sum_actions = 0
    sum_levels_completed = 0
    sum_total_levels = 0
    sum_final_score = 0.0
    total_paired_per_game = 0
    total_unpaired_per_game = 0

    for res in bench["game_runs"]:
        gid = res["game_id"]
        hist = res["history"]
        actions_taken = len(hist)
        tot_lvls = int(res["number_of_levels"])
        hist_gen = sum(int(h.get("generated_tokens", 0)) for h in hist)
        note_m = re.fullmatch(r"tokens=(\d+)", res["solver_note"])
        assert note_m, f"Unexpected solver_note for {gid}: {res['solver_note']}"
        note_tok = int(note_m.group(1))

        sum_row = summary_map[gid]
        sota_row = sota_info["summary_games"][gid]
        assert hist_gen == sum_row["tokens"] == sota_row["tokens"]
        assert actions_taken == sum_row["actions"] == sota_row["actions"]

        pairs = load_pairs(V10_DIR / f"{gid}_p0_requests.jsonl")
        all_pairs_by_gid[gid] = pairs
        ev_recs = [json.loads(l) for l in (V10_DIR / "artifacts" / f"{gid}_p0_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        all_events_by_gid[gid] = ev_recs

        paired = [p for p in pairs if p["response"] is not None]
        unpaired = [p for p in pairs if p["response"] is None]
        pg_prompt = sum(int(p["response"]["usage"]["prompt_tokens"]) for p in paired)
        pg_cached = sum(int(p["response"]["usage"]["prompt_tokens_details"]["cached_tokens"]) for p in paired)
        pg_image = sum(int(p["response"]["usage"]["prompt_tokens_details"]["image_tokens"]) for p in paired)
        pg_comp = sum(int(p["response"]["usage"]["completion_tokens"]) for p in paired)
        pg_reason = sum(int(p["response"]["usage"]["reasoning_tokens"]) for p in paired)

        detached = int(root_rec["usage"]["completion_tokens"]) if gid == "g50t-5849a774" else 0
        reconstructed_comp = pg_comp + detached
        assert note_tok == reconstructed_comp, f"{gid}: note={note_tok} != reconstructed={reconstructed_comp}"

        trailing_diff = reconstructed_comp - hist_gen
        per_game_diff = pg_comp - hist_gen

        sum_history_gen += hist_gen
        sum_summary_tok += sum_row["tokens"]
        sum_sota_tok += sota_row["tokens"]
        sum_solver_note += note_tok
        sum_per_game_comp += pg_comp
        sum_per_game_prompt += pg_prompt
        sum_per_game_cached += pg_cached
        sum_per_game_image += pg_image
        sum_per_game_reason += pg_reason
        sum_actions += actions_taken
        sum_levels_completed += int(res["levels_completed"])
        sum_total_levels += tot_lvls
        sum_final_score += float(res["final_score"])
        total_paired_per_game += len(paired)
        total_unpaired_per_game += len(unpaired)

        per_game_rows.append(
            {
                "game_id": gid,
                "state": res["state"],
                "levels_completed": int(res["levels_completed"]),
                "total_levels": tot_lvls,
                "final_score": res["final_score"],
                "actions": actions_taken,
                "history_generated_tokens": hist_gen,
                "summary_txt_tokens": sum_row["tokens"],
                "sota_log_tokens": sota_row["tokens"],
                "requests_count": len(pairs),
                "per_game_paired_responses": len(paired),
                "per_game_unpaired_requests": len(unpaired),
                "per_game_prompt_tokens": pg_prompt,
                "per_game_cached_tokens": pg_cached,
                "per_game_image_tokens": pg_image,
                "per_game_completion_tokens": pg_comp,
                "per_game_reasoning_tokens": pg_reason,
                "detached_root_completion_tokens": detached,
                "reconstructed_completion_tokens": reconstructed_comp,
                "solver_note_tokens": note_tok,
                "solver_note_minus_reconstructed": note_tok - reconstructed_comp,
                "per_game_comp_minus_history": per_game_diff,
                "reconstructed_minus_history_trailing": trailing_diff,
            }
        )

    assert sum_history_gen == sum_summary_tok == sum_sota_tok == 378304
    assert sum_actions == 386
    assert sum_levels_completed == 13 and sum_total_levels == 183
    assert sum_per_game_comp == 468510
    assert int(root_rec["usage"]["completion_tokens"]) == 2778
    assert sum_solver_note == 471288 == sum_per_game_comp + 2778
    assert sum_per_game_prompt == 7078878
    assert sum_per_game_cached == 4480704
    assert sum_per_game_prompt - sum_per_game_cached == 2598174
    assert sum_per_game_image == 762400
    assert sum_per_game_reason == 404005
    assert total_paired_per_game == 352
    assert total_unpaired_per_game == 5
    assert sum_solver_note - sum_history_gen == 92984
    assert sum_per_game_comp - sum_history_gen == 90206

    # -------------------------------------------------------------------------
    # SECTION 2: Challenge 353-Response Reconstruction & Zero Double-Counting
    # -------------------------------------------------------------------------
    g50t_pairs = all_pairs_by_gid["g50t-5849a774"]
    g50t_last_req = g50t_pairs[-1]["request"]
    assert g50t_pairs[-1]["response"] is None and g50t_pairs[-1]["pair_index"] == 15
    shared_envelope_fields = [
        "action",
        "analysis_step",
        "chat_template_kwargs",
        "messages",
        "request_index_within_turn",
        "tool_choice",
        "tools",
    ]
    envelope_match = {k: (g50t_last_req[k] == root_rec[k]) for k in shared_envelope_fields}
    assert all(envelope_match.values()), f"Envelope mismatch: {envelope_match}"

    g50t_events = all_events_by_gid["g50t-5849a774"]
    g50t_step7_ev = [e for e in g50t_events if e.get("type") == "analysis" and e.get("analysis_step") == 7]
    assert len(g50t_step7_ev) == 1
    g50t_prompt_tail = (V10_DIR / "prompts/g50t-5849a774_p0.log").read_text(encoding="utf-8")
    tc_blocks = re.findall(r"raw_tool_calls:\s*\n(\[\s*\{.*?\}\s*\])", g50t_prompt_tail, re.S)
    assert len(tc_blocks) == 2, f"Expected 2 raw_tool_calls blocks in Step 7 prompt log, got {len(tc_blocks)}"
    prior_tc = json.loads(tc_blocks[0])[0]
    root_tc = json.loads(tc_blocks[-1])[0]
    assert prior_tc["id"] == g50t_last_req["messages"][-2]["tool_calls"][0]["id"] == "call_24bf8d5f650748208a1294c6"
    root_tc_code = json.loads(root_tc["function"]["arguments"])["code"]
    assert root_tc["id"] == "call_786624f58c0f463a951acd79"
    assert root_rec["finish_reason"] == "tool_calls"
    assert root_tc_code in g50t_prompt_tail
    assert "action(['RIGHT'])" in g50t_step7_ev[0]["transcript"]
    assert "Yielded control to solver: stop_requested." in g50t_step7_ev[0]["transcript"]

    serve_data = parse_serve_log(V10_DIR / "serve.log")
    assert len(serve_data["http_posts"]) == 354
    assert all(p["code"] == 200 for p in serve_data["http_posts"])
    assert len(serve_data["req_stats"]) == 360

    # Match all 353 paired responses (352 per-game + 1 detached root) uniquely to serve.log ReqTimeStats
    # Criterion: exact tuple (input_len, cached_input_len) AND output_len >= completion_tokens with minimal nonnegative diff
    flat_resps: list[dict[str, Any]] = []
    for gid, pairs in all_pairs_by_gid.items():
        for p in pairs:
            rs = p["response"]
            loc = "per_game"
            if rs is None and gid == "g50t-5849a774":
                rs = root_rec
                loc = "root_requests_jsonl"
            if rs is not None:
                u = rs["usage"]
                pd = u["prompt_tokens_details"]
                flat_resps.append(
                    {
                        "gid": gid,
                        "pair_index": p["pair_index"],
                        "action": p["request"]["action"],
                        "analysis_step": p["request"]["analysis_step"],
                        "rit": p["request"]["request_index_within_turn"],
                        "loc": loc,
                        "prompt_tokens": int(u["prompt_tokens"]),
                        "cached_tokens": int(pd["cached_tokens"]),
                        "completion_tokens": int(u["completion_tokens"]),
                    }
                )
    assert len(flat_resps) == 353

    # Exact bijective matching using signature (input_len, cached_input_len) and nonnegative diff <= 3
    used_stats_idx: set[int] = set()
    # Skip first 3 boot/warmup records explicitly identified by signature
    boot_warmup_indices = [
        i
        for i, s in enumerate(serve_data["req_stats"])
        if s["rid"].startswith(("e19674b3", "99c16d96", "HEALTH_CHECK_"))
    ]
    assert len(boot_warmup_indices) == 3
    used_stats_idx.update(boot_warmup_indices)

    output_len_deltas: dict[int, int] = {}
    root_serve_stat: dict[str, Any] | None = None
    for fr in flat_resps:
        candidates = [
            i
            for i, s in enumerate(serve_data["req_stats"])
            if i not in used_stats_idx
            and s["in_len"] == fr["prompt_tokens"]
            and s["cached_len"] == fr["cached_tokens"]
            and 0 <= (s["out_len"] - fr["completion_tokens"]) <= 3
        ]
        assert len(candidates) >= 1, f"No serve.log ReqTimeStats match for {fr}"
        # Pick smallest diff (or earliest in log order)
        candidates.sort(key=lambda idx: (serve_data["req_stats"][idx]["out_len"] - fr["completion_tokens"], idx))
        chosen_idx = candidates[0]
        used_stats_idx.add(chosen_idx)
        stat = serve_data["req_stats"][chosen_idx]
        delta = stat["out_len"] - fr["completion_tokens"]
        output_len_deltas[delta] = output_len_deltas.get(delta, 0) + 1
        if fr["loc"] == "root_requests_jsonl":
            root_serve_stat = stat

    assert root_serve_stat is not None
    unmatched_stats = [
        serve_data["req_stats"][i]
        for i in range(len(serve_data["req_stats"]))
        if i not in used_stats_idx
    ]
    assert len(unmatched_stats) == 4, f"Expected 4 timeout ReqTimeStats, got {len(unmatched_stats)}"

    # -------------------------------------------------------------------------
    # SECTION 3: Audit Four Client Timeouts (cd82, cn04, r11l, vc33)
    # -------------------------------------------------------------------------
    # Anchor sota relative time_s to serve UTC clock using sota.log 'ended: 2026-10-30 05:30:19'
    end_mentions = [
        m for m in sota_info["token_mentions"]
        if m["text"].startswith("ended:") and "in progress" not in m["text"]
    ]
    assert end_mentions, "Missing final 'ended:' timestamp line in sota_info"
    sota_end_utc = datetime.strptime(end_mentions[-1]["text"].split("ended:")[1].strip(), "%Y-%m-%d %H:%M:%S")
    sota_t0_epoch = sota_end_utc.timestamp() - float(end_mentions[-1]["time_s"])

    # Deduplicate sota read_timeouts by (round(time_s, 2), action)
    unique_sota_to: list[dict[str, Any]] = []
    seen_sota_keys: set[tuple[float, int | None]] = set()
    for rt in sota_info["read_timeouts"]:
        key = (round(float(rt["time_s"]), 2), rt["action"])
        if key not in seen_sota_keys:
            seen_sota_keys.add(key)
            unique_sota_to.append(rt)
    assert len(unique_sota_to) == 4, f"Expected 4 unique sota timeouts, got {len(unique_sota_to)}"

    timeout_gids = ["cn04-2fe56bfb", "vc33-5430563c", "r11l-495a7899", "cd82-fb555c5d"]
    timeout_rows: list[dict[str, Any]] = []
    used_to_idx: set[int] = set()
    used_sota_idx: set[int] = set()
    for gid in timeout_gids:
        pairs = all_pairs_by_gid[gid]
        last_pair = pairs[-1]
        assert last_pair["response"] is None
        ev_recs = all_events_by_gid[gid]
        last_ev = [e for e in ev_recs if e.get("type") == "analysis"][-1]
        m_to = TIMEOUT_NUM_RE.search(last_ev["transcript"])
        assert m_to, f"Missing timeout string in {gid}"
        cli_to_s = float(m_to.group(1))
        req = last_pair["request"]

        # Match to unique_sota_to via action == req["action"] and close timeout_s
        sota_cand = [
            i
            for i, rt in enumerate(unique_sota_to)
            if i not in used_sota_idx
            and rt["action"] == int(req["action"])
            and abs(float(rt["timeout_s"]) - cli_to_s) < 1e-6
        ]
        assert len(sota_cand) == 1, f"Expected unique sota timeout for {gid}, got {sota_cand}"
        sota_rt = unique_sota_to[sota_cand[0]]
        used_sota_idx.add(sota_cand[0])
        client_utc_ts = datetime.fromtimestamp(sota_t0_epoch + float(sota_rt["time_s"]))

        prompt_log_txt = (V10_DIR / "prompts" / f"{gid}_p0.log").read_text(encoding="utf-8")
        cal: float | None = None
        for p in pairs:
            if p["response"] is not None:
                cal, _, _ = calibrate_from_usage(
                    p["request"]["messages"],
                    p["request"].get("tools"),
                    int(p["response"]["usage"]["prompt_tokens"]),
                    cal,
                    p["request"].get("tool_choice"),
                )
        est_to_req = estimate_request_input_tokens(req["messages"], req.get("tools"), cal, req.get("tool_choice"))

        best_stat = min(
            [s for j, s in enumerate(unmatched_stats) if j not in used_to_idx],
            key=lambda s: abs(
                datetime.strptime(s["ts"], "%Y-%m-%d %H:%M:%S").timestamp() - client_utc_ts.timestamp()
            ),
        )
        used_to_idx.add(unmatched_stats.index(best_stat))
        timeout_rows.append(
            {
                "game_id": gid,
                "pair_index": last_pair["pair_index"],
                "analysis_step": req["analysis_step"],
                "action": req["action"],
                "rit": req["request_index_within_turn"],
                "sota_timeout_s_rel": float(sota_rt["time_s"]),
                "client_utc_ts_est": client_utc_ts.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "client_read_timeout_s": cli_to_s,
                "estimated_prompt_tokens": est_to_req,
                "serve_req_stat": {
                    "lf_line": best_stat["lf_line"],
                    "ts": best_stat["ts"],
                    "rid": best_stat["rid"],
                    "input_len": best_stat["in_len"],
                    "cached_input_len": best_stat["cached_len"],
                    "output_len": best_stat["out_len"],
                    "queue_ms": best_stat["queue_ms"],
                    "rest": best_stat["rest"],
                },
                "has_client_usage": False,
                "in_prompt_log_timeout": ("request_timeout" in prompt_log_txt),
            }
        )
    sum_timeout_serve_out = sum(r["serve_req_stat"]["output_len"] for r in timeout_rows)
    assert sum_timeout_serve_out == 7610

    # -------------------------------------------------------------------------
    # SECTION 4: Independent FIFO & Calibration Reconstruction
    # -------------------------------------------------------------------------
    calib_live_count = 0
    calib_live_events = 0
    calib_multi_events: list[dict[str, Any]] = []
    calib_mismatches: list[dict[str, Any]] = []
    prompt_log_calib_files: list[str] = []

    for pf in prompt_files:
        txt = pf.read_text(encoding="utf-8")
        if "text_token_calibration:" in txt:
            prompt_log_calib_files.append(pf.name)

    final_cal_by_gid: dict[str, float] = {}
    eviction_rows: list[dict[str, Any]] = []
    tr87_peak_pre_open = 0
    tr87_peak_eos = 0

    for res in bench["game_runs"]:
        gid = res["game_id"]
        pairs = all_pairs_by_gid[gid]
        ev_recs = all_events_by_gid[gid]
        cal: float | None = None
        recomputed_cal_strings: list[str] = []

        for p in pairs:
            rs = p["response"]
            if rs is not None:
                new_cal, emitted, msg = calibrate_from_usage(
                    p["request"]["messages"],
                    p["request"].get("tools"),
                    int(rs["usage"]["prompt_tokens"]),
                    cal,
                    p["request"].get("tool_choice"),
                )
                cal = new_cal
                if emitted:
                    recomputed_cal_strings.append(msg)

        final_cal_by_gid[gid] = cal if cal is not None else TEXT_TOKEN_SEED

        # Check all logged calibration lines in events.jsonl
        ev_cal_strings: list[str] = []
        for ev in ev_recs:
            if ev.get("type") != "analysis":
                continue
            matches = CALIB_RE.findall(ev.get("transcript", ""))
            if matches:
                calib_live_events += 1
                if len(matches) > 1:
                    calib_multi_events.append(
                        {"gid": gid, "analysis_step": ev.get("analysis_step"), "count": len(matches)}
                    )
                for line in ev.get("transcript", "").splitlines():
                    if "text_token_calibration:" in line:
                        s_clean = line.strip()
                        ev_cal_strings.append(s_clean)
                        calib_live_count += 1

        if ev_cal_strings != recomputed_cal_strings:
            calib_mismatches.append(
                {"gid": gid, "live": ev_cal_strings, "recomputed": recomputed_cal_strings}
            )

        # Replay estimates & detect FIFO evictions
        cal_running: float | None = None
        fifo_indices = [
            i for i in range(1, len(pairs)) if classify_transition(i, pairs) == "fifo_eviction"
        ]
        # Track max pre-trim estimate for tr87 check
        for i in range(len(pairs)):
            rs_i = pairs[i]["response"]
            if rs_i is not None:
                cal_running, _, _ = calibrate_from_usage(
                    pairs[i]["request"]["messages"],
                    pairs[i]["request"].get("tools"),
                    int(rs_i["usage"]["prompt_tokens"]),
                    cal_running,
                    pairs[i]["request"].get("tool_choice"),
                )
            if i + 1 < len(pairs) and gid == "tr87-cd924810":
                prev_msgs = pairs[i]["request"]["messages"]
                next_msgs = pairs[i + 1]["request"]["messages"]
                tools = pairs[i + 1].get("request", {}).get("tools")
                tc = pairs[i + 1].get("request", {}).get("tool_choice")
                # Pre-opener end-of-invocation proxy: prev + kept suffix before new opener (approx via apply_win4 on prev)
                # Compute exact pre_open: full un-trimmed union if no drop occurred (pure_append or image_omit)
                if classify_transition(i + 1, pairs) != "fifo_eviction":
                    est_next_open = estimate_request_input_tokens(next_msgs, tools, cal_running, tc)
                    tr87_peak_pre_open = max(tr87_peak_pre_open, est_next_open)
                    # End-of-invocation before adding next opener: strip last user opener(s) appended after prev
                    # Compare prev_win4 estimate
                    win4_prev = [prev_msgs[0], *apply_history_image_window(prev_msgs[1:], HISTORY_IMAGE_KEEP)]
                    tr87_peak_eos = max(tr87_peak_eos, estimate_request_input_tokens(win4_prev, tools, cal_running, tc))

        assert len(fifo_indices) in (0, 1), f"Unexpected multiple evictions in {gid}: {fifo_indices}"
        if fifo_indices:
            ev_i = fifo_indices[0]
            prev_req = pairs[ev_i - 1]["request"]
            curr_req = pairs[ev_i]["request"]
            prev_msgs = prev_req["messages"]
            curr_msgs = curr_req["messages"]
            tools = curr_req.get("tools")
            tc = curr_req.get("tool_choice")

            # Compute running calibration EXACTLY up through response ev_i - 1!
            cal_at_ev: float | None = None
            for k in range(ev_i):
                rs_k = pairs[k]["response"]
                if rs_k is not None:
                    cal_at_ev, _, _ = calibrate_from_usage(
                        pairs[k]["request"]["messages"],
                        pairs[k]["request"].get("tools"),
                        int(rs_k["usage"]["prompt_tokens"]),
                        cal_at_ev,
                        pairs[k]["request"].get("tool_choice"),
                    )

            # Match surviving suffix of prev_msgs inside curr_msgs
            prev_hist = prev_msgs[1:]
            curr_hist = curr_msgs[1:]
            prev_keys = [strip_images_for_matching(m) for m in prev_hist]
            curr_keys = [strip_images_for_matching(m) for m in curr_hist]

            # Find earliest start index s in prev_hist matching curr_hist[0], allowing
            # _prune_control_messages (L6316) to have dropped trailing control nudges/resumes.
            anchor_key = curr_keys[0]
            curr_key_set = set(curr_keys)
            drop_count: int | None = None
            survived_keys: list[str] = []
            pruned_control_msgs: list[dict[str, Any]] = []
            for s in range(1, len(prev_keys)):
                if prev_keys[s] == anchor_key:
                    cand_survived = [prev_keys[j] for j in range(s, len(prev_keys)) if prev_keys[j] in curr_key_set]
                    if curr_keys[: len(cand_survived)] == cand_survived:
                        skipped = [prev_hist[j] for j in range(s, len(prev_keys)) if prev_keys[j] not in curr_key_set]
                        drop_count = s
                        survived_keys = cand_survived
                        pruned_control_msgs = skipped
                        break
            assert drop_count is not None, f"Could not align surviving suffix in {gid}"
            pruned_keys_set = {strip_images_for_matching(m) for m in pruned_control_msgs}
            # Also apply control pruning prior to L6321 image window / L6323 trim
            eos_prev_hist = [m for m in prev_hist if strip_images_for_matching(m) not in pruned_keys_set]
            new_suffix = curr_hist[len(survived_keys) :]

            # Split new_suffix into closing invocation tail (assistant + tool) vs next invocation opener
            last_user_idx = max(idx for idx, m in enumerate(new_suffix) if m.get("role") == "user")
            prev_tail_in_curr = new_suffix[:last_user_idx]
            curr_head_opener = new_suffix[last_user_idx:]

            full_eos_msgs = [prev_msgs[0], *apply_history_image_window([*eos_prev_hist, *prev_tail_in_curr], HISTORY_IMAGE_KEEP)]
            est_pre_win4_eos = estimate_request_input_tokens(full_eos_msgs, tools, cal_at_ev, tc)

            est_pre_raw_eos = estimate_request_input_tokens([prev_msgs[0], *eos_prev_hist, *prev_tail_in_curr], tools, cal_at_ev, tc)
            full_open_msgs = [*full_eos_msgs, *curr_head_opener]
            est_pre_open = estimate_request_input_tokens(full_open_msgs, tools, cal_at_ev, tc)

            # Determine exact simulated trim path:
            if est_pre_win4_eos > B_TOK:
                trigger_point = "end_of_invocation_L6323"
                sim_post = trim_messages_for_context(full_eos_msgs, tools, cal_at_ev, preserve_recent=0, tool_choice=tc)
                sim_post_plus_opener = [*sim_post, *curr_head_opener]
                sim_post_open_trimmed = trim_messages_for_context(
                    sim_post_plus_opener, tools, cal_at_ev, preserve_recent=1, tool_choice=tc
                )
            else:
                trigger_point = "next_opener_L6699"
                sim_post_open_trimmed = trim_messages_for_context(
                    full_open_msgs, tools, cal_at_ev, preserve_recent=1, tool_choice=tc
                )
            assert len(sim_post_open_trimmed) == len(curr_msgs), (
                f"{gid}: sim={len(sim_post_open_trimmed)} != actual={len(curr_msgs)}"
            )

            # Actions classification across Pre / EvStep / Later relative to drop action index!
            drop_step = int(curr_req["analysis_step"])
            drop_action_1idx = int(curr_req["action"])
            act_evs = sorted(
                [e for e in ev_recs if e.get("type") == "action"],
                key=lambda e: int(e["action_num"]),
            )
            assert len(act_evs) == len(res["history"]), f"{gid}: act_evs != history len"
            pre_acts = [ae for ae in act_evs if int(ae["action_num"]) < drop_action_1idx]
            post_acts = [ae for ae in act_evs if int(ae["action_num"]) >= drop_action_1idx]
            ev_step_acts = [ae for ae in post_acts if int(ae["analysis_step"]) == drop_step]
            later_acts = [ae for ae in post_acts if int(ae["analysis_step"]) > drop_step]

            eviction_rows.append(
                {
                    "game_id": gid,
                    "eviction_pair_idx": ev_i,
                    "prev_step": int(prev_req["analysis_step"]),
                    "prev_rit": int(prev_req["request_index_within_turn"]),
                    "prev_action": int(prev_req["action"]),
                    "curr_step": drop_step,
                    "curr_rit": int(curr_req["request_index_within_turn"]),
                    "curr_action": drop_action_1idx,
                    "same_step_across_eviction": int(prev_req["analysis_step"]) == drop_step,
                    "prev_msg_count": len(prev_msgs),
                    "curr_msg_count": len(curr_msgs),
                    "sim_msg_count": len(sim_post_open_trimmed),
                    "dropped_msg_count": drop_count,
                    "pruned_control_before_trim": len(pruned_control_msgs),
                    "cal_at_eviction": round(cal_at_ev, 6) if cal_at_ev is not None else None,
                    "pre_raw_eos_est": est_pre_raw_eos,
                    "pre_win4_eos_est": est_pre_win4_eos,
                    "pre_open_est": est_pre_open,
                    "post_curr_est": estimate_request_input_tokens(curr_msgs, tools, cal_at_ev, tc),
                    "trigger_point": trigger_point,
                    "pre_acts_count": len(pre_acts),
                    "pre_bf_count": sum(1 for ae in pre_acts if ae.get("board_changed") is False),
                    "ev_step_acts_count": len(ev_step_acts),
                    "ev_step_bf_count": sum(1 for ae in ev_step_acts if ae.get("board_changed") is False),
                    "later_acts_count": len(later_acts),
                    "later_bf_count": sum(1 for ae in later_acts if ae.get("board_changed") is False),
                    "total_acts": len(act_evs),
                    "pre_usage_prompt": sum(int(p["response"]["usage"]["prompt_tokens"]) for p in pairs[:ev_i] if p["response"]),
                    "pre_usage_cached": sum(int(p["response"]["usage"]["prompt_tokens_details"]["cached_tokens"]) for p in pairs[:ev_i] if p["response"]),
                    "post_usage_resps": sum(1 for p in pairs[ev_i:] if p["response"]),
                    "post_usage_prompt": sum(int(p["response"]["usage"]["prompt_tokens"]) for p in pairs[ev_i:] if p["response"]),
                    "post_usage_cached": sum(int(p["response"]["usage"]["prompt_tokens_details"]["cached_tokens"]) for p in pairs[ev_i:] if p["response"]),
                }
            )

    assert len(eviction_rows) == 9
    assert calib_live_count == 45 and calib_live_events == 42
    assert not calib_mismatches, f"Calibration mismatches: {calib_mismatches}"
    assert prompt_log_calib_files == ["ft09-0d8bbf25_p0.log", "sk48-d8078629_p0.log"]
    assert sum(r["pre_acts_count"] for r in eviction_rows) == 179
    assert sum(r["ev_step_acts_count"] for r in eviction_rows) == 16
    assert sum(r["later_acts_count"] for r in eviction_rows) == 9

    # -------------------------------------------------------------------------
    # SECTION 5: Metric Comparability & Notebook Diff & Kaggle Status
    # -------------------------------------------------------------------------
    v6_bench = json.loads((V6_DIR / "benchmark.json").read_text(encoding="utf-8"))
    v6_results = v6_bench["game_runs"]
    v6_active = sum(1 for r in v6_results if len(r["history"]) > 0)
    v6_starved = sum(1 for r in v6_results if len(r["history"]) == 0)
    v6_sum_score = sum(float(r["final_score"]) for r in v6_results)
    v6_ft09 = next(r for r in v6_results if r["game_id"].startswith("ft09"))
    assert v6_active == 10 and v6_starved == 15
    assert sum(len(r["history"]) for r in v6_results) == 270
    assert sum(int(r["levels_completed"]) for r in v6_results) == 10
    assert sum(sum(int(h.get("generated_tokens", 0)) for h in r["history"]) for r in v6_results) == 248528

    v10_ft09 = next(r for r in bench["game_runs"] if r["game_id"].startswith("ft09"))
    ft09_share_pct = 100.0 * float(v10_ft09["final_score"]) / sum_final_score
    v10_other24_sum = sum_final_score - float(v10_ft09["final_score"])

    v6_nb = json.loads(V6_NB_PATH.read_text(encoding="utf-8"))
    v10_nb = json.loads(V10_NB_PATH.read_text(encoding="utf-8"))
    assert len(v6_nb["cells"]) == 23 and len(v10_nb["cells"]) == 23
    changed_cells = [
        i for i in range(23) if "".join(v6_nb["cells"][i]["source"]) != "".join(v10_nb["cells"][i]["source"])
    ]
    assert changed_cells == [0, 4, 6, 12, 16]
    cell2_src = "".join(v6_nb["cells"][2]["source"])
    assert len(cell2_src) == 498799

    v10_status = json.loads(V10_STATUS_PATH.read_text(encoding="utf-8"))
    p60 = json.loads(PHASE6_0_JSON.read_text(encoding="utf-8"))

    # -------------------------------------------------------------------------
    # SECTION 6: Prefix-Cache Statistics (352-resp vs 353-resp & Server Sensitivity)
    # -------------------------------------------------------------------------
    def aggregate_prefix_stats(*, include_root: bool) -> dict[str, Any]:
        classes = ("initial", "pure_append", "image_omit_mutation", "fifo_eviction")
        buckets: dict[str, dict[str, Any]] = {
            c: {
                "paired_resps": 0,
                "unpaired_reqs": 0,
                "prompt_tokens": 0,
                "cached_tokens": 0,
                "uncached_tokens": 0,
                "req_hit_rates": [],
                "zero_cache_count": 0,
                "header_5056_count": 0,
                "gt_header_count": 0,
            }
            for c in classes
        }
        for gid, pairs in all_pairs_by_gid.items():
            for idx, p in enumerate(pairs):
                tcls = classify_transition(idx, pairs)
                b = buckets[tcls]
                rs = p["response"]
                if rs is None and include_root and gid == "g50t-5849a774":
                    rs = root_rec
                if rs is None:
                    b["unpaired_reqs"] += 1
                    continue
                pt = int(rs["usage"]["prompt_tokens"])
                ct = int(rs["usage"]["prompt_tokens_details"]["cached_tokens"])
                b["paired_resps"] += 1
                b["prompt_tokens"] += pt
                b["cached_tokens"] += ct
                b["uncached_tokens"] += pt - ct
                b["req_hit_rates"].append(ct / pt if pt else 0.0)
                if ct == 0:
                    b["zero_cache_count"] += 1
                elif ct == 5056:
                    b["header_5056_count"] += 1
                elif ct > 5056:
                    b["gt_header_count"] += 1

        total_pt = sum(b["prompt_tokens"] for b in buckets.values())
        total_ct = sum(b["cached_tokens"] for b in buckets.values())
        total_unc = total_pt - total_ct
        summary_classes: dict[str, Any] = {}
        for c, b in buckets.items():
            rates = b["req_hit_rates"]
            summary_classes[c] = {
                "paired_resps": b["paired_resps"],
                "unpaired_reqs": b["unpaired_reqs"],
                "prompt_tokens": b["prompt_tokens"],
                "cached_tokens": b["cached_tokens"],
                "uncached_tokens": b["uncached_tokens"],
                "token_weighted_hit_pct": round(100.0 * b["cached_tokens"] / b["prompt_tokens"], 4),
                "unweighted_mean_hit_pct": round(100.0 * (sum(rates) / len(rates)), 4) if rates else None,
                "uncached_share_pct": round(100.0 * b["uncached_tokens"] / total_unc, 4),
                "zero_cache_count": b["zero_cache_count"],
                "header_5056_count": b["header_5056_count"],
                "gt_header_count": b["gt_header_count"],
            }
        mut_unc = buckets["image_omit_mutation"]["uncached_tokens"] + buckets["fifo_eviction"]["uncached_tokens"]
        return {
            "paired_total": sum(b["paired_resps"] for b in buckets.values()),
            "unpaired_total": sum(b["unpaired_reqs"] for b in buckets.values()),
            "prompt_tokens": total_pt,
            "cached_tokens": total_ct,
            "uncached_tokens": total_unc,
            "aggregate_token_weighted_hit_pct": round(100.0 * total_ct / total_pt, 4),
            "mutation_uncached_tokens": mut_unc,
            "mutation_uncached_share_pct": round(100.0 * mut_unc / total_unc, 4),
            "by_class": summary_classes,
        }

    cache_352 = aggregate_prefix_stats(include_root=False)
    cache_353 = aggregate_prefix_stats(include_root=True)
    assert cache_352["paired_total"] == 352 and cache_353["paired_total"] == 353

    # Build server-side sensitivity including the 4 timeout ReqTimeStats records for transition classes
    timeout_class_map = {}
    for row in timeout_rows:
        gid = row["game_id"]
        idx = row["pair_index"]
        tcls = classify_transition(idx, all_pairs_by_gid[gid])
        timeout_class_map[gid] = {"class": tcls, **row["serve_req_stat"]}

    # Assemble clean result document
    results = {
        "generated_by": "11_INDEPENDENT_ARITHMETIC_CHECK.py",
        "section_1_arithmetic": {
            "v10_games": len(per_game_rows),
            "v10_total_actions": sum_actions,
            "v10_levels_completed": sum_levels_completed,
            "v10_total_levels": sum_total_levels,
            "v10_final_score_sum": round(sum_final_score, 6),
            "v10_mean_score_25": round(sum_final_score / 25.0, 6),
            "history_generated_tokens": sum_history_gen,
            "summary_txt_tokens": sum_summary_tok,
            "sota_log_tokens": sum_sota_tok,
            "per_game_paired_responses": total_paired_per_game,
            "per_game_unpaired_requests": total_unpaired_per_game,
            "per_game_prompt_tokens": sum_per_game_prompt,
            "per_game_cached_tokens": sum_per_game_cached,
            "per_game_uncached_tokens": sum_per_game_prompt - sum_per_game_cached,
            "per_game_image_tokens": sum_per_game_image,
            "per_game_completion_tokens": sum_per_game_comp,
            "per_game_reasoning_tokens": sum_per_game_reason,
            "detached_g50t_root_completion_tokens": 2778,
            "reconstructed_completion_tokens": sum_solver_note,
            "per_game_comp_minus_history": sum_per_game_comp - sum_history_gen,
            "trailing_completion_tokens_92984": sum_solver_note - sum_history_gen,
            "all_25_solver_note_exact_match": all(r["solver_note_minus_reconstructed"] == 0 for r in per_game_rows),
            "per_game": per_game_rows,
        },
        "section_2_353_reconstruction": {
            "g50t_last_request_index": g50t_pairs[-1]["pair_index"],
            "g50t_root_record_action": root_rec["action"],
            "g50t_root_record_analysis_step": root_rec["analysis_step"],
            "g50t_root_record_rit": root_rec["request_index_within_turn"],
            "g50t_root_finish_reason": root_rec["finish_reason"],
            "g50t_root_tool_call_id": root_tc["id"],
            "g50t_root_usage": root_rec["usage"],
            "seven_field_envelope_match": envelope_match,
            "tr87_done_event": sota_info["done_events"].get("tr87-cd924810"),
            "g50t_done_event": sota_info["done_events"].get("g50t-5849a774"),
            "serve_log_line_stats": {
                "cr_bytes": serve_data["cr_byte_count"],
                "lf_lines": serve_data["lf_line_count"],
                "splitlines_lines": serve_data["splitlines_line_count"],
                "http_200_posts": len(serve_data["http_posts"]),
                "req_time_stats_total": len(serve_data["req_stats"]),
                "boot_warmup_indices": [serve_data["req_stats"][i] for i in boot_warmup_indices],
                "g50t_root_serve_stat": root_serve_stat,
                "output_len_minus_completion_tokens_hist": output_len_deltas,
            },
            "reconstructed_353_totals": {
                "prompt_tokens": sum_per_game_prompt + 19438,
                "cached_tokens": sum_per_game_cached + 16064,
                "uncached_tokens": (sum_per_game_prompt - sum_per_game_cached) + 3374,
                "image_tokens": sum_per_game_image + 2000,
                "completion_tokens": sum_per_game_comp + 2778,
                "reasoning_tokens": sum_per_game_reason + 2391,
                "cache_hit_pct": round(100.0 * (sum_per_game_cached + 16064) / (sum_per_game_prompt + 19438), 4),
                "reasoning_share_pct": round(100.0 * (sum_per_game_reason + 2391) / (sum_per_game_comp + 2778), 4),
            },
        },
        "section_3_four_timeouts": {
            "count": len(timeout_rows),
            "sum_serve_output_len": sum_timeout_serve_out,
            "output_len_minus_completion_tokens_hist_353": output_len_deltas,
            "sota_log_read_timeout_count": len(sota_info["read_timeouts"]),
            "rows": timeout_rows,
        },
        "section_4_fifo_and_calibration": {
            "b_tok": B_TOK,
            "b_target": B_TARGET,
            "calib_live_strings": calib_live_count,
            "calib_live_event_records": calib_live_events,
            "calib_multi_string_events": calib_multi_events,
            "calib_prompt_log_files": prompt_log_calib_files,
            "calib_mismatches_count": len(calib_mismatches),
            "tr87_peak_pre_open_est": tr87_peak_pre_open,
            "tr87_peak_eos_est": tr87_peak_eos,
            "evicted_games_count": len(eviction_rows),
            "pre_acts_sum": sum(r["pre_acts_count"] for r in eviction_rows),
            "pre_bf_sum": sum(r["pre_bf_count"] for r in eviction_rows),
            "ev_step_acts_sum": sum(r["ev_step_acts_count"] for r in eviction_rows),
            "ev_step_bf_sum": sum(r["ev_step_bf_count"] for r in eviction_rows),
            "later_acts_sum": sum(r["later_acts_count"] for r in eviction_rows),
            "later_bf_sum": sum(r["later_bf_count"] for r in eviction_rows),
            "eviction_rows": eviction_rows,
        },
        "section_5_comparability_and_diffs": {
            "v6_active_games": v6_active,
            "v6_starved_games": v6_starved,
            "v6_actions": sum(len(r["history"]) for r in v6_results),
            "v6_levels_completed": sum(int(r["levels_completed"]) for r in v6_results),
            "v6_score_sum": round(v6_sum_score, 6),
            "v6_mean_25": round(v6_sum_score / 25.0, 6),
            "v6_ft09_score": float(v6_ft09["final_score"]),
            "v6_other24_mean": round((v6_sum_score - float(v6_ft09["final_score"])) / 24.0, 6),
            "v6_history_generated_tokens": 248528,
            "v6_solver_note_sum": sum(
                int(m.group(1))
                for r in v6_results
                if isinstance(r.get("solver_note"), str)
                for m in [re.search(r"tokens=(\d+)", r["solver_note"])]
                if m
            ),
            "v10_ft09_score": float(v10_ft09["final_score"]),
            "v10_ft09_share_pct": round(ft09_share_pct, 4),
            "v10_other24_sum": round(v10_other24_sum, 6),
            "v10_other24_per25": round(v10_other24_sum / 25.0, 6),
            "v10_other24_per24": round(v10_other24_sum / 24.0, 6),
            "notebook_total_cells": 23,
            "notebook_changed_cells": changed_cells,
            "notebook_cell2_sha256": hashlib.sha256(cell2_src.encode("utf-8")).hexdigest(),
            "notebook_cell2_chars": len(cell2_src),
            "v10_submission_status": {
                "ref": v10_status["submission_ref"],
                "raw_status": v10_status["submission_record"]["raw_status"],
                "public_score": v10_status["submission_record"]["public_score"],
                "classification": v10_status["classification"],
            },
            "phase6_0_arms": {
                k: {
                    "history_turns": v["config"]["history_turns"],
                    "actions_executed": v["actions_executed"],
                    "levels_completed": v["levels_completed"],
                }
                for k, v in p60["arms"].items()
            },
        },
        "section_6_prefix_cache": {
            "scope_352_per_game": cache_352,
            "scope_353_with_g50t_root": cache_353,
            "four_timeouts_serve_classification": timeout_class_map,
        },
    }

    OUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"ALL INDEPENDENT CHECKS PASSED -> {OUT_JSON_PATH}")
    print(
        f"S1: hist={sum_history_gen}, pg_comp={sum_per_game_comp}, root={2778}, "
        f"reconstructed={sum_solver_note}, trailing={sum_solver_note - sum_history_gen}, "
        f"score={sum_final_score:.6f} (ft09={float(v10_ft09['final_score']):.6f}, {ft09_share_pct:.2f}%)"
    )
    print(
        f"S2: HTTP_200={len(serve_data['http_posts'])}, ReqTimeStats={len(serve_data['req_stats'])}, "
        f"root_match_lf={root_serve_stat['lf_line']} deltas={output_len_deltas}"
    )
    print(f"S3: 4 timeouts serve_out_sum={sum_timeout_serve_out}, sota_timeouts={len(sota_info['read_timeouts'])}")
    print(
        f"S4: calib_strings={calib_live_count} across {calib_live_events} events, "
        f"mismatches={len(calib_mismatches)}, tr87_peak_open={tr87_peak_pre_open}, tr87_peak_eos={tr87_peak_eos}"
    )
    for row in eviction_rows:
        print(
            f"  EVICT {row['game_id']}: {row['prev_msg_count']}->{row['curr_msg_count']} "
            f"(sim={row['sim_msg_count']}) step={row['prev_step']}->{row['curr_step']} "
            f"rit={row['prev_rit']}->{row['curr_rit']} trig={row['trigger_point']} "
            f"eos={row['pre_win4_eos_est']} open={row['pre_open_est']} "
            f"acts={row['pre_acts_count']}({row['pre_bf_count']}F)/{row['ev_step_acts_count']}({row['ev_step_bf_count']}F)/{row['later_acts_count']}({row['later_bf_count']}F)"
        )
    print(
        f"S6 (352): hit={cache_352['aggregate_token_weighted_hit_pct']:.2f}% mut_unc={cache_352['mutation_uncached_share_pct']:.2f}% | "
        f"(353): hit={cache_353['aggregate_token_weighted_hit_pct']:.2f}% mut_unc={cache_353['mutation_uncached_share_pct']:.2f}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
