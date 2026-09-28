#!/usr/bin/env python3
"""
Ablation experiment infrastructure for CroissantMiner.

Supports 3 ablation types:
  prompt   — full | no_rai_instructions | no_extraction_guides | minimal
  context  — full | half | quarter
  few_shot — zero_shot | one_shot | three_shot

Usage:
    python scripts/run_ablations.py --type prompt --variant full
    python scripts/run_ablations.py --type prompt --all
    python scripts/run_ablations.py --type context --variant half
    python scripts/run_ablations.py --type few_shot --variant one_shot
    python scripts/run_ablations.py --compare prompt    # compare completed variants
    python scripts/run_ablations.py --dry-run --type prompt --variant minimal
"""

import sys
import json
import re
import time
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

BENCHMARK_MAP = {
    "2012.03411v2": "MLS",
    "2009.03300v3": "MMLU",
    "2106.03193v1": "FLORES",
    "2404.00498v2": "CIFAR",
    "1405.0312v3": "MSCOCO",
    "2311.16502v4": "MMMU",
    "1602.07332v1": "Visual Genome",
    "2310.02255v3": "MathVista",
}

RAW_DIR = Path("data/raw")
ABLATION_DIR = Path("evaluation_outputs_ablations")

ABLATION_TYPES = {
    "prompt": ["full", "no_rai_instructions", "no_extraction_guides", "minimal"],
    "context": ["full", "half", "quarter"],
    "few_shot": ["zero_shot", "one_shot", "three_shot"],
}

# ═══════════════════════════════════════════════════════════════════════
# Few-shot examples (from MLS groundtruth — excluded from eval if used)
# ═══════════════════════════════════════════════════════════════════════

FEW_SHOT_EXAMPLES = [
    {
        "paper_snippet": "MLS dataset is derived from read audiobooks from LibriVox. It consists of 8 languages: English, German, Dutch, Spanish, French, Italian, Portuguese, Polish. About 44.5K hours of English audio.",
        "extraction": {
            "name": "Multilingual LibriSpeech (MLS)",
            "description": "A large multilingual corpus suitable for speech research, derived from read audiobooks from LibriVox, consisting of 8 languages with about 44.5K hours of English and 6K hours for other languages.",
            "url": "http://www.openslr.org/94/",
            "license": "Creative Commons 4.0",
            "creator": "Vineel Pratap, Qiantong Xu, Anuroop Sriram, Gabriel Synnaeve, Ronan Collobert (Facebook AI Research)",
            "publisher": None,
            "datePublished": "2020",
            "inLanguage": "en, de, nl, es, fr, it, pt, pl",
            "citeAs": "Pratap et al., \"MLS: A Large-Scale Multilingual Dataset for Speech Research,\" Interspeech 2020",
            "isLiveDataset": "No",
            "rai:dataCollection": "Audio data was sourced from LibriVox, an online repository of free public domain audiobooks read by volunteers.",
            "rai:dataCollectionType": "Secondary Data analysis",
            "rai:dataCollectionMissingData": None,
            "rai:dataCollectionRawData": "Read audiobooks from LibriVox, a collection of free public domain audiobooks.",
            "rai:dataCollectionTimeframe": "2020",
            "rai:dataImputationProtocol": None,
            "rai:dataManipulationProtocol": None,
            "rai:dataPreprocessingProtocol": "Audio was segmented using voice activity detection, aligned with transcriptions, and split into train/dev/test sets.",
            "rai:dataAnnotationProtocol": None,
            "rai:dataAnnotationPlatform": None,
            "rai:dataAnnotationAnalysis": None,
            "rai:annotationsPerItem": None,
            "rai:annotatorDemographics": "Volunteers from the LibriVox community who read audiobooks.",
            "rai:machineAnnotationTools": None,
            "rai:dataReleaseMaintenancePlan": None,
            "rai:personalSensitiveInformation": None,
            "rai:dataSocialImpact": None,
            "rai:dataBiases": None,
            "rai:dataLimitations": None,
            "rai:dataUseCases": "Training, Testing, Validation for speech recognition and related tasks.",
        }
    },
    {
        "paper_snippet": "We introduce MMLU, a test to measure knowledge acquired during pretraining. The test covers 57 subjects across STEM, humanities, social sciences, and other areas. It ranges in difficulty from elementary to professional level.",
        "extraction": {
            "name": "Massive Multitask Language Understanding (MMLU)",
            "description": "A benchmark for measuring knowledge acquired during pretraining across 57 subjects spanning STEM, humanities, social sciences, and other areas, ranging from elementary to advanced professional difficulty.",
            "url": "https://github.com/hendrycks/test",
            "license": None,
            "creator": "Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, Jacob Steinhardt",
            "publisher": None,
            "datePublished": "2021",
            "inLanguage": "en",
            "citeAs": "Hendrycks et al., \"Measuring Massive Multitask Language Understanding,\" ICLR 2021",
            "isLiveDataset": "No",
            "rai:dataCollection": "Questions were manually collected from freely available sources including practice exams for professional certifications, academic exams, and standardized tests.",
            "rai:dataCollectionType": "Document analysis, Manual Human Curator",
            "rai:dataCollectionMissingData": None,
            "rai:dataCollectionRawData": "Practice exams, academic tests, and standardized test questions from publicly available sources.",
            "rai:dataCollectionTimeframe": None,
            "rai:dataImputationProtocol": None,
            "rai:dataManipulationProtocol": None,
            "rai:dataPreprocessingProtocol": "Questions were filtered for quality and organized into 57 subject categories.",
            "rai:dataAnnotationProtocol": None,
            "rai:dataAnnotationPlatform": None,
            "rai:dataAnnotationAnalysis": None,
            "rai:annotationsPerItem": None,
            "rai:annotatorDemographics": None,
            "rai:machineAnnotationTools": None,
            "rai:dataReleaseMaintenancePlan": None,
            "rai:personalSensitiveInformation": None,
            "rai:dataSocialImpact": None,
            "rai:dataBiases": None,
            "rai:dataLimitations": "Limited to English and multiple-choice format. Questions sourced primarily from US-centric educational materials.",
            "rai:dataUseCases": "Testing, Benchmarking for language model evaluation.",
        }
    },
    {
        "paper_snippet": "MS COCO is a large-scale dataset for detecting and segmenting objects in context. We gathered images of complex everyday scenes with common objects in their natural context. 328K images with 2.5 million labeled instances in 91 object categories.",
        "extraction": {
            "name": "Microsoft COCO (Common Objects in Context)",
            "description": "A large-scale dataset for object detection, segmentation, and captioning containing 328K images with 2.5 million labeled instances across 91 object categories in complex everyday scenes.",
            "url": "http://mscoco.org/",
            "license": None,
            "creator": "Tsung-Yi Lin, Michael Maire, Serge Belongie, James Hays, Pietro Perona, Deva Ramanan, Piotr Dollar, C. Lawrence Zitnick",
            "publisher": None,
            "datePublished": "2014",
            "inLanguage": None,
            "citeAs": "Lin et al., \"Microsoft COCO: Common Objects in Context,\" ECCV 2014",
            "isLiveDataset": "No",
            "rai:dataCollection": "Images were collected from Flickr by searching for pairs of common object categories to ensure non-iconic views of objects in natural contexts.",
            "rai:dataCollectionType": "Web Scraping, Manual Human Curator",
            "rai:dataCollectionMissingData": None,
            "rai:dataCollectionRawData": "Images sourced from Flickr, a photo-sharing platform.",
            "rai:dataCollectionTimeframe": None,
            "rai:dataImputationProtocol": None,
            "rai:dataManipulationProtocol": None,
            "rai:dataPreprocessingProtocol": "Candidate images were filtered to remove iconic views, invalid images, and images with insufficient object instances.",
            "rai:dataAnnotationProtocol": "Three-stage pipeline on Amazon Mechanical Turk: (1) category labeling per image, (2) instance spotting for each category, (3) instance segmentation with detailed polygon masks.",
            "rai:dataAnnotationPlatform": "Amazon Mechanical Turk (AMT)",
            "rai:dataAnnotationAnalysis": "Worker quality was evaluated by comparing AMT annotations with expert annotations from co-authors.",
            "rai:annotationsPerItem": "8 workers per image for category labeling; 8 workers per image for instance spotting",
            "rai:annotatorDemographics": None,
            "rai:machineAnnotationTools": None,
            "rai:dataReleaseMaintenancePlan": None,
            "rai:personalSensitiveInformation": None,
            "rai:dataSocialImpact": None,
            "rai:dataBiases": None,
            "rai:dataLimitations": "Currently only labels 'things' (objects with individual instances), not 'stuff' categories (materials/textures like sky, grass).",
            "rai:dataUseCases": "Training, Testing for object detection, instance segmentation, and image captioning.",
        }
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Prompt variant builders
# ═══════════════════════════════════════════════════════════════════════

def build_prompt_variant(variant: str):
    """Build system prompt for a given prompt ablation variant."""
    if variant == "full":
        return SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, "Full prompt with all extraction guides"

    elif variant == "no_extraction_guides":
        # Remove [EXTRACTION GUIDE] blocks and GOOD/BAD/MOST LIKELY lines
        sys_prompt = SYSTEM_PROMPT
        sys_prompt = re.sub(
            r'\n     \[EXTRACTION GUIDE\].*?(?=\n   - \*\*|\n\n|\'\'\'$)',
            '', sys_prompt, flags=re.DOTALL
        )
        return sys_prompt, USER_PROMPT_TEMPLATE, "Spec definitions only, no extraction guides"

    elif variant == "no_rai_instructions":
        # Remove the entire RAI field-specific section (section 5)
        sys_prompt = re.sub(
            r'\n5\. \*\*RAI Field-Specific Information:\*\*.*$',
            "'''",  # close the triple-quote
            SYSTEM_PROMPT, flags=re.DOTALL
        )
        # Fix: ensure it ends properly
        if not sys_prompt.rstrip().endswith("'''"):
            sys_prompt = sys_prompt.rstrip() + "'''"
        # Remove the trailing triple quotes that were part of the original
        sys_prompt = sys_prompt.replace("''''''", "'''")
        # Actually just strip to the content, we pass as a string not code
        sys_prompt = re.sub(
            r'\n5\. \*\*RAI Field-Specific Information:\*\*.*',
            '', SYSTEM_PROMPT, flags=re.DOTALL
        )
        return sys_prompt, USER_PROMPT_TEMPLATE, "General guidelines + general field info, no RAI definitions"

    elif variant == "minimal":
        sys_prompt = (
            "You are a metadata extraction assistant. "
            "Extract structured metadata from the provided academic paper. "
            "Return ONLY valid JSON. Use null for missing fields."
        )
        return sys_prompt, USER_PROMPT_TEMPLATE, "Minimal: just JSON schema, no field descriptions"

    else:
        raise ValueError(f"Unknown prompt variant: {variant}")


def build_context_variant(variant: str):
    """Return max_chars for a context ablation variant."""
    if variant == "full":
        return MAX_PDF_CHARS, f"Full context ({MAX_PDF_CHARS:,} chars)"
    elif variant == "half":
        chars = MAX_PDF_CHARS // 2
        return chars, f"Half context ({chars:,} chars)"
    elif variant == "quarter":
        chars = MAX_PDF_CHARS // 4
        return chars, f"Quarter context ({chars:,} chars)"
    else:
        raise ValueError(f"Unknown context variant: {variant}")


def build_few_shot_user_prompt(variant: str, pdf_content: str):
    """Build user prompt with few-shot examples prepended."""
    if variant == "zero_shot":
        return USER_PROMPT_TEMPLATE % pdf_content, "Zero-shot (current baseline)"

    examples = FEW_SHOT_EXAMPLES[:1] if variant == "one_shot" else FEW_SHOT_EXAMPLES[:3]
    n = len(examples)

    examples_text = ""
    for i, ex in enumerate(examples, 1):
        examples_text += f"\n--- EXAMPLE {i}/{n} ---\n"
        examples_text += f"Paper snippet: \"{ex['paper_snippet']}\"\n"
        examples_text += f"Correct extraction:\n{json.dumps(ex['extraction'], indent=2, ensure_ascii=False)}\n"
    examples_text += f"\n--- END EXAMPLES ---\n\n"

    # Insert examples before the schema
    user_prompt = USER_PROMPT_TEMPLATE.replace(
        "Extract metadata from the following academic paper",
        f"Here {'is 1 example' if n == 1 else f'are {n} examples'} of correct extraction:\n{examples_text}\n"
        "Now extract metadata from the following academic paper"
    )
    return user_prompt % pdf_content, f"{n}-shot ({n} example{'s' if n > 1 else ''} prepended)"


# ═══════════════════════════════════════════════════════════════════════
# Extraction runner
# ═══════════════════════════════════════════════════════════════════════

def run_extraction(
    output_dir: Path,
    sys_prompt: str,
    user_prompt_template: str,
    max_chars: int = MAX_PDF_CHARS,
    few_shot_variant: str = "zero_shot",
    dry_run: bool = False,
):
    """Run extraction on all 8 benchmarks with given prompt configuration."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"  [DRY RUN] Would extract 8 datasets to {output_dir}/")
        print(f"  System prompt length: {len(sys_prompt)} chars")
        print(f"  Max PDF chars: {max_chars:,}")
        print(f"  Few-shot: {few_shot_variant}")
        # Save config for reference
        config = {
            "system_prompt_length": len(sys_prompt),
            "system_prompt_preview": sys_prompt[:300] + "...",
            "max_chars": max_chars,
            "few_shot": few_shot_variant,
            "datasets": list(BENCHMARK_MAP.values()),
        }
        with open(output_dir / "ablation_config.json", "w") as f:
            json.dump(config, f, indent=2)
        return

    from metadata.extractor import setup_llm_pipeline, clean_llm_output
    from pdf.reader import extract_text_from_pdf
    from pdf.processor import clean_text

    model = setup_llm_pipeline("claude-sonnet-4-5")

    for pdf_id, ds_name in BENCHMARK_MAP.items():
        pdf_path = RAW_DIR / f"{pdf_id}.pdf"
        if not pdf_path.exists():
            print(f"  SKIP {ds_name}: PDF not found")
            continue

        print(f"  {ds_name}...", end=" ", flush=True)
        start = time.time()

        raw_text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(raw_text)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars]

        # Build user prompt (with or without few-shot examples)
        if few_shot_variant != "zero_shot":
            user_prompt, _ = build_few_shot_user_prompt(few_shot_variant, cleaned)
        else:
            user_prompt = user_prompt_template % cleaned

        output = model.generate(user_prompt, system_prompt=sys_prompt)
        json_str = clean_llm_output(output, user_prompt)

        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError:
            # Regex fallback
            metadata = {}
            for m in re.finditer(r'"([^"]+)"\s*:\s*null', json_str):
                metadata[m.group(1)] = None
            for m in re.finditer(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str):
                metadata[m.group(1)] = m.group(2).replace('\\n', ' ').strip()
            print(f"(regex: {len(metadata)} fields)", end=" ")

        with open(output_dir / f"{ds_name}_extraction.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"{time.time() - start:.0f}s")


def run_evaluation(extraction_dir: Path):
    """Run LLM-as-judge evaluation on an extraction directory."""
    from evaluation.evaluator import batch_evaluate
    from evaluation.groundtruth_parser_md import parse_markdown_groundtruth

    gt_dir = "groundtruth/parsed_md_filtered"
    parse_markdown_groundtruth("groundtruth/Croissant_Dataset_Annotations.md", output_dir=gt_dir)

    output_file = str(extraction_dir / "evaluation_report.json")
    batch_evaluate(
        extraction_outputs_dir=str(extraction_dir),
        groundtruth_dir=gt_dir,
        output_file=output_file,
        verbose=False,
        use_llm=True
    )
    return output_file


# ═══════════════════════════════════════════════════════════════════════
# Comparison
# ═══════════════════════════════════════════════════════════════════════

def compare_ablation(ablation_type: str):
    """Compare all completed variants of an ablation type."""
    variants = ABLATION_TYPES[ablation_type]
    base_dir = ABLATION_DIR / ablation_type

    print(f"\n{'='*90}")
    print(f"ABLATION COMPARISON: {ablation_type.upper()}")
    print(f"{'='*90}")

    results = {}
    for variant in variants:
        report_path = base_dir / variant / "evaluation_report.json"
        if not report_path.exists():
            print(f"  {variant}: NOT YET EVALUATED")
            continue

        with open(report_path) as f:
            data = json.load(f)

        field_scores = {}
        ds_accs = {}
        for ds_name, ds_data in data.get("results", {}).items():
            stats = ds_data.get("metrics", {}).get("overall_stats", {})
            ds_accs[ds_name] = stats.get("llm_accuracy", 0)
            for field, result in ds_data.get("metrics", {}).get("field_results", {}).items():
                field_scores.setdefault(field, []).append(result["score"])

        overall = np.mean(list(ds_accs.values())) * 100 if ds_accs else 0
        results[variant] = {"overall": overall, "ds_accs": ds_accs, "field_scores": field_scores}

    if len(results) < 2:
        print("  Need at least 2 completed variants to compare.")
        return

    # Overall comparison
    print(f"\n{'Variant':<30} {'Overall':>8} {'vs full':>8}")
    print("-" * 50)

    full_acc = results.get("full", results.get("zero_shot", {})).get("overall", 0)
    for variant in variants:
        if variant not in results:
            continue
        r = results[variant]
        delta = r["overall"] - full_acc
        marker = " (baseline)" if variant in ("full", "zero_shot") else ""
        print(f"{variant:<30} {r['overall']:>7.1f}% {delta:>+7.1f}pp{marker}")

    # Per-dataset
    print(f"\n{'Dataset':<20}", end="")
    for v in variants:
        if v in results:
            print(f" {v:>16}", end="")
    print()
    print("-" * (20 + 17 * len([v for v in variants if v in results])))

    all_datasets = sorted(set(
        ds for r in results.values() for ds in r["ds_accs"].keys()
    ))
    for ds in all_datasets:
        print(f"{ds:<20}", end="")
        for v in variants:
            if v in results:
                acc = results[v]["ds_accs"].get(ds, 0) * 100
                print(f" {acc:>15.1f}%", end="")
        print()

    # LaTeX table
    print(f"\n{'='*90}")
    print("LATEX TABLE")
    print(f"{'='*90}")
    print(r"\begin{table}[h]")
    print(r"\centering")
    print(f"\\caption{{{ablation_type.replace('_', ' ').title()} ablation results.}}")
    print(r"\begin{tabular}{l" + "c" * len(results) + "}")
    print(r"\toprule")
    header = "Dataset"
    for v in variants:
        if v in results:
            header += f" & {v.replace('_', ' ')}"
    print(header + r" \\")
    print(r"\midrule")

    for ds in all_datasets:
        row = ds
        for v in variants:
            if v in results:
                acc = results[v]["ds_accs"].get(ds, 0) * 100
                bold = acc == max(results[vv]["ds_accs"].get(ds, 0) * 100 for vv in results)
                acc_str = f"\\textbf{{{acc:.1f}\\%}}" if bold else f"{acc:.1f}\\%"
                row += f" & {acc_str}"
        print(row + r" \\")

    print(r"\midrule")
    row = "\\textbf{Overall}"
    for v in variants:
        if v in results:
            acc = results[v]["overall"]
            bold = acc == max(r["overall"] for r in results.values())
            acc_str = f"\\textbf{{{acc:.1f}\\%}}" if bold else f"{acc:.1f}\\%"
            row += f" & {acc_str}"
    print(row + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CroissantMiner ablation experiments")
    parser.add_argument("--type", choices=["prompt", "context", "few_shot"],
                        help="Ablation type")
    parser.add_argument("--variant", type=str,
                        help="Specific variant to run")
    parser.add_argument("--all", action="store_true",
                        help="Run all variants of the specified type")
    parser.add_argument("--compare", type=str, metavar="TYPE",
                        help="Compare completed variants of a type")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't run extractions, just show what would happen")
    parser.add_argument("--skip-eval", action="store_true",
                        help="Skip LLM-as-judge evaluation after extraction")
    parser.add_argument("--list", action="store_true",
                        help="List all ablation types and variants")
    args = parser.parse_args()

    if args.list:
        print("Available ablation experiments:")
        for atype, variants in ABLATION_TYPES.items():
            print(f"\n  --type {atype}")
            for v in variants:
                out_dir = ABLATION_DIR / atype / v
                status = "DONE" if (out_dir / "evaluation_report.json").exists() else \
                         "EXTRACTED" if any(out_dir.glob("*_extraction.json")) else "PENDING"
                print(f"    --variant {v:<25} [{status}]")
        return

    if args.compare:
        if args.compare not in ABLATION_TYPES:
            parser.error(f"Unknown ablation type: {args.compare}")
        compare_ablation(args.compare)
        return

    if not args.type:
        parser.error("--type is required (or use --compare, --list)")

    # Determine which variants to run
    if args.all:
        variants_to_run = ABLATION_TYPES[args.type]
    elif args.variant:
        if args.variant not in ABLATION_TYPES[args.type]:
            parser.error(f"Unknown variant '{args.variant}' for type '{args.type}'. "
                         f"Available: {ABLATION_TYPES[args.type]}")
        variants_to_run = [args.variant]
    else:
        parser.error("Specify --variant or --all")

    # Run each variant
    for variant in variants_to_run:
        out_dir = ABLATION_DIR / args.type / variant
        print(f"\n{'='*60}")
        print(f"ABLATION: {args.type} / {variant}")
        print(f"{'='*60}")

        # Check if already done
        if (out_dir / "evaluation_report.json").exists() and not args.dry_run:
            print(f"  Already completed. Skipping. (delete {out_dir} to re-run)")
            continue

        # Build configuration for this variant
        sys_prompt = SYSTEM_PROMPT
        user_template = USER_PROMPT_TEMPLATE
        max_chars = MAX_PDF_CHARS
        few_shot = "zero_shot"
        description = ""

        if args.type == "prompt":
            sys_prompt, user_template, description = build_prompt_variant(variant)
        elif args.type == "context":
            max_chars, description = build_context_variant(variant)
        elif args.type == "few_shot":
            few_shot = variant
            _, description = build_few_shot_user_prompt(variant, "")  # just get description

        print(f"  Config: {description}")
        print(f"  System prompt: {len(sys_prompt)} chars")
        print(f"  Max PDF chars: {max_chars:,}")
        print(f"  Few-shot: {few_shot}")
        print(f"  Output: {out_dir}/")

        # Save ablation config
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "ablation_config.json", "w") as f:
            json.dump({
                "type": args.type,
                "variant": variant,
                "description": description,
                "system_prompt_length": len(sys_prompt),
                "max_pdf_chars": max_chars,
                "few_shot": few_shot,
            }, f, indent=2)

        # Run extraction
        run_extraction(out_dir, sys_prompt, user_template, max_chars, few_shot, args.dry_run)

        # Run evaluation
        if not args.dry_run and not args.skip_eval:
            print(f"\n  Evaluating {variant}...")
            run_evaluation(out_dir)
            print(f"  Evaluation saved to {out_dir}/evaluation_report.json")

    # Compare if all variants of this type are done
    if args.all and not args.dry_run:
        compare_ablation(args.type)


if __name__ == "__main__":
    main()
