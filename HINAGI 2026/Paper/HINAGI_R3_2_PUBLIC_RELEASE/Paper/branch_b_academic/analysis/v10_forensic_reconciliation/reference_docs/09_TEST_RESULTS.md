# 09 — Verification & Test Execution Log

**Verification Scope:**  
1. Existing canonical test suite: `Paper/branch_b_academic/analysis/test_v10_eviction_token_tables.py` (`--verify-only` in memory, non-mutating).  
2. Full forensic reconstruction & conservation suite: `reconstruct_v10_forensics.py` (`45/45` live calibration replay, `360/360` `serve.log` matching, dual `352`/`353` accounting closure, `613` event type check, `9/9` FIFO pre-trim > `44,544` replay).  
3. Independent unit verification suite: `v10_forensic_reconciliation/test_v10_forensics.py` (`5` test classes verifying deliverable completeness, live canonical SHA-256 non-mutation, `02` request/response closure, `03` token conservation, and `08` manifest self-consistency).

---

## 1. Existing Analysis Test Suite Output (Observed)

```text
$ python3 -m unittest discover -s "HINAGI 2026/Paper/branch_b_academic/analysis" -t "HINAGI 2026/Paper/branch_b_academic/analysis" -p "test_v10_eviction_token_tables.py" -v
test_cd82_and_g50t_non_fabrication (test_v10_eviction_token_tables.TestV10EvictionTokenTables.test_cd82_and_g50t_non_fabrication) ... ok
test_conservation_and_cohorts (test_v10_eviction_token_tables.TestV10EvictionTokenTables.test_conservation_and_cohorts) ... ok
test_generated_files_match_payload (test_v10_eviction_token_tables.TestV10EvictionTokenTables.test_generated_files_match_payload) ... ok
test_vc33_post_eviction_facts (test_v10_eviction_token_tables.TestV10EvictionTokenTables.test_vc33_post_eviction_facts) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.446s

OK
```

---

## 2. Reconstructor In-Run Assertions (Observed)

`python3 "HINAGI 2026/Paper/branch_b_academic/analysis/v10_forensic_reconciliation/reconstruct_v10_forensics.py"` passed all runtime assertions (`exit 0`):
- `games_total == 25`, `score_sum == 70.9375`, `actions_executed == 386`
- `client_requests == 357`, `per_game_responses == 352`, `root_detached_responses == 1`, `total_client_responses == 353`, `true_http_read_timeouts == 4`
- `serve_log_reqtimestats_total == 360` (`3` warmup/health + `357` agent)
- `history_generated_tokens == 378304`, `trailing_post_action_comp_352 == 90206`, `trailing_post_action_comp_353 == 92984`
- `comp_tokens_352 == 468510`, `comp_tokens_353_exact_solver_note == 471288`
- `events_total == 613` (`25` `initial`, `386` `action`, `202` `analysis`)
- `live_calibration_matches == "45/45"`

---

## 3. Forensic Reconciliation Test Suite (`test_v10_forensics.py`)

Suite cases executed against final deliverables and manifest (`08_REPRODUCIBILITY_MANIFEST.json`):
- `test_01_all_deliverables_exist`: checks non-empty presence of all 10 required deliverables (`00`..`09`).
- `test_02_artifact_inventory_integrity`: checks `227` inventory rows (`212` V10 = `101,527,880 B`, `100%` `pulled_arc3_output` match, `15` comparators) and live disk SHA-256 non-mutation on primary canonical inputs.
- `test_03_request_response_reconstruction_exact_closure`: checks `360` rows (`3` warmup + `350` unique + `3` colliding + `4` timeouts), `missing_tool_call_ids == ""`, `output_len - completion_tokens` in `{0, 1, 2, 3}`, exact `g50t` root `idx=15` (`2,778` comp, `serve L2005`), and exact `4` timeout rows (`cd82 L1879`, `cn04 L1562`, `r11l L1787`, `vc33 L1723`).
- `test_04_token_accounting_conservation_and_eviction`: checks `diff_hist_vs_action_comp == 0` (`25/25`), `diff_note_vs_comp353 == 0` (`25/25`), `uncached == 0` / `final_generated == 0` defaults, `4 L6323 / 5 L6699` FIFO split, `pre_raw > 44,544`, `post_no_opener <= 28,160`.
- `test_05_manifest_self_consistency`: checks live SHA-256 and byte sizes of all deliverables against `08_REPRODUCIBILITY_MANIFEST.json`.

```text
$ python3 -m unittest discover -s "HINAGI 2026/Paper/branch_b_academic/analysis/v10_forensic_reconciliation" -t "HINAGI 2026/Paper/branch_b_academic/analysis/v10_forensic_reconciliation" -p "test_v10_forensics.py" -v
test_01_all_deliverables_exist (test_v10_forensics.TestV10ForensicsReconciliation.test_01_all_deliverables_exist) ... ok
test_02_artifact_inventory_integrity (test_v10_forensics.TestV10ForensicsReconciliation.test_02_artifact_inventory_integrity) ... ok
test_03_request_response_reconstruction_exact_closure (test_v10_forensics.TestV10ForensicsReconciliation.test_03_request_response_reconstruction_exact_closure) ... ok
test_04_token_accounting_conservation_and_eviction (test_v10_forensics.TestV10ForensicsReconciliation.test_04_token_accounting_conservation_and_eviction) ... ok
test_05_manifest_self_consistency (test_v10_forensics.TestV10ForensicsReconciliation.test_05_manifest_self_consistency) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.008s

OK
```
