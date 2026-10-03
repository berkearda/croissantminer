"""The leaderboard tab of the demo: reads leaderboard/leaderboard.csv, the same file as leaderboard/README.md."""
from __future__ import annotations

import html
from pathlib import Path

import gradio as gr
import pandas as pd

CSV = Path(__file__).resolve().parent.parent / "leaderboard" / "leaderboard.csv"
REPO = "https://github.com/berkearda/croissantminer"
ALL_DESIGNS = "All designs"
COST = "Cost per paper (US$)"
SORTS = {"Sort by composite": "composite", "Sort by core": "core", "Sort by RAI": "rai",
         "Sort by paper's score": "paper_composite", "Sort by cost (cheapest first)": "cost"}
COLORS = {"Reference": "#64748b", "Single-pass": "#2563eb", "ReAct": "#dc2626", "Parallel Specialists": "#059669",
          "Triage + Critique": "#d97706", "Locator-Extractor": "#7c3aed"}

SUBMIT = f"""
1. Run your system on the 88 test papers and save one JSON file per paper with the 30 fields.
2. Score it with `make evaluate OUTPUTS=folder NAME=name` (needs an OpenRouter key for the judge, about US$0.75).
3. Open a pull request with the folder the script writes and a row in `leaderboard/leaderboard.csv`.

The steps, the file format and the rules are in [leaderboard/README.md]({REPO}/blob/main/leaderboard/README.md).
"""


def load(path: Path = CSV) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "paper_composite" not in df:
        df["paper_composite"] = df.composite
    df["cost"] = pd.to_numeric(df.cost_per_paper_usd.where(df.cost_per_paper_usd != "self-hosted", 0), errors="coerce")
    ranked = df[df.role == "ranked"].sort_values("composite", ascending=False)
    df["rank"] = ""
    df.loc[ranked.index, "rank"] = [str(i) for i in range(1, len(ranked) + 1)]
    return df


def texts(df: pd.DataFrame) -> tuple[str, str]:
    ranked = df[df.role == "ranked"]
    shift = (ranked.composite - ranked.paper_composite).mean()
    judge = df.judge.iloc[0] if "judge" in df else "GLM-5"
    when = df.judged_on.max() if "judged_on" in df else ""
    intro = (
        f"Extraction systems scored on the 88 test papers of the CroissantMiner benchmark with the paper's scorer. "
        f"**Composite** weights all 30 fields equally, **Core** averages the 10 core fields and **RAI** the 20 "
        f"Responsible AI fields, scored by {judge}"
        + (f", which judged every row in {pd.Timestamp(when).strftime('%B %Y')}" if when else "")
        + ". The 95% confidence interval comes from 2,000 bootstrap samples over papers."
    )
    notes = (
        "\\* Built on a Claude model. Claude Sonnet 4.5 drafted the gold annotations before annotators checked them, "
        "so it is not listed (its score is not comparable), and systems built on Claude models may have an advantage.  \n"
        + ("**Paper** is the composite in the paper, judged by GLM-5 on DeepInfra in May 2026; DeepInfra has since "
           f"retired that model, and today's judge scores {abs(shift):.3f} lower on average.  \n" if abs(shift) > 0 else "")
        + "Systems added after the paper have no **Paper** score.  \n"
        + "Cost per paper at list prices of April and May 2026 for the paper's systems (the paper's Table 8), and of "
          "the day the outputs were made for later ones; self-hosted models ran on our own GPUs and have no API cost."
    )
    return intro, notes


def filtered(df: pd.DataFrame, search: str = "", design: str = ALL_DESIGNS, open_only: bool = False) -> pd.DataFrame:
    keep = pd.Series(True, index=df.index)
    if search and search.strip():
        text = (df.system + " " + df.model + " " + df.design).str.lower()
        keep &= text.str.contains(search.strip().lower(), regex=False)
    if design and design != ALL_DESIGNS:
        keep &= df.design == design
    if open_only:
        keep &= df.open_weights == "yes"
    return df[keep]


def ordered(df: pd.DataFrame, sort_by: str = "Sort by composite") -> pd.DataFrame:
    column = SORTS.get(sort_by, "composite")
    ranked = df[df.role == "ranked"].sort_values(column, ascending=column == "cost", kind="stable")
    return pd.concat([df[df.role == "reference"], ranked])


def _row(r) -> str:
    color = COLORS["Reference"] if r.role == "reference" else COLORS.get(r.design, "#64748b")
    name = html.escape(r.system) + (" *" if r.claude == "yes" else "")
    if r.role == "reference":
        name += " (reference)"
    badge = '<span class="lb-open">open weights</span>' if r.open_weights == "yes" else ""
    cost = "self-hosted" if r.cost_per_paper_usd == "self-hosted" else f"${float(r.cost_per_paper_usd):.2f}"
    return (
        f'<tr class="{"lb-ref" if r.role == "reference" else ""}" style="--c: {color}">'
        f'<td class="lb-rank">{r.rank or "ref"}</td>'
        f'<td><div class="lb-name">{name}</div></td>'
        f'<td><span class="lb-pill">{html.escape(r.design)}</span>{badge}</td>'
        f'<td class="num"><b>{r.composite:.3f}</b><span class="lb-ci">{r.ci_low:.3f} to {r.ci_high:.3f}</span>'
        f'<div class="lb-bar"><span style="width: {100 * r.composite:.1f}%"></span></div></td>'
        f'<td class="num">{r.core:.3f}</td><td class="num">{r.rai:.3f}</td>'
        f'<td class="num lb-paper">{"" if pd.isna(r.paper_composite) else f"{r.paper_composite:.3f}"}</td>'
        f'<td class="num">{cost}</td></tr>'
    )


def table_html(df: pd.DataFrame) -> str:
    if df.empty:
        return '<div class="lb-wrap"><p class="lb-empty">No system matches.</p></div>'
    head = ("<tr><th>Rank</th><th>System</th><th>Design</th><th class='num'>Composite</th><th class='num'>Core</th>"
            "<th class='num'>RAI</th><th class='num'>Paper</th><th class='num'>Cost per paper</th></tr>")
    body = "".join(_row(r) for r in df.itertuples())
    return f'<div class="lb-wrap"><table class="lb-table"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def chart(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "System": df.system + df.cost_per_paper_usd.map(lambda c: " (self-hosted)" if c == "self-hosted" else ""),
        "Design": df.design.where(df.role == "ranked", "Reference"),
        "Composite": df.composite.round(3),
        COST: df.cost.round(3),
    })


def build() -> None:
    """Adds the leaderboard's components; call inside a gr.Tab."""
    data = load()
    intro, notes = texts(data)
    designs = [ALL_DESIGNS] + sorted(data[data.role == "ranked"].design.unique(), key=lambda d: d != "Single-pass")
    gr.Markdown(intro)
    with gr.Row(equal_height=True):
        search = gr.Textbox(placeholder="Search", show_label=False, scale=3)
        design = gr.Dropdown(designs, value=ALL_DESIGNS, show_label=False, scale=2)
        sort_by = gr.Dropdown(list(SORTS), value="Sort by composite", show_label=False, scale=2)
        open_only = gr.Checkbox(label="Open weights only", value=False, scale=1, min_width=190)
    board = gr.HTML(table_html(ordered(data)), padding=False, elem_id="leaderboard")
    gr.Markdown(notes, elem_classes="lb-notes")
    plot = gr.ScatterPlot(chart(data), x=COST, y="Composite", color="Design", color_map=COLORS,
                          tooltip=["System", "Composite", COST], title="Score and cost per paper",
                          x_title="Cost per paper (US$; self-hosted at 0)", y_title="Composite score",
                          height=380, elem_id="leaderboard-plot")
    with gr.Accordion("Add your system", open=False):
        gr.Markdown(SUBMIT)

    def update(text, chosen, order, only_open):
        rows = filtered(data, text, chosen, only_open)
        return table_html(ordered(rows, order)), chart(rows)

    for control in (search, design, sort_by, open_only):
        control.change(update, inputs=[search, design, sort_by, open_only], outputs=[board, plot])
