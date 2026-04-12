#!/usr/bin/env python3
"""
Task 6: Comprehensive Validation of Silver Dataset Selection

ALL checks must pass. Any failure exits with code 1.

Usage:
  python silver/validate_selection.py
"""

import json
import logging
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
SILVER = Path(__file__).parent
MANIFEST = SILVER / "data" / "final_500_manifest.json"
TEXT_DIR = SILVER / "papers_text"
PAPER_LINKS = ROOT / "data" / "paper_links.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("validate")


class Check:
    def __init__(self, name):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def ok(self, msg):
        self.messages.append(f"OK: {msg}")

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        header = f"[{status}] {self.name}"
        return header + ("\n" + "\n".join(f"  {m}" for m in self.messages) if self.messages else "")


def main():
    checks = []

    if not MANIFEST.exists():
        log.error(f"Manifest not found: {MANIFEST}. Run select_final.py first.")
        sys.exit(1)

    with open(MANIFEST) as f:
        manifest = json.load(f)

    silver_ds_ids = set(ds["dataset_id"] for ds in manifest)
    silver_arxiv_ids = set(ds["arxiv_id"] for ds in manifest)

    # Load gold
    gold_ds_ids = set()
    gold_arxiv_ids = set()
    if PAPER_LINKS.exists():
        with open(PAPER_LINKS) as f:
            paper_links = json.load(f)
        gold_ds_ids = set(paper_links.keys())
        for url in paper_links.values():
            m = re.search(r'(\d{4}\.\d{4,5})', url)
            if m:
                gold_arxiv_ids.add(m.group(1))
        processed = ROOT / "data" / "processed"
        if processed.exists():
            for d in processed.iterdir():
                if d.is_dir():
                    gold_ds_ids.add(d.name)

    # ── 6a: Zero overlap with gold ──
    c = Check("6a: Gold overlap")
    ds_overlap = silver_ds_ids & gold_ds_ids
    arxiv_overlap = silver_arxiv_ids & gold_arxiv_ids
    if ds_overlap:
        c.fail(f"Dataset ID overlap: {ds_overlap}")
    if arxiv_overlap:
        c.fail(f"ArXiv ID overlap: {arxiv_overlap}")
    if c.passed:
        c.ok(f"0 dataset ID overlaps, 0 paper overlaps")
    checks.append(c)

    # ── 6b: No duplicate papers ──
    c = Check("6b: Deduplication")
    if len(silver_arxiv_ids) != len(manifest):
        c.fail(f"Duplicate arxiv IDs: {len(silver_arxiv_ids)} unique vs {len(manifest)} entries")
    if len(silver_ds_ids) != len(manifest):
        c.fail(f"Duplicate dataset IDs: {len(silver_ds_ids)} unique vs {len(manifest)} entries")
    if len(silver_arxiv_ids) != len(silver_ds_ids):
        c.fail(f"Not 1:1 mapping: {len(silver_arxiv_ids)} papers vs {len(silver_ds_ids)} datasets")
    if c.passed:
        c.ok(f"{len(manifest)} datasets, {len(silver_arxiv_ids)} unique papers, 1:1 mapping")
    checks.append(c)

    # ── 6c: Text integrity ──
    c = Check("6c: Text integrity")
    valid_texts = 0
    lengths = []
    for ds in manifest:
        txt_path = ROOT / ds["paper_text_path"]
        if not txt_path.exists():
            c.fail(f"Missing: {ds['paper_text_path']}")
            continue
        try:
            content = txt_path.read_text(encoding="utf-8")
            if len(content) < 1000:
                c.fail(f"Too short ({len(content)} chars): {ds['arxiv_id']}")
            elif len(content) > 500000:
                c.fail(f"Too long ({len(content)} chars): {ds['arxiv_id']}")
            else:
                # Check for binary garbage: > 90% should be printable ASCII or common UTF-8
                printable = sum(1 for ch in content[:1000] if ch.isprintable() or ch in "\n\t\r")
                if printable / min(len(content), 1000) < 0.8:
                    c.fail(f"Binary garbage detected: {ds['arxiv_id']}")
                else:
                    valid_texts += 1
                    lengths.append(len(content))
        except Exception as e:
            c.fail(f"Read error: {ds['arxiv_id']}: {e}")

    if valid_texts == len(manifest):
        import numpy as np
        c.ok(f"{valid_texts}/{len(manifest)} files valid, mean length: {np.mean(lengths):.0f} chars")
    checks.append(c)

    # ── 6d: Domain distribution ──
    c = Check("6d: Domain distribution")
    domains = Counter(ds["domain"] for ds in manifest)
    n = len(manifest)
    max_pct = max(count / n * 100 for count in domains.values())
    if max_pct > 60:
        c.fail(f"Single domain > 60%: {domains.most_common(1)}")
    if len(domains) < 3:
        c.fail(f"Only {len(domains)} domains represented (need ≥3)")
    if c.passed:
        dist_str = ", ".join(f"{d}:{cnt}" for d, cnt in domains.most_common())
        c.ok(f"{len(domains)} domains, max={max_pct:.0f}%. Distribution: {dist_str}")
    checks.append(c)

    # ── 6e: Metadata completeness ──
    c = Check("6e: Metadata completeness")
    required = ["dataset_id", "arxiv_id", "paper_text_path", "text_length", "downloads", "domain", "source"]
    for ds in manifest:
        for field in required:
            if field not in ds or ds[field] is None or ds[field] == "":
                c.fail(f"{ds.get('dataset_id', '?')}: missing or empty '{field}'")
                break
    if c.passed:
        c.ok(f"All {len(manifest)} entries have all {len(required)} required fields")
    checks.append(c)

    # ── 6f: Existing validation suite ──
    c = Check("6f: Existing validation suite")
    try:
        result = subprocess.run(
            [sys.executable, "validation/run_all.py", "--quick"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        if result.returncode == 0:
            c.ok("validation/run_all.py --quick: PASS")
        else:
            c.fail(f"validation/run_all.py failed:\n{result.stdout[-300:]}")
    except subprocess.TimeoutExpired:
        c.fail("validation/run_all.py timed out")
    except Exception as e:
        c.fail(f"Could not run validation: {e}")
    checks.append(c)

    # ── Summary ──
    print(f"\n{'='*70}")
    print("SILVER DATASET VALIDATION REPORT")
    print(f"{'='*70}")

    all_passed = True
    for check in checks:
        print(f"\n{check}")
        if not check.passed:
            all_passed = False

    print(f"\n{'='*70}")
    if all_passed:
        print("OVERALL: ALL CHECKS PASSED")
    else:
        print("OVERALL: SOME CHECKS FAILED")
    print(f"{'='*70}")

    # Save report
    report_path = SILVER / "validation_report.md"
    with open(report_path, "w") as f:
        f.write("# Silver Dataset Validation Report\n\n")
        for check in checks:
            f.write(f"## {check.name}\n")
            f.write(f"**{'PASS' if check.passed else 'FAIL'}**\n\n")
            for msg in check.messages:
                f.write(f"- {msg}\n")
            f.write("\n")

    print(f"\nReport saved: {report_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
