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

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

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
]


def build_distribution() -> list:
    """Build cr:FileObject entries for each parquet file."""
    out = []
    for p in PARQUET_FILES:
        path = ANNOT_DIR / p["filename"]
        if not path.exists():
            continue
        out.append({
            "@type": "cr:FileObject",
            "@id": f"{p['rid']}-parquet",
            "name": p["filename"],
            "description": p["description"],
            "contentUrl": p["filename"],
            "encodingFormat": "application/x-parquet",
            "sha256": sha256(path),
        })
    return out


def build_record_set(file_meta: dict) -> dict:
    """Build a cr:RecordSet describing one parquet's columns."""
    path = ANNOT_DIR / file_meta["filename"]
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
        "Maintained at https://github.com/berkearda/croissantminer. "
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
}


def build_dataset() -> dict:
    return {
        "@context": CONTEXT,
        "@type": "sc:Dataset",
        "@id": "https://github.com/berkearda/croissantminer/tree/main/data/annotations",
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
        "url": "https://github.com/berkearda/croissantminer",
        "version": "0.1.0",
        "datePublished": date.today().isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "inLanguage": "en",
        "isLiveDataset": False,
        "keywords": [
            "Responsible AI", "metadata extraction",
            "Croissant", "LLM evaluation", "human annotation",
            "inter-annotator agreement", "benchmark",
        ],
        "creator": [
            {
                "@type": "sc:Person",
                "name": "Berke Arda",
                "affiliation": "ETH Zurich",
            },
        ],
        "publisher": {
            "@type": "sc:Organization",
            "name": "ETH Zurich",
        },
        "citeAs": (
            "Arda, B., Akhtar, M., et al. CroissantMiner: Automated "
            "Extraction and Validation of Croissant Metadata for ML "
            "Datasets. NeurIPS 2026 Evaluations and Datasets Track."
        ),
        "distribution": build_distribution(),
        "recordSet": [build_record_set(p) for p in PARQUET_FILES
                      if (ANNOT_DIR / p["filename"]).exists()],
        **RAI_FIELDS,
    }


def main():
    dataset = build_dataset()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Wrote: {OUT_PATH}")
    print(f"  Distribution files: {len(dataset['distribution'])}")
    print(f"  Record sets:        {len(dataset['recordSet'])}")
    print(f"  RAI fields:         "
          f"{sum(1 for k in dataset if k.startswith('rai:'))}")
    print(f"  Total bytes:        {OUT_PATH.stat().st_size:,}")


if __name__ == "__main__":
    main()
