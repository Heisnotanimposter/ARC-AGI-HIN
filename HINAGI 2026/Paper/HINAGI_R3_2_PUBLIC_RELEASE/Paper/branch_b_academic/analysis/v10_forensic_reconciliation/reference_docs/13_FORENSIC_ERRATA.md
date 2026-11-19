# 13 — V10 Forensic Errata & Source-Grounded Correction Ledger

**Audit Scope:** Final evidence-driven reconciliation pass over `10_INDEPENDENT_REDTEAM_REVIEW.md`, `11_INDEPENDENT_ARITHMETIC_CHECK.py`, and `12_INDEPENDENT_ARITHMETIC_RESULTS.json`, cross-checked against raw V10/V6 artifacts, source code (`tool_agent.py`, `solver.py`, `taaf/game.py`), prior reports (`00`–`09`), sibling analysis (`v10_eviction_and_token_audit_report.md`, `build_v10_eviction_token_tables.py`, `Paper/ARC3_Version_History_Evidence_Ledger.md`), and `ARC3_Paper_v10_draft.tex`.  
**Non-Mutation Policy:** No existing canonical artifacts, reference source files, notebooks, reports `00`–`12`, prior scripts, or manuscript `.tex`/`.pdf` files were modified.

---

## Executive Errata Register (`ERR-01` – `ERR-15`)

| ID | Category | Affected File(s) & Exact Line(s) | Original Erroneous / Imprecise Claim | Verified Source-Grounded Correction |
|---|---|---|---|---|
| **ERR-01** | Calibration provenance | `00#L20,L80`; `05#L3,L8,L21,L46`; `08#L151`; `09#L5,L36`; `ARC3_Paper_v10_draft.tex#L933` | Unqualified `"45/45"` shorthand conflates records, matches, and files, and `.tex#L933` states calibration was *"unlogged at runtime"* using non-existent `_update_input_token_calibration`. | Actual symbol is `_calibrate_from_usage` (`tool_agent.py:5962-6008`). Runtime emitted **45** `text_token_calibration:` strings across **42** JSONL lines in `artifacts/*_p0_events.jsonl` (**3** multi-emission lines carry 2 strings each: `bp35` L3, `bp35` L14, `tn36` L3), mirrored 1:1 in **45** lines across `transcripts/*_p0.txt` and **45** lines across `solver_analysis/*_p0.html`, plus **2** `"LATEST MODEL CALL SNAPSHOT"` duplicates in `prompts/*_p0.log` (`ft09` L941 = `A16`, `sk48` L795 = `A33`), totaling **137** substring occurrences across **77** unique files. All 45 map 1:1 to `*_p0_requests.jsonl` responses. |
| **ERR-02** | Calibration clamp range | `05#L17`; `06#L17` | States `_calibrate_from_usage` clamps chars/token to `[1.8, 4.8]`. | Direct code (`tool_agent.py:2903, 2919, 5996`) proves clamp bounds are **`[1.0, 3.3]`**. Empirically **26/45** emissions clamped at `3.30` (25 initial calls from `4.30` + `r11l` `c_idx=12` from `3.41`). Note `.tex#L658` already stated `[1.0, 3.3]` accurately. |
| **ERR-03** | `vc33` control pruning | `reconstruct_v10_forensics.py#L501-L529`; `05#L39,L99`; `07#L16,L27`; `08#L747-748` | Omitted `_prune_control_messages` (`tool_agent.py:6316`) before 4-image windowing `vc33`'s `pm[43]` (`"resume"` nudge carrying 1 image), reporting `pre_win4_eos_est = 42,769` and `pre_raw_est = 45,627`. | Stripping `pm[43]` (`-1,524` tokens) **first** yields true control-pruned `L6321` `pre_win4_eos_est = 43,572` (`<= 44,544`) and true `L6699` `pre_open_est = 45,630` (`> 44,544`). Note `.tex#L933` reported `vc33: 45,630` accurately. |
| **ERR-04** | `11`/`12` `vc33` raw EOS & `preserve_recent` | `11_INDEPENDENT_ARITHMETIC_CHECK.py#L896,L907,L914`; `12_INDEPENDENT_ARITHMETIC_RESULTS.json` (`vc33`) | `11#L896,L907` removed `pm[43]` *before* computing `pre_raw_eos_est`, printing `43,572` instead of raw pre-prune `45,096` and obscuring why a `> 44,544` pre-prune crossing did not fire `L6323`; `11#L914` also passed `preserve_recent=0` on `L6323`. | Unpruned `vc33` end-of-invocation raw estimate is **`45,096 > 44,544`** (NOT an eviction trigger); `L6316` reduces it to `43,572 <= 44,544`. In `tool_agent.py:6323, 6459`, `_trim_messages_for_context` defaults to **`preserve_recent=1`**, not `0` (post-trim message counts still match 9/9 identically under `preserve_recent=1`). |
| **ERR-05** | `cn04` pre-window crossing | `05#L37`; threshold terminology across `05`/`11`/`12` | Raw end-of-invocation `pre_raw_eos_est = 44,736 > 44,544` on `cn04` must not be called an eviction trigger. | `L6321 _apply_history_image_window(..., 4)` reduced `cn04`'s end-of-invocation buffer from `44,736` down to **`43,936 <= 44,544`**, so `L6323` did NOT fire; eviction triggered later at **`L6699`** (`pre_open_est = 45,993`). |
| **ERR-06** | `L6699` pre-trim payload (`pre_raw_est` vs `pre_open_est`) | `05#L35-39,L42,L44,L46,L99,L103`; `07#L16,L27` | Uses un-windowed `pre_raw_est` (`45,450`, `46,048`, `46,793`, `45,045`, `45,627`) as the `L6699` trigger payload. | When `L6699` executes at next-turn open, history has already undergone `L6316` pruning and `L6321` 4-image windowing. True `pre_open_est` inputs entering `L6699` are **`bp35: 45,050`, `cd82: 45,249`, `cn04: 45,993`, `g50t: 44,645`, `vc33: 45,630`**. |
| **ERR-07** | `tr87` peak EOS estimate | `10#L123`; `11#L845`; `12` (`tr87_peak_eos_est`) | Reports `tr87_peak_eos_est = 42,028` by running `win4` on `prev_msgs` alone without `tr87`'s closing assistant+tool tail. | True end-of-invocation `L6321` estimate (`win4`) at `tr87` peak (`turn 8->9`) is **`42,877`** (un-windowed raw `43,677`; next-opener `pre_open_est = 44,318 <= 44,544`, `226` tokens below `B_tok`). |
| **ERR-08** | `.tex#L933` symbol, naming, & offsets | `ARC3_Paper_v10_draft.tex#L933`; `05#L31-34` | `.tex#L933` uses `_update_input_token_calibration`, `"unlogged"`, `"at turn commit"`, and shifted thresholds (`ar25: 44,729`, `ft09: 44,950`, `sb26: 49,041`, `cd82: 45,230`, `cn04: 45,974`). | Replace with `_calibrate_from_usage` (`45` live calibration logs; threshold crossing itself unlogged), **`end_of_invocation_L6323`** (since `bp35`, `r11l`, and `sb26` ran `L7184` on `turn_token_budget` yield with `step_executed=False`), and exact values (`ar25: 44,748`, `ft09: 44,972`, `sb26: 49,060`, `cd82: 45,249`, `cn04: 45,993`). |
| **ERR-09** | `352` vs `353` & `"5 unpaired"` | `v10_eviction_and_token_audit_report.md`; `build_v10_eviction_token_tables.py`; `.tex#L87,L157,L184,L195,L906,L909,L918,L920,L925,L927,L951,L963` | Omits detached `g50t idx=15` response in root `requests.jsonl` (`+2,778` comp, `+2,391` reas, `+19,438` prompt, `+16,064` cached), calling Table 4 `"5 unpaired reqs"`, calling `g50t idx=15` unpaired, and reporting `61.5%` on `g50t` post-eviction. | Per-game (`352`, `468,510`, `90,206` trailing, `63.30%` cached) and full-client (`353`, `471,288 == solver_note`, `92,984` trailing, `63.35%` cached, **`1` detached root + `4` HTTP read timeouts**, `g50t` `70.00%` post-eviction) must both be represented cleanly without double-counting. |
| **ERR-10** | Timeout imputation & `serve.log` `\r` lines | `.tex#L918,L1003` | Notes timeout usage is unavailable without noting `serve.log` server completions (`120,483` in / `41,408` cached / `7,610` `output_len`) or EOS delta `{0,1,2,3}`; Python `.splitlines()` shifts `serve.log` tail line numbers by `+86` (`2005 -> 2091`). | Retain `4` timeouts (`cn04`, `vc33`, `r11l`, `cd82`) as `N/A` in client `usage` (`4` HTTP read timeouts > client limits), report `serve.log` `7,610` solely under server-side scope (`output_len - completion_tokens` in `{0:104, +1:56, +2:111, +3:82}`), and cite LF-split lines (`1562, 1723, 1787, 1879, 2005`). |
| **ERR-11** | Red Team C1 KV header math | `ARC3_Paper_v10_draft.tex#L928-929`; `Fig 2B` | Without explicit zero-miss counts, `8 * 5,056 = 40,448 != 35,392` and `69 * 5,056 = 348,864 != 331,072`. | Verified histograms: `fifo_eviction` (`n=8`) has `7 * 5,056 = 35,392` + `1 * 0` (`cn04 idx=12`), and `image_omit_mutation` (`n=69`) has `16 * 0` + `46 * 5,056` (`232,576`) + `7` deeper partial matches (`98,496`) `= 331,072`. Causal LRU isolation remains unlogged. |
| **ERR-12** | V10 local score sum typo | `Paper/ARC3_Version_History_Evidence_Ledger.md#L116,L118` | Reports V10 local score sum `70.9395`, mean `2.8376`, diff `+21.0982`. | Exact `benchmark.json` sum verified against `taaf/game.py:381-413` (`max_abs_diff = 0`) is **`70.9375`** (`mean = 2.8375`, `V10 - V6 = +21.096230`); summing even the table's own 4-decimal rows equals `70.9375`. |
| **ERR-13** | Cell 0 contradictions & Cell 2 vs 4 attribution | `ARC3_Paper_v10_draft.tex#L629` (Table 1) | Calls V10 `Cell 0` `"Header text only; zero executable code"` without noting 3 self-contradicted claims inside `Cell 0`. Also verify Red Team C2: Sec 4 properly attributes `B_tok` formula to Cell 2 and `56K` window params to Cell 4 (`L630-631,L654`). | Flag `V10 Cell 0` claims contradicted by code/logs: (i) `precache_model_thread` remained active in `Cell 6` (`delay=30s`); (ii) `"guarantee zero Read timed out"` falsified by `4` live timeouts; (iii) `"Lean-4"` refers to pure Python `Cell 16` helpers (`solve_state_space`, `verify_transition`). |
| **ERR-14** | External LB provenance (`57827259` / `8.03`) | `.tex#L85,L194,L684,L719,L751,L886,L1000,L1011`; `00#L23,L49,L84`; `07#L14,L38-40`; `10#L212,L264` | `.tex` classifies `V10 = 8.03` as `T3` ("Official Kaggle Public-Leaderboard Score"); `10` downgrades to `E4-LB` / `ACCEPT WITH QUALIFICATION`. Both remain stronger than in-repo evidence supports. | Repo-wide scan finds **zero raw Kaggle API/CLI score payloads** for `8.03`. `artifacts/phase5_4/submission_57827259_status.json` (`E0`) records `SubmissionStatus.PENDING` and `public_score: null`; `final_submission_selection_audit.md:24` marks `57827259` `UNVERIFIED`. Reclassify `8.03` strictly as **`UNVERIFIED / REPORTED`** and place on **`HOLD`**. |
| **ERR-15** | Non-causal cohort & starvation framing | `00#L83`; `.tex#L85,L701,L922,L963` | Cohort splits (`n=9` evicted vs `n=16` non-evicted; `V6 smoke` `49.84` vs `V10` `70.9375`) risk causal or benchmark-improvement misreading. | `V6 smoke` starved `15/25` games at `0` actions (`729s` warmup timer start before server ready); V10 gained `+28.571429` (`40.28%`) from `ft09` alone while remaining 24 averaged `1.77` vs V6 `2.08` (`1.69` vs `1.99` `/25`). Eviction cohorts are confounded by trajectory length (`204` vs `182` acts). Strictly observational. |

---

## Check #1 — Calibration Provenance & Reconciled Counts

### 1.1 Exact Separation of Records, Matches, Files, and Substrings

Prior audit summaries used `"45/45"` without distinguishing source containers:

| Artifact Tree | Unique Files With Matches | Matching JSONL / Log Lines | Substring Occurrences (`text_token_calibration:`) | Provenance Role |
|---|---:|---:|---:|---|
| `submissions/arc3_v10_verified/artifacts/*_p0_events.jsonl` | **25** | **42** | **45** | Canonical structured event log (`analysis` events; 3 lines carry 2 emissions each inside multi-iteration `transcript` fields) |
| `submissions/arc3_v10_verified/transcripts/*_p0.txt` | **25** | **45** | **45** | Human-readable transcript mirror (1 line per emission) |
| `submissions/arc3_v10_verified/solver_analysis/*_p0.html` | **25** | **45** | **45** | Embedded HTML viewer mirror (1 line per emission) |
| `submissions/arc3_v10_verified/prompts/*_p0.log` | **2** | **2** | **2** | `"LATEST MODEL CALL SNAPSHOT"` tail dump ONLY (`ft09` `L941` duplicates `A16`; `sk48` `L795` duplicates `A33`) |
| **Total Across V10 Artifact Tree** | **77** | **134** | **137** | **45 distinct calibration emissions (`A01`–`A45`), 42 event JSONL records, 2 snapshot duplicates** |

**Multi-emission `events.jsonl` lines (`42 -> 45` delta = `+3`):**
1. `artifacts/bp35-0a0ad940_p0_events.jsonl:3` (`analysis_step=1`): contains **`A02`** (`cal=3.30`, `pt=6045`) and **`A03`** (`cal=3.14`, `pt=11464`).
2. `artifacts/bp35-0a0ad940_p0_events.jsonl:14` (`analysis_step=5`): contains **`A05`** (`cal=3.15`, `pt=37468`) and **`A06`** (`cal=3.05`, `pt=40934`).
3. `artifacts/tn36-ef4dde99_p0_events.jsonl:3` (`analysis_step=1`): contains **`A36`** (`cal=3.30`, `pt=6038`) and **`A37`** (`cal=3.07`, `pt=9968`).

**Clamp Range Correction (`ERR-02`):** `tool_agent.py:2903, 2919, 5996` sets `[ARC3_TEXT_TOKEN_CHARS_MIN, ARC3_TEXT_TOKEN_CHARS_MAX] = [1.0, 3.3]`. All **25** initial calls clamped downward from raw `4.30` to `3.30`, and **`A27`** (`r11l`, `c_idx=12`, `respL=26`) clamped downward from raw `3.41` to `3.30` (**26/45** clamped, **19/45** unclamped).

**Timestamp Availability Note:** Neither `artifacts/*_p0_events.jsonl` nor `*_p0_requests.jsonl` records per-event timestamps. All **45** emissions link 1:1 by exact `prompt_tokens` (`linked=45, unlinked=0, multi=0`) to response lines in `*_p0_requests.jsonl`, which in turn join 1:1 via `02_REQUEST_RESPONSE_RECONSTRUCTION.csv` to UTC completion timestamps in `serve.log` (`ReqTimeStats`).

### 1.2 Complete 45-Emission Enumeration (`A01` – `A45`)

| ID | Game ID | `events.jsonl` Line | `transcript` Line | `html` Line | Linked Req (`c_idx` / `respL` / `ast`,`act`,`rit`) | `serve.log` LF Line & UTC Timestamp | `prompt_tok` | `img_tok` | `text_chars` | Observed `cal` (`raw` if clamped) |
|---|---|---:|---:|---:|---|---|---:|---:|---:|---|
| **A01** | `ar25-0c556536` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L636` / `2026-10-30 05:18:43` | 6,051 | 402 | 24,273 | `3.30` (`raw 4.30`) |
| **A02** | `bp35-0a0ad940` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L203` / `2026-10-30 05:16:06` | 6,045 | 402 | 24,256 | `3.30` (`raw 4.30`) |
| **A03** | `bp35-0a0ad940` | `L3` | `L385` | `L386` | `c_idx=1` / `L4` (`s1,a1,r2`) | `L248` / `2026-10-30 05:16:20` | 11,464 | 402 | 34,783 | `3.14` |
| **A04** | `bp35-0a0ad940` | `L13` | `L1357` | `L1358` | `c_idx=7` / `L16` (`s4,a4,r1`) | `L603` / `2026-10-30 05:18:30` | 27,688 | 2,814 | 80,505 | `3.24` |
| **A05** | `bp35-0a0ad940` | `L14` | `L1881` | `L1882` | `c_idx=12` / `L26` (`s5,a9,r3`) | `L860` / `2026-10-30 05:19:58` | 37,468 | 3,618 | 106,769 | `3.15` |
| **A06** | `bp35-0a0ad940` | `L14` | `L2051` | `L2052` | `c_idx=13` / `L28` (`s5,a9,r4`) | `L938` / `2026-10-30 05:20:33` | 40,934 | 3,618 | 113,934 | `3.05` |
| **A07** | `cd82-fb555c5d` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L694` / `2026-10-30 05:19:02` | 6,048 | 402 | 24,267 | `3.30` (`raw 4.30`) |
| **A08** | `cn04-2fe56bfb` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L196` / `2026-10-30 05:16:05` | 6,048 | 402 | 24,267 | `3.30` (`raw 4.30`) |
| **A09** | `dc22-fdcac232` | `L4` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a2,r1`) | `L201` / `2026-10-30 05:16:05` | 6,048 | 402 | 24,284 | `3.30` (`raw 4.30`) |
| **A10** | `ft09-0d8bbf25` | `L2` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L791` / `2026-10-30 05:19:35` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A11** | `ft09-0d8bbf25` | `L5` | `L999` | `L1000` | `c_idx=3` / `L8` (`s1,a1,r1`) | `L1415` / `2026-10-30 05:24:31` | 16,474 | 804 | 47,787 | `3.05` |
| **A12** | `ft09-0d8bbf25` | `L9` | `L1289` | `L1290` | `c_idx=4` / `L10` (`s2,a2,r1`) | `L1438` / `2026-10-30 05:24:48` | 19,019 | 1,206 | 53,121 | `2.98` |
| **A13** | `ft09-0d8bbf25` | `L11` | `L1549` | `L1550` | `c_idx=5` / `L12` (`s3,a5,r1`) | `L1452` / `2026-10-30 05:24:52` | 21,881 | 1,608 | 61,786 | `3.05` |
| **A14** | `ft09-0d8bbf25` | `L19` | `L2267` | `L2268` | `c_idx=9` / `L20` (`s5,a12,r2`) | `L1686` / `2026-10-30 05:27:14` | 32,436 | 2,814 | 87,076 | `2.94` |
| **A15** | `ft09-0d8bbf25` | `L34` | `L2630` | `L2631` | `c_idx=10` / `L22` (`s5,a12,r1`) | `L1700` / `2026-10-30 05:27:25` | 37,071 | 2,814 | 98,906 | `2.89` |
| **A16** | `ft09-0d8bbf25` | `L37` | `L3261` | `L3262` | `c_idx=13` / `L28` (`s7,a27,r1`) | `L1947` / `2026-10-30 05:29:46` | 27,056 | 2,412 | 77,385 | `3.14` *(+`prompts L941`)* |
| **A17** | `g50t-5849a774` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L947` / `2026-10-30 05:20:36` | 6,033 | 402 | 24,202 | `3.30` (`raw 4.30`) |
| **A18** | `ka59-38d34dbb` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L194` / `2026-10-30 05:16:05` | 6,046 | 402 | 24,260 | `3.30` (`raw 4.30`) |
| **A19** | `lf52-271a04aa` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L475` / `2026-10-30 05:17:42` | 6,049 | 402 | 24,266 | `3.30` (`raw 4.30`) |
| **A20** | `lp85-305b61c3` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L211` / `2026-10-30 05:16:07` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A21** | `lp85-305b61c3` | `L19` | `L1844` | `L1845` | `c_idx=8` / `L18` (`s7,a10,r1`) | `L1417` / `2026-10-30 05:24:31` | 31,126 | 3,216 | 89,951 | `3.22` |
| **A22** | `ls20-9607627b` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L825` / `2026-10-30 05:19:48` | 6,031 | 402 | 24,195 | `3.30` (`raw 4.30`) |
| **A23** | `m0r0-492f87ba` | `L6` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L188` / `2026-10-30 05:16:04` | 6,048 | 402 | 24,267 | `3.30` (`raw 4.30`) |
| **A24** | `r11l-495a7899` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L522` / `2026-10-30 05:17:59` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A25** | `r11l-495a7899` | `L9` | `L968` | `L969` | `c_idx=5` / `L12` (`s3,a6,r2`) | `L1028` / `2026-10-30 05:21:19` | 20,516 | 2,010 | 60,105 | `3.25` |
| **A26** | `r11l-495a7899` | `L12` | `L1313` | `L1314` | `c_idx=6` / `L14` (`s3,a6,r1`) | `L1079` / `2026-10-30 05:21:39` | 31,465 | 2,412 | 92,262 | `3.18` |
| **A27** | `r11l-495a7899` | `L19` | `L2575` | `L2576` | `c_idx=12` / `L26` (`s5,a11,r1`) | `L1679` / `2026-10-30 05:27:11` | 27,403 | 1,608 | 88,005 | `3.30` (`raw 3.41`) |
| **A28** | `re86-8af5384d` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L186` / `2026-10-30 05:16:04` | 6,033 | 402 | 24,202 | `3.30` (`raw 4.30`) |
| **A29** | `s5i5-18d95033` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L439` / `2026-10-30 05:17:25` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A30** | `sb26-7fbdac44` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L676` / `2026-10-30 05:18:56` | 6,043 | 402 | 24,250 | `3.30` (`raw 4.30`) |
| **A31** | `sc25-635fd71a` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L547` / `2026-10-30 05:18:08` | 6,046 | 402 | 24,260 | `3.30` (`raw 4.30`) |
| **A32** | `sk48-d8078629` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L192` / `2026-10-30 05:16:04` | 6,049 | 402 | 24,266 | `3.30` (`raw 4.30`) |
| **A33** | `sk48-d8078629` | `L8` | `L1387` | `L1388` | `c_idx=7` / `L16` (`s3,a3,r1`) | `L1630` / `2026-10-30 05:26:34` | 27,725 | 2,412 | 80,639 | `3.19` *(+`prompts L795`)* |
| **A34** | `sp80-589a99af` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L616` / `2026-10-30 05:18:34` | 6,048 | 402 | 24,267 | `3.30` (`raw 4.30`) |
| **A35** | `su15-1944f8ab` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L863` / `2026-10-30 05:19:59` | 6,041 | 402 | 24,243 | `3.30` (`raw 4.30`) |
| **A36** | `tn36-ef4dde99` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L184` / `2026-10-30 05:16:04` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A37** | `tn36-ef4dde99` | `L3` | `L281` | `L282` | `c_idx=1` / `L4` (`s1,a1,r2`) | `L217` / `2026-10-30 05:16:10` | 9,968 | 402 | 29,382 | `3.07` |
| **A38** | `tn36-ef4dde99` | `L5` | `L635` | `L636` | `c_idx=4` / `L10` (`s2,a2,r1`) | `L316` / `2026-10-30 05:16:39` | 14,623 | 1,206 | 41,683 | `3.11` |
| **A39** | `tn36-ef4dde99` | `L10` | `L1131` | `L1132` | `c_idx=7` / `L16` (`s4,a4,r1`) | `L444` / `2026-10-30 05:17:25` | 20,134 | 2,814 | 55,811 | `3.22` |
| **A40** | `tn36-ef4dde99` | `L12` | `L1369` | `L1370` | `c_idx=8` / `L18` (`s5,a6,r1`) | `L462` / `2026-10-30 05:17:38` | 23,316 | 3,618 | 64,607 | `3.28` |
| **A41** | `tr87-cd924810` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L909` / `2026-10-30 05:20:15` | 6,031 | 402 | 24,195 | `3.30` (`raw 4.30`) |
| **A42** | `tr87-cd924810` | `L39` | `L2579` | `L2580` | `c_idx=14` / `L30` (`s7,a31,r2`) | `L1940` / `2026-10-30 05:29:44` | 40,101 | 3,618 | 113,893 | `3.12` |
| **A43** | `tu93-0768757b` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L206` / `2026-10-30 05:16:06` | 6,031 | 402 | 24,195 | `3.30` (`raw 4.30`) |
| **A44** | `vc33-5430563c` | `L3` | `L146` | `L147` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L849` / `2026-10-30 05:19:55` | 6,038 | 402 | 24,237 | `3.30` (`raw 4.30`) |
| **A45** | `wa30-ee6fef47` | `L3` | `L145` | `L146` | `c_idx=0` / `L2` (`s1,a1,r1`) | `L754` / `2026-10-30 05:19:23` | 6,033 | 402 | 24,202 | `3.30` (`raw 4.30`) |

---

## Check #2 — Eviction Trigger Reconstruction (`tool_agent.py` Execution Order)

### 2.1 Exact Source-Code Execution Pipeline

Importing `tool_agent.ToolAgent` directly to replay all **177** post-initial turn boundaries across the 25 games establishes exact source-code fidelity (`all_45_cal_match=True`, `open_match=177/177` byte-for-byte next-request messages, `hm_match=177/177` `history_messages:` counts):

1. `tool_agent.py:7184` (`finally:` block at end of invocation): calls `_persistent_history_messages(messages, tools)` (`tool_agent.py:6313-6350`).
2. `tool_agent.py:6316`: `_prune_control_messages(messages)` strips `_arc3_control` resumption/nudge messages (marked e.g. at `tool_agent.py:6694`).
3. `tool_agent.py:6321`: `_apply_history_image_window(messages, keep_images=4)` replaces older historical grid images with `[grid image omitted from history]`.
4. `tool_agent.py:6323`: `_trim_messages_for_context(messages, tools=tools)` runs with default **`preserve_recent=1`** (`tool_agent.py:6459`). If `est > 44,544`, drains via `_drop_oldest_history_block` toward `B_target = 28,160`.
5. `tool_agent.py:6330-6335`: `_keep_recent_history_turns(..., max_turns=36, drain_turns=12, force_drain=token_trim_dropped and _history_drain_coalesce())` coalesces turn limit to `24` if step 4 dropped messages. Observed drops across all 177 boundaries: **`l6330_drops = 0`** (`max_asst_in_any_req = 21`, `max_asst_eos = 19 <= 22 < 24`).
6. `tool_agent.py:6336-6344`: user-opener boundary guard + `_drop_until_first_user_message(history)`.
7. `tool_agent.py:6698-6703`: next invocation appends new `opening_message` (`L6698`) and calls `_trim_messages_for_context(messages, tools=tools, preserve_recent=1)` (`L6699`).
8. `tool_agent.py:6743`: pre-call trim inside multi-turn tool loop. Observed mid-turn drops across all requests: **`0`**.

### 2.2 Complete Stage-by-Stage Reconciliation Table (`9` Evicted Games + Near-Miss `tr87`)

| Game (`turn` / `ast`,`act`) | `cal` | Pre-Process Raw EOS (`>44,544`?) | `L6316` Pruned & Post-Prune | `L6321` Win4 EOS (`L6323` Input) | `L6323` Trim? -> Post `L6323` (Persist Msgs) | `L6699` Next-Opener (`pre_open_est`) | `L6699` Trim? -> Final Submitted (`msgs`) | Exact Source Trigger & Non-Trigger Resolution |
|---|---|---|---|---|---|---|---|---|
| **`ar25-0c556536`** (`11->12`, `a32`) | `3.30` | `45,548` (`46` msgs) | `0` (`45,548`) | **`44,748`** (`>44,544`) | **Yes** -> `25,678` (`18`; `hm=17`) | `27,491` (`19`) | No -> `27,491` (`19`) | **`end_of_invocation_L6323`** (replaces `.tex#L933` `44,729`) |
| **`ft09-0d8bbf25`** (`9->10`, `a27`) | `2.8885` | `45,771` (`33` msgs) | `0` (`45,771`) | **`44,972`** (`>44,544`) | **Yes** -> `27,360` (`16`; `hm=15`) | `29,203` (`17`) | No -> `29,203` (`17`) | **`end_of_invocation_L6323`** (replaces `.tex#L933` `44,950`) |
| **`r11l-495a7899`** (`7->8`, `s5,a11`) | `3.1250` | `52,675` (`30` msgs) | `0` (`52,675`) | **`52,276`** (`>44,544`) | **Yes** -> `28,102` (`13`; `hm=12`) | `29,770` (`14`) | No -> `29,770` (`14`) | **`end_of_invocation_L6323`** (`finally:` after yield; NOT `turn commit`) |
| **`sb26-7fbdac44`** (`13->14`, `s12,a34`) | `3.30` | `49,860` (`57` msgs) | `0` (`49,860`) | **`49,060`** (`>44,544`) | **Yes** -> `27,199` (`23`; `hm=22`) | `28,552` (`24`) | No -> `28,552` (`24`) | **`end_of_invocation_L6323`** (`finally:` after yield; replaces `.tex#L933` `49,041`) |
| **`bp35-0a0ad940`** (`5->6`, `s5,a9`) | `3.0532` | `44,013` (`34` msgs) | `0` (`44,013`) | `43,613` (`<=44,544`) | No (`hm=33`) | **`45,050`** (`35`) | **Yes** -> **`25,183`** (`18`) | **`next_opener_L6699`** (replaces `05#L35` un-windowed `45,450`) |
| **`cd82-fb555c5d`** (`9->10`, `a11`) | `3.30` | `44,023` (`38` msgs) | `0` (`44,023`) | `43,223` (`<=44,544`) | No (`hm=37`) | **`45,249`** (`39`) | **Yes** -> **`27,681`** (`16`) | **`next_opener_L6699`** (replaces `05#L36` `46,048` & `.tex#L933` `45,230`) |
| **`cn04-2fe56bfb`** (`7->8`, `a25`) | `3.2561` | `44,736` (`>44,544` pre-win4; **NOT trigger**) | `0` (`44,736`) | **`43,936`** (`<=44,544`) | No (`hm=31`) | **`45,993`** (`33`) | **Yes** -> **`26,222`** (`17`) | **`next_opener_L6699`** (`L6321` prevented `L6323`; replaces `05#L37` `46,793` & `.tex#L933` `45,974`) |
| **`g50t-5849a774`** (`7->8`, `a13`) | `3.30` | `42,922` (`32` msgs) | `0` (`42,922`) | `42,523` (`<=44,544`) | No (`hm=31`) | **`44,645`** (`33`) | **Yes** -> **`14,937`** (`7`) | **`next_opener_L6699`** (replaces `05#L38` un-windowed `45,045`) |
| **`vc33-5430563c`** (`10->11`, `a26`) | `3.30` | `45,096` (`>44,544` pre-prune; **NOT trigger**) | **`1`** (`-1,524` tok -> **`43,572`**) | **`43,572`** (`<=44,544`) | No (`hm=44`) | **`45,630`** (`46`) | **Yes** -> **`27,212`** (`18`) | **`next_opener_L6699`** (`L6316` stripped `pm[43]`; fixes `05#L39` `42,769`/`45,627` & `12`'s `pre_raw_eos_est = 43,572`) |
| *`tr87-cd924810` (near-miss)* (`8->9`) | `3.1113` | `43,677` (`40` msgs) | `0` (`43,677`) | **`42,877`** (`<=44,544`) | No (`hm=39`) | `44,318` (`41`) | No (`226` below `44,544`) | Never evicted (replaces `10#L123`, `11#L845`, `12` `42,028`) |

---

## Check #3 — Token Accounting, `352` vs `353` Views, and Non-Imputed Timeouts

1. **Action-Attributed vs Full-Response Completion Scopes (Strict Exact Identities):**
   - Action-attributed (`benchmark.json` `history[*].generated_tokens` `==` `summary.txt` `==` `arc-agi-3-sota.log` `tokens=`): **`378,304`** (`25/25` game-level `diff = 0`).
   - Per-game paired responses (`*_p0_requests.jsonl`, **`352`** responses): **`468,510`** (`404,005` reasoning = `86.23%`; `7,078,878` prompt; `4,480,704` cached = **`63.30%`**; `2,598,174` uncached; `762,400` image; trailing scope diff `90,206 = 19.25%`).
   - Detached `g50t-5849a774` root response (`submissions/arc3_v10_verified/requests.jsonl`, `idx=15`, `ast=7, act=14, rit=2`, `tool_call_id=call_786624f58c0f463a951acd79`, `serve.log` LF `L2005` / CR-normalized `L2091`, `2026-10-30 05:30:19`, `input_len=19,438`, `cached=16,064`, `output_len=2,780`): adds **`+2,778`** completion tokens (`+2,391` reasoning, `+19,438` prompt, `+16,064` cached = `82.64%`, `+3,374` uncached, `+2,000` image). Caused by `tr87` exiting at `05:30:06` and reducing `*_runtime_state.json <= 1` (`tool_agent.py:3238-3240, 3314`) between `g50t idx=15` request write (`L6767`) and response write (`L6788`).
   - Full reconstructed client responses (**`353`** responses): **`471,288 == sum(solver_note)`** (`25/25` exact per-game equality, `diff = 0`; `406,396` reasoning = `86.23%`; `7,098,316` prompt; `4,496,768` cached = **`63.35%`**; `2,601,548` uncached; `764,400` image; trailing scope diff **`92,984 = 19.73%`**).
2. **Affected Files Needing Correction (`ERR-09`, `ERR-10`, `ERR-11`):**
   - `v10_eviction_and_token_audit_report.md` / `build_v10_eviction_token_tables.py` are arithmetic-exact within `352`-response scope but miss `g50t` root `requests.jsonl` (`+2,778`) and label the `5` unreturned per-game requests cleanly as `"5 unpaired"` instead of **`1 detached root response + 4 HTTP read timeouts`**.
   - `ARC3_Paper_v10_draft.tex` (`L87, L157, L184, L195, L906, L909, L918, L920, L925, L927, L951, L963`) must co-report or standardize on the `353`-response full-client accounting alongside the `352` per-game subtotals, replace `"5 unpaired reqs"` / `"one unpaired final request"`, and update `g50t` post-eviction KV reuse from `61.5%` to **`70.00%`** (`33,728 / 48,182`; `61.45%` excluding root).
   - **Four Client HTTP Read Timeouts Retained Un-Imputed (`N/A`):** `cn04 idx=13` (`50.92s`), `vc33 idx=19` (`30.00s`), `r11l idx=13` (`30.00s`), `cd82 idx=14` (`49.14s`). Across all `353` delivered responses, SGLang `serve.log` `output_len - completion_tokens` varies across `{0: 104, +1: 56, +2: 111, +3: 82}` (`serve.log` sums on 4 timeouts = `120,483` input, `41,408` cached, **`7,610` `output_len`** at LF lines `1562, 1723, 1787, 1879`). Never impute client `usage.completion_tokens` from `7,610`.
   - **Red Team C1 Prefix Header Clarification:** `fifo_eviction` (`n=8`) caches `35,392` because `7` hit `5,056` (`7 * 5,056 = 35,392`) and `1` (`cn04 idx=12`, `pt=26,297`) hit `0` (plus timed-out `cd82 idx=14` hit `5,056` on server). `image_omit_mutation` (`n=69`) has `16` at `0`, `46` at `5,056`, and `7` partial prefixes (`98,496`) = `331,072`. Causal GPU LRU causes remain unisolated.

---

## Check #4 — Score Comparability (`V6_SMOKE` vs `V10`, `ft09`, `70.9395` Erratum)

1. **Exact RHAE Verification (`taaf/game.py:381-413`):** Recomputing `min(sum((k+1)*s_k)/sum(k+1), sum_{s_k>0}(k+1)/sum(k+1)*100)` across both `V10` (`25` games) and `V6_SMOKE` (`25` games) gives **`max_abs_diff = 0.000000e+00`** (`0` mismatches).
2. **Distinction of Sums, Means, Active Means, and `ft09` Concentration:**
   - **V10 Local (`submissions/arc3_v10_verified/benchmark.json`):** `25/25` active (`386` actions, `13/183` levels), sum = **`70.937500`** (NOT `70.9395`), mean (`/25`) = **`2.837500`**, active mean (`/25`) = `2.837500`. Single game **`ft09`** solved `3/6` levels, scoring `(1+2+3)/(1+2+3+4+5+6) * 100 = 6/21 * 100 = 28.571429`, which is **`28.571429 / 70.937500 = 40.276898%` (`40.28%`)** of V10's total 25-game sum. The remaining 24 games sum to **`42.366071`** (mean `/24` = **`1.765253`**, `/25` contribution = **`1.694643`**).
   - **V6 Local Smoke (`submissions/arc3_v6_smoke_verified/benchmark.json`):** `10/25` active (`270` actions, `10/183` levels), **`15/25` starved at `0` actions** due to pre-readiness timer start (`t=729s`, `15` starved exits at `t=1331s`), sum = **`49.841270`**, unconditional `/25` mean = **`1.993651`**, active `/10` mean = **`4.984127`**, `ft09 = 0.00` (`0` actions), other-24 `/24` mean = **`2.076720`**.
3. **Version-Ledger Rounding Erratum (`ERR-12`):** `Paper/ARC3_Version_History_Evidence_Ledger.md#L116,L118` reports `70.9395`, `2.8376`, `+21.0982`; corrected values are **`70.9375`**, **`2.8375`**, **`+21.096230`**.
4. **Comparability Verdict (`ERR-15`):** Although `V6_SMOKE` and `V10` share the exact RHAE metric and 25-game local suite, they are **non-comparable as an architecture-quality contrast** because `V6_SMOKE` suffered `15/25` warmup starvation fixed by V10 `Cell 16`, V10 changed `5` notebook cells simultaneously (`Cells 0, 4, 6, 12, 16`), and V10's entire local gain came from single game `ft09` while the other 24 games averaged lower (`1.77` vs `2.08`).
5. **Cell 0 & Cell 2 Attribution (`ERR-13`):** `.tex#L629` must disclose that V10 `Cell 0` contains 3 self-contradicted claims (`precache_model_thread` disabled -> still active in `Cell 6`; `"guarantee zero Read timed out"` -> `4` live timeouts; `"Lean-4"` -> pure Python `Cell 16` helpers). `.tex#L630-631,L654` already correctly separate Cell 2's formula from Cell 4's window parameters.

---

## Check #5 — Kaggle Provenance (`57827259` and `8.03`)

1. **Direct Raw Artifacts:** `artifacts/phase5_4/submission_57827259_status.json` records `submission_ref: 57827259`, `raw_status: "SubmissionStatus.PENDING"`, `public_score: null`, `classification: "OUT_OF_POLICY_EXCEPTION_SUBMISSION"`; `artifacts/phase5_4/final_submission_selection_audit.md:24` marks `57827259` `UNVERIFIED`.
2. **Repo-Wide Scan:** Searching every file in `HINAGI 2026/` confirms **zero raw Kaggle API/CLI score payloads** contain `8.03`. `8.03` appears only in secondary markdown/report/manuscript files (earliest `artifacts/phase6_4/reports/phase6_4_competition_performance_bridge.md:20,27`), alongside `Paper/ARC3_Version_History_Evidence_Ledger.md:129` already logging the missing Kaggle API proof as open.
3. **Correction (`ERR-14`):** Supersedes `.tex` `T3` and report `10`'s `E4-LB / ACCEPT WITH QUALIFICATION`: `8.03` for submission `57827259` is strictly **`UNVERIFIED / REPORTED`** and placed on **`HOLD`** for manuscript verification claims until a raw completed Kaggle API status payload is archived in-repo.
