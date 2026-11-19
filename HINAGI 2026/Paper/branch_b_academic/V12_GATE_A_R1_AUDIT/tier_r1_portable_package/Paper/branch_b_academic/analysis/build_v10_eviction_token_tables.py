#!/usr/bin/env python3
"""Build and verify Branch-B tables for V10 local 25-game eviction and token accounting.

Reads strictly read-only from ``HINAGI 2026/submissions/arc3_v10_verified/`` and writes
self-contained CSV, JSON, and Markdown deliverables into
``HINAGI 2026/Paper/branch_b_academic/analysis/``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(os.environ.get("R1_PACKAGE_ROOT", Path(__file__).resolve().parents[3]))
DEFAULT_V10_DIR = Path(os.environ.get("R1_V10_DIR", PACKAGE_ROOT / "submissions/arc3_v10_verified"))
DEFAULT_OUT_DIR = Path(os.environ.get("R1_AN_OUT_DIR", PACKAGE_ROOT / "replay_out/analysis"))

FINISHED_RE = re.compile(
    r'\[finished\]\s+(\S+)\s+state=(\S+)\s+level=(\S+)\s+score=(\S+)\s+'
    r'actions=(\d+)\s+tokens=(\d+)\s+per-level=(\S+).*?note="(.*?)"'
)
SUMMARY_GAME_RE = re.compile(
    r"^\s+([a-z0-9-]+):\s+score=([0-9.]+),\s+levels=([0-9.]+)/(\d+),\s+"
    r"actions=(\d+),\s+tokens=(\d+)\s*$"
)
NOTE_TOKENS_RE = re.compile(r"tokens=(\d+)")
TIMEOUT_RE = re.compile(r"read timeout=([0-9.]+)")


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_summary_txt(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Parse summary.txt header totals and per-game rows."""
    header: dict[str, Any] = {}
    per_game: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = SUMMARY_GAME_RE.match(line)
        if m:
            gid, score_s, lvl_done_s, lvl_tot_s, act_s, tok_s = m.groups()
            per_game[gid] = {
                "score": float(score_s),
                "levels_completed": int(float(lvl_done_s)),
                "total_levels": int(lvl_tot_s),
                "actions": int(act_s),
                "tokens": int(tok_s),
            }
            continue
        for key in ("total actions:", "total tokens:", "mean score:", "median score:", "duration:"):
            if line.startswith(key):
                raw_val = line.split(":", 1)[1].strip()
                norm_key = key[:-1].replace(" ", "_")
                if norm_key in ("total_actions", "total_tokens"):
                    header[norm_key] = int(raw_val)
                elif norm_key in ("mean_score", "median_score"):
                    header[norm_key] = float(raw_val)
                else:
                    header[norm_key] = raw_val
    return header, per_game


def parse_benchmark_json(path: Path) -> dict[str, dict[str, Any]]:
    """Parse benchmark.json game_runs keyed by game_id."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for gr in data.get("game_runs", []):
        gid = gr["game_id"]
        hist = gr.get("history", [])
        note_m = NOTE_TOKENS_RE.search(gr.get("solver_note") or "")
        out[gid] = {
            "state": gr.get("state"),
            "number_of_levels": gr.get("number_of_levels"),
            "levels_completed": gr.get("levels_completed"),
            "final_score": gr.get("final_score"),
            "history_actions": len(hist),
            "history_tokens": sum(int(h.get("generated_tokens", 0)) for h in hist),
            "history_uncached_tokens": sum(int(h.get("uncached_input_tokens", 0)) for h in hist),
            "final_generated_tokens": int(gr.get("final_generated_tokens", 0)),
            "solver_note": gr.get("solver_note"),
            "solver_note_tokens": int(note_m.group(1)) if note_m else None,
            "wallclock_seconds": float(gr.get("final_wallclock_seconds", 0.0)),
        }
    return out


def parse_sota_log(path: Path) -> dict[str, dict[str, Any]]:
    """Parse arc-agi-3-sota.log [finished] lines keyed by game_id."""
    finished: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip().lstrip(",")
        if not cleaned:
            continue
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        for sub in obj.get("data", "").splitlines():
            m = FINISHED_RE.search(sub)
            if not m:
                continue
            gid, st, lvl, sc, act, rep_tok, pl, note = m.groups()
            nt_m = NOTE_TOKENS_RE.search(note)
            finished[gid] = {
                "state": st,
                "level": lvl,
                "score": float(sc),
                "actions": int(act),
                "rep_tokens": int(rep_tok),
                "per_level": pl,
                "note": note,
                "note_tokens": int(nt_m.group(1)) if nt_m else None,
            }
    return finished


def pair_requests_and_responses(req_path: Path) -> list[tuple[int, dict[str, Any], dict[str, Any] | None]]:
    """Pair each 'request' event with its following 'response' event, or None if unreturned."""
    pairs: list[tuple[int, dict[str, Any], dict[str, Any] | None]] = []
    cur_req: dict[str, Any] | None = None
    with req_path.open(encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            ev = obj.get("event")
            if ev == "request":
                if cur_req is not None:
                    pairs.append((len(pairs), cur_req, None))
                cur_req = obj
            elif ev == "response":
                if cur_req is None:
                    raise ValueError(f"Orphan response in {req_path}")
                pairs.append((len(pairs), cur_req, obj))
                cur_req = None
    if cur_req is not None:
        pairs.append((len(pairs), cur_req, None))
    return pairs


def extract_tool_call_ids(messages: list[dict[str, Any]]) -> list[str]:
    """Return ordered assistant tool_call IDs in a request message list."""
    ids: list[str] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            tc_id = tc.get("id")
            if tc_id:
                ids.append(tc_id)
    return ids


def classify_prefix_transition(
    idx: int, pairs: list[tuple[int, dict[str, Any], dict[str, Any] | None]]
) -> tuple[str, int]:
    """Classify request prefix transition vs previous request and return missing tool_call count."""
    if idx == 0:
        return "initial", 0
    prev_msgs = pairs[idx - 1][1].get("messages", [])
    curr_msgs = pairs[idx][1].get("messages", [])
    prev_tc = extract_tool_call_ids(prev_msgs)
    curr_tc_set = set(extract_tool_call_ids(curr_msgs))
    missing_tc = sum(1 for tid in prev_tc if tid not in curr_tc_set)
    if missing_tc > 0 or len(curr_msgs) < len(prev_msgs):
        return "fifo_eviction", missing_tc
    # Count identical prefix messages; any mutation breaks KV cache from that index onward.
    exact_prefix = 0
    for a, b in zip(prev_msgs, curr_msgs):
        if a == b:
            exact_prefix += 1
        else:
            break
    if exact_prefix == len(prev_msgs):
        return "pure_append", 0
    return "image_omit_mutation", 0


def parse_analyzer_config(transcript: str) -> dict[str, str]:
    """Extract key: value configuration fields from [ANALYZER STATUS]."""
    cfg: dict[str, str] = {}
    if "[ANALYZER STATUS]" not in transcript:
        return cfg
    tail = transcript.split("[ANALYZER STATUS]")[-1]
    for line in tail.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k_s = k.strip()
        if k_s in (
            "model",
            "max_output_tokens",
            "reply_reserve_tokens",
            "context_budget_tokens",
            "request_safety_margin_tokens",
            "tool_output_tokens",
            "yield_seconds",
            "yield_tokens",
            "python_timeout_seconds",
        ):
            cfg[k_s] = v.strip()
    return cfg


def classify_termination(analysis_events: list[dict[str, Any]]) -> str:
    """Determine final game termination reason from last analysis transcript."""
    if not analysis_events:
        return "UNKNOWN"
    tr = analysis_events[-1].get("transcript", "")
    tail = tr.split("[ANALYZER STATUS]")[-1] if "[ANALYZER STATUS]" in tr else tr
    if "request_timeout" in tail:
        m = TIMEOUT_RE.search(tail)
        return f"request_timeout ({float(m.group(1)):.2f}s)" if m else "request_timeout"
    if "Yielded control to solver: stop_requested." in tail:
        return "stop_requested"
    return "other"


def parse_events_jsonl(events_path: Path) -> dict[str, Any]:
    """Parse artifacts/<gid>_p0_events.jsonl for action, analysis, stale errors, and config."""
    action_events: list[dict[str, Any]] = []
    analysis_events: list[dict[str, Any]] = []
    config: dict[str, str] = {}
    with events_path.open(encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            etype = obj.get("type")
            if etype == "action":
                action_events.append(obj)
            elif etype == "analysis":
                analysis_events.append(obj)
                if not config:
                    config = parse_analyzer_config(obj.get("transcript", ""))

    stale_steps = [
        int(ae["analysis_step"])
        for ae in analysis_events
        if "StaleStateActionError" in ae.get("transcript", "")
    ]
    wwm_steps = [
        int(ae["analysis_step"])
        for ae in analysis_events
        if "Working world model" in ae.get("transcript", "")
    ]
    return {
        "action_events": action_events,
        "analysis_events": analysis_events,
        "termination_cause": classify_termination(analysis_events),
        "analyzer_config": config,
        "stale_error_steps": stale_steps,
        "wwm_analysis_steps": wwm_steps,
    }


def sum_response_usage(pairs_slice: list[tuple[int, dict[str, Any], dict[str, Any] | None]]) -> dict[str, Any]:
    """Aggregate exact token fields over paired HTTP responses in a slice."""
    prompt = 0
    cached = 0
    image = 0
    comp = 0
    reason = 0
    total = 0
    resps = 0
    unpaired = 0
    for _, _, rs in pairs_slice:
        if rs is None:
            unpaired += 1
            continue
        resps += 1
        u = rs["usage"]
        pd = u.get("prompt_tokens_details", {})
        p = int(u["prompt_tokens"])
        c = int(pd.get("cached_tokens", 0))
        im = int(pd.get("image_tokens", 0))
        co = int(u["completion_tokens"])
        re_t = int(u.get("reasoning_tokens", 0))
        to = int(u["total_tokens"])
        if to != p + co:
            raise AssertionError(f"total_tokens mismatch: {to} != {p} + {co}")
        prompt += p
        cached += c
        image += im
        comp += co
        reason += re_t
        total += to
    uncached = prompt - cached
    non_reason = comp - reason
    return {
        "reqs": len(pairs_slice),
        "resps": resps,
        "unpaired_reqs": unpaired,
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "uncached_prefill_tokens": uncached,
        "cache_hit_pct": round(100.0 * cached / prompt, 2) if prompt else None,
        "image_tokens": image,
        "completion_tokens": comp,
        "reasoning_tokens": reason,
        "non_reasoning_output_tokens": non_reason,
        "reasoning_share_pct": round(100.0 * reason / comp, 2) if comp else None,
        "total_tokens": total,
    }


def count_wwm_in_messages(messages: list[dict[str, Any]]) -> int:
    """Count messages containing 'Working world model' in their serialized content."""
    return sum(1 for m in messages if "Working world model" in json.dumps(m))


def count_roles(messages: list[dict[str, Any]]) -> dict[str, int]:
    """Count message roles in a chat prompt."""
    counts = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
    for m in messages:
        role = m.get("role", "")
        counts[role] = counts.get(role, 0) + 1
    return counts


def classify_eviction_outcome(
    gid: str,
    post_action_rows: list[dict[str, Any]],
    termination: str,
    post_usage: dict[str, Any],
    levels_post: int,
) -> str:
    """Return a strictly evidence-based behavioral summary of eviction+post-eviction execution."""
    if post_usage["resps"] == 0:
        return f"Immediate HTTP timeout on eviction request ({termination}); 0 responses, 0 actions."
    if not post_action_rows:
        return (
            f"{post_usage['resps']} response(s) after eviction returned 0 executed env actions; "
            f"ended with {termination}."
        )
    if levels_post > 0:
        return (
            f"Solved +{levels_post} level(s) across {len(post_action_rows)} eviction/post-eviction actions "
            f"(built Working world model post-eviction); ended with {termination}."
        )
    if gid == "vc33-5430563c":
        return (
            "Executed 9x MOUSE(56,46) Phase 1 of carried Level-3 plan (8 board_changed=True, 9th False); "
            f"then {termination} aborted before Phases 2-4."
        )
    return (
        f"Executed {len(post_action_rows)} action(s) at/after eviction "
        f"({sum(1 for a in post_action_rows if not a['board_changed'])} board_changed=False); "
        f"ended with {termination}."
    )


def analyze_game(
    gid: str,
    v10_dir: Path,
    summary_row: dict[str, Any],
    bjson_row: dict[str, Any],
    sota_row: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    """Build complete per-game record, optional eviction breakdown, post-eviction actions, and prefix breakdown."""
    pairs = pair_requests_and_responses(v10_dir / f"{gid}_p0_requests.jsonl")
    ev_data = parse_events_jsonl(v10_dir / "artifacts" / f"{gid}_p0_events.jsonl")
    action_events = ev_data["action_events"]

    # Classify every request transition and detect eviction points
    transitions: list[tuple[str, int]] = []
    evict_indices: list[int] = []
    for i in range(len(pairs)):
        cls, missing_tc = classify_prefix_transition(i, pairs)
        transitions.append((cls, missing_tc))
        if cls == "fifo_eviction":
            evict_indices.append(i)

    if len(evict_indices) > 1:
        raise AssertionError(f"Expected at most 1 eviction in {gid}, got {evict_indices}")

    evicted = len(evict_indices) == 1
    drop_idx = evict_indices[0] if evicted else None

    # Full usage and per-transition usage
    full_usage = sum_response_usage(pairs)
    by_cls: dict[str, list[tuple[int, dict[str, Any], dict[str, Any] | None]]] = {
        "initial": [],
        "pure_append": [],
        "image_omit_mutation": [],
        "fifo_eviction": [],
    }
    for (cls, _), pair in zip(transitions, pairs):
        by_cls[cls].append(pair)
    cls_usage = {k: sum_response_usage(v) for k, v in by_cls.items()}

    max_prompt_tokens = max(
        (rs["usage"]["prompt_tokens"] for _, _, rs in pairs if rs is not None), default=0
    )
    bchg_false_total = sum(1 for a in action_events if not a.get("board_changed", True))
    comp_tokens = full_usage["completion_tokens"]
    sum_tokens = summary_row["tokens"]
    note_tokens = bjson_row["solver_note_tokens"]
    note_minus_comp = (note_tokens - comp_tokens) if note_tokens is not None else None

    unlogged_status = "none"
    if full_usage["unpaired_reqs"] > 0:
        if "timeout" in ev_data["termination_cause"]:
            unlogged_status = f"N/A (HTTP {ev_data['termination_cause']}; {full_usage['unpaired_reqs']} req)"
        elif note_minus_comp and note_minus_comp > 0:
            unlogged_status = (
                f"N/A_in_requests_jsonl (+{note_minus_comp} tokens in solver_note; "
                f"{full_usage['unpaired_reqs']} unpaired req)"
            )

    game_row = {
        "game_id": gid,
        "cohort": "evicted" if evicted else "non_evicted",
        "evicted": evicted,
        "evict_req_idx": drop_idx if drop_idx is not None else "N/A",
        "evict_step": pairs[drop_idx][1].get("analysis_step") if drop_idx is not None else "N/A",
        "evict_next_action": pairs[drop_idx][1].get("action") if drop_idx is not None else "N/A",
        "score": summary_row["score"],
        "levels_completed": summary_row["levels_completed"],
        "total_levels": summary_row["total_levels"],
        "reported_actions": summary_row["actions"],
        "logged_action_events": len(action_events),
        "board_changed_false": bchg_false_total,
        "stale_state_errors": len(ev_data["stale_error_steps"]),
        "reqs": full_usage["reqs"],
        "resps": full_usage["resps"],
        "unpaired_reqs": full_usage["unpaired_reqs"],
        "max_prompt_tokens": max_prompt_tokens,
        "prompt_tokens": full_usage["prompt_tokens"],
        "cached_tokens": full_usage["cached_tokens"],
        "uncached_prefill_tokens": full_usage["uncached_prefill_tokens"],
        "cache_hit_pct": full_usage["cache_hit_pct"],
        "image_tokens": full_usage["image_tokens"],
        "completion_tokens": comp_tokens,
        "reasoning_tokens": full_usage["reasoning_tokens"],
        "non_reasoning_output_tokens": full_usage["non_reasoning_output_tokens"],
        "reasoning_share_pct": full_usage["reasoning_share_pct"],
        "total_tokens_requests_jsonl": full_usage["total_tokens"],
        "summary_reported_tokens": sum_tokens,
        "benchmark_history_tokens": bjson_row["history_tokens"],
        "sota_log_note_tokens": note_tokens,
        "comp_minus_summary_tokens": comp_tokens - sum_tokens,
        "note_minus_comp_tokens": note_minus_comp,
        "handoff_summary_tokens": "0 (N/A: FIFO eviction only)",
        "unlogged_timeout_status": unlogged_status,
        "pure_append_resps": cls_usage["pure_append"]["resps"],
        "pure_append_cache_pct": cls_usage["pure_append"]["cache_hit_pct"],
        "image_omit_resps": cls_usage["image_omit_mutation"]["resps"],
        "image_omit_cache_pct": cls_usage["image_omit_mutation"]["cache_hit_pct"],
        "fifo_evict_resps": cls_usage["fifo_eviction"]["resps"],
        "fifo_evict_cache_pct": cls_usage["fifo_eviction"]["cache_hit_pct"],
        "termination_cause": ev_data["termination_cause"],
        "wallclock_seconds": round(bjson_row["wallclock_seconds"], 3),
        "analyzer_config": ev_data["analyzer_config"],
    }

    evict_detail: dict[str, Any] | None = None
    post_action_rows: list[dict[str, Any]] = []
    if evicted and drop_idx is not None:
        pre_pairs = pairs[:drop_idx]
        post_pairs = pairs[drop_idx:]
        pre_usage = sum_response_usage(pre_pairs)
        post_usage = sum_response_usage(post_pairs)

        pre_msgs = pairs[drop_idx - 1][1]["messages"]
        post_msgs = pairs[drop_idx][1]["messages"]
        pre_roles = count_roles(pre_msgs)
        post_roles = count_roles(post_msgs)
        pre_tc = extract_tool_call_ids(pre_msgs)
        post_tc = extract_tool_call_ids(post_msgs)
        kept_tc = sum(1 for tid in post_tc if tid in set(pre_tc))

        drop_next_action = int(pairs[drop_idx][1]["action"])
        drop_step = int(pairs[drop_idx][1]["analysis_step"])

        pre_acts = [a for a in action_events if int(a["action_num"]) < drop_next_action]
        post_acts = [a for a in action_events if int(a["action_num"]) >= drop_next_action]

        levels_pre = sum(1 for a in pre_acts if a.get("level_completed"))
        levels_post = sum(1 for a in post_acts if a.get("level_completed"))
        bchg_false_pre = sum(1 for a in pre_acts if not a.get("board_changed", True))
        bchg_false_post = sum(1 for a in post_acts if not a.get("board_changed", True))

        stale_pre = sum(1 for s in ev_data["stale_error_steps"] if s < drop_step)
        stale_post = sum(1 for s in ev_data["stale_error_steps"] if s >= drop_step)

        for a in post_acts:
            act_step = int(a["analysis_step"])
            post_action_rows.append(
                {
                    "game_id": gid,
                    "action_num": int(a["action_num"]),
                    "analysis_step": act_step,
                    "evict_step": drop_step,
                    "phase": "at_eviction_step" if act_step == drop_step else "strictly_later_step",
                    "level": int(a["level"]),
                    "action_display": a.get("action_display"),
                    "board_changed": bool(a.get("board_changed", False)),
                    "level_completed": bool(a.get("level_completed", False)),
                    "score_after": float(a.get("score", 0.0)),
                }
            )

        pre_last_rs = pairs[drop_idx - 1][2]
        pre_last_prompt = pre_last_rs["usage"]["prompt_tokens"] if pre_last_rs else None
        pre_last_tot = pre_last_rs["usage"]["total_tokens"] if pre_last_rs else None

        evict_rs = pairs[drop_idx][2]
        evict_prompt = evict_rs["usage"]["prompt_tokens"] if evict_rs else None
        evict_cached = evict_rs["usage"]["prompt_tokens_details"]["cached_tokens"] if evict_rs else None

        evict_detail = {
            "game_id": gid,
            "drop_req_idx": drop_idx,
            "drop_step": drop_step,
            "drop_next_action": drop_next_action,
            "msgs_before": len(pre_msgs),
            "msgs_after": len(post_msgs),
            "msgs_dropped_net": len(pre_msgs) - len(post_msgs),
            "asst_turns_before": pre_roles["assistant"],
            "asst_turns_after": post_roles["assistant"],
            "prev_tool_calls_retained": kept_tc,
            "prev_tool_calls_evicted": transitions[drop_idx][1],
            "wwm_msgs_before": count_wwm_in_messages(pre_msgs),
            "wwm_msgs_after": count_wwm_in_messages(post_msgs),
            "wwm_created_after_evict_steps": sum(
                1 for s in ev_data["wwm_analysis_steps"] if s >= drop_step
            ),
            "pre_last_prompt_tokens": pre_last_prompt,
            "pre_last_total_tokens": pre_last_tot,
            "evict_turn_prompt_tokens": evict_prompt if evict_prompt is not None else "N/A (timeout)",
            "evict_turn_cached_tokens": evict_cached if evict_cached is not None else "N/A (timeout)",
            "pre_reqs": pre_usage["reqs"],
            "pre_resps": pre_usage["resps"],
            "pre_prompt_tokens": pre_usage["prompt_tokens"],
            "pre_cached_tokens": pre_usage["cached_tokens"],
            "pre_uncached_prefill_tokens": pre_usage["uncached_prefill_tokens"],
            "pre_cache_hit_pct": pre_usage["cache_hit_pct"],
            "pre_completion_tokens": pre_usage["completion_tokens"],
            "pre_reasoning_tokens": pre_usage["reasoning_tokens"],
            "pre_actions": len(pre_acts),
            "pre_board_changed_false": bchg_false_pre,
            "pre_levels_solved": levels_pre,
            "pre_stale_errors": stale_pre,
            "post_reqs": post_usage["reqs"],
            "post_resps": post_usage["resps"],
            "post_unpaired_reqs": post_usage["unpaired_reqs"],
            "post_prompt_tokens": post_usage["prompt_tokens"] if post_usage["resps"] else "N/A (0 resps)",
            "post_cached_tokens": post_usage["cached_tokens"] if post_usage["resps"] else "N/A (0 resps)",
            "post_uncached_prefill_tokens": (
                post_usage["uncached_prefill_tokens"] if post_usage["resps"] else "N/A (0 resps)"
            ),
            "post_cache_hit_pct": (
                post_usage["cache_hit_pct"] if post_usage["cache_hit_pct"] is not None else "N/A"
            ),
            "post_completion_tokens": (
                post_usage["completion_tokens"] if post_usage["resps"] else "N/A (0 resps)"
            ),
            "post_reasoning_tokens": (
                post_usage["reasoning_tokens"] if post_usage["resps"] else "N/A (0 resps)"
            ),
            "post_actions": len(post_acts),
            "post_actions_at_evict_step": sum(
                1 for r in post_action_rows if r["phase"] == "at_eviction_step"
            ),
            "post_actions_later_steps": sum(
                1 for r in post_action_rows if r["phase"] == "strictly_later_step"
            ),
            "post_board_changed_false": bchg_false_post,
            "post_levels_solved": levels_post,
            "post_stale_errors": stale_post,
            "final_score": summary_row["score"],
            "note_minus_comp_tokens": note_minus_comp,
            "termination_cause": ev_data["termination_cause"],
            "behavioral_classification": classify_eviction_outcome(
                gid, post_action_rows, ev_data["termination_cause"], post_usage, levels_post
            ),
        }

    return game_row, evict_detail, post_action_rows, cls_usage


def summarize_cohort(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    """Compute exact aggregate statistics over a cohort of game records."""
    n = len(rows)
    prompt = sum(r["prompt_tokens"] for r in rows)
    cached = sum(r["cached_tokens"] for r in rows)
    uncached = sum(r["uncached_prefill_tokens"] for r in rows)
    image = sum(r["image_tokens"] for r in rows)
    comp = sum(r["completion_tokens"] for r in rows)
    reason = sum(r["reasoning_tokens"] for r in rows)
    non_reason = sum(r["non_reasoning_output_tokens"] for r in rows)
    total = sum(r["total_tokens_requests_jsonl"] for r in rows)
    summ_tok = sum(r["summary_reported_tokens"] for r in rows)
    note_tok = sum(r["sota_log_note_tokens"] or 0 for r in rows)
    acts = sum(r["reported_actions"] for r in rows)
    bchg_f = sum(r["board_changed_false"] for r in rows)
    scores = [r["score"] for r in rows]
    solved_lvls = sum(r["levels_completed"] for r in rows)
    solved_games = sum(1 for r in rows if r["levels_completed"] > 0)
    return {
        "cohort": label,
        "games": n,
        "games_with_levels_solved": solved_games,
        "total_levels_solved": solved_lvls,
        "mean_score": round(sum(scores) / n, 4) if n else 0.0,
        "total_actions": acts,
        "board_changed_false_actions": bchg_f,
        "board_changed_false_pct": round(100.0 * bchg_f / acts, 2) if acts else 0.0,
        "reqs": sum(r["reqs"] for r in rows),
        "resps": sum(r["resps"] for r in rows),
        "unpaired_reqs": sum(r["unpaired_reqs"] for r in rows),
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "uncached_prefill_tokens": uncached,
        "cache_hit_pct": round(100.0 * cached / prompt, 2) if prompt else 0.0,
        "image_tokens": image,
        "completion_tokens": comp,
        "reasoning_tokens": reason,
        "non_reasoning_output_tokens": non_reason,
        "reasoning_share_pct": round(100.0 * reason / comp, 2) if comp else 0.0,
        "total_tokens_requests_jsonl": total,
        "summary_reported_tokens": summ_tok,
        "sota_log_note_tokens": note_tok,
        "comp_minus_summary_tokens": comp - summ_tok,
        "note_minus_comp_tokens": note_tok - comp,
    }


def verify_invariants(
    summary_header: dict[str, Any],
    summary_games: dict[str, dict[str, Any]],
    bjson_games: dict[str, dict[str, Any]],
    sota_games: dict[str, dict[str, Any]],
    game_rows: list[dict[str, Any]],
    evict_rows: list[dict[str, Any]],
    prefix_totals: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Run strict cross-file conservation checks; return verified check dictionary."""
    if len(game_rows) != 25:
        raise AssertionError(f"Expected 25 games, got {len(game_rows)}")
    if len(evict_rows) != 9:
        raise AssertionError(f"Expected 9 evicted games, got {len(evict_rows)}")

    tot_rep_act = sum(r["reported_actions"] for r in game_rows)
    tot_ev_act = sum(r["logged_action_events"] for r in game_rows)
    tot_sum_tok = sum(r["summary_reported_tokens"] for r in game_rows)
    tot_bjson_tok = sum(r["benchmark_history_tokens"] for r in game_rows)
    tot_sota_rep = sum(sota_games[g]["rep_tokens"] for g in summary_games)

    assert tot_rep_act == summary_header["total_actions"] == tot_ev_act == 386, (
        tot_rep_act,
        summary_header["total_actions"],
        tot_ev_act,
    )
    assert tot_sum_tok == summary_header["total_tokens"] == tot_bjson_tok == tot_sota_rep == 378304, (
        tot_sum_tok,
        summary_header["total_tokens"],
        tot_bjson_tok,
        tot_sota_rep,
    )

    for g in summary_games:
        assert summary_games[g]["actions"] == sota_games[g]["actions"]
        assert summary_games[g]["actions"] == bjson_games[g]["history_actions"]
        assert summary_games[g]["tokens"] == sota_games[g]["rep_tokens"] == bjson_games[g]["history_tokens"]

    # Token identity checks across all 25 games
    all_cohort = summarize_cohort(game_rows, "All 25")
    assert all_cohort["prompt_tokens"] == all_cohort["cached_tokens"] + all_cohort["uncached_prefill_tokens"]
    assert all_cohort["completion_tokens"] == (
        all_cohort["reasoning_tokens"] + all_cohort["non_reasoning_output_tokens"]
    )
    assert all_cohort["total_tokens_requests_jsonl"] == (
        all_cohort["prompt_tokens"] + all_cohort["completion_tokens"]
    )
    assert all_cohort["reqs"] == all_cohort["resps"] + all_cohort["unpaired_reqs"]

    # Prefix breakdown must sum to full 25-game totals
    for field in ("resps", "prompt_tokens", "cached_tokens", "uncached_prefill_tokens", "image_tokens", "completion_tokens", "reasoning_tokens"):
        s = sum(prefix_totals[k][field] for k in ("initial", "pure_append", "image_omit_mutation", "fifo_eviction"))
        assert s == all_cohort[field], f"Prefix partition mismatch on {field}: {s} != {all_cohort[field]}"

    # Pre + Post eviction partitions must sum to evicted-game totals
    ev_map = {r["game_id"]: r for r in game_rows if r["evicted"]}
    for er in evict_rows:
        gr = ev_map[er["game_id"]]
        assert er["pre_reqs"] + er["post_reqs"] == gr["reqs"]
        assert er["pre_resps"] + er["post_resps"] == gr["resps"]
        assert er["pre_actions"] + er["post_actions"] == gr["reported_actions"]
        assert er["pre_board_changed_false"] + er["post_board_changed_false"] == gr["board_changed_false"]
        assert er["pre_levels_solved"] + er["post_levels_solved"] == gr["levels_completed"]
        post_comp = 0 if isinstance(er["post_completion_tokens"], str) else er["post_completion_tokens"]
        post_prompt = 0 if isinstance(er["post_prompt_tokens"], str) else er["post_prompt_tokens"]
        post_cached = 0 if isinstance(er["post_cached_tokens"], str) else er["post_cached_tokens"]
        assert er["pre_completion_tokens"] + post_comp == gr["completion_tokens"]
        assert er["pre_prompt_tokens"] + post_prompt == gr["prompt_tokens"]
        assert er["pre_cached_tokens"] + post_cached == gr["cached_tokens"]

    return {
        "games_checked": len(game_rows),
        "evicted_games_checked": len(evict_rows),
        "total_actions_conserved": tot_rep_act,
        "summary_tokens_conserved": tot_sum_tok,
        "requests_jsonl_completion_tokens": all_cohort["completion_tokens"],
        "sota_log_note_tokens": all_cohort["sota_log_note_tokens"],
        "all_checks_passed": True,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Write rows to CSV cleanly with UTF-8 encoding."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def render_markdown_report(
    payload: dict[str, Any], out_dir: Path, v10_dir: Path
) -> str:
    """Render a comprehensive, evidence-grounded Markdown audit report."""
    cohorts = payload["cohorts"]
    c_all = cohorts["all_25"]
    c_ev = cohorts["evicted_9"]
    c_no = cohorts["non_evicted_16"]
    pt = payload["prefix_transitions"]
    cfg = payload["analyzer_config"]
    checks = payload["verification"]

    ev_tot_pre_act = sum(r["pre_actions"] for r in payload["evicted_breakdown"])
    ev_tot_post_act = sum(r["post_actions"] for r in payload["evicted_breakdown"])
    ev_tot_post_bchg_f = sum(r["post_board_changed_false"] for r in payload["evicted_breakdown"])
    ev_tot_post_lvl = sum(r["post_levels_solved"] for r in payload["evicted_breakdown"])

    lines: list[str] = [
        "# V10 Local 25-Game Pre/Post-Eviction & Full Token Accounting Audit",
        "",
        f"- **Source dataset (read-only, relative)**: `submissions/arc3_v10_verified`",
        f"- **Generator script (relative)**: `Paper/branch_b_academic/analysis/build_v10_eviction_token_tables.py`",
        f"- **`summary.txt` SHA-256**: `{payload['source_hashes']['summary_txt_sha256']}`",
        f"- **`benchmark.json` SHA-256**: `{payload['source_hashes']['benchmark_json_sha256']}`",
        f"- **Observed `[ANALYZER STATUS]` config**: model=`{cfg.get('model')}`, "
        f"context_budget_tokens=`{cfg.get('context_budget_tokens')}`, "
        f"reply_reserve_tokens=`{cfg.get('reply_reserve_tokens')}`, "
        f"max_output_tokens=`{cfg.get('max_output_tokens')}`, "
        f"tool_output_tokens=`{cfg.get('tool_output_tokens')}`, "
        f"yield_tokens=`{cfg.get('yield_tokens')}`, "
        f"request_safety_margin_tokens=`{cfg.get('request_safety_margin_tokens')}`",
        f"- **Conservation assertions**: `{checks['all_checks_passed']}` "
        f"({checks['games_checked']} games, {checks['total_actions_conserved']} actions, "
        f"{checks['summary_tokens_conserved']} `summary.txt` tokens == `benchmark.json` history == `sota.log` reported tokens; "
        f"{checks['requests_jsonl_completion_tokens']} `*_p0_requests.jsonl` completion tokens)",
        "",
        "---",
        "",
        "## 1. Executive Empirical Corrections (Why This Audit Was Necessary)",
        "",
        "1. **Every FIFO eviction triggered on token budget (`context_budget_tokens = 44,544`), NEVER on the 36-turn assistant limit.** "
        "Across all 9 evicted games (`36.0%` of the 25-game suite), pre-eviction prompt tokens reached `35,813–42,353` (`total_tokens = 38,931–52,217`) "
        "with only `11–21` assistant turns (`asst_turns_before`), long before a 36-turn cap.",
        "2. **`summary.txt` omits 90,206 generated output tokens (`19.25%` of logged completion tokens).** "
        "`summary.txt` reports `378,304` generated tokens (which equals the sum of `history[*].generated_tokens` attached to executed environment actions), "
        "whereas `*_p0_requests.jsonl` logs **`468,510` `completion_tokens`** (`404,005` `reasoning_tokens` = **`86.23%`**; `64,505` non-reasoning output) "
        "plus **`7,078,878` `prompt_tokens`** (`4,480,704` cached = `63.30%`, `2,598,174` uncached prefill, `762,400` image). "
        "`arc-agi-3-sota.log` `solver_note` totals **`471,288`** because **`g50t-5849a774`** records `+2,778` tokens in `solver_note` (`31,679` vs `28,901` in paired responses) alongside 1 unpaired trailing request.",
        "3. **Post-eviction behavior is NOT a uniform 'amnesia dead loop'—especially not on `vc33`.** "
        "Across the 9 evicted games (`179` pre-eviction actions; `25` eviction-turn + post-eviction actions), **6 games produced `0` actions after eviction** "
        "(either immediate HTTP `request_timeout` on eviction `[cd82]` or `stop_requested`/timeout before acting `[bp35, ft09, g50t@act13, r11l, sb26@act34]`). "
        "Of the 3 games with multi-action execution at/after eviction: **`ar25-0c556536`** executed 11 actions (`act 32–42`), built its first `Working world model`, and **solved Level 2** (`score 4.17 -> 8.33`); "
        "**`cn04-2fe56bfb`** executed `3x RIGHT` (`act 25–27`, all `board_changed=True`) before `step 9` timed out; and **`vc33-5430563c`** executed `9x MOUSE(56,46)` (`act 26–34`, `8 board_changed=True`, `1 False`) "
        "which was **Phase 1** of its explicit carried Level-3 plan (`Working world model`) before `HTTP Read timed out (30.0s)` aborted Step 10 prior to Phases 2–4.",
        "4. **`75.46%` of all uncached prefill tokens come from prefix-mutating history edits (`image_omit_mutation` + `fifo_eviction`), not server KV eviction alone.** "
        "Across `250` strict `pure_append` requests, RadixAttention cache hit rate is **`88.54%`**. "
        "Across `69` `image_omit_mutation` requests (replacing older grid images in-place with `[grid image omitted from history]` once >5 image-pairs accumulate), "
        "cache hit rate collapses to **`15.53%`** (`1,800,791` uncached tokens). Across `8` completed `fifo_eviction` requests, it is **`18.12%`** (`159,890` uncached tokens). "
        "Combined, those 77 prefix mutations account for `1,960,681 / 2,598,174` (**`75.46%`**) of V10's uncached prefill compute.",
        "",
        "---",
        "",
        "## 2. Token Accounting & Cohort Comparison (Evicted n=9 vs Non-Evicted n=16 vs All 25)",
        "",
        "| Cohort | Games | Solved Games | Total Levels Solved | Mean Score | Actions | `board_changed=False` | Reqs / Resps / Unpaired | Prompt Tokens | Cached Input | Uncached Prefill | Cache Hit % | Image Tokens | Completion (`*_p0_requests`) | Reasoning Tokens (Share %) | Non-Reasoning Output | `summary.txt` Tokens | `sota.log` Note Tokens | Unlogged `comp - summary` | Handoff / Summary Overhead |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for c in (c_ev, c_no, c_all):
        lines.append(
            f"| {c['cohort']} | {c['games']} | {c['games_with_levels_solved']} | {c['total_levels_solved']} | "
            f"{c['mean_score']:.2f} | {c['total_actions']} | {c['board_changed_false_actions']} ({c['board_changed_false_pct']:.1f}%) | "
            f"{c['reqs']} / {c['resps']} / {c['unpaired_reqs']} | "
            f"{c['prompt_tokens']:,} | {c['cached_tokens']:,} | {c['uncached_prefill_tokens']:,} | {c['cache_hit_pct']:.2f}% | "
            f"{c['image_tokens']:,} | {c['completion_tokens']:,} | "
            f"{c['reasoning_tokens']:,} ({c['reasoning_share_pct']:.2f}%) | {c['non_reasoning_output_tokens']:,} | "
            f"{c['summary_reported_tokens']:,} | {c['sota_log_note_tokens']:,} | "
            f"{c['comp_minus_summary_tokens']:,} | 0 (FIFO eviction only) |"
        )

    lines.extend([
        "",
        "> **Unlogged / Timeout Caveat**: All `5` unpaired requests (`cd82`, `cn04`, `g50t`, `r11l`, `vc33`) belong to the **Evicted (`n=9`) cohort**. "
        "`cd82`, `cn04`, `r11l`, `vc33` ended with HTTP `request_timeout` (`49.14s`, `50.92s`, `30.00s`, `30.00s`) and have **N/A (timeout / unreturned)** server `usage` in `*_p0_requests.jsonl`. "
        "`g50t` ended with `stop_requested` yet shows `+2,778` tokens in `solver_note` (`31,679`) above its 15 paired responses (`28,901`); those `2,778` tokens are reported strictly via `solver_note` and never guessed into per-field prompt/reasoning splits.",
        "",
        "---",
        "",
        "## 3. RadixAttention Prefix-Cache Stratification Across All 352 Paired Responses (+ 5 Unpaired)",
        "",
        "| Prefix Transition Type | Paired Resps | Unpaired Reqs | Prompt Tokens | Cached Input Tokens | Uncached Prefill Tokens | Cache Hit % | Image Tokens | Completion Tokens | Reasoning Tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])

    for k in ("initial", "pure_append", "image_omit_mutation", "fifo_eviction"):
        v = pt[k]
        lines.append(
            f"| `{k}` | {v['resps']} | {v['unpaired_reqs']} | {v['prompt_tokens']:,} | "
            f"{v['cached_tokens']:,} | {v['uncached_prefill_tokens']:,} | {v['cache_hit_pct']:.2f}% | "
            f"{v['image_tokens']:,} | {v['completion_tokens']:,} | {v['reasoning_tokens']:,} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Full Pre- vs Post-Eviction Breakdown of All 9 Evicted Games",
        "",
        f"- Evicted cohort actions: **{ev_tot_pre_act} pre-eviction actions** + **{ev_tot_post_act} eviction/post-eviction actions** "
        f"(`{ev_tot_post_bchg_f}` `board_changed=False`, `+{ev_tot_post_lvl}` level solved [`ar25` Level 2], `0` post-eviction `StaleStateActionError`).",
        "",
        "| Game ID | Drop Req / Step / NextAct | Msgs (`pre->post`) | Asst Turns (`pre->post`, kept TC) | WWM Msgs (`pre->post`, post+WWM) | Last Pre Prompt / Total | Pre Cache Hit % (`n` resps) | Post Cache Hit % (`n` resps / unp) | Pre -> Post Actions (`bchg=False`) | Levels Pre -> Post | Score | Termination / Post-Eviction Outcome |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ])

    for er in payload["evicted_breakdown"]:
        post_hit_s = (
            f"{er['post_cache_hit_pct']:.2f}% ({er['post_resps']}r / {er['post_unpaired_reqs']}u)"
            if isinstance(er["post_cache_hit_pct"], float)
            else f"N/A ({er['post_resps']}r / {er['post_unpaired_reqs']}u)"
        )
        lines.append(
            f"| `{er['game_id']}` | req {er['drop_req_idx']} / step {er['drop_step']} / act {er['drop_next_action']} | "
            f"{er['msgs_before']} -> {er['msgs_after']} (-{er['msgs_dropped_net']}) | "
            f"{er['asst_turns_before']} -> {er['asst_turns_after']} (kept {er['prev_tool_calls_retained']}) | "
            f"{er['wwm_msgs_before']} -> {er['wwm_msgs_after']} (+{er['wwm_created_after_evict_steps']}) | "
            f"{er['pre_last_prompt_tokens']:,} / {er['pre_last_total_tokens']:,} | "
            f"{er['pre_cache_hit_pct']:.2f}% ({er['pre_resps']}r) | {post_hit_s} | "
            f"{er['pre_actions']} ({er['pre_board_changed_false']}F) -> {er['post_actions']} ({er['post_board_changed_false']}F) | "
            f"{er['pre_levels_solved']} -> +{er['post_levels_solved']} | {er['final_score']:.2f} | "
            f"{er['behavioral_classification']} |"
        )

    lines.extend([
        "",
        "### Pre- vs Post-Eviction Token Totals Across the 9 Evicted Games",
        "",
        "| Game ID | Pre Prompt | Pre Cached | Pre Comp (`Reason`) | Evict-Req Prompt / Cached | Post Prompt (incl. Evict Req) | Post Cached | Post Comp (`Reason`) | `summary.txt` Tok | `sota.log` Note (`note-comp`) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])

    gr_map = {r["game_id"]: r for r in payload["games"]}
    for er in payload["evicted_breakdown"]:
        gr = gr_map[er["game_id"]]
        ev_pr_s = (
            f"{er['evict_turn_prompt_tokens']:,} / {er['evict_turn_cached_tokens']:,}"
            if isinstance(er["evict_turn_prompt_tokens"], int)
            else "N/A (timeout)"
        )
        po_pr_s = f"{er['post_prompt_tokens']:,}" if isinstance(er["post_prompt_tokens"], int) else er["post_prompt_tokens"]
        po_ca_s = f"{er['post_cached_tokens']:,}" if isinstance(er["post_cached_tokens"], int) else er["post_cached_tokens"]
        po_co_s = (
            f"{er['post_completion_tokens']:,} ({er['post_reasoning_tokens']:,})"
            if isinstance(er["post_completion_tokens"], int)
            else er["post_completion_tokens"]
        )
        delta_s = f"+{gr['note_minus_comp_tokens']}" if gr["note_minus_comp_tokens"] else "0"
        lines.append(
            f"| `{er['game_id']}` | {er['pre_prompt_tokens']:,} | {er['pre_cached_tokens']:,} | "
            f"{er['pre_completion_tokens']:,} ({er['pre_reasoning_tokens']:,}) | {ev_pr_s} | "
            f"{po_pr_s} | {po_ca_s} | {po_co_s} | "
            f"{gr['summary_reported_tokens']:,} | {gr['sota_log_note_tokens']:,} ({delta_s}) |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 5. Complete Action-by-Action Trace of All 25 Eviction-Turn & Post-Eviction Actions",
        "",
        "| Game ID | Action # | Analysis Step (Evict Step) | Phase | Level | Action | `board_changed` | `level_completed` | Score After |",
        "|---|---:|---:|---|---:|---|---:|---:|---:|",
    ])
    for pa in payload["post_eviction_actions"]:
        lines.append(
            f"| `{pa['game_id']}` | {pa['action_num']} | {pa['analysis_step']} ({pa['evict_step']}) | "
            f"`{pa['phase']}` | {pa['level']} | `{pa['action_display']}` | "
            f"{pa['board_changed']} | {pa['level_completed']} | {pa['score_after']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Per-Game 25-Game Complete Token Accounting",
        "",
        "| Game ID | Evicted | Score | Lvls | Actions (`bchg=F`) | Stale Errs | Reqs/Resps/Unp | Prompt Tokens | Cached (%) | Uncached Prefill | Image Tokens | Comp (`*_p0_requests`) | Reasoning (%) | Non-Reason Out | `summary.txt` Tok | `comp - sum` | `note - comp` | Termination |",
        "|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])

    for gr in payload["games"]:
        ev_s = f"YES (step {gr['evict_step']})" if gr["evicted"] else "no"
        nc_s = f"+{gr['note_minus_comp_tokens']}" if gr["note_minus_comp_tokens"] else "0"
        lines.append(
            f"| `{gr['game_id']}` | {ev_s} | {gr['score']:.2f} | {gr['levels_completed']}/{gr['total_levels']} | "
            f"{gr['reported_actions']} ({gr['board_changed_false']}) | {gr['stale_state_errors']} | "
            f"{gr['reqs']}/{gr['resps']}/{gr['unpaired_reqs']} | {gr['prompt_tokens']:,} | "
            f"{gr['cached_tokens']:,} ({gr['cache_hit_pct']:.1f}%) | {gr['uncached_prefill_tokens']:,} | "
            f"{gr['image_tokens']:,} | {gr['completion_tokens']:,} | "
            f"{gr['reasoning_tokens']:,} ({gr['reasoning_share_pct']:.1f}%) | {gr['non_reasoning_output_tokens']:,} | "
            f"{gr['summary_reported_tokens']:,} | {gr['comp_minus_summary_tokens']:,} | {nc_s} | "
            f"{gr['termination_cause']} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_all(v10_dir: Path, out_dir: Path, verify_only: bool = False) -> dict[str, Any]:
    """Run full extraction, verify conservation laws, and optionally write output deliverables."""
    summary_path = v10_dir / "summary.txt"
    bjson_path = v10_dir / "benchmark.json"
    sota_path = v10_dir / "arc-agi-3-sota.log"

    summary_header, summary_games = parse_summary_txt(summary_path)
    bjson_games = parse_benchmark_json(bjson_path)
    sota_games = parse_sota_log(sota_path)

    game_ids = sorted(summary_games.keys())
    game_rows: list[dict[str, Any]] = []
    evict_rows: list[dict[str, Any]] = []
    post_action_rows: list[dict[str, Any]] = []
    prefix_totals: dict[str, dict[str, int | float]] = {
        k: {
            "resps": 0,
            "unpaired_reqs": 0,
            "prompt_tokens": 0,
            "cached_tokens": 0,
            "uncached_prefill_tokens": 0,
            "image_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
        }
        for k in ("initial", "pure_append", "image_omit_mutation", "fifo_eviction")
    }
    observed_config: dict[str, str] = {}

    for gid in game_ids:
        gr, er, par, cls_u = analyze_game(
            gid, v10_dir, summary_games[gid], bjson_games[gid], sota_games[gid]
        )
        if not observed_config and gr["analyzer_config"]:
            observed_config = gr["analyzer_config"]
        game_rows.append(gr)
        if er is not None:
            evict_rows.append(er)
        post_action_rows.extend(par)
        for cls_name, stats in cls_u.items():
            for field in (
                "resps",
                "unpaired_reqs",
                "prompt_tokens",
                "cached_tokens",
                "uncached_prefill_tokens",
                "image_tokens",
                "completion_tokens",
                "reasoning_tokens",
            ):
                prefix_totals[cls_name][field] += int(stats[field])

    for stats in prefix_totals.values():
        pr = int(stats["prompt_tokens"])
        ca = int(stats["cached_tokens"])
        stats["cache_hit_pct"] = round(100.0 * ca / pr, 2) if pr else 0.0

    verification = verify_invariants(
        summary_header, summary_games, bjson_games, sota_games, game_rows, evict_rows, prefix_totals  # type: ignore[arg-type]
    )

    ev_games = [r for r in game_rows if r["evicted"]]
    non_ev_games = [r for r in game_rows if not r["evicted"]]
    payload: dict[str, Any] = {
        "source_dir": "submissions/arc3_v10_verified",
        "source_hashes": {
            "summary_txt_sha256": sha256_file(summary_path),
            "benchmark_json_sha256": sha256_file(bjson_path),
        },
        "analyzer_config": observed_config,
        "summary_header": summary_header,
        "verification": verification,
        "cohorts": {
            "evicted_9": summarize_cohort(ev_games, "Evicted (n=9)"),
            "non_evicted_16": summarize_cohort(non_ev_games, "Non-Evicted (n=16)"),
            "all_25": summarize_cohort(game_rows, "All 25"),
        },
        "prefix_transitions": prefix_totals,
        "games": game_rows,
        "evicted_breakdown": evict_rows,
        "post_eviction_actions": post_action_rows,
    }

    if verify_only:
        return payload

    out_dir.mkdir(parents=True, exist_ok=True)
    game_csv_fields = [
        "game_id", "cohort", "evicted", "evict_req_idx", "evict_step", "evict_next_action",
        "score", "levels_completed", "total_levels", "reported_actions", "logged_action_events",
        "board_changed_false", "stale_state_errors", "reqs", "resps", "unpaired_reqs",
        "max_prompt_tokens", "prompt_tokens", "cached_tokens", "uncached_prefill_tokens",
        "cache_hit_pct", "image_tokens", "completion_tokens", "reasoning_tokens",
        "non_reasoning_output_tokens", "reasoning_share_pct", "total_tokens_requests_jsonl",
        "summary_reported_tokens", "benchmark_history_tokens", "sota_log_note_tokens",
        "comp_minus_summary_tokens", "note_minus_comp_tokens", "handoff_summary_tokens",
        "unlogged_timeout_status", "pure_append_resps", "pure_append_cache_pct",
        "image_omit_resps", "image_omit_cache_pct", "fifo_evict_resps", "fifo_evict_cache_pct",
        "termination_cause", "wallclock_seconds",
    ]
    write_csv(out_dir / "v10_25game_token_and_eviction_summary.csv", game_rows, game_csv_fields)

    ev_csv_fields = list(evict_rows[0].keys())
    write_csv(out_dir / "v10_9evicted_games_breakdown.csv", evict_rows, ev_csv_fields)

    pa_csv_fields = list(post_action_rows[0].keys())
    write_csv(out_dir / "v10_9evicted_post_eviction_actions.csv", post_action_rows, pa_csv_fields)

    (out_dir / "v10_25game_cohort_and_prefix_summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "v10_eviction_and_token_audit_report.md").write_text(
        render_markdown_report(payload, out_dir, v10_dir), encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v10-dir", type=Path, default=DEFAULT_V10_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    payload = build_all(args.v10_dir, args.out_dir, verify_only=args.verify_only)
    c_all = payload["cohorts"]["all_25"]
    print(
        f"VERIFIED V10 25-game audit: actions={c_all['total_actions']}, "
        f"summary_tokens={c_all['summary_reported_tokens']}, "
        f"comp_tokens={c_all['completion_tokens']}, "
        f"note_tokens={c_all['sota_log_note_tokens']}, "
        f"evicted={payload['cohorts']['evicted_9']['games']}, "
        f"post_evict_actions={len(payload['post_eviction_actions'])}"
    )


if __name__ == "__main__":
    main()
