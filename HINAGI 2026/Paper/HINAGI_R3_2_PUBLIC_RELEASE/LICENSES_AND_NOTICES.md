# Tier R1 Licenses, Attributions, and Public Release Notice

## 1. First-Party Public Release Materials — Apache License, Version 2.0
Original first-party software, telemetry analysis scripts, test harnesses, configuration
files, and `shared/` utilities in `HINAGI_R3_2_PUBLIC_RELEASE/` are distributed by
**Seungwon Lee (`redcar1024@gmail.com`, Independent Researcher)** under the **Apache License,
Version 2.0** (see root `LICENSE` and `NOTICE`). Historical `V12 R3.2-CP-3` and
`Original Tier R1` snapshots remain permanently preserved under their original **MIT License**
without retroactive revocation.

## 2. Upstream Inference, Fork & Mixed Snapshot Attributions — Apache-2.0 / MIT
- **Upstream base repository:** `Tufalabs/duck-harness` verified commit
  `7652836056c59e044f093e3c13ed7438c814169e` (Jeroen Cottaar and Tufa Labs;
  `ARC3-Inference/pyproject.toml`: **MIT License**).
- **Upstream fork repository:** `da-fr/arc-agi-3-solution` verified commit
  `10882e332d883af3e61616df8c8a17d03a328a75` (Daniel Franzen; root `LICENSE`:
  **Apache License, Version 2.0**).
- **Local verified bundle (`reference/arc3_franzen_m2/`):** `13/13` files verified
  byte-identical to `da-fr/arc-agi-3-solution@10882e332d883af3e61616df8c8a17d03a328a75`.
- **Mixed snapshot notebooks (`artifacts/phase6_5/reference_snapshots/`):**
  `phase6_3_candidate.ipynb`, `v10_reference.ipynb`, and `v6_reference.ipynb` are classified
  as `DERIVATIVE_MIXED_APACHE2_AND_FIRST_PARTY` (`Cell 02` exact match to `7652836..af58714`
  + `12` `Tufalabs@7652836` cells + `Cells 00, 04, 16` first-party customizations, with
  explicit caveat on `7` Kaggle-only cells `01, 05, 06, 11, 12, 17, 18`).

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
