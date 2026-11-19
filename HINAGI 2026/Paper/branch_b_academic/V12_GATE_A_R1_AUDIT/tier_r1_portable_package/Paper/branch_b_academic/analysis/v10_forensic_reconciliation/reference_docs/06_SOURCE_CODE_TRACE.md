# 06 — Source Code & Configuration Diff Trace (`tool_agent.py`, `solver.py`, `taaf/game.py`, V6 vs V10 Notebooks)

**Scope:** Exact symbol, line-range, and SHA-256 provenance trace grounding V10 token accounting, logging splits, context pruning, timeout handling, and V6->V10 notebook changes (`E0`/`E1`/`E2`).

---

## 1. Core Agent Mechanics (`tool_agent.py`, SHA-256 `053556f4a2d19bbb0f04d3ecde14bad2d76abfe91e89254740b763136a5a8e82`)

Note: Comparing `v6_reference.ipynb` Cell 2 and `v10_reference.ipynb` Cell 2 shows **byte-identical source** (`498,799` chars, SHA-256 `6fdcd1ae7445c0cfc26eec1047363aa0c196c867d289a35b6f64403b5a43dce2`). Thus all differences in `tool_agent.py` behavior between V6 and V10 arise solely from Cell 4 environment variables and Cell 16 monkey-patches, NOT from edits to Cell 2 / `tool_agent.py`.

| Symbol / Site | Exact Location | Verified Behavior & Evidence |
|---|---|---|
| `_resolve_run_artifact_location(state_path)` | `tool_agent.py:3234` (call at `3256`) | Extracts `(run_root, game_stem)` from `state_path`. |
| `_resolve_prompt_log_path(state_path)` | `tool_agent.py:3305` (call at `6586`) | Resolves per-game `prompts/<game_stem>_p0.log` (human-readable diagnostic/calibration logs). |
| **`_resolve_request_log_path(state_path)`** | `tool_agent.py:3314` (calls at `6767`, `6788`) | Returns `<run_root>/<game_stem>_p0_requests.jsonl` when `game_stem` resolves; falls back to root `requests.jsonl` when `game_stem is None` — explaining why `g50t` `idx=15`'s request landed in `g50t-5849a774_p0_requests.jsonl` while its response (`idx=15`) landed in `submissions/arc3_v10_verified/requests.jsonl`. |
| `_accumulate_usage_tokens(...)` | `tool_agent.py:3632` (calls at `6096`, `6783`) | Accumulates response `usage.completion_tokens` across requests inside a run; returns cumulative `total_tokens` printed by `solver.py:740` (`tokens=471288` total across `353` delivered responses). |
| **`_calibrate_from_usage(...)`** | **`tool_agent.py:5962-6008`** (call at `6778`, log line `6004`) | **Verified actual symbol.** Updates sliding chars/token calibration factor (clamped `[1.8, 4.8]`, seed `3.0`) using live API `prompt_tokens`, scrubbed text chars, and `_split_messages_for_estimate` image tokens; emits `"text_token_calibration: ..."` (`45` matched live entries in `artifacts/*_p0_events.jsonl` + `2` lines in `prompts/*_p0.log`). **`_update_input_token_calibration` DOES NOT EXIST** anywhere in `tool_agent.py` or Cell 2 (`count = 0`). |
| `_split_messages_for_estimate(messages)` | `tool_agent.py:2974` (calls at `5983`, `6215`) | Replaces `image_url` payloads with `<image>` placeholders and sums `ceil(W/32)*ceil(H/32) + 2` patch/sentinel tokens (`402` per `640x640` grid image). |
| `_estimate_request_input_tokens(messages, tools)` | `tool_agent.py:6204` (calls at `6025-6026`, `6511`, `6525`) | Serializes scrubbed messages + tools + `tool_choice` and divides char count by live `_input_chars_per_token`, adding image patch tokens. |
| `_trim_messages_for_context(messages, tools)` | `tool_agent.py:6454` (calls at `6323`, `6699`, `6743`, `6811`) | Enforces `self._context_budget_tokens = _LOCAL_ANALYZER_CONTEXT_WINDOW - self._reply_reserve_tokens - _REQUEST_SAFETY_MARGIN_TOKENS` (`57,344 - 12,288 - 512 = 44,544` at `tool_agent.py:205, 3505-3509`), draining oldest user-anchored blocks toward target `B_target = 28,160` (`44,544 - 16,384` at `tool_agent.py:6471-6472`). Does NOT log eviction events directly at runtime. |
| **`_persistent_history_messages(messages, tools)`** | **`tool_agent.py:6313-6345`** (call at `7184`) | End-of-step persistence order: (1) `_prune_control_messages` (`6316`), (2) **`_apply_history_image_window(..., keep=4)` (`6321`)**, (3) **`_trim_messages_for_context` (`6323`)**, (4) `_keep_recent_history_turns` (`6330`, `max_turns=36`, `drain=12`, `coalesce=1`). Running step (2) *before* step (3) shrinks end-of-step history below `44,544` on `5/9` games (`bp35, cd82, cn04, g50t, vc33`), deferring their FIFO trim to next turn `6699`; the remaining `4/9` (`ar25, ft09, r11l, sb26`) exceed `44,544` even after image windowing (`44,748..52,276`) and trim directly at `6323`. |

---

## 2. Harness Accounting & Timeout Mechanics (`solver.py` + `taaf/game.py`)

| Symbol / Site | Exact Location | Verified Behavior & Forensic Effect |
|---|---|---|
| `request_timeout_seconds(self)` | `solver.py:536` (call at `679`) | Computes remaining per-game runtime budget for HTTP read timeouts. |
| **`solver_note` formatting** | `solver.py:704, 733, 739-740` | Sets `run.solver_note = f"tokens={total_tokens}"` (`L740`) using accumulated API `completion_tokens` (`471,288` across 25 games == `353` responses). Even on the `4` timeout games (`cd82`, `cn04`, `r11l`, `vc33`), `solver_note` equals completed client responses (`18,510`, `28,304`, `33,628`, `25,854`), confirming server-completed timeout outputs (`7,610` `serve.log` `output_len`) never entered `_accumulate_usage_tokens`. |
| **Hardcoded `uncached_input_tokens=0`** | **`solver.py:1252`** | Records `GameActionRecord(..., action, generated_tokens=generated_tokens, uncached_input_tokens=0)`. Confirms why `386/386` `history[*].uncached_input_tokens == 0` (`E0`) in `benchmark.json`: prompt/uncached tokens were never passed down from `ToolAgent` into `GameActionRecord`. |
| `final_generated_tokens` | `taaf/game.py:260, 308, 340, 361, 617, 638`; `taaf/diagnostics.py:478, 881-882` | Designed to hold post-final-action trailing tokens (`GameRun.final_generated_tokens = 0` default, `L308`), but NEVER populated by V10's solver loop (`25/25` games record `0`), creating the `90,206` (`352`-resp) / `92,984` (`353`-resp) gap between `summary.txt` (`378,304`) and `solver_note` / API completion (`471,288`). |

---

## 3. Exact 23-Cell Diff: `v6_reference.ipynb` vs `v10_reference.ipynb` (`E0`/`E1`)

- `v6_reference.ipynb`: `584,060` bytes, `sha256=bb532e8c502ac5ce72c36918a2b1ac90e0de3cc96f5bdc70682953914466c90e` (`23` cells)
- `v10_reference.ipynb`: `591,785` bytes, `sha256=5f940b9615dee4ab337c564e465fb1701635cdd842b66bbeacc83372e71c5b3b` (`23` cells)
- **`18` cells byte-identical** (including `Cell 2`: `498,799` chars, `6fdcd1ae7445c0cfc26eec1047363aa0c196c867d289a35b6f64403b5a43dce2`).
- **`5` differing cells:**

| Cell | V6 SHA-256 | V10 SHA-256 | Exact Diff & Technical Impact |
|---|---|---|---|
| **Cell 0** (`918 -> 1208` ch) | `f34fab7499ca8b55e3bef3c955ab14b39795d48727d817afd91ed03e482fd2d8` | `2686225cedcf706768bfdaff62c4940c66af081f3590c379ec4c448eaa6be711` | Title/changelog markdown. **Contains 3 false claims contradicted by executable code/logs**: (1) claims `precache_model_thread` was disabled (still enabled in Cell 6); (2) claims zero `Read timed out` guaranteed (`4` occurred live); (3) calls `verify_transition` & `solve_state_space` *"Lean-4"* (pure Python BFS/state-checkers in Cell 16). |
| **Cell 4** (`6256 -> 6512` ch) | `e5141e12761674003185903291a2f5f43548a1407a11d1ca3b577420067a16cf` | `ab10de52175ce0f31870dc945245662a6684fcb8f25067e21a3cd16a978a51dd` | `LOCAL_ANALYZER_TOOL_STEPS: 0->12`, `YIELD_TOKENS: 2048->3072`, `TEMPERATURE: 0.7->0.6`, `CONTEXT_WINDOW: (116+12)*1024 -> (44+12)*1024`, `CONTEXT_DRAIN_TOKENS: 58*1024 -> 16*1024`, `HISTORY_ASSISTANT_TURNS: 150 -> 36`, `HISTORY_TURN_DRAIN: 30 -> 12`, `+HISTORY_IMAGE_KEEP='4'`, `+PRUNE_CONTROL_CONTEXT='1'`, `+NOOP_REPEAT_GUARD='1'`, `MEMORY_SECTIONS: 'off'->'medium'`, `+TOLERANT_SECTION_HEADERS='1'`, `+WM_WIPE_ON_LEVEL='0'`, `+WM_WIPE_ON_GAME_OVER='0'`. |
| **Cell 6** (`2321 -> 2321` ch) | `7ef53c4c2f0a6c2e636be00056ac7ce2a6813c8d6d2ced8e65937e1d6465641a` | `23a830b7dea6393a582ac7b50fc8c6481779f63b028b44e2f1a3755458f1af2d` | Only changes `precache_model_thread` warmup delay from `60s -> 30s` (does NOT disable it). |
| **Cell 12** (`18718 -> 18719` ch) | `c362ce556dc35ed0725c31b3f5c60b86bc83a2d94152fd1a109116813a4b5cf8` | `c905c1c863f58f5b5ca2c430c29aac624e140ccdb80a757cd9cf027b65897dd4` | Single boolean flip in SGLang server config: `DROP_CACHE_AFTER_LOAD=True -> False`. |
| **Cell 16** (`15838 -> 22671` ch) | `5606cee7e46ae5d0d027b844099fdd20155aadef31cd77658f6d328cdc4a14c0` | `18f4979a8d16e69562a3ccf64e2177fd06fc796671bfded41d7bad096a9526bc` | Monkey-patches `_patched_play_inner` (`/health` wait + post-gate `started_at` reset -> eliminated V6's `15/25` warmup starvation), `_patched_request_timeout` (`max(30.0, t)`), `_patched_runtime_limit_reached` (`>= max(30.0, max_runtime_s_per_game - 15.0)`), `_quantum_maybe_handover` (`18,000` tok/level), enriched `segment_layer` (`topleft`, `bbox`, `center`, `size`), `allowed_cells`, and Python `solve_state_space` / `verify_transition` helpers (`L425`, `L454`, `L481-482`). |

---

## 4. `serve.log` LF-Line Offset Trap Verification (`E0`)

`submissions/arc3_v10_verified/serve.log` (`446,633` bytes, `sha256=755a22bd7f41e1a87564265c45ecd51c3de176e5132c68835d3015a79c1ec986`) contains `2,006` LF (`\n`) delimiters and `86` standalone CR (`\r`) progress-bar bytes (e.g., SGLang TQDM/weight-loading lines), with zero CRLF (`\r\n`). Calling Python's `.splitlines()` splits on standalone `\r` bytes too (`2,093` lines), shifting line numbers after loading by up to **`+86`**. Using strict `.split("\n")` aligns line citations identically with `wc -l`, `grep -n`, and `read_file` (`L116`, `L156`, `L163` warmups; `L1562`, `L1723`, `L1787`, `L1879` timeouts; `L2005` `g50t` root response).
