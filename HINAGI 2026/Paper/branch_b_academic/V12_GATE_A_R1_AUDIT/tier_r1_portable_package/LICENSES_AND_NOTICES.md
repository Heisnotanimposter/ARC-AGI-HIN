# Tier R1 Licenses, Attributions, and Binary Exclusion Notice (GA-04)

## 1. Original Project Materials — MIT License
All original telemetry analysis scripts, test harnesses, notebooks diffs, configuration
files, and `shared/` utilities authored for HINAGI 2026 are distributed under the root
**MIT License** (see `LICENSE`, Copyright (c) 2024 Seungwon Lee).

## 2. Upstream Inference & Orchestration Source Trace Targets — Apache-2.0 / MIT
Files included under `reference/arc3_franzen_m2/` purely for exact symbol/line source
tracing of `tool_agent.py`, `solver.py`, and `taaf/game.py` retain their original open
licenses and upstream credit:
- **Upstream repository:** `dfranzen/arc-agi-3-solution` (`reference/arc3_franzen_m2/LICENSE`:
  **Apache License, Version 2.0**; `ARC3-Inference/pyproject.toml` classifier: **MIT License**).
- **Upstream framework:** `Tufalabs/duck-harness` & `tufa-arc-agi-framework`
  (Jeroen Cottaar and Tufa Labs).
- **Attribution preserved verbatim** in `reference/arc3_franzen_m2/LICENSE` and upstream READMEs.

## 3. Strictly Excluded Artifacts (Metadata / SHA-256 Pointers Only in `excluded_artifacts_metadata.json`)
Per Kaggle Competition Rules (`Sec. 2.4.b.1`) and V12 Identity A Gate A criteria (`GA-04`):
1. **Competition Game Environments (`environment_files/`):** Excluded (proprietary competition assets).
2. **Third-Party Model Weights & Serving Wheels:** Excluded (`dfranzen/intel-qwen3.8-flash-next-w4a16-autoround`,
   `dfranzen/albucino-qwen3-8-flash-next-drafter`, `dfranzen/pennyroyal-v253` wheels, `.so`, `.pt`, `.whl`).
3. **Unverified / Heavy Binary & Redundant Render Outputs:** Excluded from R1 payload (`.mp4` replays [25],
   `.pkl` state caches [4], `submission.parquet` [1], `diagnostics.html`, `movies/*.html`, `solver_analysis/*.html`,
   `transcripts/*.txt`, `artifacts/*_p0_viewer_data.json`, plus excluded sibling dumps `pulled_from_kaggle/`,
   `submissions/arc3_output/`, `arc3_v8_smoke_verified/`, `arc3_v9_smoke_verified/`). Their raw byte counts
   and SHA-256 hashes remain cryptographically documented in `excluded_artifacts_metadata.json`.
4. **Telemetry Sanitization Disclosure (`GA-02`):** `submissions/arc3_v10_verified/arc-agi-3-sota.log`
   (L176) and `submissions/arc3_v6_smoke_verified/arc-agi-3-sota.log` (L178) scrub the upstream local
   home directory literal in `HarnessSolver(local_server_repo_dir=...)` to `<USER_HOME_REDACTED>`.
   Both raw and sanitized SHA-256 hashes are recorded in `excluded_artifacts_metadata.json`.
