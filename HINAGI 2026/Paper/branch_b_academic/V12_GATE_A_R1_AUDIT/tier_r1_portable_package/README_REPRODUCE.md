# HINAGI 2026 — Tier R1 Portable CPU Audit-Reproducibility Package

This standalone package executes **V12 Identity A Tier R1** verification cleanly on CPU
with zero hardcoded machine paths, zero network access, zero GPUs, and zero external PyPI packages.

## Quick Clean-Room Reproduction (`< 60s`)

```bash
# 1. Copy package into an isolated temp directory outside the repository
rm -rf /tmp/hinagi_r1_cleanroom && cp -R . /tmp/hinagi_r1_cleanroom
cd /tmp/hinagi_r1_cleanroom

# 2. Create a clean virtual environment and install pinned requirements
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Execute the single-command Tier R1 verification harness
.venv/bin/python verify_tier_r1.py
```

## What `verify_tier_r1.py` Executes and Asserts
1. **Cryptographic Integrity (`SHA256_MANIFEST.txt`):** Verifies every shipped static file before replay.
2. **Hygiene & Binary Exclusion Gate:** Confirms 0 home-directory literals, 0 live credentials/API keys,
   0 `.git` directories, and 0 excluded binaries (`.mp4`, `.pkl`, `.parquet`, `.so`, `.whl`, `environment_files`).
3. **25-Game Eviction & Token Tables (`build_v10_eviction_token_tables.py` + `test_v10_eviction_token_tables.py`):**
   Reconstructs all tables into `replay_out/analysis/` and passes all unit assertions.
4. **Full Request/Response & Boundary Forensics (`reconstruct_v10_forensics.py --r1-portable` + `test_v10_forensics.py`):**
   Rebuilds all 360 `serve.log` mappings, `352 + 1 = 353` client responses, 4 HTTP read timeouts (`output_len=7,610`),
   `45/45` live calibration matches, 9 FIFO evictions (`4` end-of-step + `5` next-opener), `177/177` boundary checks,
   and asserts byte-for-byte SHA-256 identity of regenerated CSVs against `expected_canonical/`.
5. **Independent Arithmetic Check (`11_INDEPENDENT_ARITHMETIC_CHECK.py`):**
   Independently recomputes `378,304`, `468,510`, `2,778`, `471,288`, `92,984`, V6 vs V10 smoke metrics, and
   V6/V10 5-cell notebook diff, verifying byte-identical JSON output against `expected_canonical/12_INDEPENDENT_ARITHMETIC_RESULTS.json`.
6. **V12 Addendum & Rule Auditors (`verify_r1_statistical_addenda.py` + `audit_traffic_rules.py`):**
   Verifies Matched-10 (`0W/6L/4T`, `-65.95%`), `N/A` timeout right-censoring (`N=5` vs `N=16`), V10 skew/KV clustering,
   and portable Traffic Rules CLI execution.
