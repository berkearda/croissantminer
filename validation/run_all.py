#!/usr/bin/env python3
"""
Task 7: Validation Runner
Runs all checks in order, produces summary report.

Usage:
  python validation/run_all.py           # run all checks
  python validation/run_all.py --quick   # skip slow checks (LLM judge, PDF parsing)
"""

import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
VALIDATION_DIR = Path(__file__).parent


def run_check(name, cmd, critical=True):
    """Run a check script and return (passed, output)."""
    print(f"\n{'─' * 70}")
    print(f"Running: {name}")
    print(f"{'─' * 70}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(ROOT)
        )
        elapsed = time.time() - start
        output = result.stdout + result.stderr
        passed = result.returncode == 0

        # Print output
        print(output)
        print(f"  → {'PASS' if passed else 'FAIL'} ({elapsed:.1f}s)")

        return passed, output, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"  → TIMEOUT after {elapsed:.0f}s")
        return False, "TIMEOUT", elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"  → ERROR: {e}")
        return False, str(e), elapsed


def main():
    quick = "--quick" in sys.argv
    start_time = datetime.now()

    print("=" * 70)
    print(f"CroissantMiner Validation Suite — {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Mode: {'QUICK' if quick else 'FULL'}")
    print("=" * 70)

    checks = []

    # Task 1: Data Integrity
    checks.append(("Data Integrity", [
        sys.executable, "validation/check_data_integrity.py"
    ], True))

    # Task 3: Metric Unit Tests
    checks.append(("Metric Unit Tests", [
        sys.executable, "-m", "pytest", "validation/test_metrics.py", "-v", "--tb=short"
    ], True))

    # Task 4: Sanity Checks
    checks.append(("Sanity Checks", [
        sys.executable, "validation/sanity_checks.py"
    ], True))

    results = []
    for name, cmd, critical in checks:
        passed, output, elapsed = run_check(name, cmd, critical)
        results.append({
            "name": name,
            "passed": passed,
            "critical": critical,
            "elapsed": elapsed,
        })

        if not passed and critical:
            print(f"\n⚠ CRITICAL CHECK FAILED: {name}")
            if quick:
                print("  Continuing in quick mode...")
            # Don't stop — run all checks so we see the full picture

    # Summary
    total_time = (datetime.now() - start_time).total_seconds()
    all_passed = all(r["passed"] for r in results)
    critical_passed = all(r["passed"] for r in results if r["critical"])

    print(f"\n{'=' * 70}")
    print("VALIDATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n{'Check':<30} {'Status':>8} {'Time':>8}")
    print("-" * 50)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['name']:<28} {status:>8} {r['elapsed']:>6.1f}s")
    print(f"\n  {'Total':28} {'PASS' if all_passed else 'FAIL':>8} {total_time:>6.1f}s")

    if all_passed:
        print("\n✓ ALL CHECKS PASSED — safe to run experiments")
    elif critical_passed:
        print("\n⚠ NON-CRITICAL CHECKS FAILED — review before proceeding")
    else:
        print("\n✗ CRITICAL CHECKS FAILED — fix before running experiments")

    # Save report
    report_path = VALIDATION_DIR / "report.md"
    with open(report_path, "w") as f:
        f.write(f"# Validation Report — {start_time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Mode: {'Quick' if quick else 'Full'}\n\n")
        f.write("| Check | Status | Time |\n")
        f.write("|-------|--------|------|\n")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            f.write(f"| {r['name']} | {status} | {r['elapsed']:.1f}s |\n")
        f.write(f"\n**Overall: {'PASS' if all_passed else 'FAIL'}** ({total_time:.1f}s)\n")
    print(f"\nReport saved: {report_path}")

    return 0 if critical_passed else 1


if __name__ == "__main__":
    sys.exit(main())
