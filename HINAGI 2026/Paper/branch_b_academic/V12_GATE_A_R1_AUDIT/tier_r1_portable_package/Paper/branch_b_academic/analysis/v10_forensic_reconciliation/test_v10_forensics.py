#!/usr/bin/env python3
"""Portable unit tests verifying Tier R1 V10 forensic reconstruction and canonical parity."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = Path(os.environ.get("R1_PACKAGE_ROOT", str(HERE.parents[3])))
OUT_DIR = Path(os.environ.get("R1_REC_OUT_DIR", str(PKG_ROOT / "replay_out/v10_forensic_reconciliation")))
AN_OUT_DIR = Path(os.environ.get("R1_AN_OUT_DIR", str(PKG_ROOT / "replay_out/analysis")))
EXP_DIR = PKG_ROOT / "expected_canonical"
REF_DOCS_DIR = HERE / "reference_docs"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestTierR1V10Forensics(unittest.TestCase):
    inv_rows: list[dict[str, str]]
    req_rows: list[dict[str, str]]
    tok_rows: list[dict[str, str]]
    manifest: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        with (OUT_DIR / "01_ARTIFACT_INVENTORY.csv").open(encoding="utf-8") as fh:
            cls.inv_rows = list(csv.DictReader(fh))
        with (OUT_DIR / "02_REQUEST_RESPONSE_RECONSTRUCTION.csv").open(encoding="utf-8") as fh:
            cls.req_rows = list(csv.DictReader(fh))
        with (OUT_DIR / "03_TOKEN_ACCOUNTING_RECONCILIATION.csv").open(encoding="utf-8") as fh:
            cls.tok_rows = list(csv.DictReader(fh))
        cls.manifest = json.loads((OUT_DIR / "08_REPRODUCIBILITY_MANIFEST.json").read_text(encoding="utf-8"))

    def test_01_r1_outputs_and_reference_docs_exist(self) -> None:
        expected_out = [
            "01_ARTIFACT_INVENTORY.csv",
            "02_REQUEST_RESPONSE_RECONSTRUCTION.csv",
            "03_TOKEN_ACCOUNTING_RECONCILIATION.csv",
            "08_REPRODUCIBILITY_MANIFEST.json",
            "12_INDEPENDENT_ARITHMETIC_RESULTS.json",
        ]
        for fn in expected_out[:-1]:
            p = OUT_DIR / fn
            self.assertTrue(p.exists(), f"Missing generated deliverable: {p}")
            self.assertGreater(p.stat().st_size, 0)
        for fn in [
            "00_EXECUTIVE_FINDINGS.md",
            "04_FOUR_UNMATCHED_REQUESTS.md",
            "05_EVICTION_PREFIX_CACHE_REPRODUCTION.md",
            "06_SOURCE_CODE_TRACE.md",
            "07_MANUSCRIPT_CHANGE_RECOMMENDATIONS.md",
            "09_TEST_RESULTS.md",
            "13_FORENSIC_ERRATA.md",
        ]:
            self.assertTrue((REF_DOCS_DIR / fn).exists(), f"Missing reference doc: {fn}")

    def test_02_r1_scoped_inventory_and_excluded_binary_transparency(self) -> None:
        bundled = [r for r in self.inv_rows if r["scope"].startswith("v10_r1_bundled_")]
        excluded = [r for r in self.inv_rows if r["scope"].startswith("v10_excluded_in_r1_")]
        self.assertEqual(len(bundled), 81)
        self.assertEqual(len(excluded), 131)
        self.assertEqual(len(bundled) + len(excluded), 212)

        meta = json.loads((PKG_ROOT / "excluded_artifacts_metadata.json").read_text(encoding="utf-8"))
        san_v10 = meta["sanitized_files"]["submissions/arc3_v10_verified/arc-agi-3-sota.log"]
        sota_row = next(r for r in bundled if r["relative_path"] == "submissions/arc3_v10_verified/arc-agi-3-sota.log")
        self.assertEqual(sota_row["sha256"], san_v10["sanitized_sha256"])
        self.assertNotEqual(sota_row["sha256"], san_v10["raw_sha256"])

        # Verify excluded files genuinely do NOT exist in Tier R1 bundle
        for r in excluded:
            self.assertFalse((PKG_ROOT / r["relative_path"]).exists(), f"Excluded binary leaked into R1: {r['relative_path']}")

        # Verify comparator hashes present in R1
        by_path = {r["relative_path"]: r for r in self.inv_rows}
        self.assertEqual(
            by_path["artifacts/phase6_5/reference_snapshots/v6_reference.ipynb"]["sha256"],
            "bb532e8c502ac5ce72c36918a2b1ac90e0de3cc96f5bdc70682953914466c90e",
        )
        self.assertEqual(
            by_path["artifacts/phase6_5/reference_snapshots/v10_reference.ipynb"]["sha256"],
            "5f940b9615dee4ab337c564e465fb1701635cdd842b66bbeacc83372e71c5b3b",
        )
        self.assertEqual(
            by_path["reference/arc3_franzen_m2/ARC3-Inference/inference/agent/tool_agent.py"]["sha256"],
            "053556f4a2d19bbb0f04d3ecde14bad2d76abfe91e89254740b763136a5a8e82",
        )
        self.assertEqual(
            by_path["reference/arc3_franzen_m2/ARC3-Inference/inference/framework/solver.py"]["sha256"],
            "42b4794f0447e071ba118194c64d009f7fa59df0b84f3d9c35da4dd215824c52",
        )

    def test_03_request_response_reconstruction_exact_closure(self) -> None:
        self.assertEqual(len(self.req_rows), 360)
        counts = Counter(r["row_type"] for r in self.req_rows)
        self.assertEqual(counts["client_request"], 357)
        self.assertEqual(
            counts["sglang_structured_output_warmup"]
            + counts["kaggle_notebook_http_warmup"]
            + counts["harness_health_check"],
            3,
        )

        resp_loc = Counter(r["response_location"] for r in self.req_rows)
        self.assertEqual(resp_loc["per_game_requests_jsonl"], 352)
        self.assertEqual(resp_loc["root_requests_jsonl"], 1)
        self.assertEqual(resp_loc["TIMEOUT_NO_RESPONSE"], 4)
        self.assertEqual(resp_loc["SERVE_LOG_ONLY"], 3)

        serve_rids = [r["serve_rid"] for r in self.req_rows]
        self.assertEqual(len(set(serve_rids)), 360)
        self.assertTrue(all(bool(rid) for rid in serve_rids))

        agent_rows = [r for r in self.req_rows if r["request_logged"] == "True"]
        self.assertEqual(len(agent_rows), 357)
        self.assertTrue(all(len(r["serve_rid"]) == 32 for r in agent_rows))
        self.assertEqual(sum(1 for r in agent_rows if r["response_logged"] == "True"), 353)
        self.assertEqual(sum(1 for r in agent_rows if r["response_logged"] == "False"), 4)

        for r in agent_rows:
            if r["response_logged"] == "True":
                diff = int(r["serve_output_len"]) - int(r["completion_tokens"])
                self.assertGreaterEqual(diff, 0)
                self.assertLessEqual(diff, 3)

        g50t = next(r for r in agent_rows if r["response_location"] == "root_requests_jsonl")
        self.assertEqual(g50t["game_id"], "g50t-5849a774")
        self.assertEqual(int(g50t["client_req_idx"]), 15)
        self.assertEqual(int(g50t["completion_tokens"]), 2778)
        self.assertEqual(g50t["missing_tool_call_ids"], "")

        timeouts = [r for r in agent_rows if r["serve_match_status"] == "SERVER_COMPLETED_AFTER_CLIENT_TIMEOUT"]
        self.assertEqual({r["game_id"] for r in timeouts}, {"cd82-fb555c5d", "cn04-2fe56bfb", "r11l-495a7899", "vc33-5430563c"})
        self.assertEqual(sum(int(r["serve_output_len"]) for r in timeouts), 7610)

        trans_353 = Counter(r["prefix_transition"] for r in agent_rows if r["response_logged"] == "True")
        self.assertEqual(trans_353, {"pure_append": 251, "image_omit_mutation": 69, "initial": 25, "fifo_eviction": 8})

    def test_04_token_accounting_conservation_and_eviction(self) -> None:
        games = [r for r in self.tok_rows if r["row_kind"] == "game"]
        self.assertEqual(len(games), 25)
        tot = next(r for r in self.tok_rows if r["row_kind"] == "total_all_25")
        ev9 = next(r for r in self.tok_rows if r["row_kind"] == "cohort_evicted_9")
        non16 = next(r for r in self.tok_rows if r["row_kind"] == "cohort_non_evicted_16")

        self.assertEqual(int(ev9["actions_executed"]) + int(non16["actions_executed"]), 386)
        self.assertEqual(int(tot["history_generated_tokens"]), 378304)
        self.assertEqual(int(tot["summary_txt_tokens"]), 378304)
        self.assertEqual(int(tot["action_attributed_comp_tokens"]), 378304)
        self.assertEqual(int(tot["comp_tokens_352"]), 468510)
        self.assertEqual(int(tot["comp_tokens_353"]), 471288)
        self.assertEqual(int(tot["solver_note_tokens"]), 471288)
        self.assertEqual(int(tot["trailing_post_action_comp_352"]), 90206)
        self.assertEqual(int(tot["trailing_post_action_comp_353"]), 92984)
        self.assertEqual(int(tot["diff_hist_vs_action_comp"]), 0)
        self.assertEqual(int(tot["diff_note_vs_comp353"]), 0)

        for r in games:
            self.assertEqual(int(r["history_uncached_input_tokens"]), 0)
            self.assertEqual(int(r["final_generated_tokens"]), 0)
            self.assertEqual(int(r["diff_hist_vs_action_comp"]), 0)
            self.assertEqual(int(r["diff_note_vs_comp353"]), 0)

        ev_games = [r for r in games if r["is_evicted"] == "True"]
        self.assertEqual(len(ev_games), 9)
        self.assertEqual(sum(int(r["events_action"]) for r in ev_games), 204)

    def test_05_manifest_and_canonical_csv_parity(self) -> None:
        self.assertEqual(self.manifest["reconciled_totals"]["live_calibration_matches"], "45/45")
        self.assertEqual(self.manifest["reconciled_totals"]["actions_executed"], 386)
        self.assertEqual(self.manifest["reconciled_totals"]["comp_tokens_353_exact_solver_note"], 471288)

        # Verify freshly regenerated CSVs match canonical reference byte-for-byte
        pairs = [
            (OUT_DIR / "02_REQUEST_RESPONSE_RECONSTRUCTION.csv", EXP_DIR / "02_REQUEST_RESPONSE_RECONSTRUCTION.csv"),
            (OUT_DIR / "03_TOKEN_ACCOUNTING_RECONCILIATION.csv", EXP_DIR / "03_TOKEN_ACCOUNTING_RECONCILIATION.csv"),
            (AN_OUT_DIR / "v10_25game_token_and_eviction_summary.csv", EXP_DIR / "v10_25game_token_and_eviction_summary.csv"),
            (AN_OUT_DIR / "v10_9evicted_games_breakdown.csv", EXP_DIR / "v10_9evicted_games_breakdown.csv"),
            (AN_OUT_DIR / "v10_9evicted_post_eviction_actions.csv", EXP_DIR / "v10_9evicted_post_eviction_actions.csv"),
        ]
        for regen, canonical in pairs:
            self.assertTrue(regen.exists(), f"Missing regenerated CSV: {regen}")
            self.assertEqual(
                _sha256(regen),
                _sha256(canonical),
                f"SHA-256 parity mismatch vs canonical baseline: {regen.name}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
