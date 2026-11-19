#!/usr/bin/env python3
"""Verify V12 Identity A statistical & structural addenda (GA-09, GA-10, GA-11) live from raw R1 files."""

from __future__ import annotations

import csv
import json
import os
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = Path(os.environ.get("R1_PACKAGE_ROOT", str(HERE.parents[3])))
REC_OUT_DIR = Path(os.environ.get("R1_REC_OUT_DIR", str(PKG_ROOT / "replay_out/v10_forensic_reconciliation")))


def quantile_linear(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def main() -> None:
    v6 = {
        r["game_id"]: r
        for r in json.loads((PKG_ROOT / "submissions/arc3_v6_smoke_verified/benchmark.json").read_text(encoding="utf-8"))["game_runs"]
    }
    v10 = {
        r["game_id"]: r
        for r in json.loads((PKG_ROOT / "submissions/arc3_v10_verified/benchmark.json").read_text(encoding="utf-8"))["game_runs"]
    }
    with (REC_OUT_DIR / "03_TOKEN_ACCOUNTING_RECONCILIATION.csv").open(encoding="utf-8") as fh:
        tok_games = {r["game_id"]: r for r in csv.DictReader(fh) if r["row_kind"] == "game"}
    with (REC_OUT_DIR / "02_REQUEST_RESPONSE_RECONSTRUCTION.csv").open(encoding="utf-8") as fh:
        req_rows = list(csv.DictReader(fh))

    # 1. GA-09: Matched-10 (games where V6 had >0 logged actions)
    matched10 = sorted(gid for gid, r in v6.items() if len(r["history"]) > 0)
    assert len(matched10) == 10
    v6_m10_sum = round(sum(float(v6[g]["final_score"]) for g in matched10), 4)
    v10_m10_sum = round(sum(float(v10[g]["final_score"]) for g in matched10), 4)
    v6_m10_acts = sum(len(v6[g]["history"]) for g in matched10)
    v10_m10_acts = sum(len(v10[g]["history"]) for g in matched10)
    wins = sum(1 for g in matched10 if float(v10[g]["final_score"]) > float(v6[g]["final_score"]) + 1e-9)
    losses = [g for g in matched10 if float(v10[g]["final_score"]) < float(v6[g]["final_score"]) - 1e-9]
    ties = sum(1 for g in matched10 if abs(float(v10[g]["final_score"]) - float(v6[g]["final_score"])) <= 1e-9)
    non_ev_losses = sum(1 for g in losses if tok_games[g]["is_evicted"] == "False")

    assert v6_m10_sum == 49.8413, v6_m10_sum
    assert v10_m10_sum == 16.9692, v10_m10_sum
    assert v6_m10_acts == 270 and v10_m10_acts == 131
    assert (wins, len(losses), ties) == (0, 6, 4)
    assert non_ev_losses == 5
    rel_drop_pct = round(100.0 * (v10_m10_sum - v6_m10_sum) / v6_m10_sum, 2)
    assert rel_drop_pct == -65.95, rel_drop_pct

    # 2. GA-10: Right-censoring on trailing completion tokens
    censored_gids = sorted(gid for gid, r in tok_games.items() if int(r["timeout_requests"]) > 0)
    assert censored_gids == ["cd82-fb555c5d", "cn04-2fe56bfb", "r11l-495a7899", "vc33-5430563c"]
    unc_ev = sorted(int(r["trailing_post_action_comp_353"]) for r in tok_games.values() if r["is_evicted"] == "True" and int(r["timeout_requests"]) == 0)
    unc_non = sorted(int(r["trailing_post_action_comp_353"]) for r in tok_games.values() if r["is_evicted"] == "False" and int(r["timeout_requests"]) == 0)
    assert len(unc_ev) == 5 and len(unc_non) == 16
    assert round(sum(unc_ev) / len(unc_ev), 2) == 3185.40
    assert statistics.median(unc_ev) == 1247
    assert round(sum(unc_non) / len(unc_non), 2) == 3974.81
    assert statistics.median(unc_non) == 3450.0
    assert sum(unc_non) == 63597

    # 3. GA-11: Skew, zero-inflation, ft09 concentration, and game-clustered KV metrics
    v10_scores = sorted(float(r["final_score"]) for r in v10.values())
    v10_sum = round(sum(v10_scores), 4)
    v10_mean = round(v10_sum / 25.0, 4)
    ft09_score = float(v10["ft09-0d8bbf25"]["final_score"])
    ft09_share_pct = round(100.0 * ft09_score / sum(v10_scores), 2)
    v10_zeros = sum(1 for s in v10_scores if s == 0.0)
    v10_wins = sum(1 for r in v10.values() if int(r["levels_completed"]) >= int(r["number_of_levels"]))
    assert v10_sum == 70.9375 and v10_mean == 2.8375
    assert ft09_share_pct == 40.28
    assert v10_zeros == 16 and v10_wins == 0
    assert statistics.median(v10_scores) == 0.0

    # Cluster-level KV categories over 352 paired responses vs 353 delivered responses
    by_class_353: dict[str, dict[str, object]] = {}
    for row in req_rows:
        if row["response_logged"] != "True":
            continue
        cls = row["prefix_transition"]
        bucket = by_class_353.setdefault(cls, {"n_resps": 0, "games": set(), "zero_hits": 0, "prompt": 0, "cached": 0})
        bucket["n_resps"] += 1  # type: ignore[operator]
        bucket["games"].add(row["game_id"])  # type: ignore[union-attr]
        ca = int(row["cached_tokens"])
        pt = int(row["prompt_tokens"])
        if ca == 0:
            bucket["zero_hits"] += 1  # type: ignore[operator]
        bucket["prompt"] += pt  # type: ignore[operator]
        bucket["cached"] += ca  # type: ignore[operator]

    kv_summary = {
        k: {
            "n_requests": v["n_resps"],
            "N_games": len(v["games"]),  # type: ignore[arg-type]
            "zero_cache_hits": v["zero_hits"],
            "pooled_cache_pct": round(100.0 * int(v["cached"]) / int(v["prompt"]), 2),  # type: ignore[arg-type]
        }
        for k, v in sorted(by_class_353.items())
    }
    assert kv_summary["fifo_eviction"]["n_requests"] == 8
    assert kv_summary["fifo_eviction"]["N_games"] == 8
    assert kv_summary["pure_append"]["n_requests"] == 251  # 250 per-game + 1 detached g50t root response
    assert kv_summary["image_omit_mutation"]["n_requests"] == 69
    assert kv_summary["initial"]["n_requests"] == 25
    assert sum(v["n_requests"] for v in kv_summary.values()) == 353

    report = {
        "matched_10": {
            "N_games": 10,
            "v6_sum": v6_m10_sum,
            "v10_sum": v10_m10_sum,
            "w_l_t_v10_vs_v6": [wins, len(losses), ties],
            "v10_losses_non_evicted": non_ev_losses,
            "rel_change_pct": rel_drop_pct,
        },
        "right_censoring_trailing_tokens": {
            "censored_games_N": 4,
            "censored_games": censored_gids,
            "uncensored_evicted_N": len(unc_ev),
            "uncensored_evicted_mean": 3185.40,
            "uncensored_evicted_median": 1247,
            "uncensored_non_evicted_N": len(unc_non),
            "uncensored_non_evicted_mean": 3974.81,
            "uncensored_non_evicted_median": 3450.0,
        },
        "v10_distribution": {
            "N_games": 25,
            "sum": v10_sum,
            "mean": v10_mean,
            "sd_sample": round(statistics.stdev(v10_scores), 4),
            "median": statistics.median(v10_scores),
            "iqr_linear": round(quantile_linear(v10_scores, 0.75) - quantile_linear(v10_scores, 0.25), 4),
            "zeros": v10_zeros,
            "full_wins": v10_wins,
            "ft09_share_pct": ft09_share_pct,
        },
        "kv_clusters_353": kv_summary,
    }
    out = REC_OUT_DIR / "r1_statistical_addenda_check.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("ALL STATISTICAL ADDENDA CHECKS (GA-09/GA-10/GA-11) PASSED:", json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
