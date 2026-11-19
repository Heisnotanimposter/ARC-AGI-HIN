# ARC-AGI-3 Version History & Evidence Ledger (Paper Track v2)

**Purpose.** This ledger separates remote Kaggle Kernel versions, competition submissions, local smoke benchmarks, and research-only work. A number in the Kaggle Kernel Version column is not assumed to be a competition submission ID.

## 1. Verified score and artifact anchors

| Artifact / submission | Evidence | Value | Interpretation |
|---|---|---:|---|
| V6 / Submission `57758308` | Remote provenance ledger, V6 notebook snapshot, project score record | **33.38** | Highest verified on-time public score; primary paper artifact. |
| V9 / Submission `57791530` | Remote submission audit and score record | **0.00** | Official zero-score submission. Local commit log shows segmentation worker crash; exact private-run causal chain not independently observed. |
| V10 / Submission `57827259` | Later Phase 6.4/6.5 reports | **8.03** | Official result recorded in later forensic report. Earlier Phase 4 snapshot listed it as pending; preserve this provenance history. |
| V13 / Submission `57912660` | User-provided Kaggle result card | **23.41** | `Succeeded (after deadline)`; scored execution but not an on-time competition result. |

## 2. Kernel version ledger

| Version | Retained artifact / observation | Metrics | Status / confidence | Allowed paper wording |
|---|---|---|---|---|
| V1 | No individually mapped remote notebook or submission record in supplied archive | None attributable | **Unresolved** | “The retained archive does not preserve a one-to-one V1 record.” |
| V2 | No individually mapped remote notebook or submission record | None attributable | **Unresolved** | Same; do not assign early named-run scores to V2. |
| V3 | No individually mapped remote notebook or submission record | None attributable | **Unresolved** | Same. |
| V4 | No individually mapped remote notebook or submission record | None attributable | **Unresolved** | Same. |
| V5 | No individually mapped remote notebook or submission record | None attributable | **Unresolved** | Same. |
| V6 | Full 23-cell snapshot; SHA-256 `bb532e8c502ac5ce72c36918a2b1ac90e0de3cc96f5bdc70682953914466c90e` | Official public score **33.38**; local 25-game smoke sum **49.8413**, mean **1.9937**, 7/25 progressing, 10 levels | **Verified baseline** | “Best verified on-time submission in this lineage.” Keep official and local metrics separate. |
| V7 | Full remote kernel version in provenance report | 400 actions in commit/smoke run; no official score identified | **Commit-only evidence** | “Commit-mode action telemetry; no verified competition score.” |
| V8 | Full remote kernel version in provenance report | 409 actions in commit/smoke run; no official score identified | **Commit-only evidence** | Same. |
| V9 | Submission `57791530`; code hash recorded in remote ledger | Official **0.00**; local commit log: 0 gameplay actions, segmentation `UnboundLocalError` | **Score verified; cause provisional** | “Zero-score submission; matching local version log contains a worker crash. The private scoring-run causal link is unobserved.” |
| V10 | Full remote notebook snapshot; SHA-256 `5f940b9615dee4ab337c564e465fb1701635cdd842b66bbeacc83372e71c5b3b` | Official **8.03** in later Phase 6.4/6.5 reports; local smoke 70.9395 sum, 2.8376 mean, 9/25 progressing, 13 levels, 386 actions, 378,304 tokens | **Official score later recorded; local smoke independently verified** | Explicitly label local smoke as public 25-game commit mode, not leaderboard score. |
| V11 | Reported two-cell `re86` probe derivative; bootstrap failure from broad wheel glob (150+ wheels) reported in V12 probe report | `CalledProcessError`, return code 1; no score | **Probe / failed bootstrap** | “A targeted probe failed at dependency discovery; not a full competition solver.” |
| V12 | Two-cell `re86` SPACE probe; SHA from source report `8c46f121...` | 55s run; real game class loaded; canonical 19-action replay; one SPACE at each of two positions; two local pixel changes, zero level delta and zero reward | **Mechanic probe, no level advance** | “A controlled intervention changed local state but did not advance the level.” |
| V13 | Full 23-cell candidate; SHA-256 `6b4b57d31f13723db9ade638a9c1ea5eb453ea7885ac619c0f2b15f29d0fe38c`; scriptVersionId `364906609` | Submission `57912660`: **23.41**, succeeded after deadline | **Scored after deadline** | “Later follow-up candidate; does not replace V6’s on-time best.” |

## 3. Pre-V6 historical experiments (not safely mappable to V1–V5)

The README preserves these named runs and outcomes, but not their exact remote kernel-version numbers. They should be listed as an unnumbered early-experiment series rather than falsely relabeled V1, V2, etc.

| Named run | Recorded score | Recorded lesson | Evidence qualification |
|---|---:|---|---|
| `TestHIN1` / `ARCHIN2` / `taaf-model` | 1.19–2.97 | Unbounded physical actions produced oscillation and repeated fatal transitions | Historical summary; not individually version-mapped. |
| `Duck Qwen3.8 Anim Base` | 3.39 | Naive vLLM serving without speculative decoding; context thrashing and blind interaction | Historical summary. |
| `ARC3 M2 Solution` | 24.35 | Initial runtime port before memory-budget corrections | Historical summary. |
| `ARC-AGI-3 Milestone 2 Solution` | 25.41 | Unquantized/partial-cache configuration without tail fade | Historical summary. |
| `Try merging it—you might get lucky and win gold` | 25.26 | Merged trajectories reportedly reduced prefix-cache hit rate from 93.4% to below 40% | Historical summary; retain “reported” unless raw telemetry is appended. |
| `ARC-AGI-3 Milestone 2 Solution ac8172` | 28.16 | Qwen3.8-Flash-Next + Albucino MTP, 10 streams, 128K-to-57K context trimming | Historical summary. |
| Earlier milestone SGLang runtime (`arc3-1025-lb3071.ipynb`) | 30.71 | Reference Milestone 2 baseline (`reference/arc3_franzen_m2/arc3-1025-lb3071.ipynb`). Cell-by-cell audit confirms 20 of 23 cells are byte-identical to V6 (`57758308`), including Cell 2 (`498,799` chars, SHA-256 `6fdcd1ae...`), Cell 12 (`18,718` chars), `_PriorityGate`/`ProgressPace`, `150/30` history policy, `ARC3_BATCH_NOOP_BLOCK=1`, and `ARC3_STALE_STATE_BLOCK=1`. | Direct cell-by-cell notebook comparison (`arc3-1025-lb3071.ipynb` vs. `ARC3_V6_Official_Artifact_57758308.ipynb`). |

## 4. V6 architecture and exact lineage vs. Milestone 2 (`30.71`)

- **Inherited from Milestone 2 (`arc3-1025-lb3071.ipynb`, 20 of 23 cells byte-identical):**
  - **Cell 2 Runtime Patch (`498,799` chars, SHA-256 `6fdcd1ae...`):** Fatal-action ledger (`_death_ledger_record`, `_fatal_prefix_match`, `KnownDeathActionError`), intra-snippet repeat guard, `NoopRepeatGuard`, HUD border cropping (`ARC3_NOOP_GUARD_BORDER=4`, which crops 4-cell HUD borders during frame comparison rather than acting as a standalone state-action blocker), and `_PriorityGate` / `ProgressPace` / `Tail Fade` scheduling.
  - **Cell 12 Serving Stack (`18,718` chars):** Main model `Qwen3.8-Flash-Next` (W4A16 AutoRound), speculative drafter `Albucino` INT4-G32 MTP (three draft steps), `Pennyroyal v2.5.3` + SGLang, `MAXREQ=10`, `ARC3_MAX_ACTIVE_STREAMS=10`, temperature 0.7, top-p 0.95, top-k 20.
  - **Shared Cell 4 Settings:** 128K context (`(116+12)*1024`), 58K drain, `150/30` assistant-turn history (`ARC3_HISTORY_ASSISTANT_TURNS=150`, `ARC3_HISTORY_TURN_DRAIN=30`), `LOCAL_ANALYZER_TOOL_STEPS=0`, `ARC3_BATCH_NOOP_BLOCK=1`, `ARC3_STALE_STATE_BLOCK=1`.
- **V6 Cell 4 Configuration Changes (`5,213` $\to$ `6,256` chars):**
  - Added dynamic `/kaggle/input` mount discovery (`_discover_mount`), enabled `EXPOSE_RESET=on`, and activated four guard flags already implemented in Cell 2: `ARC3_REPEAT_STATE_GUARD=1`, `ARC3_DEATH_REPEAT_GUARD=1`, `ARC3_DEATH_GUARD_LOOKAHEAD=1`, and `ARC3_BOARD_DUMP_GUARD=1`. Note that `ARC3_NOOP_REPEAT_GUARD` remained `OFF` in V6.
- **V6 Cell 16 Newly Authored Code (`1,144` $\to$ `15,838` chars):**
  - Injected five Python sandbox helpers into `_pts._SANDBOX_BOOTSTRAP`: `find_objects` (adapter reading pre-existing `frame.segmentation["nodes"]`), `bfs_shortest_path`, `a_star_search`, `plan_tsp_order` (exact permutations for $\le 7$ targets, greedy nearest-target chaining for $> 7$ targets), and `solve_sokoban` (40,000-state cap).
- **Audited Cell 16 Implementation Defect & Test Attribution:**
  - In V6 Cell 16, `bfs_shortest_path` and `a_star_search` execute `walkable.add(board[gr][gc])` to step onto the goal cell; when wall obstacles share the goal tile's color, all walls of that color become passable (`solve_sokoban` similarly adds player, box, and target colors to its global walkable set). Furthermore, `tests/test_phase6_5_fail_closed.py` tests the later 24,071-char candidate (`arc3_sota_milestone_plus.ipynb`, matching V13's Cell 16), not V6's 15,838-char Cell 16.

Do not describe V6 as a pure symbolic solver, and do not attribute inherited Milestone 2 Cell 2/12 runtime machinery as newly written in V6.

## 5. V6-to-V10 regression evidence

| Change | V6 | V10 | Evidence class |
|---|---:|---:|---|
| Assistant history | 150 turns | 36 turns | Controlled local `vc33` ablation supports multi-death memory degradation at 36 turns. |
| Context / drain | 128K / 58K | 56K / 16K | Mechanism-based hypothesis; independent contribution not isolated. |
| Tool steps | 0 | 12 | Plausible operational factor; no independent full-suite ablation. |
| Forced quantum handover | absent | every 18K tokens | Scheduler intervention verified in code; exact score contribution unquantified. |
| Readiness health gate | absent | present | Operational fix; retained in later candidate. |
| Request timeout clamp | absent | present | Operational fix; retained. |
| Runtime cushion | absent | present | Operational fix; retained. |
| Spatial nodes / path fixes | basic | enriched | Verified code changes; contribution to score not separately measured. |

Official result difference: 33.38 (V6) to 8.03 (V10), a decline of 25.35 points (about 75.9% relative to V6). This is an observed version-level difference, not a causal estimate for any one parameter.

## 6. Local evaluations that must not be presented as leaderboard scores

| Run | Games | Progressing | Levels cleared | Score sum | Mean per 25 games | Notes |
|---|---:|---:|---:|---:|---:|---|
| V6 local public-game smoke | 25 | 7 | 10 | 49.8413 | 1.9937 | Local scorecard; not Kaggle score 33.38. |
| V10 local public-game smoke | 25 | 9 | 13 | 70.9395 | 2.8376 | Local scorecard; not Kaggle score 8.03. `ft09` contributed 40.28% of sum. |
| Phase 6.4 integrated local candidate | 25 | 22 | 39 | 260.3968 | 10.4159 | Known/public game replay and state-conditioned solver portfolio; not blind hidden-test evaluation, not V13 official result. |
| Phase 6.3 portfolio ledger | 25 | 22 | 40 | 259.0476 | 10.3619 | Local verified TAAF label; mixed provenance (fixed plans, demonstrations, replay, BFS). |

The apparent mismatch—V10 local smoke exceeding V6 while its official score was much lower—is a key generalization and evaluation-discipline finding. The local 25-game suite is not an unbiased proxy for the hidden 110-game competition set.

### 6.1 Per-game local smoke comparison (25 public games)

| Game | Total levels | V6 cleared / score | V10 cleared / score | V10−V6 score delta |
|---|---:|---:|---:|---:|
| ar25 | 8 | 0 / 0.0000 | 2 / 8.3333 | +8.3333 |
| bp35 | 9 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| cd82 | 6 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| cn04 | 6 | 1 / 4.7619 | 1 / 4.7619 | 0.0000 |
| dc22 | 6 | 1 / 4.7619 | 0 / 0.0000 | -4.7619 |
| ft09 | 6 | 0 / 0.0000 | 3 / 28.5714 | +28.5714 |
| g50t | 7 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| ka59 | 7 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| lf52 | 10 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| lp85 | 8 | 2 / 8.3333 | 1 / 2.7778 | -5.5556 |
| ls20 | 7 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| m0r0 | 6 | 1 / 4.7619 | 0 / 0.0000 | -4.7619 |
| r11l | 6 | 0 / 0.0000 | 1 / 4.7619 | +4.7619 |
| re86 | 8 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| s5i5 | 8 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| sb26 | 8 | 0 / 0.0000 | 1 / 2.7778 | +2.7778 |
| sc25 | 6 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| sk48 | 8 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| sp80 | 6 | 0 / 0.0000 | 1 / 4.7619 | +4.7619 |
| su15 | 9 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| tn36 | 7 | 1 / 3.5714 | 0 / 0.0000 | -3.5714 |
| tr87 | 6 | 0 / 0.0000 | 1 / 4.7619 | +4.7619 |
| tu93 | 9 | 0 / 0.0000 | 0 / 0.0000 | 0.0000 |
| vc33 | 7 | 3 / 21.4286 | 2 / 9.4296 | -11.9990 |
| wa30 | 9 | 1 / 2.2222 | 0 / 0.0000 | -2.2222 |
| **Total** | **183** | **10 / 49.8413** | **13 / 70.9395** | **+21.0982** |

This table is useful for analyzing the local smoke suite only. It is not a per-game decomposition of the official hidden-set scores (33.38, 8.03, or 23.41). `ft09` alone contributed 28.5714 of V10's 70.9395 local score sum (40.28%), showing concentration in a single game.

## 7. Post-candidate research: exclude from V13 claims

- **Phase 6.5:** Held–Karp TSP and bounded Sokoban helper implementations were marked `IMPLEMENTED_NOT_INTEGRATED` in the audit. Do not claim these were active V13 production solvers.
- **Phase 6.7 Swarm:** research branch only. The bridge's `success` condition could be true while the game remained `RUNNING`; action queue replacement could truncate the remaining plan. A later audit reproduced the false-success behavior in a mock fixture. Reported synthetic microbenchmarks are not whole-process or Kaggle E2E measurements.
- **Phase 6.8 RVICS:** research-only modules and user-reported 59/59 tests were not present in the supplied archive used for this audit. The gtr87/gg50t contact sheets support visual descriptions of UI/state changes, not solver correctness or 15/120-action solutions. Claimed 97.7% token savings and score uplifts require source logs and reproducible paired trials.

## 9. Open evidence gaps before Paper Track submission

1. Export Kaggle Kernel Version History for V1–V5 and V11 to V12, including source hashes, timestamps, and output references, if a strict per-version history is desired.
2. Obtain official public submission detail for V10 ref `57827259` to reconcile its earlier `PENDING` snapshot with later 8.03 reports.
3. Export the per-game breakdown for V6 ref `57758308` and V13 ref `57912660`, if available. Do not infer hidden-game count or completion from aggregate score alone.
4. Confirm the Paper Track submission should link to V6 notebook/hash (recommended for the 33.38 headline result) and separately cite V13 as post-deadline follow-up.
5. Provide public code/notebook and a license compatible with Paper Prize open-source rules.
