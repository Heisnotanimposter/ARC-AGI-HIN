#!/usr/bin/env python3
"""Single-command clean-room CPU verification harness for V12 Identity A Tier R1."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
REPLAY_OUT = PKG_ROOT / "replay_out"

HOME_RE = re.compile(r"(?:/" + r"Users|/" + r"home)/[A-Za-z0-9._-]+")
SECRET_RE = re.compile(r"(KGAT_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{30,})")
EXCLUDED_EXTS = {".mp4", ".pkl", ".parquet", ".whl", ".so", ".safetensors", ".pt", ".pth", ".bin"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest() -> int:
    mf = PKG_ROOT / "SHA256_MANIFEST.txt"
    if not mf.exists():
        raise AssertionError(f"Missing manifest: {mf}")
    checked = 0
    for raw in mf.read_text(encoding="utf-8").splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        digest, size_str, rel = ln.split(None, 2)
        target = PKG_ROOT / rel
        if not target.exists():
            raise AssertionError(f"Manifest entry missing: {rel}")
        data = target.read_bytes()
        if len(data) != int(size_str) or hashlib.sha256(data).hexdigest() != digest:
            raise AssertionError(f"Checksum mismatch on {rel}")
        checked += 1
    return checked


def verify_hygiene() -> dict[str, int]:
    files_scanned = 0
    for p in sorted(PKG_ROOT.rglob("*")):
        if "__pycache__" in p.parts or ".venv" in p.parts or "replay_out" in p.parts or ".cache" in p.parts:
            continue
        if p.name == ".git" or p.name == "environment_files":
            raise AssertionError(f"Forbidden directory/file inside Tier R1: {p.relative_to(PKG_ROOT)}")
        if not p.is_file():
            continue
        if p.suffix.lower() in EXCLUDED_EXTS:
            raise AssertionError(f"Forbidden binary artifact inside Tier R1: {p.relative_to(PKG_ROOT)}")
        files_scanned += 1
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if HOME_RE.search(txt):
            raise AssertionError(f"Home-path PII hit inside Tier R1: {p.relative_to(PKG_ROOT)}")
        if SECRET_RE.search(txt):
            raise AssertionError(f"Credential/token pattern hit inside Tier R1: {p.relative_to(PKG_ROOT)}")
    return {"files_scanned": files_scanned, "home_path_hits": 0, "secret_hits": 0, "forbidden_binaries": 0}


def run_step(label: str, cmd: list[str], env: dict[str, str]) -> dict[str, object]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=PKG_ROOT, env=env, capture_output=True, text=True)
    dt_s = round(time.perf_counter() - t0, 3)
    if proc.returncode != 0:
        print(f"[FAIL] {label} (rc={proc.returncode}, {dt_s}s)")
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr)
        raise SystemExit(proc.returncode)
    print(f"[PASS] {label} ({dt_s}s)")
    return {"step": label, "returncode": proc.returncode, "seconds": dt_s, "stdout_tail": proc.stdout.strip().splitlines()[-3:]}


def main() -> None:
    t_start = time.perf_counter()
    manifest_files = verify_manifest()
    print(f"[PASS] SHA256_MANIFEST.txt verified ({manifest_files} files)")
    hygiene = verify_hygiene()
    print(f"[PASS] Hygiene & binary exclusion gate ({hygiene['files_scanned']} text files cleanly verified)")

    an_out = REPLAY_OUT / "analysis"
    rec_out = REPLAY_OUT / "v10_forensic_reconciliation"
    an_out.mkdir(parents=True, exist_ok=True)
    rec_out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["R1_PACKAGE_ROOT"] = str(PKG_ROOT)
    env["R1_V10_DIR"] = str(PKG_ROOT / "submissions/arc3_v10_verified")
    env["R1_AN_OUT_DIR"] = str(an_out)
    env["R1_REC_OUT_DIR"] = str(rec_out)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    py = sys.executable
    an_dir = PKG_ROOT / "Paper/branch_b_academic/analysis"
    rec_dir = an_dir / "v10_forensic_reconciliation"

    steps = []
    steps.append(run_step("1_build_v10_eviction_token_tables", [py, str(an_dir / "build_v10_eviction_token_tables.py")], env))
    steps.append(run_step("2_test_v10_eviction_token_tables", [py, "-m", "unittest", "-v", "test_v10_eviction_token_tables"], {**env, "PYTHONPATH": str(an_dir)}))
    steps.append(run_step("3_reconstruct_v10_forensics", [py, str(rec_dir / "reconstruct_v10_forensics.py"), "--r1-portable"], env))
    steps.append(run_step("4_11_INDEPENDENT_ARITHMETIC_CHECK", [py, str(rec_dir / "11_INDEPENDENT_ARITHMETIC_CHECK.py")], env))
    steps.append(run_step("5_test_v10_forensics_and_canonical_parity", [py, "-m", "unittest", "-v", "test_v10_forensics"], {**env, "PYTHONPATH": str(rec_dir)}))
    steps.append(run_step("6_verify_r1_statistical_addenda", [py, str(rec_dir / "verify_r1_statistical_addenda.py")], env))
    steps.append(
        run_step(
            "7_audit_traffic_rules_portable_cli_smoke",
            [
                py,
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); import audit_traffic_rules as a; "
                "assert hasattr(a, 'audit_file'); "
                "rc = a.audit_file(sys.argv[2]); "
                "print(f'audit_traffic_rules portable smoke ok (rc={rc} on ledger)')",
                str(PKG_ROOT / "Paper"),
                str(PKG_ROOT / "Paper/ARC3_Version_History_Evidence_Ledger.md"),
            ],
            env,
        )
    )

    # Assert exact SHA-256 identity on 12_INDEPENDENT_ARITHMETIC_RESULTS.json too
    regen_12 = sha256_file(rec_out / "12_INDEPENDENT_ARITHMETIC_RESULTS.json")
    exp_12 = sha256_file(PKG_ROOT / "expected_canonical/12_INDEPENDENT_ARITHMETIC_RESULTS.json")
    if regen_12 != exp_12:
        raise AssertionError(f"12_INDEPENDENT_ARITHMETIC_RESULTS.json hash mismatch: {regen_12} != {exp_12}")
    print(f"[PASS] 12_INDEPENDENT_ARITHMETIC_RESULTS.json exact SHA-256 match ({regen_12[:16]}...)")

    total_s = round(time.perf_counter() - t_start, 3)
    if total_s >= 60.0:
        raise AssertionError(f"Clean-room CPU replay exceeded <60s SLA: {total_s}s")

    report = {
        "python_version": sys.version,
        "platform": sys.platform,
        "manifest_verified_files": manifest_files,
        "hygiene": hygiene,
        "total_wallclock_seconds": total_s,
        "under_60s_sla": True,
        "canonical_12_json_sha256": regen_12,
        "steps": steps,
    }
    (REPLAY_OUT / "replay_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nALL TIER R1 CPU REPLAY CHECKS PASSED IN {total_s:.3f}s")


if __name__ == "__main__":
    main()
