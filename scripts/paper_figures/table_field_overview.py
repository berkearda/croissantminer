#!/usr/bin/env python3
"""
Table 1: Field overview with gold AND silver coverage columns.
LaTeX table: Field Name | Type | Metric | Definition | Gold Coverage | Silver Coverage
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from style import FIGURE_DIR

ROOT = Path(__file__).parent.parent.parent
PROCESSED = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
SILVER_EXT = ROOT / "silver" / "extractions"

FIELDS = [
    ("name",           "name",          "General", "Constrained", "Dataset name"),
    ("description",    "description",   "General", "Short-text",  "Brief dataset description"),
    ("url",            "url",           "General", "Constrained", "Access URL"),
    ("license",        "license",       "General", "Constrained", "Distribution license"),
    ("creator",        "creator",       "General", "Short-text",  "Dataset creator(s)"),
    ("publisher",      "publisher",     "General", "Constrained", "Publishing venue/org"),
    ("datePublished",  "datePublished", "General", "Constrained", "Publication date"),
    ("inLanguage",     "inLanguage",    "General", "Constrained", "Content language(s)"),
    ("citeAs",         "citeAs",        "General", "Short-text",  "Citation format"),
    ("isLiveDataset",  "isLiveDataset", "General", "Constrained", "Actively updated?"),
    ("rai:dataCollection",              "dataCollection",              "RAI", "LLM Judge", "Collection methodology"),
    ("rai:dataCollectionType",          "dataCollectionType",          "RAI", "LLM Judge", "Collection type (controlled vocab)"),
    ("rai:dataCollectionMissingData",   "dataCollectionMissingData",   "RAI", "LLM Judge", "Missing data handling"),
    ("rai:dataCollectionRawData",       "dataCollectionRawData",       "RAI", "LLM Judge", "Raw source data description"),
    ("rai:dataCollectionTimeframe",     "dataCollectionTimeframe",     "RAI", "LLM Judge", "Collection period"),
    ("rai:dataImputationProtocol",      "dataImputationProtocol",      "RAI", "LLM Judge", "Imputation methods"),
    ("rai:dataManipulationProtocol",    "dataManipulationProtocol",    "RAI", "LLM Judge", "Post-processing modifications"),
    ("rai:dataPreprocessingProtocol",   "dataPreprocessingProtocol",   "RAI", "LLM Judge", "Data cleaning/formatting steps"),
    ("rai:dataAnnotationProtocol",      "dataAnnotationProtocol",      "RAI", "LLM Judge", "Annotation methodology"),
    ("rai:dataAnnotationPlatform",      "dataAnnotationPlatform",      "RAI", "LLM Judge", "Annotation platform"),
    ("rai:dataAnnotationAnalysis",      "dataAnnotationAnalysis",      "RAI", "LLM Judge", "Annotation quality analysis"),
    ("rai:annotationsPerItem",          "annotationsPerItem",          "RAI", "LLM Judge", "Labels per data item"),
    ("rai:annotatorDemographics",       "annotatorDemographics",       "RAI", "LLM Judge", "Annotator demographics"),
    ("rai:machineAnnotationTools",      "machineAnnotationTools",      "RAI", "LLM Judge", "ML annotation tools"),
    ("rai:dataReleaseMaintenancePlan",  "dataReleaseMaintenancePlan",  "RAI", "LLM Judge", "Versioning/maintenance plan"),
    ("rai:personalSensitiveInformation","personalSensitiveInfo",       "RAI", "LLM Judge", "Sensitive attributes"),
    ("rai:dataSocialImpact",            "dataSocialImpact",            "RAI", "LLM Judge", "Social implications"),
    ("rai:dataBiases",                  "dataBiases",                  "RAI", "LLM Judge", "Known biases"),
    ("rai:dataLimitations",             "dataLimitations",             "RAI", "LLM Judge", "Known limitations"),
    ("rai:dataUseCases",                "dataUseCases",                "RAI", "LLM Judge", "Intended use cases"),
]


def main():
    # Load gold extractions
    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    gold_coverage = {}
    n_gold = 0
    for ds_id in sorted(paper_links.keys()):
        ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not ext_path.exists():
            continue
        n_gold += 1
        with open(ext_path) as f:
            d = json.load(f)
        for key, *_ in FIELDS:
            val = d.get(key)
            if val is not None and str(val).strip():
                gold_coverage[key] = gold_coverage.get(key, 0) + 1

    # Load silver extractions
    silver_coverage = {}
    n_silver = 0
    for ext_path in sorted(SILVER_EXT.glob("*.json")):
        with open(ext_path) as f:
            d = json.load(f)
        ext = d["extraction"]
        n_silver += 1
        for key, *_ in FIELDS:
            val = ext.get(key)
            if val is not None and str(val).strip():
                silver_coverage[key] = silver_coverage.get(key, 0) + 1

    print(f"  Gold: {n_gold} datasets, Silver: {n_silver} datasets")

    # Generate LaTeX
    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Overview of the 30 metadata fields in the Croissant 1.1 schema (10 General + 20 RAI). Coverage shows the percentage of datasets where each field was extracted as non-null for both the gold (N=" + str(n_gold) + r") and silver (N=" + str(n_silver) + r") datasets.}")
    lines.append(r"\label{tab:field-overview}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{lllllrr}")
    lines.append(r"\toprule")
    lines.append(r"Field & Type & Metric & Definition & Gold & Silver \\")
    lines.append(r"\midrule")

    gold_total_fill = 0
    silver_total_fill = 0

    prev_type = None
    for key, display, ftype, category, definition in FIELDS:
        if ftype != prev_type and prev_type is not None:
            lines.append(r"\midrule")
        prev_type = ftype

        g_cov = gold_coverage.get(key, 0)
        g_pct = g_cov / n_gold * 100 if n_gold > 0 else 0
        s_cov = silver_coverage.get(key, 0)
        s_pct = s_cov / n_silver * 100 if n_silver > 0 else 0

        gold_total_fill += g_pct
        silver_total_fill += s_pct

        display_tex = display.replace("_", r"\_")
        lines.append(f"\\texttt{{{display_tex}}} & {ftype} & {category} & {definition} & {g_pct:.0f}\\% & {s_pct:.0f}\\% \\\\")

    lines.append(r"\midrule")
    gold_avg = gold_total_fill / len(FIELDS)
    silver_avg = silver_total_fill / len(FIELDS)
    lines.append(f"\\textbf{{Average}} & & & & \\textbf{{{gold_avg:.1f}\\%}} & \\textbf{{{silver_avg:.1f}\\%}} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")

    latex = "\n".join(lines)

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURE_DIR / "table1_field_overview.tex"
    with open(out_path, "w") as f:
        f.write(latex)

    print(f"  Saved: {out_path}")
    print(f"  Gold avg fill: {gold_avg:.1f}%, Silver avg fill: {silver_avg:.1f}%")
    print(f"\n{latex}")


if __name__ == "__main__":
    main()
