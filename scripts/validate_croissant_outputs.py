#!/usr/bin/env python3.10
"""
Validate CroissantMiner outputs as Croissant JSON-LD files.

Converts extraction outputs to proper Croissant format, validates with
mlcroissant library, and compares against HF auto-generated Croissant files.

Requires Python 3.10+ and mlcroissant: pip install mlcroissant

Usage:
    python3.10 scripts/validate_croissant_outputs.py
"""

import sys
import json
import logging
from pathlib import Path
from collections import defaultdict

# Suppress verbose mlcroissant warnings during bulk validation
logging.getLogger("absl").setLevel(logging.ERROR)

BENCHMARK_MAP = {
    "MLS": "facebook/multilingual_librispeech",
    "MMLU": "cais/mmlu",
    "FLORES": "facebook/flores",
    "CIFAR": "uoft-cs/cifar10",
    "MSCOCO": "detection-datasets/coco",
    "MMMU": "MMMU/MMMU",
    "Visual Genome": "ranjaykrishna/visual_genome",
    "MathVista": "AI4Math/MathVista",
}

EXTRACTION_DIR = Path("evaluation_outputs_v2")
COMBINED_DIR = Path("results/ablations/source_ablation/combined")
HF_RAW_DIR = Path("data/baselines/hf_croissant_raw")
OUTPUT_DIR = Path("data/croissant_outputs")

# Official Croissant 1.0 @context (from mlcommons/croissant spec)
CROISSANT_CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataBiases": "cr:dataBiases",
    "dataCollection": "cr:dataCollection",
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "fileProperty": "cr:fileProperty",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "personalSensitiveInformation": "cr:personalSensitiveInformation",
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


def extraction_to_croissant(extraction: dict, ds_name: str, hf_id: str) -> dict:
    """Convert raw extraction output to valid Croissant JSON-LD."""
    # Get values with fallback
    def get(key, *alt_keys):
        v = extraction.get(key)
        if v is None or (isinstance(v, str) and v.strip().lower() in ("null", "", "none")):
            for alt in alt_keys:
                v = extraction.get(alt)
                if v is not None and str(v).strip().lower() not in ("null", "", "none"):
                    return v
            return None
        return v

    name = get("name", "sc:name") or ds_name
    url = get("url", "sc:url") or f"https://huggingface.co/datasets/{hf_id}"

    croissant = {
        "@context": CROISSANT_CONTEXT,
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": name,
        "url": url,
    }

    # Optional general fields
    desc = get("description", "sc:description")
    if desc:
        croissant["description"] = desc

    license_val = get("license", "sc:license")
    if license_val:
        croissant["license"] = license_val

    creator = get("creator", "sc:creator")
    if creator:
        if isinstance(creator, str):
            croissant["creator"] = {"@type": "Organization", "name": creator}
        elif isinstance(creator, dict):
            croissant["creator"] = creator
        elif isinstance(creator, list):
            croissant["creator"] = [
                {"@type": "Person", "name": c} if isinstance(c, str) else c
                for c in creator
            ]

    date = get("datePublished", "sc:datePublished")
    if date:
        croissant["datePublished"] = str(date)

    lang = get("inLanguage", "sc:inLanguage")
    if lang:
        croissant["inLanguage"] = lang

    cite = get("citeAs", "cr:citeAs")
    if cite:
        croissant["citeAs"] = cite

    is_live = get("isLiveDataset", "cr:isLiveDataset")
    if is_live is not None:
        croissant["isLiveDataset"] = str(is_live).lower() in ("true", "yes")

    publisher = get("publisher", "sc:publisher")
    if publisher:
        croissant["publisher"] = {"@type": "Organization", "name": publisher}

    # RAI fields (Croissant RAI extension)
    rai_fields = {
        "dataCollection": get("rai:dataCollection", "dataCollection"),
        "dataBiases": get("rai:dataBiases", "dataBiases"),
        "personalSensitiveInformation": get("rai:personalSensitiveInformation", "personalSensitiveInformation"),
    }
    for k, v in rai_fields.items():
        if v:
            croissant[k] = v

    # Distribution: point to the HF repository
    safe_name = name.replace(" ", "-").lower()
    croissant["distribution"] = [
        {
            "@type": "cr:FileObject",
            "@id": "repo",
            "name": "repo",
            "description": "The dataset repository.",
            "contentUrl": url,
            "encodingFormat": "git+https",
            "sha256": "https://github.com/mlcommons/croissant/issues/80",
        }
    ]

    # Minimal recordSet with proper source reference
    croissant["recordSet"] = [
        {
            "@type": "cr:RecordSet",
            "@id": f"{safe_name}-records",
            "name": f"{safe_name}-records",
            "field": [
                {
                    "@type": "cr:Field",
                    "@id": f"{safe_name}-records/data",
                    "name": "data",
                    "dataType": "sc:Text",
                    "source": {
                        "fileObject": {"@id": "repo"},
                        "extract": {"column": "data"},
                    },
                }
            ],
        }
    ]

    return croissant


def validate_file(filepath: str) -> dict:
    """Validate a Croissant JSON-LD file using mlcroissant."""
    try:
        import mlcroissant
        ds = mlcroissant.Dataset(filepath)
        errors = ds.metadata.issues.errors
        warnings = ds.metadata.issues.warnings

        return {
            "valid": len(errors) == 0,
            "errors": len(errors),
            "warnings": len(warnings),
            "error_list": [str(e) for e in errors],
            "warning_list": [str(w) for w in warnings],
            "name": ds.metadata.name,
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "error_list": [str(e)],
            "warning_list": [],
            "name": None,
        }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("CROISSANT JSON-LD VALIDATION")
    print("=" * 80)

    # Step 1: Convert CroissantMiner extractions to Croissant JSON-LD
    print("\nStep 1: Converting CroissantMiner extractions to Croissant JSON-LD...")

    cm_results = {}
    # Prefer combined extractions if available, fall back to paper-only
    for ds_name, hf_id in BENCHMARK_MAP.items():
        # Try combined first, then paper-only
        ext_file = COMBINED_DIR / f"{ds_name}_extraction.json"
        if not ext_file.exists():
            ext_file = EXTRACTION_DIR / f"{ds_name}_extraction.json"
        if not ext_file.exists():
            print(f"  {ds_name}: NO EXTRACTION FOUND")
            continue

        with open(ext_file) as f:
            extraction = json.load(f)

        croissant = extraction_to_croissant(extraction, ds_name, hf_id)

        out_file = OUTPUT_DIR / f"{ds_name}_croissant.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(croissant, f, indent=2, ensure_ascii=False)

        # Count populated fields
        populated = sum(1 for k, v in croissant.items()
                        if k not in ("@context", "@type", "conformsTo", "distribution", "recordSet")
                        and v is not None)

        print(f"  {ds_name}: {populated} fields populated → {out_file.name}")

    # Step 2: Validate CroissantMiner outputs
    print("\nStep 2: Validating CroissantMiner outputs...")

    cm_validations = {}
    for f in sorted(OUTPUT_DIR.glob("*_croissant.json")):
        ds_name = f.stem.replace("_croissant", "")
        result = validate_file(str(f))
        cm_validations[ds_name] = result
        status = "✓ VALID" if result["valid"] else f"✗ {result['errors']} errors"
        warnings_str = f", {result['warnings']} warnings" if result['warnings'] > 0 else ""
        print(f"  {ds_name}: {status}{warnings_str}")
        if result["error_list"]:
            for e in result["error_list"][:3]:
                print(f"    ERROR: {e[:100]}")
        if result["warning_list"]:
            for w in result["warning_list"][:3]:
                print(f"    WARN: {w[:100]}")

    # Step 3: Validate HF Auto-Croissant files
    print("\nStep 3: Validating HF Auto-Croissant files...")

    hf_validations = {}
    for ds_name in BENCHMARK_MAP:
        f = HF_RAW_DIR / f"{ds_name}.json"
        if not f.exists():
            print(f"  {ds_name}: NO HF FILE")
            continue
        result = validate_file(str(f))
        hf_validations[ds_name] = result
        status = "✓ VALID" if result["valid"] else f"✗ {result['errors']} errors"
        warnings_str = f", {result['warnings']} warnings" if result['warnings'] > 0 else ""
        print(f"  {ds_name}: {status}{warnings_str}")

    # Step 4: Comparison table
    print(f"\n{'='*80}")
    print("COMPARISON TABLE")
    print(f"{'='*80}")

    cm_valid = sum(1 for v in cm_validations.values() if v["valid"])
    cm_errors = sum(v["errors"] for v in cm_validations.values())
    cm_warnings = sum(v["warnings"] for v in cm_validations.values())
    cm_n = len(cm_validations)

    hf_valid = sum(1 for v in hf_validations.values() if v["valid"])
    hf_errors = sum(v["errors"] for v in hf_validations.values())
    hf_warnings = sum(v["warnings"] for v in hf_validations.values())
    hf_n = len(hf_validations)

    print(f"\n{'Method':<22} {'Valid':>7} {'Errors':>8} {'Warnings':>10}")
    print("-" * 50)
    print(f"{'CroissantMiner':<22} {cm_valid}/{cm_n:>3}  {cm_errors:>6}  {cm_warnings:>8}")
    print(f"{'HF Auto-Croissant':<22} {hf_valid}/{hf_n:>3}  {hf_errors:>6}  {hf_warnings:>8}")

    # Per-dataset detail
    print(f"\n{'Dataset':<20} {'CM Valid':>9} {'CM Err':>7} {'CM Wrn':>7} {'HF Valid':>9} {'HF Err':>7} {'HF Wrn':>7}")
    print("-" * 70)
    for ds_name in BENCHMARK_MAP:
        cm = cm_validations.get(ds_name, {"valid": False, "errors": -1, "warnings": -1})
        hf = hf_validations.get(ds_name, {"valid": False, "errors": -1, "warnings": -1})
        cm_v = "✓" if cm["valid"] else "✗"
        hf_v = "✓" if hf["valid"] else "✗"
        print(f"{ds_name:<20} {cm_v:>9} {cm['errors']:>7} {cm['warnings']:>7} {hf_v:>9} {hf['errors']:>7} {hf['warnings']:>7}")

    # Save results
    results = {
        "croissantminer": {
            "valid": cm_valid, "total": cm_n,
            "total_errors": cm_errors, "total_warnings": cm_warnings,
            "per_dataset": {k: v for k, v in cm_validations.items()},
        },
        "hf_auto": {
            "valid": hf_valid, "total": hf_n,
            "total_errors": hf_errors, "total_warnings": hf_warnings,
            "per_dataset": {k: v for k, v in hf_validations.items()},
        },
    }
    with open(OUTPUT_DIR / "validation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to {OUTPUT_DIR}/")
    print(f"Croissant files: {OUTPUT_DIR}/*_croissant.json")


if __name__ == "__main__":
    main()
