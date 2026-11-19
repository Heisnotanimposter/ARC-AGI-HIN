# 00 — V10 Forensic Evidence Reconstruction: Executive Findings

**Mission:** `ARC-AGI-3 HINAGI — V10 Forensic Evidence Reconstruction & Manuscript Integrity Audit` (P0 — Research Integrity)  
**Target Directory Analyzed:** `HINAGI 2026/submissions/arc3_v10_verified/` (`212` files, `101,527,880` bytes; `100%` byte-for-byte identical to `HINAGI 2026/pulled_from_kaggle/arc3_output/`)  
**Execution Policy:** Strictly read-only on all canonical artifacts, reference code, notebooks, existing audit tables, and manuscript `.tex`/`.pdf`. All deliverables live inside `HINAGI 2026/Paper/branch_b_academic/analysis/v10_forensic_reconciliation/`.  
**Primary Reconciliation Machine Artifacts:**  
- Script: `reconstruct_v10_forensics.py`  
- Tables: `01_ARTIFACT_INVENTORY.csv`, `02_REQUEST_RESPONSE_RECONSTRUCTION.csv`, `03_TOKEN_ACCOUNTING_RECONCILIATION.csv`  
- Manifest: `08_REPRODUCIBILITY_MANIFEST.json`

---

## 1. Evidence Grade Legend

Every factual statement across this audit carries an explicit provenance tag separating direct observation, mechanical code replay, and unverified external claims:

| Grade | Definition | Examples in This Audit |
|---|---|---|
| **E0** | Direct raw artifact or file byte/hash inspection (`submissions/*`, `artifacts/*`, `reference/*`, git-immutable logs) | `benchmark.json`, `summary.txt`, `*_p0_requests.jsonl`, `requests.jsonl`, `serve.log`, `arc-agi-3-sota.log`, `artifacts/*_p0_events.jsonl`, `prompts/*_p0.log` |
| **E1** | Direct arithmetic aggregation, exact record joining, or schema verification over `E0` files | `357 = 352 + 1 + 4`, `360 = 3 + 353 + 4`, `378,304 + 92,984 = 471,288 == solver_note`, `45/45` live `text_token_calibration:` matches |
| **E2** | Exact source-code execution trace & deterministic offline replay using Cell 2 / `tool_agent.py` functions over `E0` inputs | Replaying `_split_messages_for_estimate` + `_estimate_request_input_tokens` across the `9` FIFO boundaries (`pre_raw_est > 44,544`, `pre_win4_eos_est` `L6323` vs `L6699`) |
| **E3** | Inference across logged telemetry where internal server state (e.g., SGLang RadixAttention LRU eviction / worker routing) is not directly emitted | Interpreting why `cn04 idx=12` (`fifo_eviction`) and `16/69` `image_omit_mutation` responses logged `cached_tokens = 0` at position `0` |
| **E4-LB** | External leaderboard / competition claim lacking a captured raw Kaggle CLI/API score payload in-repo | Claim `V10 Public LB = 8.03` vs `Submission 57827259`: `submission_57827259_status.json` still records `SubmissionStatus.PENDING` and `public_score: null`; `8.03` appears first in internal markdown reports |
| **E4-Repro** | Cross-run sibling / offline reproduction artifact incomparable or unverified against live V10 LLM trajectories | `pulled_from_kaggle/arc3_output/` (`212/212` identical), `arc3_v6_smoke_verified/` (`15/25` timer starvation), `Phase 6.0` / `Phase 6.4` offline scripts |

---

## 2. Verdict on the Seven Mission Objectives

1. **All 25 benchmark games have corresponding request and event records (`E0`/`E1`):** Verified `25/25` `game_runs` in `benchmark.json`, `25/25` `*_p0_requests.jsonl` files in `submissions/arc3_v10_verified/` (`357` client requests), `25/25` `*_p0_events.jsonl` files in `artifacts/` (`613` total events = `25` `initial` + `386` `action` + `202` `analysis`), and `25/25` `prompts/*_p0.log` files.
2. **All 357 client requests and 360 SGLang `serve.log` `ReqTimeStats` records are accounted for with ZERO unexplained remainder (`E0`/`E1`):**
   - `352` HTTP-200 responses paired in per-game `*_p0_requests.jsonl` (`468,510` completion tokens; `349` exact unique `(input_len, cached_input_len)` 1:1 server matches + `3` key-colliding initial-request `ft09/re86/s5i5` matches deterministically disambiguated via timestamps; adding the `1` unique root match yields `350 + 3 = 353` client responses).
   - `1` detached HTTP-200 response in root `submissions/arc3_v10_verified/requests.jsonl` (`g50t-5849a774` `idx=15`, `action=14`, `prompt_tokens=19,438`, `cached_tokens=16,064`, `completion_tokens=2,778`, `reasoning_tokens=2,391`, `serve.log` `L2005`). Including this detached response yields `353` client responses and `471,288` total completion tokens, which equals the exact sum of `benchmark.json` `solver_note` (`471,288`, `diff = 0`).
   - `4` true client-side HTTP read timeouts (`cn04` `idx=13` at `50.92s`, `vc33` `idx=19` at `30.00s`, `r11l` `idx=13` at `30.00s`, `cd82` `idx=14` at `49.14s`) where the SGLang server still finished generation after client socket close (`serve.log` LF lines `1562, 1723, 1787, 1879`; sum `input_len=120,483`, `cached_input_len=41,408`, `output_len=7,610`).
   - `3` pre-benchmark warmup/health `ReqTimeStats` rows (`serve.log` LF lines `116, 156, 163`) complete `3 + 353 + 4 = 360` `serve.log` server completions (`0` missing, `0` unattributed).
3. **Why `history.generated_tokens` sums to `378,304` while API completion reconstructs to `468,510` / `471,288` (`E0`/`E1`/`E2`):**
   - `solver.py` + `tool_agent.py` attribute `completion_tokens` ONLY to requests whose `action <= len(history)` when an action executes (`history[*].generated_tokens`, total `378,304`, identical to `summary.txt` across all `25/25` games, `diff = 0`).
   - Trailing requests (`action > len(history)` — post-final-action `analysis` loops ending via `stop_req` or wallclock/turn exit without emitting a new action) generate `90,206` tokens in the `352`-response per-game view (`378,304 + 90,206 = 468,510`) and `92,984` tokens in the `353`-response full-client view (`378,304 + 92,984 = 471,288`).
   - Additionally, `solver.py:1252` hardcodes `uncached_input_tokens=0` in every `GameActionRecord` (`386/386` sum = `0`), and `taaf/game.py:308` keeps `final_generated_tokens=0` across all `25/25` games even when trailing requests consumed up to `+14,749` (`sp80`), `+13,460` (`r11l`), `+11,052` (`sk48`), or `+5,147` (`g50t`, full view).
4. **Root `requests.jsonl` detached record proven (`E0`/`E1`/`E2`):**
   - `requests.jsonl` (`85,199` bytes, `1` JSON line) matches `g50t-5849a774` `idx=15` (`action=14`) on all 7 payload fields (`messages`, `tools`, `chat_template_kwargs`, `tool_choice`, `analysis_step`, `action`, `request_index_within_turn`) and matches `serve.log:2005` (`in=19,438, ca=16,064, out=2,780`). While `idx=15`'s request line (`tool_agent.py:6767`) resolved `g50t-5849a774_p0_requests.jsonl`, `_resolve_request_log_path(state_path)` (`tool_agent.py:3314`) wrote `idx=15`'s response line (`tool_agent.py:6788`) to the fallback root `requests.jsonl` path (`submissions/arc3_v10_verified/requests.jsonl`; full trace in `04_FOUR_UNMATCHED_REQUESTS.md` and `06_SOURCE_CODE_TRACE.md`).
5. **Why `output_len` in `serve.log` cannot 1:1 substitute for missing `completion_tokens` on the 4 timeouts (`E1`):** Across all `353` matched responses, `serve_output_len - completion_tokens` varies across `{0: 104, 1: 56, 2: 111, 3: 82}` (identical variation `{0: 101, 1: 56, 2: 111, 3: 82}` across the `350` unique 1:1 matches), proving EOS/special tokens make raw SGLang `output_len` differ from OpenAI `completion_tokens` by `0..3` tokens. Under strict no-imputation policy, client `usage` on the `4` timeout requests remains `N/A`, while server-side `serve.log` telemetry (`120,483` input, `41,408` cached, `7,610` output) is reported separately under its distinct server scope.
6. **Existing audit tables & `ARC3_Paper_v10_draft.tex` accuracy verdict (`E0`/`E1`/`E2`):**
   - `build_v10_eviction_token_tables.py` is arithmetic-accurate **within its 352-response per-game scope**, but omits the `g50t` root `requests.jsonl` response (`+2,778` completion tokens) and therefore misclassifies V10 as having `5 unpaired reqs` (`Evicted n=9`) instead of `1 detached root response + 4 true client timeouts`. Including `g50t`'s detached response resolves the `solver_note` gap (`471,288 - 468,510 = +2,778` -> `0`) and shifts `g50t` post-eviction KV hit rate from `61.45%` to `70.00%` (`353`-response aggregate KV hit `63.35%`).
   - **Six specific errors/defects remain in `ARC3_Paper_v10_draft.tex`** (see `07_MANUSCRIPT_CHANGE_RECOMMENDATIONS.md` for line-level recommendations):
     1. **Non-existent symbol & wrong logging claim (`L933`):** Cites `_update_input_token_calibration` (does not exist anywhere in `tool_agent.py` or Cell 2!) instead of `_calibrate_from_usage` (`tool_agent.py:5962-6008`), AND incorrectly describes calibration as *"unlogged at runtime"* when `45` live `text_token_calibration:` records are present across `42` event transcripts in `artifacts/*_p0_events.jsonl` plus `2` lines in `prompts/*_p0.log` (`ft09` L941, `sk48` L795).
     2. **Incomplete `352` vs `353` integration (`L87, L906, L909, L918, L927, L951`):** Lists `"5 unpaired reqs"` in `Table 4`, calls `g50t` `idx=15` `"one unpaired final request"`, and reports `468,510` / `90,206` instead of co-reporting or integrating the `353` full-client totals (`471,288`, `92,984`, `63.35%`, `88.52%`, `75.37%`).
     3. **Cell 0 self-contradictions unflagged (`L627–L635`, `Cell 0` vs `Cell 6/16`):** V10 `Cell 0` markdown header claims *"Disabled duplicate `precache_model_thread`"*, *"to guarantee zero `Read timed out` HTTP failures"*, and *"Lean-4 `verify_transition` & `solve_state_space`"*, all three of which are contradicted by `Cell 6` (still active with `delay=30`), `4` live timeouts, and pure Python `Cell 16` helpers.
     4. **External LB provenance gap (`8.03` vs `57827259`, `L85, L194, L684, L719, L751, L886, L1011`):** Classifies `8.03` as `T3` ("Official Kaggle Public-Leaderboard Score") despite `submission_57827259_status.json` (`E0`) still recording `SubmissionStatus.PENDING` / `public_score: null` and zero raw Kaggle API/CLI files in-repo containing `8.03` (`E4-LB`).
     5. **FIFO estimator minor discrepancies (`L933`):** Slight `19–400` token offsets relative to exact Cell 2 `_estimate_request_input_tokens` replay (e.g., `g50t` `44,645` vs exact `pre_raw_est = 45,045`, `cd82` `45,230` vs exact `46,048`, `ar25` `44,729` vs exact `pre_win4_eos_est = 44,748`).
     6. **Timeout server telemetry unnoted in Limitations (`L1003`):** States timeout usage is unavailable without noting that SGLang `serve.log` DOES contain the 4 completed server `ReqTimeStats` records (`in=120,483`, `cached=41,408`, `out=7,610`) with non-zero EOS delta `{0..3}` preventing direct client `usage` backfill.

---

## 3. Master Dual-Accounting Summary Table (`E0`/`E1`)

| Metric | Action-Attributed (`summary.txt` / `history[*]`) | Client Per-Game (`352` resps) | Full Client + Root (`353` resps) | Full Client + 4 Timeouts Server View (`357` agent / `360` total `serve.log`) |
|---|---:|---:|---:|---:|
| **Games / Actions** | `25` games / `386` actions | `25` games / `386` actions | `25` games / `386` actions | `25` games / `386` actions (`3` pre-bm warmups) |
| **Responses Covered** | `<= 353` (`action <= len(history)`) | `352` (`349` uniq + `3` colliding) | **`353`** (`352` per-game + `1` `g50t` root) | `357` agent (`+4` timeouts) / `360` total (`+3` pre-bm) |
| **Prompt / Input Tokens** | `0` logged (`uncached_input_tokens=0` hardcoded) | `7,078,878` (`prompt_tokens`) | **`7,098,316`** (`prompt_tokens`) | `7,218,799` agent `input_len` (`+120,483` TO; `7,218,932` total w/ warmups) |
| **Cached Input Tokens** | N/A | `4,480,704` (**63.30%**) | **`4,496,768`** (**63.35%**) | `4,538,176` agent `cached_input_len` (**62.87%**; `+41,408` TO) |
| **Uncached Prefill Tokens** | N/A | `2,598,174` | **`2,601,548`** | `2,680,623` agent (`+79,075` TO) |
| **Image Prompt Tokens** | N/A | `762,400` | **`764,400`** (`+2,000` root) | Client `image_tokens` N/A for 4 timeouts |
| **Completion / Output Tokens** | **`378,304`** | **`468,510`** (`-2,778` vs note) | **`471,288`** (`== solver_note`) | `471,288` client + `7,610` `serve.log` `output_len` on 4 TOs (note `output_len - completion_tokens` in `{0..3}`) |
| **Reasoning Tokens** | N/A | `404,005` (`86.23%`) | **`406,396`** (`86.23%`) | `406,396` client (`N/A` in `serve.log` for 4 TOs) |
| **Trailing Post-Action Scope Diff** | `0` (by definition) | `+90,206` (`19.25%` of `468,510`) | **`+92,984`** (`19.73%` of `471,288`) | Same + unreturned timeout output |

*Note on `352 = 349 unique + 3 colliding` vs `353`:* Across `353` client responses (`352` per-game + `1` root), `350` match a unique `(input_len, cached_input_len)` key in `serve.log` (including `g50t` root `idx=15`), and `3` initial `idx=0` requests (`ft09`, `re86`, `s5i5`) share colliding `(input_len, cached_input_len)` keys resolved unambiguously via timestamps. Every single one of `350 + 3 = 353` matches cleanly.

---

## 4. Defensibility Assessment of V10 Manuscript Claims

| Claim in `ARC3_Paper_v10_draft.tex` | Defensible? | Required Nuance / Boundary |
|---|---|---|
| Byte-identical Cell 2 core & 5 changed cells (`Cells 0, 4, 6, 12, 16`) | **Yes (`E0`/`E1`)** | State that V10 `Cell 0` claims on disabling `precache`, zero timeouts, and Lean-4 are self-contradicted by `Cell 6`, `4` timeouts, and Python `Cell 16`. |
| Local 25-game score (`70.94`, `2.84` mean) vs V6 (`49.84`, `1.99` mean) driven by `15/25` warmup starvation fix & `ft09` (`40.28%`) | **Yes (`E0`/`E1`)** | Hold: 24 remaining games average `1.77` (V10) vs `2.08` (V6), showing local score concentration in `ft09`. |
| Action-attributed (`378,304`) vs API completion (`468,510` / `471,288`) scope separation | **Yes (`E1`/`E2`)** | Must report BOTH `468,510` (`352` per-game) and `471,288` (`353` full client matching `solver_note`), and replace `"5 unpaired"` with `1 detached root + 4 timeouts`. |
| All `9/9` FIFO evictions caused by `B_tok = 44,544` `< 36`-turn cap | **Yes (`E2`)** | Fix non-existent symbol `_update_input_token_calibration` -> `_calibrate_from_usage` (`tool_agent.py:5962`), note live `45/45` logs exist, and use exact replay values (`4` at `L6323`, `5` at `L6699`). |
| Prefix-cache split (`~88.5%` append vs `~15.5%` image-omit & `18.12%` FIFO = `~75.4%` uncached share) | **Yes (`E1`)** | Observational co-occurrence only (`16` image-omit and `1` FIFO response hit `0` cached tokens; `7/8` FIFO matched `5,056`). Explain why `7 * 5,056 = 35,392` rather than `8 * 5,056`. |
| Post-eviction `vc33` Level-3 plan preservation before `30.00s` HTTP timeout | **Yes (`E0`/`E1`)** | Verified cleanly from `vc33` `idx=18` (`step=9`, `act=26..34`, `L6699`) -> `idx=19` (`act=35`, `32.20s > 30.00s`). |
| Evicted (`n=9`) vs Non-Evicted (`n=16`) causes lower score / lower cache hit | **NO (`E3` Overclaim)** | Observational cohort descriptors confounded by trajectory length and exposure time; explicitly avoid causal language. |
| Official V10 Kaggle Public LB = `8.03` (`Submission 57827259`) | **Caveated (`E4-LB`)** | Cannot be presented as raw `E0`/`T3` in-repo evidence while `submission_57827259_status.json` says `PENDING / null` with zero raw Kaggle API response backing `8.03`. |
