from pathlib import Path
#!/usr/bin/env python3
"""
World-Class Academic Paper Traffic Rules Auditor
Script: audit_traffic_rules.py
Enforces the 10 Traffic Signals defined in WORLD_CLASS_ACADEMIC_TRAFFIC_RULES.md.
"""

import sys
import re
import os
import subprocess

RED_PATTERNS = [
    (r"NeurIPS\s+Paper\s+Checklist", "Administrative boilerplate (Checklist questionnaire block detected)"),
    (r"\\section\*?\{.*Checklist.*\}", "Checklist section header detected"),
    (r"\b(groundbreaking|revolutionary|game-changing|miraculous|flawless|unprecedented|astonishing)\b", "Marketing hyperbole / promotional rhetoric detected"),
    (r"\bTheorem\s+1\s*\(Bounded\s+RHAE", "Unverified pseudo-theorem detected (A_AI <= A_human + 2D_mec)"),
    (r"A_\{?AI\}?\s*\\le\s*A_\{?human\}?\s*\+\s*2\s*D", "Unverified physical bound pseudo-theorem equation"),
    (r"official\s+(competition\s+)?(score|result|points)\s*(of|was|is|:)?\s*70\.9[34]", "Falsely claiming local 25-game smoke score (70.94) as official competition score"),
    (r"Held[–-]Karp.*integrated\s+into\s+V13", "Falsely claiming research module Held-Karp was integrated in production V13"),
    (r"RVICS.*integrated\s+into\s+V13", "Falsely claiming RVICS was integrated in production V13"),
]

YELLOW_PATTERNS = [
    (r"history.*caused\s+the\s+(entire\s+)?25\.35", "Asserting single-cause causality for confounded V6->V10 regression"),
    (r"measured\s+cache\s+hit\s+ratio\s+of\s+98\.5", "Stating derived analytical estimate (98.5%) as measured server telemetry"),
]

GREEN_REQUIRED = [
    (r"(Limitations|Threats to [Vv]alidity)", "Dedicated Limitations / Threats to Validity section"),
    (r"57758308", "V6 primary submission reference anchor (57758308)"),
    (r"bb532e8c502ac5ce72c36918a2b1ac90(\\allowbreak\s*)?e0de3cc96f5bdc70682953914466c90e", "V6 official artifact SHA-256 hash"),
    (r"57912660", "V13 follow-up submission reference anchor (57912660)"),
    (r"(after deadline|post-deadline)", "Transparent disclosure of V13 post-deadline completion status"),
]

def audit_file(filepath):
    print(f"\n=======================================================")
    print(f"🚦 AUDITING TRAFFIC RULES: {os.path.basename(filepath)}")
    print(f"=======================================================")
    
    if not os.path.exists(filepath):
        print(f"❌ Error: File not found: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    red_violations = []
    yellow_warnings = []
    green_passes = []

    # 1. Audit RED flags
    for pat, desc in RED_PATTERNS:
        matches = re.findall(pat, content, re.IGNORECASE)
        if matches:
            red_violations.append((desc, len(matches)))

    # 2. Audit YELLOW flags
    for pat, desc in YELLOW_PATTERNS:
        matches = re.findall(pat, content, re.IGNORECASE)
        if matches:
            yellow_warnings.append((desc, len(matches)))

    # 3. Audit GREEN mandatory standards
    for pat, desc in GREEN_REQUIRED:
        if re.search(pat, content, re.IGNORECASE):
            green_passes.append(desc)
        else:
            red_violations.append((f"Missing mandatory standard: {desc}", 1))

    # Print Report
    print(f"\n[1] 🔴 RED LIGHT (Fatal Violations): {len(red_violations)}")
    if red_violations:
        for desc, cnt in red_violations:
            print(f"   ❌ [VIOLATION] {desc} (count: {cnt})")
    else:
        print("   ✅ Zero fatal violations! 100% Academic Integrity.")

    print(f"\n[2] 🟡 YELLOW LIGHT (Caution Warnings): {len(yellow_warnings)}")
    if yellow_warnings:
        for desc, cnt in yellow_warnings:
            print(f"   ⚠️  [WARNING] {desc} (count: {cnt})")
    else:
        print("   ✅ Zero yellow warnings. Causality and telemetry properly scoped.")

    print(f"\n[3] 🟢 GREEN LIGHT (Golden Standards): {len(green_passes)} / {len(GREEN_REQUIRED)}")
    for desc in green_passes:
        print(f"   ✨ [PASSED] {desc}")

    # Summary
    is_clean = len(red_violations) == 0
    print("\n-------------------------------------------------------")
    if is_clean:
        print("🏆 AUTOMATED STRUCTURAL AUDIT: PASSED (Predefined Rule Checks Passed)")
        print("   Notice: Automated checks verify rule compliance and do not replace independent peer review.")
    else:
        print("🚫 AUTOMATED STRUCTURAL AUDIT: FAILED (Corrections Required)")
    print("-------------------------------------------------------\n")
    return is_clean

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "ARC3_Version_History_Evidence_Ledger.md")
    success = audit_file(target)
    sys.exit(0 if success else 1)
