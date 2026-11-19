# 04 — Forensic Reconstruction of the Five Unpaired Per-Game Requests (1 Detached Root Response + 4 HTTP Read Timeouts)

**Scope:** All 5 requests in `submissions/arc3_v10_verified/*_p0_requests.jsonl` that lacked a paired `response` record inside their per-game JSONL file.  
**Data Source Table:** `02_REQUEST_RESPONSE_RECONSTRUCTION.csv` (all `360` rows: `3` pre-benchmark warmups + `357` client requests).

---

## 1. Summary Decomposition (`5` -> `1 Detached Root` + `4 True HTTP Timeouts`)

Prior reports (`v10_eviction_and_token_audit_report.md` and `ARC3_Paper_v10_draft.tex` Table 4) grouped `5` terminal requests in the Evicted (`n=9`) cohort under the uniform label `"5 unpaired reqs"`. Byte-level cross-referencing across per-game JSONL logs, root `requests.jsonl`, `arc-agi-3-sota.log`, `serve.log`, and `benchmark.json` proves these 5 requests consist of **two strictly distinct mechanisms** (`E0`/`E1`/`E2`):

| Game ID | Req `idx` | `action` | `step` | Transition Class | Client Terminal Event (`arc-agi-3-sota.log`) | Client Response Location | `serve.log` LF Line & `rid` | Server `in / cached / out` | Server Timing (`queue + fwd`) vs Timeout Limit |
|---|---:|---:|---:|---|---|---|---|---|---|
| **`g50t-5849a774`** | `15` | `14` | `7` | `pure_append` | Graceful exit (`pre-limit`, no error) | **`submissions/arc3_v10_verified/requests.jsonl`** (root file) | `L2005`, `b16dc5d9a7204a7c8eca157b7bf600af` | `19,438 / 16,064 / 2,780` (`comp=2,778`, `reas=2,391`) | `0.66 ms + 16,816.32 ms = 16.82 s` (HTTP 200 OK delivered) |
| **`cn04-2fe56bfb`** | `13` | `28` | `9` | `pure_append` | `L241`: `analyzer request timed out at action 28; read timeout=50.92s` (`50.916...s`) | None (`TIMEOUT_NO_RESPONSE`) | `L1562`, `ab44e7bd483747919c64c14b397032c0` | `32,084 / 26,240 / 2,902` | `0.76 ms + 52,556.07 ms = 52.56 s` (**> `50.92s`** limit) |
| **`vc33-5430563c`** | `19` | `35` | `10` | `image_omit_mutation` | `L248`: `analyzer request timed out at action 35; read timeout=30.00s` | None (`TIMEOUT_NO_RESPONSE`) | `L1723`, `d5eff89d799640adaf8cb762862c4d38` | `33,349 / 5,056 / 1,067` | `4,990.56 ms + 27,214.28 ms = 32.20 s` (**> `30.00s`** limit) |
| **`r11l-495a7899`** | `13` | `11` | `6` | `image_omit_mutation` | `L296`: `analyzer request timed out at action 11; read timeout=30.00s` | None (`TIMEOUT_NO_RESPONSE`) | `L1787`, `310ae40fac5c443b9a62c96aca52ab5f` | `30,622 / 5,056 / 1,713` | `0.65 ms + 32,137.20 ms = 32.14 s` (**> `30.00s`** limit) |
| **`cd82-fb555c5d`** | `14` | `11` | `10` | `fifo_eviction` | `L304`: `analyzer request timed out at action 11; read timeout=49.14s` (`49.133...s`) | None (`TIMEOUT_NO_RESPONSE`) | `L1879`, `9346eaa0338142c6b734aa6640880987` | `24,428 / 5,056 / 1,928` | `4,884.24 ms + 48,553.25 ms = 53.44 s` (**> `49.14s`** limit) |

Notice **every single one of the 4 timeouts satisfies `queue_duration + forward_duration > client read_timeout`**, proving the exact physical failure chain: the client's `httpx` / HTTP read timeout closed the socket shortly before SGLang finished streaming/computing the forward pass (`+1.64s` on `cn04`, `+2.20s` on `vc33`, `+2.14s` on `r11l`, `+4.30s` on `cd82`). Because the client never received the final SSE/HTTP JSON chunk, no OpenAI `usage` payload was returned or written to `*_p0_requests.jsonl`.

---

## 2. Exact Proof of the Detached `g50t-5849a774` Root `requests.jsonl` Record (`E0`/`E1`/`E2`)

`submissions/arc3_v10_verified/requests.jsonl` (`85,199` bytes, `sha256=c3d3e9e5ecee90d8dc37b152f71f7a220f65a5b47b074f4512457698a39d2ce`, `1` line) is NOT an unlinked stray response:

1. **Full 7-Field Structural Equality (`E0`):** Every key in `g50t-5849a774_p0_requests.jsonl` final request (`idx=15`, `action=14`) matches `submissions/arc3_v10_verified/requests.jsonl` byte-for-byte across all 7 request metadata and payload fields (`messages`, `tools`, `chat_template_kwargs`, `tool_choice`, `analysis_step`, `action`, `request_index_within_turn`).
2. **Exact Token Conservation Closure (`E1`):**
   - `g50t` per-game completion sum (`15` paired responses): `28,901` tokens.
   - `g50t` root `requests.jsonl` completion (`idx=15`): `2,778` tokens (`reasoning_tokens = 2,391`, `prompt_tokens = 19,438`, `cached_tokens = 16,064`, `finish_reason = "tool_calls"`).
   - `28,901 + 2,778 = 31,679` == exact `benchmark.json` `solver_note = "tokens=31679"` (`diff = 0`).
   - Across all 25 games, `468,510 + 2,778 = 471,288` == exact sum of all 25 `solver_note` values (`471,288`, `diff = 0`).
3. **Exact `serve.log` Line Verification (`E0`/`E1`):**
   - `serve.log` LF line `2005`: `[2026-10-30 05:30:19] ReqTimeStats(rid=b16dc5d9a7204a7c8eca157b7bf600af, input_len=19438, cached_input_len=16064, output_len=2780, attempts=1, type=mixed): queue_duration=0.66ms, ..., forward_duration=16816.32ms`.
   - `input_len = 19,438 == prompt_tokens` (`19,438`) and `cached_input_len = 16,064 == cached_tokens` (`16,064`).
4. **Why `idx=15`'s Response Landed in Root `requests.jsonl` (`E2` / `E3`):**
   In `tool_agent.py:3314`, `_resolve_request_log_path(state_path)` resolves `<run_root>/<game_stem>_p0_requests.jsonl` via `_resolve_run_artifact_location(state_path)` (`tool_agent.py:3234`) when `game_stem` is present, and otherwise writes `requests.jsonl` in the root run/working directory. While both the `request` log call (`tool_agent.py:6767`) and `response` log call (`tool_agent.py:6788`) run around the same API invocation, `idx=15`'s request landed in `g50t-5849a774_p0_requests.jsonl` whereas its response landed in root `requests.jsonl` (`submissions/arc3_v10_verified/requests.jsonl`), with the framework still crediting `idx=15`'s `2,778` completion tokens into `benchmark.json`'s `solver_note = "tokens=31679"`.
5. **Impact on Prefix-Cache Metrics (`E1`):** On `g50t` post-eviction turns (`idx >= 13`), `idx=15` was a `pure_append` turn achieving `16,064 / 19,438 = 82.64%` KV hit rate. Excluding `idx=15` lowered `g50t`'s post-eviction hit rate to `61.45%` (`17,664 / 28,744`), whereas restoring `idx=15` brings `g50t` post-eviction KV reuse to **`70.00%`** (`33,728 / 48,182`), consistent with SGLang RadixAttention recovering after prefix stabilization.

---

## 3. Why `serve.log` Contains the 4 Timeout Server Records — and Why They Are NOT Substituted 1:1 into Client Usage Tables (`E0`/`E1`)

All `4` client-timed-out requests completed on the SGLang server (`output_len > 0` in `serve.log`) **without logging `POST /v1/chat/completions HTTP/1.1 200 OK`**, because SGLang logs `ReqTimeStats` as the scheduler finishes the batch/request even if the downstream `uvicorn` / HTTP client connection already closed after `read_timeout`:

- Sum of server-completed telemetry across the `4` timeout requests (`serve.log` LF lines `1562, 1723, 1787, 1879`):
  - `input_len` = `32,084 + 33,349 + 30,622 + 24,428 = 120,483` tokens
  - `cached_input_len` = `26,240 + 5,056 + 5,056 + 5,056 = 41,408` tokens (`34.37%` of timeout server input)
  - `output_len` = `2,902 + 1,067 + 1,713 + 1,928 = 7,610` tokens
  - `cached / prompt` patterns remain physically consistent with their prefix transition classes: `cn04 idx=13` (`pure_append`) reused `26,240 / 32,084` (`81.79%`), while `vc33 idx=19` (`5,056`), `r11l idx=13` (`5,056`), and `cd82 idx=14` (`5,056`, `fifo_eviction`) matched ONLY the `5,056`-token system+tools header!

**Exact Empirical Rejection of Naive 1:1 `output_len -> completion_tokens` Substitution (`E1`):**  
Comparing `serve_output_len - completion_tokens` across all **`353`** paired HTTP-200 responses yields:

| Difference `serve_output_len - completion_tokens` | Count (`353` All Client Responses) | Count (`350` Unique 1:1) | Count (`3` Colliding Time-Disambiguated) |
|---:|---:|---:|---:|
| **`0`** | `104` | `101` | `3` |
| **`+1`** | `56` | `56` | `0` |
| **`+2`** | `111` | `111` | `0` |
| **`+3`** | `82` | `82` | `0` |
| **Total** | **`353`** | **`350`** | **`3`** |

Because `serve.log`'s internal scheduler `output_len` exceeds OpenAI API `usage.completion_tokens` by `0, 1, 2, or 3` tokens (`EOS`/stop/delimiter tokens stripped during response serialization) — and because `serve.log` does not split `reasoning_tokens` vs visible tool-call output — substituting `7,610` directly into OpenAI `completion_tokens` would introduce up to `4 * 3 = 12` tokens of measurement error AND fabricate client-side delivery that never occurred (since the client closed the socket before parsing response JSON).  

Under HINAGI's **no-imputation (no-backfill) policy**, both facts should be reported cleanly side-by-side:
1. **Client API usage (`N/A` on 4 timeouts):** `353` received responses total `471,288` completion tokens (`468,510` in per-game JSONL + `2,778` in root `requests.jsonl`).
2. **Server compute telemetry (`serve.log`):** All `4` timed-out requests burned `120,483` prefill (`79,075` uncached) and `7,610` SGLang `output_len` tokens on GPU (`360/360` total `ReqTimeStats` = `3` warmups + `353` delivered + `4` client-aborted completions).

---

## 4. Timeout Trigger Mechanism Interaction (`Cell 4` + `Cell 16` + `solver.py`, `E0`/`E2`)

1. **`solver.py:536-553` (`request_timeout_seconds`):** Computes remaining game wallclock budget `remaining = max_runtime_s_per_game - (time.monotonic() - self.started_at)`.
2. **`v10_reference.ipynb` Cell 16 (`L61-L75`):** Patches two safeguards that *failed to prevent* these 4 timeouts:
   - `_patched_request_timeout` clamps `max(30.0, float(t))` (`Cell 16 L62-L68`). Thus, near game end, when `< 30s` remained (even with `_patched_runtime_limit_reached` checking `>= max(30.0, max_runtime_s_per_game - 15.0)` between steps!), two possibilities allowed late-step requests to hit `30.00s`: (a) `vc33` (`idx=19`) and `r11l` (`idx=13`) entered a new request just before hitting the `-15s` guard so `remaining` clamped to **`30.00s`**, which `32.20s` and `32.14s` exceeded; (b) `cn04` (`50.92s`) and `cd82` (`49.14s`) occurred with `~50s` remaining on the game timer, so `request_timeout_seconds` stayed above `30.0s`, yet uncached prefill (`cd82`: `5.0s` queue + `48.6s` fwd) or long reasoning (`cn04`: `2,902` output tokens, `52.56s` fwd) still exceeded `50.92s` and `49.14s`.
3. **Why V10 `Cell 0` Claim Was Contradicted (`E0`):** `v10_reference.ipynb` Cell 0 advertised *"to guarantee zero `Read timed out` HTTP failures"*; live execution produced **4** `Read timed out` terminations directly visible in `arc-agi-3-sota.log`.
