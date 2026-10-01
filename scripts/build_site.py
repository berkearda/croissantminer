"""Build the leaderboard website from leaderboard/leaderboard.csv.

    python scripts/build_site.py               # writes the site to _site/
    python scripts/build_site.py --out DIR

Every row of leaderboard/leaderboard.csv becomes a row of the table. Its `results` column names a folder under
leaderboard/ whose per_field.csv holds the system's score on each of the 30 fields (with a `system` column when the
file holds several systems, as leaderboard/paper/per_field.csv does). Styles, script, news and the preview image come
from site/. Only the Python standard library is used. GitHub Actions runs this on every change to the leaderboard
(.github/workflows/site.yml) and publishes the result at SITE_URL.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "leaderboard"
SITE = ROOT / "site"
SITE_URL = "https://berkearda.github.io/croissantminer/"
REPO = "https://github.com/berkearda/croissantminer"
DATASET = "https://huggingface.co/datasets/bearda/croissantminer"
DEMO = "https://huggingface.co/spaces/bearda/croissantminer"
PAPER = ""                      # the arXiv link, once it exists
SUBMIT = f"{REPO}/blob/main/leaderboard/README.md#add-your-system"

AUTHORS = [("Berke Arda", "1*"), ("Ahmetcan Yavuz", "1*"), ("Paul Gerry", "1,3"), ("Sebastian Lobentanzer", "4"),
           ("Nobin Sarwar", "5"), ("Joan Giner-Miguelez", "6"), ("Kongtao Chen", "7"), ("Luyao Zhang", "8"),
           ("Mrinmaya Sachan", "1,2"), ("Mubashara Akhtar", "1,2")]
AFFILIATIONS = ["ETH Zurich", "ETH AI Center", "CSAIL, MIT", "Helmholtz Zentrum München",
                "University of Maryland, Baltimore County", "Barcelona Supercomputing Center", "Google",
                "Duke Kunshan University"]
BIBTEX = """@inproceedings{arda2026croissantminer,
  title     = {CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets},
  author    = {Arda, Berke and Yavuz, Ahmetcan and Gerry, Paul and Lobentanzer, Sebastian and
               Sarwar, Nobin and Giner-Miguelez, Joan and Chen, Kongtao and Zhang, Luyao and
               Sachan, Mrinmaya and Akhtar, Mubashara},
  booktitle = {Advances in Neural Information Processing Systems (Evaluations and Datasets Track)},
  year      = {2026}
}"""
# The 30 fields in the order of the schema, with the names shown on the page.
CORE = {"sc:name": "Name", "sc:description": "Description", "sc:url": "URL", "sc:license": "License",
        "sc:creator": "Creator", "sc:publisher": "Publisher", "sc:datePublished": "Date published",
        "sc:inLanguage": "Language", "cr:citeAs": "Citation", "cr:isLiveDataset": "Live dataset"}
RAI = {"rai:dataCollection": "Data collection", "rai:dataCollectionType": "Collection type",
       "rai:dataCollectionMissingData": "Missing data", "rai:dataCollectionRawData": "Raw data",
       "rai:dataCollectionTimeframe": "Collection timeframe", "rai:dataImputationProtocol": "Imputation",
       "rai:dataManipulationProtocol": "Manipulation", "rai:dataPreprocessingProtocol": "Preprocessing",
       "rai:dataAnnotationProtocol": "Annotation protocol", "rai:dataAnnotationPlatform": "Annotation platform",
       "rai:dataAnnotationAnalysis": "Annotation analysis", "rai:annotationsPerItem": "Annotations per item",
       "rai:annotatorDemographics": "Annotator demographics", "rai:machineAnnotationTools": "Machine annotation tools",
       "rai:dataReleaseMaintenancePlan": "Maintenance plan",
       "rai:personalSensitiveInformation": "Personal and sensitive information",
       "rai:dataSocialImpact": "Social impact", "rai:dataBiases": "Biases", "rai:dataLimitations": "Limitations",
       "rai:dataUseCases": "Use cases"}
LABELS = {**CORE, **RAI}
# What each field asks for, shown when a visitor points at a field name.
DESCRIPTIONS = {
    "sc:name": "The dataset's name.", "sc:description": "A short summary of the dataset.",
    "sc:url": "Where the dataset can be found.", "sc:license": "The license the data is released under.",
    "sc:creator": "Who made the dataset.", "sc:publisher": "The organization that publishes it.",
    "sc:datePublished": "When it was published.", "sc:inLanguage": "The language or languages of the data.",
    "cr:citeAs": "How to cite the dataset.", "cr:isLiveDataset": "Whether the data keeps changing or is fixed.",
    "rai:dataCollection": "How the data was collected.",
    "rai:dataCollectionType": "The kind of collection, such as crowdsourcing or web scraping.",
    "rai:dataCollectionMissingData": "How missing data was handled.",
    "rai:dataCollectionRawData": "The raw sources the data comes from.",
    "rai:dataCollectionTimeframe": "When the data was collected.",
    "rai:dataImputationProtocol": "How missing values were filled in.",
    "rai:dataManipulationProtocol": "How the data was changed or transformed.",
    "rai:dataPreprocessingProtocol": "The preprocessing steps applied to the data.",
    "rai:dataAnnotationProtocol": "How the data was annotated.",
    "rai:dataAnnotationPlatform": "The platform used for annotation, such as Amazon Mechanical Turk.",
    "rai:dataAnnotationAnalysis": "How the quality of the annotations was checked.",
    "rai:annotationsPerItem": "How many annotations each item received.",
    "rai:annotatorDemographics": "Who the annotators were.",
    "rai:machineAnnotationTools": "Models or tools used to annotate.",
    "rai:dataReleaseMaintenancePlan": "Plans for updating and maintaining the data.",
    "rai:personalSensitiveInformation": "Personal or sensitive information in the data, and how it is handled.",
    "rai:dataSocialImpact": "Possible effects of the data on society.",
    "rai:dataBiases": "Known biases in the data.", "rai:dataLimitations": "Known limitations of the data.",
    "rai:dataUseCases": "What the data is meant to be used for."}
AGENTS = {"ReAct", "Parallel Specialists", "Triage + Critique", "Locator-Extractor"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
SUN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
       '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2'
       'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')
ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' \
       'stroke-linejoin="round" aria-hidden="true">{}</svg>'
ICONS = {"paper": ICON.format('<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>'
                              '<path d="M8 13h8M8 17h5"/>'),
         "data": ICON.format('<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
                             '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
         "code": ICON.format('<path d="M8 6l-6 6 6 6M16 6l6 6-6 6"/>'),
         "demo": ICON.format('<path d="M7 4l13 8-13 8z"/>'),
         "submit": ICON.format('<path d="M12 19V5M5 12l7-7 7 7"/>'),
         "download": ICON.format('<path d="M12 4v12M6 10l6 6 6-6M4 20h16"/>')}
# In the dark-theme logo the pickaxe's navy steel becomes light steel, so it stays visible on a dark background.
DARK_STEEL = {"steel": ["#a9bccb", "#97abbb", "#8599aa"], "steel-edge": ["#b8c8d4", "#7b90a2"],
              "steel-collar": ["#93a8b9", "#8397a9"]}
DARK_LOGO = {'<g id="word-croissant" fill="#062538">': '<g id="word-croissant" fill="#eef3f6">',
             '<g id="word-miner" fill="#008f97">': '<g id="word-miner" fill="#3cc3cb">',
             '<g id="tagline" fill="#193446">': '<g id="tagline" fill="#b9c6cf">'}


def e(text) -> str:
    return html.escape(str(text), quote=True)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def month(day: str) -> str:
    return f"{MONTHS[int(day[5:7]) - 1]} {day[:4]}" if day else ""


def full_date(day: str) -> str:
    return f"{int(day[8:10])} {month(day)}" if day else ""


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load() -> tuple[list[dict], dict, dict]:
    rows = read_csv(BOARD / "leaderboard.csv")
    for r in rows:
        for k in ("core", "rai", "composite", "ci_low", "ci_high"):
            r[k] = float(r[k])
        r["paper_composite"] = float(r["paper_composite"]) if r.get("paper_composite") else None
        r["cost"] = None if r["cost_per_paper_usd"] in ("", "self-hosted") else float(r["cost_per_paper_usd"])
    ranked = sorted((r for r in rows if r["role"] == "ranked"), key=lambda r: -r["composite"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    reference = [r for r in rows if r["role"] == "reference"]
    fields: dict[str, dict[str, float]] = {}
    cache: dict[Path, list[dict]] = {}
    for r in rows:
        if not r.get("results"):
            continue
        path = BOARD / r["results"] / "per_field.csv"
        lines = cache.setdefault(path, read_csv(path)) if path.exists() else []
        mine = [x for x in lines if x.get("system", r["system"]) == r["system"]]
        scores = {x["field_id"]: float(x["score"]) for x in mine if x["field_id"] in LABELS}
        if scores:
            if set(scores) != set(LABELS):
                sys.exit(f"{path}: {r['system']} has scores for {len(scores)} of the 30 fields")
            fields[r["system"]] = scores
    with_fields = [r for r in ranked if r["system"] in fields]
    average = {f: sum(fields[r["system"]][f] for r in with_fields) / len(with_fields) for f in LABELS}
    best = {f: max(with_fields, key=lambda r: fields[r["system"]][f]) for f in LABELS}
    return reference + ranked, fields, {"average": average, "best": best}


def shown_name(r: dict) -> str:
    """The name in the table: the paper's systems are "<design> (<model>)", and the design has its own column."""
    paper_style = r["system"] in (r["model"], f'{r["design"]} ({r["model"].replace("Claude ", "")})',
                                  f'{r["design"]} ({r["model"]})')
    return r["model"] if paper_style and r["model"] else r["system"]


def table_row(r: dict, key: str) -> str:
    reference = r["role"] == "reference"
    if reference:
        rank = '<span class="tag">Ref.</span>'
    elif r["rank"] <= 3:
        rank = f'<span class="medal {("gold", "silver", "bronze")[r["rank"] - 1]}">{r["rank"]}</span>'
    else:
        rank = str(r["rank"])
    star = '<span class="star" title="Built on a Claude model">*</span>' if r["claude"] == "yes" else ""
    tags = ('<span class="tag">open</span>' if r["open_weights"] == "yes" else "") + \
        ('<span class="tag">reference</span>' if reference else "")
    team = r.get("team") or ""
    team_html = ""
    if team and team != "CroissantMiner paper" and not reference:     # the paper's systems: said once below the table
        link = r.get("link") or ""
        inner = f'<a href="{e(link)}">{e(team)}</a>' if link else e(team)
        team_html = f'<span class="team">{inner}</span>'
    groups = [g for g, ok in (("single", r["design"] == "Single-pass"), ("agents", r["design"] in AGENTS),
                              ("open", r["open_weights"] == "yes")) if ok]
    cost = "self-hosted" if r["cost"] is None else f'${r["cost"]:.2f}'
    paper = f'{r["paper_composite"]:.3f}' if r["paper_composite"] is not None else "&ndash;"
    paper_value = "" if r["paper_composite"] is None else f'{r["paper_composite"]:.6f}'
    cost_value = "" if r["cost"] is None else r["cost"]          # empty values sort last
    attrs = (f'data-key="{key}" data-slug="{slug(r["system"])}" data-system="{e(r["system"])}" '
             f'data-group="{" ".join(groups)}" data-rank="{r.get("rank", 0)}" '
             f'data-core="{r["core"]:.6f}" data-rai="{r["rai"]:.6f}" data-composite="{r["composite"]:.6f}" '
             f'data-paper="{paper_value}" data-cost="{cost_value}" data-date="{e(month(r.get("date") or ""))}" '
             f'data-ci="{r["ci_low"]:.3f} to {r["ci_high"]:.3f}"')
    return (f'<tr class="sys-row{" ref" if reference else ""}" {attrs}>'
            f'<td class="rank">{rank}</td>'
            f'<td class="sys"><button class="name" type="button" aria-expanded="false">'
            f'<span class="chev" aria-hidden="true"></span>{e(shown_name(r))}{star}</button>{tags}{team_html}</td>'
            f'<td class="design">{e(r["design"])}</td>'
            f'<td class="num">{r["core"]:.3f}</td><td class="num">{r["rai"]:.3f}</td>'
            f'<td class="num comp" data-tip="95% interval {r["ci_low"]:.3f} to {r["ci_high"]:.3f}">'
            f'<span class="score">{r["composite"]:.3f}</span></td>'
            f'<td class="num muted">{paper}</td><td class="num">{cost}</td></tr>')


def hardest_fields(summary: dict, fields: dict) -> str:
    rows = []
    for field in sorted(LABELS, key=lambda f: summary["average"][f]):
        value = summary["average"][field]
        kind = "core" if field in CORE else "rai"
        best = summary["best"][field]
        tip = (f'{LABELS[field]}: {DESCRIPTIONS[field]} Average {value:.3f}; best {best["system"]} '
               f'with {fields[best["system"]][field]:.3f}.')
        rows.append(f'<div class="frow" tabindex="0" data-tip="{e(tip)}"><span class="fname">{e(LABELS[field])}</span>'
                    f'<span class="track"><span class="bar {kind}" style="width:{100 * value:.1f}%"></span></span>'
                    f'<span class="fval">{value:.2f}</span></div>')
    return ('<div class="chart"><div class="legend"><span><i style="background:var(--core)"></i>Core field (scored by rules)'
            '</span><span><i style="background:var(--rai)"></i>Responsible AI field (scored by the judge)</span></div>'
            + "".join(rows) + "</div>")


def page(rows: list[dict], fields: dict, summary: dict) -> str:
    keys = {r["system"]: f"s{i}" for i, r in enumerate(rows)}
    ranked = [r for r in rows if r["role"] == "ranked"]
    judged = max((r.get("judged_on") or "" for r in rows), default="")
    judge = next((r.get("judge") for r in rows if r.get("judge")), "the judge model")
    updated = max([judged] + [r.get("date") or "" for r in rows])
    data = {"labels": LABELS, "descriptions": DESCRIPTIONS, "core": list(CORE), "rai": list(RAI),
            "average": {f: round(v, 4) for f, v in summary["average"].items()},
            "systems": {keys[s]: {f: round(v, 4) for f, v in scores.items()} for s, scores in fields.items()}}
    news = read_csv(SITE / "news.csv")
    news_html = "".join(f'<li><span class="sub">{e(full_date(n["date"]))}</span>{n["text"]}</li>'
                        for n in news)
    authors = ", ".join(f"<span>{e(n)}<sup>{s}</sup></span>" for n, s in AUTHORS)
    affils = " ".join(f"<span><sup>{i}</sup>{e(a)}</span>" for i, a in enumerate(AFFILIATIONS, 1))
    paper_button = (f'<a href="{e(PAPER)}">{ICONS["paper"]}Paper</a>' if PAPER else
                    f'<a class="off" aria-disabled="true">{ICONS["paper"]}Paper (arXiv soon)</a>')
    description = ("Leaderboard of systems that turn the paper introducing a dataset into Croissant metadata, "
                   "including the 20 Responsible AI fields. 102 dataset papers, 30 fields, 3,060 gold answers.")
    sort_head = ('<tr><th class="rank" data-sort="rank">Rank</th><th class="sys">Model</th><th class="design">Design</th>'
                 '<th class="num" data-sort="core">Core</th><th class="num" data-sort="rai">RAI</th>'
                 '<th class="num" data-sort="composite">Composite</th><th class="num" data-sort="paper">Paper</th>'
                 '<th class="num" data-sort="cost">Cost / paper</th></tr>')
    body = "".join(table_row(r, keys[r["system"]]) for r in rows)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CroissantMiner Leaderboard</title>
<meta name="description" content="{e(description)}">
<meta property="og:type" content="website">
<meta property="og:title" content="CroissantMiner Leaderboard">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{SITE_URL}preview.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<script>try {{ var t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; }} catch (e) {{}}</script>
</head>
<body>
<header>
  <button class="theme" id="theme" type="button" aria-label="Switch theme">{SUN}</button>
  <div class="hero wrap">
    <img class="logo logo-light" src="logo.svg" alt="CroissantMiner">
    <img class="logo logo-dark" src="logo-dark.svg" alt="CroissantMiner">
    <h1 class="title">CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets</h1>
    <p class="authors">{authors}</p>
    <div class="venue"><span>NeurIPS 2026 &middot; Evaluations and Datasets Track</span>
      <details class="affils"><summary>Affiliations</summary><div>{affils} <span>* Lead authors</span></div></details></div>
    <dl class="facts"><div><dt>102</dt><dd>dataset papers</dd></div><div><dt>30</dt><dd>metadata fields</dd></div>
      <div><dt>3,060</dt><dd>gold answers</dd></div><div><dt>22</dt><dd>annotators</dd></div></dl>
      <div class="buttons">{paper_button}<a href="{DATASET}">{ICONS["data"]}Dataset</a><a href="{REPO}">{ICONS["code"]}Code</a>
        <a href="{DEMO}">{ICONS["demo"]}Demo</a><a class="primary" href="{SUBMIT}">{ICONS["submit"]}Submit your system</a></div>
  </div>
</header>
<main class="wrap">
  <aside>
    <div class="part"><h2>About the benchmark</h2>
      <p>A benchmark for turning the paper that introduces a dataset into
      <a href="https://github.com/mlcommons/croissant">Croissant</a> metadata, including the 20 Responsible AI fields:
      how the data was collected and annotated, known biases, limitations and intended uses. Systems read the paper
      and fill the 30 fields; their answers are compared with answers that annotators checked by hand.</p>
    </div>
    <div class="part"><h2>Get the data</h2>
      <div class="code-head"><span>Data on Hugging Face</span>
        <button class="copy" type="button" data-copy="code-data">Copy</button></div>
      <pre id="code-data">import datasets
gold = datasets.load_dataset(
    "bearda/croissantminer",
    "gold")</pre>
      <div class="code-head"><span>Extraction tool on PyPI</span>
        <button class="copy" type="button" data-copy="code-pip">Copy</button></div>
      <pre id="code-pip">pip install croissantminer</pre>
    </div>
    <div class="part"><h2>Submit your system</h2>
      <ol><li>Run it on the 88 test papers and save one JSON file per paper.</li>
        <li>Score it with <code>make evaluate</code>, the paper's scorer and judge model.</li>
        <li>Open a pull request with the result. <a href="{SUBMIT}">Details</a></li></ol>
    </div>
    <div class="part"><h2>News</h2><ul class="news">{news_html}</ul></div>
  </aside>
  <section aria-label="Leaderboard">
    <div class="lb-title"><h2>Leaderboard</h2>
      <p class="muted">Composite score of each system on the 88 test papers, all 30 fields weighted equally.</p></div>
    <div class="lb-top">
      <div class="tabs" role="tablist">
        <button class="on" type="button" role="tab" aria-selected="true" data-tab="all">All systems</button>
        <button type="button" role="tab" aria-selected="false" data-tab="single">Single-pass</button>
        <button type="button" role="tab" aria-selected="false" data-tab="agents">Agent designs</button>
        <button type="button" role="tab" aria-selected="false" data-tab="open">Open weights</button></div>
      <span class="downloads">{ICONS["download"]}CSV: <a href="leaderboard.csv" download>scores</a> &middot;
      <a href="field_scores.csv" download>field scores</a></span></div>
    <div class="lb">
      <div class="scroll"><table id="board"><thead>{sort_head}</thead><tbody>{body}</tbody></table></div>
      <div class="lb-foot"><p>Click a row to see the system's score on each of the 30 fields; the page address
      then links straight to it. The systems listed so far are the paper's.</p>
      <p>Composite weights all 30 fields equally; point at it for its 95% interval. Core covers the 10 core fields,
      scored by rules; RAI the 20 Responsible AI fields, scored by {e(judge)}, which judged every row in
      {e(month(judged))}. Paper is the composite in the paper, from the judge run of May 2026. The panel of each system
      also shows its interval and when its outputs were made. Cost per paper at list prices of April and May 2026.</p>
      <p>* Built on a Claude model, which may have an advantage because Claude Sonnet 4.5 drafted the gold answers;
      that model is shown for reference and not ranked.</p></div>
    </div>
  </section>
</main>
<section class="fields wrap" aria-label="Which fields are hard">
  <h2>Which fields are hard?</h2>
  <p class="intro">Average score of the {len(ranked)} ranked systems on each field, hardest first. Point at a field to
  see what it asks for and the best system on it.</p>
  {hardest_fields(summary, fields)}
</section>
<div class="cite wrap"><div class="code-head"><h2>Citation</h2>
  <button class="copy" type="button" data-copy="code-bibtex">Copy</button></div>
  <pre id="code-bibtex">{e(BIBTEX)}</pre>
</div>
<footer>Last updated {e(full_date(updated))} &middot; <a href="{REPO}">github.com/berkearda/croissantminer</a></footer>
<script id="field-data" type="application/json">{json.dumps(data, separators=(",", ":"))}</script>
<script src="app.js"></script>
</body>
</html>
"""


def build(out: Path) -> Path:
    rows, fields, summary = load()
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(rows, fields, summary), encoding="utf-8")
    for name in ("style.css", "app.js", "preview.png"):
        shutil.copy(SITE / name, out / name)
    logo = (ROOT / "assets" / "croissantminer-logo.svg").read_text(encoding="utf-8")
    (out / "logo.svg").write_text(logo, encoding="utf-8")
    for light, dark in DARK_LOGO.items():          # the wordmark in light colors for the dark theme
        if logo.count(light) != 1:
            sys.exit(f"assets/croissantminer-logo.svg changed: {light} not found once")
        logo = logo.replace(light, dark)
    for gradient, colors in DARK_STEEL.items():
        found = re.search(r'<(linearGradient|radialGradient)[^>]*id="%s"[^>]*>.*?</\1>' % gradient, logo, re.S)
        stops = re.findall(r'stop-color="#[0-9a-fA-F]+"', found.group(0)) if found else []
        if len(stops) != len(colors):
            sys.exit(f"assets/croissantminer-logo.svg changed: gradient {gradient} has {len(stops)} stops")
        block = found.group(0)
        for old, new in zip(stops, colors):
            block = block.replace(old, f'stop-color="{new}"', 1)
        logo = logo.replace(found.group(0), block)
    (out / "logo-dark.svg").write_text(logo, encoding="utf-8")
    shutil.copy(ROOT / "assets" / "croissantminer-icon.svg", out / "icon.svg")
    shutil.copy(BOARD / "leaderboard.csv", out / "leaderboard.csv")
    with (out / "field_scores.csv").open("w", newline="", encoding="utf-8") as f:     # every system, all 30 fields
        writer = csv.writer(f)
        writer.writerow(["system", "field_id", "field", "score"])
        for r in rows:
            for field in LABELS:
                if r["system"] in fields:
                    writer.writerow([r["system"], field, LABELS[field], f'{fields[r["system"]][field]:.4f}'])
    (out / ".nojekyll").write_text("")
    return out / "index.html"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "_site", help="output folder (default: _site)")
    args = ap.parse_args(argv)
    index = build(args.out)
    print(f"wrote {index} ({date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
