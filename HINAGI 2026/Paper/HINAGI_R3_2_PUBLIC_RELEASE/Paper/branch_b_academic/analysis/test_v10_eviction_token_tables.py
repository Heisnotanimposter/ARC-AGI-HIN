#!/usr/bin/env python3
"""Unit tests and conservation checks for build_v10_eviction_token_tables.py."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from build_v10_eviction_token_tables import DEFAULT_OUT_DIR, DEFAULT_V10_DIR, build_all


class TestV10EvictionTokenTables(unittest.TestCase):
    """Verify exact numerical conservation and non-fabrication across generated deliverables."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_all(DEFAULT_V10_DIR, DEFAULT_OUT_DIR, verify_only=True)

    def test_conservation_and_cohorts(self) -> None:
        self.assertTrue(self.payload["verification"]["all_checks_passed"])
        cohorts = self.payload["cohorts"]
        self.assertEqual(cohorts["evicted_9"]["games"], 9)
        self.assertEqual(cohorts["non_evicted_16"]["games"], 16)
        self.assertEqual(cohorts["all_25"]["games"], 25)
        self.assertEqual(cohorts["all_25"]["total_actions"], 386)
        self.assertEqual(cohorts["all_25"]["summary_reported_tokens"], 378304)
        self.assertEqual(cohorts["all_25"]["completion_tokens"], 468510)
        self.assertEqual(cohorts["all_25"]["sota_log_note_tokens"], 471288)
        self.assertEqual(cohorts["evicted_9"]["unpaired_reqs"], 5)
        self.assertEqual(cohorts["non_evicted_16"]["unpaired_reqs"], 0)

    def test_cd82_and_g50t_non_fabrication(self) -> None:
        ev_by_id = {r["game_id"]: r for r in self.payload["evicted_breakdown"]}
        cd82 = ev_by_id["cd82-fb555c5d"]
        self.assertEqual(cd82["post_resps"], 0)
        self.assertEqual(cd82["post_prompt_tokens"], "N/A (0 resps)")
        self.assertEqual(cd82["post_completion_tokens"], "N/A (0 resps)")

        g_by_id = {r["game_id"]: r for r in self.payload["games"]}
        g50t = g_by_id["g50t-5849a774"]
        self.assertEqual(g50t["completion_tokens"], 28901)
        self.assertEqual(g50t["sota_log_note_tokens"], 31679)
        self.assertEqual(g50t["note_minus_comp_tokens"], 2778)

    def test_vc33_post_eviction_facts(self) -> None:
        ev_by_id = {r["game_id"]: r for r in self.payload["evicted_breakdown"]}
        vc33 = ev_by_id["vc33-5430563c"]
        self.assertEqual(vc33["pre_actions"], 25)
        self.assertEqual(vc33["post_actions"], 9)
        self.assertEqual(vc33["post_board_changed_false"], 1)
        self.assertIn("Phase 1", vc33["behavioral_classification"])
        self.assertIn("request_timeout", vc33["termination_cause"])

    def test_generated_files_match_payload(self) -> None:
        json_path = DEFAULT_OUT_DIR / "v10_25game_cohort_and_prefix_summary.json"
        csv_25 = DEFAULT_OUT_DIR / "v10_25game_token_and_eviction_summary.csv"
        csv_9 = DEFAULT_OUT_DIR / "v10_9evicted_games_breakdown.csv"
        csv_pa = DEFAULT_OUT_DIR / "v10_9evicted_post_eviction_actions.csv"
        md_path = DEFAULT_OUT_DIR / "v10_eviction_and_token_audit_report.md"

        for p in (json_path, csv_25, csv_9, csv_pa, md_path):
            self.assertTrue(p.exists(), f"Missing generated output: {p}")

        disk_json = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(disk_json["cohorts"], self.payload["cohorts"])

        with csv_25.open(encoding="utf-8") as fh:
            rows_25 = list(csv.DictReader(fh))
        with csv_9.open(encoding="utf-8") as fh:
            rows_9 = list(csv.DictReader(fh))
        with csv_pa.open(encoding="utf-8") as fh:
            rows_pa = list(csv.DictReader(fh))

        self.assertEqual(len(rows_25), 25)
        self.assertEqual(len(rows_9), 9)
        self.assertEqual(len(rows_pa), 25)


if __name__ == "__main__":
    unittest.main()
