#!/usr/bin/env python3
"""
Task 1: Data Integrity Checks
Verifies paper corpus, extractions, annotations, and cross-consistency.
"""

import csv
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

import fitz  # PyMuPDF
import openpyxl

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
PAGE_COUNTS = ROOT / "data" / "paper_lengths.csv"
ANNOTATION_DIR = Path(os.environ.get("ANNOTATION_SHEETS_DIR", "data/annotations/phase2"))

# Canonical 30 field names (unprefixed general + rai:-prefixed RAI)
EXPECTED_FIELDS = {
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
}

VALID_RATINGS = {"1", "2", "3",
                 "1 - Correct", "2 - Partially Correct", "3 - Not Correct"}
VALID_FAILURE_MODES = {
    "Incomplete", "Hallucination", "Wrong Section",
    "Granularity Mismatch", "Format Error", "Other",
}
DROPOUTS = {"annotator", "annotator", "annotator"}


class CheckResult:
    def __init__(self, name):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def warn(self, msg):
        self.messages.append(f"WARN: {msg}")

    def info(self, msg):
        self.messages.append(f"INFO: {msg}")

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        header = f"[{status}] {self.name}"
        if self.messages:
            return header + "\n" + "\n".join(f"  {m}" for m in self.messages)
        return header


def check_paper_corpus():
    """1a: Paper corpus integrity."""
    r = CheckResult("1a: Paper Corpus")

    if not PAPER_LINKS.exists():
        r.fail(f"paper_links.json not found at {PAPER_LINKS}")
        return r

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    expected_count = len(paper_links)
    r.info(f"Expected datasets: {expected_count}")

    # Check PDFs exist
    missing = []
    sizes = []
    pages = []
    for ds_id in sorted(paper_links.keys()):
        pdf = RAW_DIR / f"{ds_id}.pdf"
        if not pdf.exists():
            # Check benchmark naming
            found = False
            for p in ROOT.glob(f"data/*.pdf"):
                if ds_id.lower() in p.stem.lower():
                    found = True
                    break
            if not found:
                missing.append(ds_id)
                continue
        else:
            sizes.append(pdf.stat().st_size)
            try:
                doc = fitz.open(pdf)
                pages.append(len(doc))
                doc.close()
            except Exception as e:
                r.fail(f"Corrupted PDF: {ds_id}: {e}")

    if missing:
        r.warn(f"{len(missing)} PDFs not found in data/raw/ (may use arxiv names): {missing[:5]}")
    else:
        r.info("All PDFs found")

    if sizes:
        r.info(f"PDF sizes: min={min(sizes)//1024}KB, max={max(sizes)//1024}KB, avg={sum(sizes)//len(sizes)//1024}KB")
    if pages:
        r.info(f"Pages: min={min(pages)}, max={max(pages)}, avg={sum(pages)/len(pages):.1f}")

    # Check unique papers
    url_groups = defaultdict(list)
    for ds_id, url in paper_links.items():
        url_groups[url].append(ds_id)
    n_unique = len(url_groups)
    n_dupes = sum(1 for v in url_groups.values() if len(v) > 1)
    r.info(f"Unique papers: {n_unique}, duplicate groups: {n_dupes}")

    return r


def check_extractions():
    """1b: Extraction JSON integrity."""
    r = CheckResult("1b: Extractions")

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    missing = []
    invalid_json = []
    field_issues = []
    null_counts = Counter()
    total = 0

    for ds_id in sorted(paper_links.keys()):
        ext_path = PROCESSED_DIR / ds_id / "full_pdf_metadata_result.json"
        if not ext_path.exists():
            missing.append(ds_id)
            continue

        total += 1
        try:
            with open(ext_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            invalid_json.append((ds_id, str(e)))
            continue

        fields = set(data.keys())
        if fields != EXPECTED_FIELDS:
            extra = fields - EXPECTED_FIELDS
            miss = EXPECTED_FIELDS - fields
            if extra or miss:
                field_issues.append((ds_id, list(extra)[:3], list(miss)[:3]))

        for field in EXPECTED_FIELDS:
            val = data.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                null_counts[field] += 1

    r.info(f"Extractions found: {total}/{len(paper_links)}")

    if missing:
        r.fail(f"{len(missing)} extractions missing: {missing[:5]}")
    if invalid_json:
        r.fail(f"{len(invalid_json)} invalid JSON files: {invalid_json[:3]}")
    if field_issues:
        r.fail(f"{len(field_issues)} files with wrong fields: {field_issues[:3]}")

    # Null rate per field
    r.info(f"Null rates (top 5):")
    for field, count in null_counts.most_common(5):
        pct = count / total * 100 if total else 0
        r.info(f"  {field}: {count}/{total} ({pct:.0f}%)")

    return r


def check_annotations():
    """1c: Annotation data integrity."""
    r = CheckResult("1c: Annotations")

    if not ANNOTATION_DIR.exists():
        r.warn(f"Annotation directory not found: {ANNOTATION_DIR}")
        r.info("Skipping annotation checks — set ANNOTATION_DIR to correct path")
        return r

    files = sorted(ANNOTATION_DIR.glob("Phase2_*.xlsx"))
    r.info(f"Annotation files: {len(files)}")

    total_annotations = 0
    invalid_ratings = []
    invalid_fms = []
    per_annotator = Counter()
    per_field = Counter()
    datasets_seen = set()

    for f in files:
        aname = f.stem.replace("Phase2_", "").replace("_", " ")
        if f.stem.replace("Phase2_", "") in DROPOUTS:
            continue

        try:
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        except Exception as e:
            r.fail(f"Cannot open {f.name}: {e}")
            continue

        if "Annotations" not in wb.sheetnames:
            r.warn(f"{aname}: no 'Annotations' tab")
            wb.close()
            continue

        ws = wb["Annotations"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 6 or row[0] is None:
                continue

            dataset = str(row[1]).strip() if row[1] else None
            field = str(row[3]).strip() if len(row) > 3 and row[3] else None
            rating_raw = str(row[5]).strip() if len(row) > 5 and row[5] else None
            fm_raw = str(row[6]).strip() if len(row) > 6 and row[6] and str(row[6]).strip() else None

            if dataset:
                datasets_seen.add(dataset)
            if field and field != "`":
                per_field[field] += 1 if rating_raw else 0

            if rating_raw:
                total_annotations += 1
                per_annotator[aname] += 1

                if rating_raw not in VALID_RATINGS:
                    invalid_ratings.append((aname, rating_raw))

                if fm_raw and fm_raw not in VALID_FAILURE_MODES:
                    invalid_fms.append((aname, fm_raw))

        wb.close()

    r.info(f"Total rated annotations: {total_annotations}")
    r.info(f"Unique datasets in annotations: {len(datasets_seen)}")

    if invalid_ratings:
        r.fail(f"{len(invalid_ratings)} invalid ratings: {invalid_ratings[:5]}")
    if invalid_fms:
        r.warn(f"{len(invalid_fms)} invalid failure modes: {invalid_fms[:5]}")

    return r


def check_cross_consistency():
    """1d: Cross-consistency between datasets, extractions, and annotations."""
    r = CheckResult("1d: Cross-Consistency")

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    corpus_ids = set(paper_links.keys())

    # Check extractions cover corpus
    extraction_ids = set()
    for ds_id in corpus_ids:
        if (PROCESSED_DIR / ds_id / "full_pdf_metadata_result.json").exists():
            extraction_ids.add(ds_id)

    missing_ext = corpus_ids - extraction_ids
    extra_ext = extraction_ids - corpus_ids
    if missing_ext:
        r.fail(f"{len(missing_ext)} corpus datasets missing extractions: {list(missing_ext)[:5]}")
    if extra_ext:
        r.warn(f"{len(extra_ext)} extractions not in corpus: {list(extra_ext)[:5]}")

    # Check PDFs cover corpus
    pdf_ids = set()
    for ds_id in corpus_ids:
        if (RAW_DIR / f"{ds_id}.pdf").exists():
            pdf_ids.add(ds_id)

    missing_pdf = corpus_ids - pdf_ids
    if missing_pdf:
        r.warn(f"{len(missing_pdf)} corpus datasets missing PDFs in data/raw/: {list(missing_pdf)[:5]}")

    # Check field name consistency
    sample_ds = next(iter(extraction_ids), None)
    if sample_ds:
        with open(PROCESSED_DIR / sample_ds / "full_pdf_metadata_result.json") as f:
            sample = json.load(f)
        actual_fields = set(sample.keys())
        if actual_fields == EXPECTED_FIELDS:
            r.info("Field names match expected schema")
        else:
            r.fail(f"Field mismatch: extra={actual_fields - EXPECTED_FIELDS}, missing={EXPECTED_FIELDS - actual_fields}")

    # Check for whitespace/case issues in field names across all extractions
    field_variants = defaultdict(set)
    for ds_id in list(extraction_ids)[:20]:
        with open(PROCESSED_DIR / ds_id / "full_pdf_metadata_result.json") as f:
            data = json.load(f)
        for k in data.keys():
            field_variants[k.strip().lower()].add(k)

    inconsistent = {k: v for k, v in field_variants.items() if len(v) > 1}
    if inconsistent:
        r.fail(f"Inconsistent field names: {inconsistent}")
    else:
        r.info("No field name inconsistencies detected")

    return r


def main():
    checks = [
        check_paper_corpus(),
        check_extractions(),
        check_annotations(),
        check_cross_consistency(),
    ]

    print("\n" + "=" * 80)
    print("DATA INTEGRITY REPORT")
    print("=" * 80)

    all_passed = True
    for check in checks:
        print(f"\n{check}")
        if not check.passed:
            all_passed = False

    print(f"\n{'=' * 80}")
    if all_passed:
        print("OVERALL: ALL CHECKS PASSED")
    else:
        print("OVERALL: SOME CHECKS FAILED — review above")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
