# 05 — FIFO Eviction Trigger & RadixAttention Prefix-Cache Reproduction

**Scope:** Independent offline reproduction of all `9/9` FIFO eviction events in `submissions/arc3_v10_verified/`, live `text_token_calibration:` matching (`45/45`), full `352`-response vs `353`-response prefix-cache stratification, Red Team C1 header-hit resolution, `vc33` / `g50t` trajectories, and observational vs causal bounds.  
**Data Sources:** `02_REQUEST_RESPONSE_RECONSTRUCTION.csv`, `03_TOKEN_ACCOUNTING_RECONCILIATION.csv`, `08_REPRODUCIBILITY_MANIFEST.json`, `reconstruct_v10_forensics.py`.

---

## 1. Live Token Calibration Replay (`45/45` Exact Match, `E0`/`E1`/`E2`)

Before testing why FIFO eviction fired on `9` games with only `11`–`21` retained assistant turns (far below `ARC3_HISTORY_ASSISTANT_TURNS = 36`), we verified that offline token estimation matches V10's live runtime estimator byte-for-byte:

1. **Method & Budget Constants (`Cell 4` + `tool_agent.py`):**
   - `LOCAL_ANALYZER_CONTEXT_WINDOW = (44 + 12) * 1024 = 57,344`
   - `LOCAL_ANALYZER_MAX_OUTPUT = 12 * 1024 = 12,288` (`self._reply_reserve_tokens` at `tool_agent.py:3498`)
   - `_REQUEST_SAFETY_MARGIN_TOKENS = 512` (`tool_agent.py:205, 3505`)
   - Client input token budget (`tool_agent.py:3506-3509`): `B_tok = 57,344 - 12,288 - 512 = 44,544` (`ARC3_CONTEXT_DRAIN_TOKENS = 16,384`, target `B_target = 44,544 - 16,384 = 28,160` at `tool_agent.py:6471-6472`).
   - Calibration clamp range: `_calibrate_from_usage` (`tool_agent.py:5962-6008`) initializes `cal = 3.0` chars/token and updates `clamped = max(1.8, min(4.8, ...))`, logging `text_token_calibration: ...`.
   - Vision patch token formula (`tool_agent.py:2974` `_split_messages_for_estimate`): `ceil(W / 32) * ceil(H / 32) + 2` sentinels (`640x640` upscaled grid image -> `20 * 20 + 2 = 402` tokens per image, with fallback `402`).
2. **Exact Runtime Log Verification (`E0`/`E1`):**
   - Contrary to the draft manuscript's statement (`ARC3_Paper_v10_draft.tex:933`) that calibration was *"unlogged at runtime"*, `reconstruct_v10_forensics.py` located **`45`** `text_token_calibration:` records emitted across **`42`** `analysis` event transcripts in `submissions/arc3_v10_verified/artifacts/*_p0_events.jsonl`, plus **`2`** lines in `submissions/arc3_v10_verified/prompts/*_p0.log` (`ft09-0d8bbf25_p0.log:941` at `3.14` chars/token and `sk48-d8078629_p0.log:795` at `3.19` chars/token).
   - Replaying `_split_messages_for_estimate` + `_estimate_payload_tokens` across all `357` requests matched **`45/45`** live `text_token_calibration:` records across `clamped` (`.2f`), `images`, and `text chars` with **`0` mismatches**.

---

## 2. Exact FIFO Trigger Reproduction on All `9` Evicted Games (`E2`)

Using the live calibrated `cal` state at each step, we reconstructed the pre-trim message buffer (`raw_pre = [msgs[0], *pm[1:], *new_tail]`, where `pm` is request `idx-1` and `new_tail` is the suffix after the surviving prefix anchor `msgs[1]`) and ALSO the end-of-step image-windowed buffer (`win4_eos`, reflecting `_apply_history_image_window(..., 4)` executed at `tool_agent.py:6321` right before `_trim_messages_for_context` at `tool_agent.py:6323`):

| Game ID | Req `idx` | Exact Trim Site (`tool_agent.py`) | `cal` | `msgs` (`prev->cur`) | `pre_raw_est` (`> 44,544`?) | `pre_win4_eos_est` (`> 44,544`?) | `post_no_opener` (`<= 28,160`?) | `post_full` (submitted) | Ret. Proof Notes |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| **`ar25-0c556536`** | `17` | `L6323_end_of_step` | `3.30` | `44 -> 19` | **`47,360`** (Yes) | **`44,748`** (Yes) | **`25,678`** (Yes) | `27,491` (Yes) | Crossed `44,544` at end of step 11 even after 4-img window (`44,748 > 44,544`) |
| **`ft09-0d8bbf25`** | `13` | `L6323_end_of_step` | `2.89` | `31 -> 17` | **`47,614`** (Yes) | **`44,972`** (Yes) | **`27,360`** (Yes) | **`29,203`** (`> 28,160`!) | Mathematical proof of `L6323`: `post_full > 28,160` impossible under `L6699` |
| **`r11l-495a7899`** | `12` | `L6323_end_of_step` | `3.125` | `28 -> 14` | **`54,344`** (Yes) | **`52,276`** (Yes) | **`28,102`** (Yes) | **`29,770`** (`> 28,160`!) | Mathematical proof of `L6323`: `post_full > 28,160` impossible under `L6699` |
| **`sb26-7fbdac44`** | `22` | `L6323_end_of_step` | `3.30` | `55 -> 24` | **`51,213`** (Yes) | **`49,060`** (Yes) | **`27,199`** (Yes) | **`28,552`** (`> 28,160`!) | Mathematical proof of `L6323`: `post_full > 28,160` impossible under `L6699` |
| **`bp35-0a0ad940`** | `14` | `L6699_start_of_step_or_resume` | `3.05` | `32 -> 18` | **`45,450`** (Yes) | `43,613` (No) | `23,746` | **`25,183`** (Yes) | End-of-step `43,613 <= 44,544`; crossed upon appending opener (`45,450`) |
| **`cd82-fb555c5d`** | `14` | `L6699_start_of_step_or_resume` | `3.30` | `36 -> 16` | **`46,048`** (Yes) | `43,223` (No) | `25,655` | **`27,681`** (Yes) | End-of-step `43,223 <= 44,544`; crossed upon appending opener (`46,048`) |
| **`cn04-2fe56bfb`** | `12` | `L6699_start_of_step_or_resume` | `3.26` | `30 -> 17` | **`46,793`** (Yes) | `43,936` (No) | `24,166` | **`26,222`** (Yes) | End-of-step `43,936 <= 44,544`; crossed upon appending opener (`46,793`) |
| **`g50t-5849a774`** | `13` | `L6699_start_of_step_or_resume` | `3.30` | `30 -> 7` | **`45,045`** (Yes) | `42,523` (No) | `12,814` | **`14,937`** (Yes) | End-of-step `42,523 <= 44,544`; crossed upon appending opener (`45,045`) |
| **`vc33-5430563c`** | `18` | `L6699_start_of_step_or_resume` | `3.30` | `44 -> 18` | **`45,627`** (Yes) | `42,769` (No) | `25,155` | **`27,212`** (Yes) | End-of-step `42,769 <= 44,544`; crossed upon appending opener (`45,627`) |

### Key Verification Takeaways
- **`9/9` exceed `B_tok = 44,544` pre-trim (`E2`):** `pre_raw_est` spans `45,045` (`g50t`) to `54,344` (`r11l`).
- **Highest non-evicted game (`E1`/`E2`):** `tr87-cd924810` `idx=16` reached `est_tokens_calibrated = 44,318` (`226` tokens below `44,544`; actual server `prompt_tokens = 44,124`), remaining completely un-evicted across `17` requests (`30` actions).
- **Clear separation (`4` at `L6323` vs `5` at `L6699`):** `ar25`, `ft09`, `r11l`, and `sb26` exceeded `44,544` at end-of-step (`pre_win4_eos_est = 44,748..52,276`), whereas `bp35`, `cd82`, `cn04`, `g50t`, and `vc33` stayed below `44,544` at end-of-step (`42,523..43,936`) and crossed `44,544` when the next `user` opener was appended at `L6699` (`pre_raw_est = 45,045..46,793`).
- **Max image count bound (`E1`):** Maximum `image_count_client` across all `357` requests is `10` (`wa30-ee6fef47` `idx=7`), matching `ARC3_HISTORY_IMAGE_KEEP=4` historical user turns (`<= 2` images each: board + diff) plus active step images.
- **Note on Minor Estimator Difference in `ARC3_Paper_v10_draft.tex:933`:** The `.tex` draft preserves the exact `4` (`ar25, ft09, sb26, r11l`) vs `5` (`g50t, bp35, cd82, vc33, cn04`) split, while quoting slightly shifted pre-trim values (`ar25: 44,729` vs `44,748`, `g50t: 44,645` vs `45,045`, `cd82: 45,230` vs `46,048`) consistent with an earlier offline script excluding `tool_choice` / one image delta (`19`–`400` tokens). Our `reconstruct_v10_forensics.py` implementation matches **45/45** live `text_token_calibration:` records exactly.

---

## 3. Dual Prefix-Cache Telemetry (`352` Per-Game vs `353` Full Client, `E1`)

Transition classes are computed strictly chronologically across requests within each game (`initial`: `idx=0`; `pure_append`: prior message list is an exact prefix; `image_omit_mutation`: message count grows/matches cleanly except upstream `[grid image omitted from history]` replacement; `fifo_eviction`: leading `user`-anchored history block deleted).

### 3A. `352`-Response Per-Game View (`build_v10_eviction_token_tables.py` Scope)
| Prefix Transition | Responses | Unpaired Requests | `prompt_tokens` | `cached_tokens` | `uncached_prompt` | Token-Wtd Hit % | Share of All Uncached % | `completion_tokens` | `reasoning_tokens` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `initial` | `25` | `0` | `151,030` | `40,576` | `110,454` | `26.87%` (`26.8662%`) | `4.25%` (`4.2512%`) | `3,337` | `687` |
| `pure_append` | `250` | `2` (`cn04`, `g50t` root) | `4,600,703` | `4,073,664` | `527,039` | **`88.54%`** (`88.5444%`) | `20.29%` (`20.2850%`) | `325,502` | `283,569` |
| `image_omit_mutation` | `69` | `2` (`r11l`, `vc33`) | `2,131,863` | `331,072` | `1,800,791` | **`15.53%`** (`15.5297%`) | `69.31%` (`69.3099%`) | `121,017` | `104,733` |
| `fifo_eviction` | `8` | `1` (`cd82`) | `195,282` | `35,392` | `159,890` | **`18.12%`** (`18.1235%`) | `6.15%` (`6.1539%`) | `18,654` | `15,016` |
| **Mutations Combined** | **`77`** | **`3`** | `2,327,145` | `366,464` | `1,960,681` | `15.75%` | **`75.46%`** | `139,671` | `119,749` |
| **Total (`352` view)** | **`352`** | **`5`** | **`7,078,878`** | **`4,480,704`** | **`2,598,174`** | **`63.30%`** (`63.2968%`) | **`100.00%`** | **`468,510`** | **`404,005`** |

### 3B. `353`-Response Full-Client View (+ `g50t` Root `requests.jsonl` `idx=15`, `pure_append`)
| Prefix Transition | Responses | Unpaired (True Timeouts Only) | `prompt_tokens` | `cached_tokens` | `uncached_prompt` | Token-Wtd Hit % | Share of All Uncached % | `completion_tokens` | `reasoning_tokens` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `initial` | `25` | `0` | `151,030` | `40,576` | `110,454` | `26.87%` (`26.8662%`) | `4.25%` (`4.2457%`) | `3,337` | `687` |
| `pure_append` | **`251`** | `1` (`cn04`) | **`4,620,141`** | **`4,089,728`** | **`530,413`** | **`88.52%`** (`88.5195%`) | `20.39%` (`20.3884%`) | **`328,280`** | **`285,960`** |
| `image_omit_mutation` | `69` | `2` (`r11l`, `vc33`) | `2,131,863` | `331,072` | `1,800,791` | **`15.53%`** (`15.5297%`) | `69.22%` (`69.2200%`) | `121,017` | `104,733` |
| `fifo_eviction` | `8` | `1` (`cd82`) | `195,282` | `35,392` | `159,890` | **`18.12%`** (`18.1235%`) | `6.15%` (`6.1460%`) | `18,654` | `15,016` |
| **Mutations Combined** | **`77`** | **`3`** | `2,327,145` | `366,464` | `1,960,681` | `15.75%` | **`75.37%`** | `139,671` | `119,749` |
| **Total (`353` view)** | **`353`** | **`4`** | **`7,098,316`** | **`4,496,768`** | **`2,601,548`** | **`63.35%`** (`63.3498%`) | **`100.00%`** | **`471,288`** | **`406,396`** |

---

## 4. Red Team C1 Header-Preservation Resolution (`E0`/`E1`/`E3`)

An independent Red Team critique (`ARC3 Paper v9 C1`) flagged an apparent contradiction: if the shared system/tool prompt header is `5,056` tokens, why did `8` `fifo_eviction` responses cache `35,392` (`< 8 * 5,056 = 40,448`) and `69` `image_omit_mutation` responses cache `331,072` (`< 69 * 5,056 = 348,864`)?

Direct per-request histogram inspection of `02_REQUEST_RESPONSE_RECONSTRUCTION.csv` resolves the arithmetic completely (`E1`):
- **`fifo_eviction` (`n = 8` responses):**
  - `5,056` cached tokens: **`7` responses** (`ar25 idx=17`, `bp35 idx=14`, `ft09 idx=13`, `g50t idx=13`, `r11l idx=12`, `sb26 idx=22`, `vc33 idx=18`) -> `7 * 5,056 = 35,392`.
  - `0` cached tokens: **`1` response** (`cn04-2fe56bfb idx=12`, `serve.log L1476`, `2026-10-30 05:25:02`, `prompt_tokens=26,297`).
  - Note the timed-out 9th FIFO request (`cd82-fb555c5d idx=14`, `serve.log L1879`) ALSO hit **`5,056`** cached tokens on the server!
- **`image_omit_mutation` (`n = 69` responses):**
  - `0` cached tokens: **`16` responses** (`ar25` `[9,11]`, `cn04` `[7,11]`, `lp85` `[7,8]`, `r11l` `[7]`, `sb26` `[7,10,11]`, `sp80` `[9,10,12]`, `vc33` `[10,13,14]`).
  - `5,056` cached tokens: **`46` responses**.
  - `> 5,056` partial prefixes (when an internal user-turn omission left earlier history turns intact): `8,640` (`1`), `9,600` (`1`), `10,112` (`2`), `11,392` (`2`), `37,248` (`1`).
  - Sum: `(16 * 0) + (46 * 5,056) + 8,640 + 9,600 + 2*10,112 + 2*11,392 + 37,248 = 331,072` exact.
- **`initial` (`n = 25` responses):** `{0: 17, 5056: 6, 5120: 2}` = `40,576` (`5,056`-token header hit on `6` games; `5,120` header+opener prefix on `2`; cold `0` on `17`).
- **Observational Boundary (`E3`):** Why `cn04 idx=12` (`fifo_eviction`) and `16/69` `image_omit_mutation` requests received `0` cached tokens at position `0` (despite identical system+tools bytes) cannot be isolated from client logs alone: internal SGLang server logs do not dump RadixTree page eviction / concurrent 10-stream KV pressure / cache-block misses vs worker scheduling. Therefore, manuscripts must describe the observed `{0, 5056}` bimodal header hit distribution directly rather than assuming every mutation response preserves `5,056` tokens.

---

## 5. `vc33` & `g50t` Case Studies + Observational Cohort Caveat (`E0`/`E1`/`E3`)

1. **`vc33-5430563c` Full Context Lifecycle (`02_REQUEST_RESPONSE_RECONSTRUCTION.csv`):**
   - `idx=0..17` (`step=1..8`, `act=1..24`): Reaches `2/7` levels (`score = 9.42956349`). At `idx=17` (`step=8`, `act=24`), `msgs=44`, `est=43,365`, `prompt_tokens=42,353`, `cached=5,056` (`image_omit_mutation`).
   - `idx=18` (`step=9`, `act=26`, `serve.log L1669`): `L6699_start_of_step_or_resume` trims `44 -> 18` messages (`pre_raw_est=45,627 -> post_est_full=27,212 <= 28,160`), `prompt_tokens=26,120`, `cached=5,056` (`19.36%`). Crucially, the surviving suffix preserves `vc33`'s Level-3 plan (`Phase 1`: `9x(56,46)` plus `1` non-changing move `act=26..34`), consuming `5,766` completion tokens (`100.16s` forward duration) while advancing through `act=34` (`hgen=25,854`).
   - `idx=19` (`step=10`, `act=35`, `serve.log L1723`): Enters final turn with `< 30s` remaining (`_patched_request_timeout` clamps `read timeout = 30.00s`); server queues `4.99s` + computes `27.21s` (`32.20s` > `30.00s`, `in=33,349`, `ca=5,056`, `out=1,067`), closing the client socket before response delivery (`arc-agi-3-sota.log:248`). Note V6 smoke (`submissions/arc3_v6_smoke_verified/benchmark.json`) scored `21.43` (`3/7` levels, `43` actions) on `vc33`.
2. **`g50t-5849a774` Post-Eviction Recovery in Dual Views (`E1`):**
   - Pre-eviction (`idx=0..12`): `209,856 / 295,529 = 71.01%` KV hit (`26,532` action-attributed `hgen`).
   - Boundary (`idx=13`, `step=6`, `L6699`): `30 -> 7` messages (`45,045 -> 14,937`), `prompt_tokens=12,650`, `cached=5,056`.
   - Post-eviction `352`-resp view (`idx=13..14`): `17,664 / 28,744 = 61.45%`.
   - Post-eviction `353`-resp view (`idx=13..15`, including root `requests.jsonl` `idx=15` `16,064/19,438 = 82.64%`): **`33,728 / 48,182 = 70.00%`**.
3. **Strict Observational (Non-Causal) Interpretation (`E1`/`E3`):**
   - Evicted (`n=9`) vs Non-Evicted (`n=16`) show `58.44%` vs `68.03%` aggregate cache hit (`353`-resp view) and `4/9` vs `0/16` HTTP timeouts, alongside higher mean score (`6.52` vs `0.77`, driven by `ft09 = 28.57`, `vc33 = 9.43`, `ar25 = 8.33`).
   - Because eviction occurs conditionally on **long trajectories and cumulative token growth**, these cohort metrics are **observational descriptors**, NOT causal estimates of eviction's effect on score, cache miss rate, or timeout risk.
