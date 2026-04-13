#!/usr/bin/env python3
"""
Figure 3: Annotation results from real Phase 2 data.
(a) Rating distribution per field (stacked %, abbreviated labels)
(b) Failure mode composition per field type (normalized 100% stacked)
(c) Pairwise agreement per field (abbreviated labels)
(d) Rating distribution by field type (grouped bars)

Data source: Phase 2 annotation spreadsheets (latest download).
"""

import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, COLORS, DOUBLE_COL

SHEET_DIR = Path(os.environ.get("ANNOTATION_SHEETS_DIR", "data/annotations/phase2"))

# Field groupings
CONSTRAINED = ["name", "license", "inLanguage", "isLiveDataset", "datePublished", "publisher", "url", "citeAs"]
SHORT_TEXT = ["creator", "description"]
RAI_FIELDS = [
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]
ALL_FIELDS = CONSTRAINED + SHORT_TEXT + RAI_FIELDS

# Abbreviated display names
ABBREV = {
    "name": "name", "license": "license", "inLanguage": "inLanguage",
    "isLiveDataset": "isLiveDataset", "datePublished": "datePublished",
    "publisher": "publisher", "url": "url", "citeAs": "citeAs",
    "creator": "creator", "description": "description",
    "rai:dataCollection": "Collection", "rai:dataCollectionType": "CollType",
    "rai:dataCollectionMissingData": "MissingData",
    "rai:dataCollectionRawData": "RawData",
    "rai:dataCollectionTimeframe": "Timeframe",
    "rai:dataImputationProtocol": "Imputation",
    "rai:dataManipulationProtocol": "Manipulation",
    "rai:dataPreprocessingProtocol": "Preprocessing",
    "rai:dataAnnotationProtocol": "AnnProtocol",
    "rai:dataAnnotationPlatform": "AnnPlatform",
    "rai:dataAnnotationAnalysis": "AnnAnalysis",
    "rai:annotationsPerItem": "AnnPerItem",
    "rai:annotatorDemographics": "AnnDemog.",
    "rai:machineAnnotationTools": "MachineAnn",
    "rai:dataReleaseMaintenancePlan": "ReleasePlan",
    "rai:personalSensitiveInformation": "PSI",
    "rai:dataSocialImpact": "SocialImpact",
    "rai:dataBiases": "Biases",
    "rai:dataLimitations": "Limitations",
    "rai:dataUseCases": "UseCases",
}

name_map = {"annotator": "A09"}


def parse_rating(val):
    if pd.isna(val):
        return None
    m = re.match(r'^(\d)', str(val).strip())
    if m and int(m.group(1)) in (1, 2, 3):
        return int(m.group(1))
    return None


def field_type(f):
    if f in set(CONSTRAINED):
        return "Constrained"
    if f in set(SHORT_TEXT):
        return "Short-text"
    return "RAI"


def normalize_fm(fm_raw):
    fm_raw = fm_raw.lower().strip()
    if "incomplete" in fm_raw or "missing" in fm_raw:
        return "Incomplete"
    if "hallucin" in fm_raw or "fabricat" in fm_raw:
        return "Hallucination"
    if "wrong section" in fm_raw or "wrong field" in fm_raw:
        return "Wrong Section"
    if "granularity" in fm_raw or "too specific" in fm_raw or "too general" in fm_raw:
        return "Granularity Mismatch"
    if "format" in fm_raw:
        return "Format Error"
    return "Other"


def load_annotations():
    all_rows = []
    for xlsx_file in sorted(SHEET_DIR.glob("Phase2_*.xlsx")):
        name_raw = xlsx_file.stem.replace("Phase2_", "").replace("_", " ")
        aname = name_map.get(name_raw, name_raw)

        try:
            sheets = pd.read_excel(xlsx_file, sheet_name=None, engine="openpyxl")
        except Exception:
            continue

        ann_df = None
        ann_sheet_name = None
        for sn, df in sheets.items():
            if "annot" in sn.lower() and "analysis" not in sn.lower():
                ann_df = df
                ann_sheet_name = sn
                break
        if ann_df is None or ann_df.empty:
            continue

        cols_lower = [str(c).strip().lower() for c in ann_df.columns]
        ann_df.columns = cols_lower
        field_col = next((c for c in cols_lower if 'field' in c and 'name' in c), None)
        rating_col = next((c for c in cols_lower if 'rating' in c), None)

        if field_col is None or rating_col is None:
            ann_df_raw = pd.read_excel(xlsx_file, sheet_name=ann_sheet_name, engine="openpyxl", header=None)
            for hi in range(min(5, len(ann_df_raw))):
                row_vals = [str(v).strip().lower() for v in ann_df_raw.iloc[hi] if pd.notna(v)]
                if any('rating' in v for v in row_vals):
                    ann_df = ann_df_raw.copy()
                    ann_df.columns = [str(c).strip().lower() for c in ann_df_raw.iloc[hi]]
                    ann_df = ann_df.iloc[hi+1:].reset_index(drop=True)
                    cols_lower = list(ann_df.columns)
                    break
            field_col = next((c for c in cols_lower if 'field' in c and 'name' in c), None)
            rating_col = next((c for c in cols_lower if 'rating' in c), None)

        if field_col is None or rating_col is None:
            continue

        failure_col = next((c for c in cols_lower if 'failure' in c), None)
        ds_col = next((c for c in cols_lower if 'dataset' in c), None)

        for _, row in ann_df.iterrows():
            fv = row.get(field_col)
            if pd.isna(fv):
                continue
            fn = str(fv).strip()
            rating = parse_rating(row.get(rating_col))
            if rating is None:
                continue

            fm = ""
            if failure_col and not pd.isna(row.get(failure_col, None)):
                fm = str(row[failure_col]).strip()

            ds_id = ""
            if ds_col and not pd.isna(row.get(ds_col, None)):
                ds_id = str(row[ds_col]).strip()

            all_rows.append({
                "annotator": aname, "field": fn, "rating": rating,
                "failure_mode": fm, "ds_id": ds_id,
            })

    return all_rows


def main():
    setup_style()
    print("Loading Phase 2 annotations...", flush=True)
    rows = load_annotations()
    print(f"  Loaded {len(rows)} rated annotations")

    # Per-field ratings
    field_ratings = defaultdict(list)
    for r in rows:
        field_ratings[r["field"]].append(r["rating"])

    # Only show fields with >= 10 ratings
    shown_fields = [f for f in ALL_FIELDS if len(field_ratings.get(f, [])) >= 10]

    fig, axes = plt.subplots(2, 2, figsize=(DOUBLE_COL, 7.5))

    # ── (a) Rating distribution per field (stacked %) ──
    ax = axes[0, 0]

    # Create x positions with gaps between field type groups
    constrained_end = sum(1 for f in shown_fields if field_type(f) == "Constrained")
    short_end = constrained_end + sum(1 for f in shown_fields if field_type(f) == "Short-text")
    gap = 1.0  # gap width between groups
    x = []
    for i, f in enumerate(shown_fields):
        if i < constrained_end:
            x.append(i)
        elif i < short_end:
            x.append(i + gap)
        else:
            x.append(i + 2 * gap)
    x = np.array(x)

    width = 0.7
    bottoms = np.zeros(len(shown_fields))
    rating_colors = [COLORS["green"], COLORS["gold"], COLORS["highlight"]]
    rating_labels = ["Correct", "Partial", "Incorrect"]

    for ri, (label, color) in enumerate(zip(rating_labels, rating_colors)):
        pcts = []
        for f in shown_fields:
            rats = field_ratings[f]
            total = len(rats)
            count = sum(1 for r in rats if r == ri + 1)
            pcts.append(count / total * 100 if total > 0 else 0)
        ax.bar(x, pcts, width, bottom=bottoms, label=label, color=color,
               edgecolor="white", linewidth=0.3)
        bottoms += pcts

    ax.set_xticks(x)
    ax.set_xticklabels([ABBREV.get(f, f) for f in shown_fields],
                       rotation=55, ha="right", fontsize=7)
    ax.set_ylabel("Percentage")
    ax.set_title("(a) Rating Distribution per Field")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.38),
              ncol=3, frameon=False)
    ax.set_ylim(0, 100)

    # Group labels in the gap space, centered above
    con_mid = np.mean(x[:constrained_end])
    st_mid = np.mean(x[constrained_end:short_end])
    rai_mid = np.mean(x[short_end:])
    for mid, label in [(con_mid, "Constrained"), (st_mid, "Short-text"), (rai_mid, "RAI")]:
        ax.text(mid, 103, label, ha="center", fontsize=6.5, color="0.4", fontstyle="italic")
    ax.set_ylim(0, 108)

    # ── (b) Failure mode composition (normalized 100% stacked) ──
    ax = axes[0, 1]
    categories = ["Constrained", "Short-text", "RAI"]
    fm_ordered = ["Incomplete", "Hallucination", "Wrong Section",
                  "Granularity Mismatch", "Format Error", "Other"]
    fm_colors = [COLORS["claude"], COLORS["highlight"], COLORS["purple"],
                 COLORS["gold"], COLORS["teal"], COLORS["brown"]]

    fm_counts = {cat: Counter() for cat in categories}
    fm_totals = {cat: 0 for cat in categories}
    for r in rows:
        if r["rating"] in (2, 3) and r["failure_mode"]:
            ft = field_type(r["field"])
            fm_counts[ft][normalize_fm(r["failure_mode"])] += 1
            fm_totals[ft] += 1

    x_fm = np.arange(len(categories))
    bottom_fm = np.zeros(len(categories))
    for fm, color in zip(fm_ordered, fm_colors):
        vals = []
        for cat in categories:
            total = fm_totals[cat]
            vals.append(fm_counts[cat].get(fm, 0) / total * 100 if total > 0 else 0)
        ax.bar(x_fm, vals, 0.5, bottom=bottom_fm, label=fm, color=color,
               edgecolor="white", linewidth=0.3)
        bottom_fm += vals

    ax.set_xticks(x_fm)
    # Show category with total count
    ax.set_xticklabels([f"{cat}\n(n={fm_totals[cat]})" for cat in categories], fontsize=8)
    ax.set_ylabel("Percentage")
    ax.set_title("(b) Failure Mode Composition")
    ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=3, frameon=False)
    ax.set_ylim(0, 105)

    # ── (c) Pairwise agreement per field (abbreviated labels) ──
    ax = axes[1, 0]

    field_ds_ratings = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["ds_id"]:
            field_ds_ratings[r["field"]][r["ds_id"]].append(r["rating"])

    agree_rates = {}
    for f in shown_fields:
        agree = 0
        total = 0
        for ds_id, rats in field_ds_ratings[f].items():
            if len(rats) >= 2:
                for i in range(len(rats)):
                    for j in range(i + 1, len(rats)):
                        total += 1
                        if rats[i] == rats[j]:
                            agree += 1
        agree_rates[f] = agree / total * 100 if total > 0 else -1

    y_pos = np.arange(len(shown_fields))
    agree_vals = [agree_rates[f] for f in shown_fields]
    type_colors = [COLORS["claude"] if field_type(f) == "Constrained" else
                   COLORS["gpt"] if field_type(f) == "Short-text" else COLORS["green"]
                   for f in shown_fields]

    bars = ax.barh(y_pos, [max(v, 0) for v in agree_vals], color=type_colors,
                   edgecolor="white", linewidth=0.3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([ABBREV.get(f, f) for f in shown_fields], fontsize=7)
    ax.set_xlabel("Pairwise Agreement (%)")
    ax.set_title("(c) Inter-Annotator Agreement")
    ax.set_xlim(0, 105)
    ax.invert_yaxis()

    for i, v in enumerate(agree_vals):
        if v < 0:
            ax.text(2, i, "N/A", va="center", fontsize=6, color="gray")

    # Legend for field type colors
    from matplotlib.patches import Patch
    type_legend = [
        Patch(facecolor=COLORS["claude"], label="Constrained"),
        Patch(facecolor=COLORS["gpt"], label="Short-text"),
        Patch(facecolor=COLORS["green"], label="RAI"),
    ]
    ax.legend(handles=type_legend, fontsize=7, loc="lower right", frameon=True,
              framealpha=0.9, edgecolor="0.8")

    # ── (d) Rating distribution by field type (grouped bars) ──
    ax = axes[1, 1]

    type_ratings = {cat: Counter() for cat in categories}
    for r in rows:
        ft = field_type(r["field"])
        type_ratings[ft][r["rating"]] += 1

    x_type = np.arange(len(categories))
    width_t = 0.25
    for ri, (label, color) in enumerate(zip(rating_labels, rating_colors)):
        pcts = []
        for cat in categories:
            total = sum(type_ratings[cat].values())
            pcts.append(type_ratings[cat].get(ri + 1, 0) / total * 100 if total > 0 else 0)
        bars = ax.bar(x_type + ri * width_t, pcts, width_t, label=label, color=color,
                      edgecolor="white", linewidth=0.3)
        # Add percentage labels on bars
        for bar, pct in zip(bars, pcts):
            if pct > 3:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                        f"{pct:.0f}%", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x_type + width_t)
    # Show category with total count
    type_totals = {cat: sum(type_ratings[cat].values()) for cat in categories}
    ax.set_xticklabels([f"{cat}\n(n={type_totals[cat]})" for cat in categories], fontsize=8)
    ax.set_ylabel("Percentage")
    ax.set_title("(d) Rating Distribution by Field Type")
    ax.legend(fontsize=7, loc="upper right", frameon=True, framealpha=0.9, edgecolor="0.8")
    ax.set_ylim(0, 100)

    fig.tight_layout()
    save_fig(fig, "fig3_annotation_results")
    print(f"  Total annotations: {len(rows)}")
    print(f"  Failure mode totals: {dict(fm_totals)}")


if __name__ == "__main__":
    main()
