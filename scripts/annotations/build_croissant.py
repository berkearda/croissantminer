"""
Build the MLCommons Croissant 1.1 JSON-LD metadata file for the
CroissantMiner annotation dataset.

Reads parquet schemas dynamically, maps pandas dtypes to Croissant
dataTypes, and emits a single self-contained JSON-LD file at
data/annotations/croissant.json.

The output covers Croissant Core 1.1 + RAI 1.0 (mandatory at NeurIPS
2026 E&D submission per the call for papers).

Run: python scripts/annotations/build_croissant.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

# ── Anonymisation toggle ─────────────────────────────────────────
# Default to ANONYMOUS for double-blind NeurIPS submission. Set
# CROISSANT_FINAL=1 in env or pass --final at the camera-ready stage to
# restore identities. Per NeurIPS 2026 double-blind policy, the
# Croissant metadata file submitted with the paper PDF must not contain
# author names, affiliations, or de-anonymising URLs.
ANON = os.environ.get("CROISSANT_FINAL", "0") != "1"

# Anonymous values used when ANON=True
ANON_PROJECT_URL = "https://anonymous.4open.science/r/croissantminer-F87C"
ANON_REPO_URL = "https://anonymous.4open.science/r/croissantminer-F87C"
ANON_CREATOR = [{"@type": "sc:Person", "name": "Anonymous Author(s)", "affiliation": "Anonymous"}]
ANON_PUBLISHER = {"@type": "sc:Organization", "name": "Anonymous"}
ANON_CITE = "Anonymous Authors. CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets. NeurIPS 2026 Evaluations and Datasets Track (under review)."

# Final (camera-ready) values
FINAL_PROJECT_URL = "https://github.com/berkearda/croissantminer"
FINAL_REPO_URL = "https://github.com/berkearda/croissantminer"
FINAL_CREATOR = [{"@type": "sc:Person", "name": "Berke Arda", "affiliation": "ETH Zurich"}]
FINAL_PUBLISHER = {"@type": "sc:Organization", "name": "ETH Zurich"}
FINAL_CITE = "Arda, B., Yavuz, A., et al. CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets. NeurIPS 2026 Evaluations and Datasets Track."

REPO_ROOT = Path(__file__).resolve().parents[2]
ANNOT_DIR = REPO_ROOT / "data" / "annotations"
OUT_PATH = ANNOT_DIR / "croissant.json"

# ── Map pandas dtypes to Croissant dataType URIs ──────────────────────────
DTYPE_TO_CROISSANT = {
    "object": "sc:Text",
    "int64": "sc:Integer",
    "int32": "sc:Integer",
    "int8": "sc:Integer",
    "float64": "sc:Float",
    "float32": "sc:Float",
    "bool": "sc:Boolean",
    "datetime64[ns]": "sc:Date",
}


def croissant_dtype(pandas_dtype: str) -> str:
    return DTYPE_TO_CROISSANT.get(pandas_dtype, "sc:Text")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Croissant 1.1 @context block (standard) ───────────────────────────────
CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "prov": "http://www.w3.org/ns/prov#",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}

# ── Per-parquet description metadata ──────────────────────────────────────
PARQUET_FILES = [
    {
        "filename": "ratings.parquet",
        "rid": "ratings",
        "description": (
            "Long-format raw human ratings, one row per "
            "(paper, field, annotator). Annotators were instructed to "
            "rate each LLM-extracted Croissant metadata value as "
            "Correct (1), Partially Correct (2), or Not Correct (3); "
            "for ratings of 2 or 3, an optional corrected_value and "
            "free-text notes were collected, plus a confidence label "
            "(High / Medium / Low) and a failure-mode category."
        ),
    },
    {
        "filename": "calibration.parquet",
        "rid": "calibration",
        "description": (
            "Pilot ratings collected before the main collection began. "
            "Used a binary TRUE/FALSE rubric (mapped to rating 1 or 3 "
            "in this file) on a 15-cell sample. Released for "
            "transparency; downstream evaluation should use ratings.parquet."
        ),
    },
    {
        "filename": "gold.parquet",
        "rid": "gold",
        "description": (
            "Derived gold values, one row per (paper, field). Computed by "
            "majority vote across raters (3 to 4 raters per cell, see "
            "n_raters column); cells where no rating reached majority "
            "(gold_method = 'tie_split') were sent to senior adjudication "
            "and the gold_value/gold_rating were filled by the adjudicator."
        ),
    },
    {
        "filename": "iaa.parquet",
        "rid": "iaa",
        "description": (
            "Per-field inter-annotator agreement metrics with bootstrap "
            "95 percent confidence intervals. Reports Krippendorff's alpha "
            "(ordinal), Gwet's AC1 (chance-corrected, prevalence-robust), "
            "raw pairwise agreement, and percent unanimous cells. The "
            "AC1 + pairwise pair triangulates against the prevalence "
            "paradox in alpha when ratings cluster on one category."
        ),
    },
    {
        "filename": "annotators.parquet",
        "rid": "annotators",
        "description": (
            "Pseudonymized roster of the 22 annotators who contributed "
            "to the main set. Demographics aggregated from the recruitment "
            "registration form: role, affiliation, ML familiarity, "
            "paper-experience frequency, hours dedicated. No personally "
            "identifying information beyond what annotators publicly "
            "associate with their professional profiles."
        ),
    },
    {
        "filename": "silver.parquet",
        "rid": "silver",
        "description": (
            "Silver split: 500 ML dataset papers with paper-level "
            "metadata (arXiv ID, downloads, domain, license, tasks, "
            "language, datePublished, dataCollectionType). LLM-derived "
            "from arXiv metadata + Claude Sonnet 4.5 pre-fill at "
            "temperature 0; not human-validated. Used for scale studies "
            "and silver-vs-gold validation in the paper."
        ),
    },
]


CONTENT_URL_BASE: str | None = None


def build_distribution() -> list:
    """Build cr:FileObject entries for each parquet file.

    Prefers `data/annotations/_release/<file>` (pseudonymized output of
    scripts/submission/pseudonymize_for_release.py) when present, so the
    published sha256 matches the public parquet bytes. Falls back to the
    raw parquet otherwise.

    `contentUrl` is the bare filename by default (relative resolution
    against the JSON-LD file's directory works locally for mlcroissant).
    Pass `--base-url https://huggingface.co/datasets/<handle>/<repo>/resolve/main`
    to emit absolute URLs once the dataset is hosted, so the HF
    Croissant validator's records-generation test passes.
    """
    out = []
    release_dir = ANNOT_DIR / "_release"
    for p in PARQUET_FILES:
        release_path = release_dir / p["filename"]
        raw_path = ANNOT_DIR / p["filename"]
        path = release_path if release_path.exists() else raw_path
        if not path.exists():
            continue
        if CONTENT_URL_BASE:
            content_url = f"{CONTENT_URL_BASE.rstrip('/')}/{p['filename']}"
        else:
            content_url = p["filename"]
        out.append({
            "@type": "cr:FileObject",
            "@id": f"{p['rid']}-parquet",
            "name": p["filename"],
            "description": p["description"],
            "contentUrl": content_url,
            "encodingFormat": "application/x-parquet",
            "sha256": sha256(path),
        })
    return out


def _resolve_parquet_path(filename: str) -> Path | None:
    """Find a parquet by checking _release/ first, then ANNOT_DIR."""
    release = ANNOT_DIR / "_release" / filename
    if release.exists():
        return release
    raw = ANNOT_DIR / filename
    return raw if raw.exists() else None


def build_record_set(file_meta: dict) -> dict:
    """Build a cr:RecordSet describing one parquet's columns."""
    path = _resolve_parquet_path(file_meta["filename"])
    df = pd.read_parquet(path)
    fields = []
    for col in df.columns:
        fields.append({
            "@type": "cr:Field",
            "@id": f"{file_meta['rid']}/{col}",
            "name": col,
            "dataType": croissant_dtype(str(df[col].dtype)),
            "source": {
                "fileObject": {"@id": f"{file_meta['rid']}-parquet"},
                "extract": {"column": col},
            },
        })
    return {
        "@type": "cr:RecordSet",
        "@id": file_meta["rid"],
        "name": file_meta["rid"],
        "description": file_meta["description"],
        "field": fields,
    }


# ── RAI fields describing how the annotation dataset was collected ────────
# Each value is a brief, paper-quotable description. These are the fields
# CroissantMiner is itself built to extract; for the annotation dataset
# release we populate them directly.
RAI_FIELDS = {
    "rai:dataCollection": (
        "Human ratings of LLM-extracted Croissant metadata across "
        "102 ML dataset papers and 30 RAI fields. Collected over seven "
        "phases between March and April 2026: pilot calibration, "
        "Phase 2 main collection, mid-project redistribution to balance "
        "coverage, a round-3 top-up, two final sweeps for cells under "
        "the three-rater target, and an orphan top-up to bring every "
        "cell to at least three distinct annotators. Senior adjudication "
        "resolved cells where no rating reached majority."
    ),
    "rai:dataCollectionType": (
        "Manual Human Curator. Annotators were instructed not to use AI "
        "tools while rating."
    ),
    "rai:dataCollectionTimeframe": "2026-03-10 to 2026-04-25",
    "rai:dataCollectionRawData": (
        "AI-extracted Croissant metadata values produced by Claude "
        "Sonnet 4.5 on 102 arXiv-published ML dataset papers, plus the "
        "papers themselves (read by annotators when validating each value)."
    ),
    "rai:dataAnnotationProtocol": (
        "Each (paper, field) cell received three independent ratings on "
        "a three-level rubric (Correct / Partially Correct / Not Correct) "
        "with six failure-mode categories (Incomplete, Hallucination, "
        "Wrong Section, Granularity Mismatch, Format Error, Other) and "
        "an optional corrected value plus free-text notes. Confidence "
        "(High / Medium / Low) was recorded per rating."
    ),
    "rai:dataAnnotationPlatform": (
        "Excel files distributed via shared cloud storage; one workbook "
        "per annotator with separate sheets for Instructions, Field "
        "Definitions, Calibration Examples, and Annotations."
    ),
    "rai:dataAnnotationAnalysis": (
        "Krippendorff's alpha (ordinal, primary), Gwet's AC1 "
        "(chance-corrected, prevalence-robust), raw pairwise agreement, "
        "and percent unanimous cells, all computed per field with "
        "1000-iteration bootstrap 95 percent confidence intervals. "
        "Triangulation across alpha and AC1 is necessary because alpha "
        "collapses under skewed marginals (Feinstein-Cicchetti paradox)."
    ),
    "rai:annotationsPerItem": "3",
    "rai:annotatorDemographics": (
        "22 distinct annotators after deduplicating two who registered "
        "twice and merging name variants. Roles spanned PhD students, "
        "postdoctoral researchers, faculty, and industry professionals "
        "across academic and external institutions. Aggregate "
        "demographics in annotators.parquet (role, affiliation, ML "
        "familiarity tier, paper-experience frequency, hours dedicated). "
        "No personally identifying demographic data (age, gender, "
        "ethnicity, geography) was collected."
    ),
    "rai:machineAnnotationTools": (
        "None. Annotators were instructed not to use AI tools while "
        "rating. The pre-filled metadata values rated by annotators "
        "were generated by Claude Sonnet 4.5 (not part of the rating "
        "step itself)."
    ),
    "rai:dataReleaseMaintenancePlan": (
        "Released alongside the CroissantMiner NeurIPS 2026 E&D paper. "
        f"Maintained at {ANON_REPO_URL if ANON else FINAL_REPO_URL}. "
        "Versioning via Git tags. Bug-fix updates expected through "
        "2027; substantive schema changes deprecated rather than "
        "silently overwritten."
    ),
    "rai:personalSensitiveInformation": (
        "None collected. Annotator names appear in the local raw "
        "ratings.parquet for build provenance and are replaced with "
        "pseudonymous integer IDs (A01..A22) before public release; "
        "the raw-name version is gitignored."
    ),
    "rai:dataSocialImpact": (
        "Enables study of LLM extraction quality on Responsible AI "
        "metadata. Permits downstream research into RAI-field difficulty, "
        "extraction-distillation, and disagreement-aware fine-tuning. "
        "Limitation: source papers are arXiv-published English-language "
        "ML dataset papers, so coverage is biased toward the English-"
        "speaking ML research community."
    ),
    "rai:dataBiases": (
        "Annotator pool is biased toward ML/AI researchers (recruited "
        "via an open call to NeurIPS-track-adjacent researchers); "
        "ratings reflect this group's interpretation of the Croissant "
        "RAI rubric. Source-paper sample is biased toward Vision and NLP "
        "domains (the two largest fractions of the 102-paper benchmark). "
        "Field difficulty is non-uniform: short-text fields (sc:license, "
        "sc:datePublished) saw substantially higher pairwise agreement "
        "than long-form RAI fields (rai:dataBiases, rai:dataSocialImpact)."
    ),
    "rai:dataLimitations": (
        "Three RAI field definitions (rai:dataCollectionMissingData, "
        "rai:dataManipulationProtocol, rai:dataBiases) were tightened "
        "in the annotator rubric beyond the canonical Croissant RAI 1.0 "
        "specification, which contributes to definitional asymmetry on "
        "rai:dataBiases between LLM extractions and human ratings. "
        "Annotator demographics are aggregate-only; no per-annotator "
        "demographic stratification of agreement is released. "
        "Source-paper PDFs are not redistributed; downstream users "
        "must obtain them from the original publishers."
    ),
    "rai:dataUseCases": (
        "Training, Testing, Validation, and Benchmarking of LLM-based "
        "metadata extraction systems for Responsible AI documentation. "
        "Suitable for evaluating extraction accuracy, abstention "
        "calibration (when fields are absent from a paper), and "
        "field-specific difficulty profiles."
    ),
    # ── Required RAI 1.0 fields per NeurIPS 2026 E&D hosting guidelines ──
    "rai:isSyntheticData": (
        "False. Annotations are human ratings produced by 22 annotators "
        "on real LLM-generated extractions of real published academic "
        "papers; no synthetic generation step is part of the annotation "
        "pipeline. The 500-paper silver split contains LLM-generated "
        "metadata, but the metadata itself is grounded in real source "
        "papers rather than synthesised from scratch."
    ),
    "rai:sourceDatasets": (
        "The 102 gold papers and 500 silver papers are drawn from "
        "publicly available academic publications associated with "
        "Hugging Face datasets, ranked by download count. Source "
        "datasets are listed in the released paper-link manifest "
        "(data/paper_links.json) by arXiv identifier; individual paper "
        "PDFs are not redistributed and must be obtained from the "
        "original publishers (typically arXiv)."
    ),
    "rai:provenanceActivities": (
        "Provenance: (1) Source-paper PDFs were downloaded from arXiv "
        "between November 2025 and January 2026 and parsed with PyPDF2 "
        "3.0.1. (2) Pre-fill extractions were generated by Claude "
        "Sonnet 4.5 (claude-sonnet-4-5-20250929) at temperature 0 with "
        "a canonical prompt (SHA-256 prefix 1e1cfdd99246bbf5). (3) "
        "Human ratings were collected from 22 annotators between "
        "March and April 2026 across seven phases. (4) Gold values "
        "were derived by majority vote per (paper, field) cell, with "
        "senior-author adjudication for tie-split cells. (5) An "
        "end-to-end author audit in May 2026 corrected 191 of 3,060 "
        "gold cells (gold_method = 'audit_corrected_2026-05-04'). "
        "Each pre-fill extraction's _meta block records the model "
        "identifier, prompt SHA-256 prefix, and parser version."
    ),
}


# Structured RAI / PROV-O siblings to the prose fields above. Required by the
# NeurIPS 2026 E&D RAI editor (huggingface.co/spaces/JoaquinVanschoren/
# croissant-rai-checker), which checks the boolean / list forms.
RAI_HAS_SYNTHETIC_DATA = False

PROV_WAS_DERIVED_FROM = [
    {
        "@id": "https://huggingface.co/datasets",
        "prov:label": "HuggingFace Datasets Hub (top-downloaded ML datasets)",
        "sc:license": "Various (per-dataset)",
        "prov:wasAttributedTo": {
            "@id": "https://huggingface.co",
            "prov:label": "Hugging Face",
        },
    },
    {
        "@id": "https://arxiv.org",
        "prov:label": "arXiv",
        "sc:license": "Per-paper (arXiv non-exclusive license to distribute)",
        "prov:wasAttributedTo": {
            "@id": "https://ror.org/05bnh6r87",
            "prov:label": "arXiv (Cornell University)",
        },
    },
]

PROV_WAS_GENERATED_BY = [
    {
        "@type": "prov:Activity",
        "prov:type": {"@id": "https://www.wikidata.org/wiki/Q4929239"},
        "prov:label": "Source paper acquisition",
        "sc:description": (
            "Source-paper PDFs (102 gold + 500 silver) downloaded from arXiv "
            "between November 2025 and January 2026, seeded by the "
            "HuggingFace top-downloaded ML datasets list. PDFs parsed with "
            "PyPDF2 3.0.1."
        ),
        "prov:atTime": "2025-11-01T00:00:00Z",
    },
    {
        "@type": "prov:Activity",
        "prov:type": {"@id": "https://www.wikidata.org/wiki/Q5227332"},
        "prov:label": "LLM pre-fill extraction",
        "sc:description": (
            "Claude Sonnet 4.5 (claude-sonnet-4-5-20250929) generated initial "
            "metadata extractions at temperature 0 using a canonical prompt "
            "(SHA-256 prefix 1e1cfdd99246bbf5). These pre-fills served as "
            "the rating substrate for human annotators."
        ),
        "prov:atTime": "2026-02-15T00:00:00Z",
    },
    {
        "@type": "prov:Activity",
        "prov:type": {"@id": "https://www.wikidata.org/wiki/Q109719325"},
        "prov:label": "Human rating + adjudication",
        "sc:description": (
            "22 annotators rated LLM-generated extractions across 7 phases "
            "(March – April 2026). Gold derived by majority rule (>=3 raters) "
            "with senior adjudication on disagreements. Final pipeline: "
            "9,595 deduplicated ratings to 3,060 gold cells."
        ),
        "prov:atTime": "2026-03-01T00:00:00Z",
    },
]


def build_dataset() -> dict:
    return {
        "@context": CONTEXT,
        "@type": "sc:Dataset",
        "@id": (ANON_PROJECT_URL if ANON else FINAL_PROJECT_URL) + "/tree/main/data/annotations",
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": "CroissantMiner Annotations",
        "description": (
            "Human-validated annotation dataset accompanying the "
            "CroissantMiner benchmark for automated extraction of "
            "MLCommons Croissant Responsible AI metadata from ML "
            "dataset papers. Contains 9595 ratings and 267 calibration "
            "ratings from 22 annotators across 102 papers and 30 "
            "Croissant Core + RAI fields, with derived gold values, "
            "per-field inter-annotator agreement metrics, and "
            "pseudonymized annotator demographics. Released under "
            "CC-BY-4.0; LLM-generated extractions referenced by the "
            "ratings are subject to their respective providers' terms."
        ),
        "url": ANON_PROJECT_URL if ANON else FINAL_PROJECT_URL,
        "version": "1.0.0",
        "datePublished": date.today().isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "inLanguage": "en",
        "isLiveDataset": False,
        "keywords": [
            "Responsible AI", "metadata extraction",
            "Croissant", "LLM evaluation", "human annotation",
            "inter-annotator agreement", "benchmark",
        ],
        "creator": ANON_CREATOR if ANON else FINAL_CREATOR,
        "publisher": ANON_PUBLISHER if ANON else FINAL_PUBLISHER,
        "citeAs": ANON_CITE if ANON else FINAL_CITE,
        "distribution": build_distribution(),
        "recordSet": [build_record_set(p) for p in PARQUET_FILES
                      if _resolve_parquet_path(p["filename"]) is not None],
        **RAI_FIELDS,
        "rai:hasSyntheticData": RAI_HAS_SYNTHETIC_DATA,
        "prov:wasDerivedFrom": PROV_WAS_DERIVED_FROM,
        "prov:wasGeneratedBy": PROV_WAS_GENERATED_BY,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true",
                    help="Build the camera-ready (de-anonymised) version")
    ap.add_argument("--base-url", default=None,
                    help="Absolute URL prefix for distribution contentUrl "
                         "(e.g., https://huggingface.co/datasets/foo/bar/"
                         "resolve/main). Required for the HF Croissant "
                         "Space's records-generation test to pass.")
    args = ap.parse_args()
    if args.final:
        global ANON
        ANON = False
    if args.base_url:
        global CONTENT_URL_BASE
        CONTENT_URL_BASE = args.base_url

    dataset = build_dataset()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    mode = "ANONYMOUS (submission)" if ANON else "FINAL (camera-ready)"
    print(f"Wrote: {OUT_PATH}  [{mode}]")
    print(f"  Distribution files: {len(dataset['distribution'])}")
    print(f"  Record sets:        {len(dataset['recordSet'])}")
    print(f"  RAI fields:         "
          f"{sum(1 for k in dataset if k.startswith('rai:'))}")
    print(f"  Total bytes:        {OUT_PATH.stat().st_size:,}")
    if ANON:
        print(f"  creator: {dataset['creator'][0]['name']!r}")
        print(f"  publisher: {dataset['publisher']['name']!r}")
        print(f"  url: {dataset['url']}")


if __name__ == "__main__":
    main()
