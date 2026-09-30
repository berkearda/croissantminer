"""
CroissantMiner — Automated RAI Metadata Extraction for ML Dataset Papers
HuggingFace Space Demo (Gradio)
"""

import html
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import gradio as gr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipelines  # noqa: E402
from pipelines import METHODS, METHODS_BY_LABEL  # noqa: E402

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

GENERAL_FIELDS = [
    ("name", "Dataset name"),
    ("description", "Brief description of the dataset"),
    ("url", "URL where dataset can be accessed"),
    ("license", "License information"),
    ("creator", "Authors or creators"),
    ("publisher", "Publishing organization"),
    ("datePublished", "Publication date"),
    ("inLanguage", "Language(s) of the dataset"),
    ("citeAs", "Recommended citation format"),
    ("isLiveDataset", "Whether dataset is live/updating or static"),
]

RAI_FIELDS = [
    ("rai:dataCollection", "How data was collected (methodology)"),
    ("rai:dataCollectionType", "Type: Crowdsourcing, Web Scraping, Manual Curation, etc."),
    ("rai:dataCollectionMissingData", "How missing data was handled"),
    ("rai:dataCollectionRawData", "Description of raw/source data"),
    ("rai:dataCollectionTimeframe", "When data was collected"),
    ("rai:dataImputationProtocol", "Methods for imputing missing values"),
    ("rai:dataManipulationProtocol", "Data manipulation procedures"),
    ("rai:dataPreprocessingProtocol", "Preprocessing steps applied"),
    ("rai:dataAnnotationProtocol", "Annotation methodology"),
    ("rai:dataAnnotationPlatform", "Platform used (e.g., Amazon MTurk)"),
    ("rai:dataAnnotationAnalysis", "Quality analysis of annotations"),
    ("rai:annotationsPerItem", "Number of annotations per data item"),
    ("rai:annotatorDemographics", "Demographics of annotators"),
    ("rai:machineAnnotationTools", "ML tools used in annotation"),
    ("rai:dataReleaseMaintenancePlan", "Maintenance and update plans"),
    ("rai:personalSensitiveInformation", "PII/sensitive data handling"),
    ("rai:dataSocialImpact", "Social impact considerations"),
    ("rai:dataBiases", "Known biases in the dataset"),
    ("rai:dataLimitations", "Dataset limitations"),
    ("rai:dataUseCases", "Intended use cases"),
]

ALL_FIELD_KEYS = [f[0] for f in GENERAL_FIELDS + RAI_FIELDS]

# ---------------------------------------------------------------------------
# Example input
# ---------------------------------------------------------------------------

EXAMPLE_PAPER = """Title: GSM8K: Training Verifiers to Solve Math Word Problems

Authors: Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, Christopher Hesse, John Schulman (OpenAI)

Abstract: State-of-the-art language models can match human performance on many tasks, but they still struggle to reliably perform multi-step mathematical reasoning. We present GSM8K, a dataset of 8.5K high quality linguistically diverse grade school math word problems created by human problem writers. We find that even the largest transformer models fail to achieve high test performance, despite the conceptual simplicity of the problems.

Dataset Description: GSM8K (Grade School Math 8K) consists of 8,500 high quality grade school math word problems. The dataset is split into 7,473 training problems and 1,319 test problems. Each problem requires between 2 and 8 steps to solve, and solutions primarily involve performing a sequence of elementary calculations using basic arithmetic operations (+ − × ÷). A bright middle school student should be able to solve every problem.

Data Collection: Problems were created by a team of human problem writers hired through Upwork. Writers were asked to compose original math word problems at the grade school level. Each problem was required to have a natural language solution with a numeric final answer. Writers were paid $15-20 per hour.

Annotation: Solutions were written by the same problem writers. Each solution provides step-by-step reasoning leading to the final numeric answer. Solutions use a calculator annotation format where calculations are enclosed in <<>> brackets. Quality control involved review by a separate team member.

License: MIT License
URL: https://github.com/openai/grade-school-math
Published: October 2021
Language: English"""

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _is_valid(val):
    """Check if a metadata value is informative."""
    if val is None:
        return False
    if not isinstance(val, str):
        return bool(val)
    v = val.strip().lower()
    return bool(v) and v not in {
        "not mentioned", "not available", "n/a", "unknown",
        "not specified", "not provided", "null", "",
    }


def _value_text(val) -> str:
    if isinstance(val, dict):
        return val.get("name") or json.dumps(val, ensure_ascii=False)
    if isinstance(val, list):
        return ", ".join(_value_text(v) for v in val)
    return str(val)


def _compute_coverage(metadata: dict) -> tuple[int, int, int]:
    general = sum(1 for k, _ in GENERAL_FIELDS if _is_valid(metadata.get(k)))
    rai = sum(1 for k, _ in RAI_FIELDS if _is_valid(metadata.get(k)))
    return general + rai, general, rai


def _summary_md(metadata: dict | None = None, method=None, result=None) -> str:
    metadata = metadata or {}
    total, general, rai = _compute_coverage(metadata)
    n = len(ALL_FIELD_KEYS)
    lines = [f"### Extraction Coverage: {total}/{n} fields ({int(100 * total / n)}%)",
             f"**General:** {general}/{len(GENERAL_FIELDS)} &nbsp;|&nbsp; "
             f"**RAI:** {rai}/{len(RAI_FIELDS)}"]
    if method is not None and result is not None:
        run = f"{method.label} · {result.elapsed_s:.0f} s"
        if result.cost_usd:
            run += f" · ≈ ${result.cost_usd:.2f}"
        lines.append(f"<span style='color:#666'>{html.escape(run)}</span>")
    return "\n\n".join(lines)


def _build_field_cards(metadata: dict, fields: list, evidence: dict | None = None,
                       null_reasons: dict | None = None) -> str:
    """Render fields as cards: name + description + value, plus the supporting
    quote (Triage + Critique, Locator-Extractor) or, for empty fields, the
    agent's reason for leaving them empty (ReAct)."""
    evidence = evidence or {}
    null_reasons = null_reasons or {}
    blocks = []
    for key, desc in fields:
        val = metadata.get(key)
        filled = _is_valid(val)
        accent = "#5a4fcf" if filled else "#cccccc"
        body = (html.escape(_value_text(val)) if filled
                else '<span style="color:#9aa0a6">—</span>')
        extra = ""
        if filled and evidence.get(key):
            quote = html.escape(str(evidence[key]).strip())
            extra = (f'<div style="margin-top:6px; font-size:0.85em; color:#6b6b6b;">'
                     f'<span style="font-weight:600;">Evidence</span> “{quote}”</div>')
        elif not filled and null_reasons.get(key):
            extra = (f'<div style="margin-top:4px; font-size:0.85em; color:#8a8a8a;">'
                     f'{html.escape(str(null_reasons[key]))}</div>')
        blocks.append(
            f'<div style="border-left:3px solid {accent}; padding:8px 14px; '
            f'margin:6px 0; background:#fafafa; border-radius:4px;">'
            f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
            f'<code style="font-weight:600; color:#1a1a1a;">{key}</code>'
            f'<span style="font-size:0.8em; color:#666;">{desc}</span>'
            f'</div>'
            f'<div style="margin-top:6px; line-height:1.5; color:#333; white-space:pre-wrap;">'
            f'{body}</div>{extra}</div>'
        )
    return f'<div class="field-card-list">{"".join(blocks)}</div>'


_ORG_WORDS = re.compile(r"\b(inc|corp|llc|ltd|university|institute|lab|labs|laboratory|"
                        r"research|foundation|google|openai|meta|microsoft|deepmind|"
                        r"anthropic|nvidia|allen|team|group|center|centre)\b", re.I)


def _creator_jsonld(creator):
    """schema.org creator: a list of Person for comma-separated names, an
    Organization for a single organisation name."""
    if isinstance(creator, dict):
        return creator
    text = _value_text(creator).strip()
    # "OpenAI (Karl Cobbe, ...)" or "Karl Cobbe, ... (OpenAI)": keep the people
    m = re.match(r"^([^()]+)\((.+)\)$", text)
    if m:
        outer, inner = m.group(1).strip(), m.group(2).strip()
        text = inner if "," in inner and "," not in outer else outer
    parts = [p.strip() for p in re.split(r",|;|\band\b", text) if p.strip()]
    if len(parts) > 1 and not any(_ORG_WORDS.search(p) for p in parts):
        return [{"@type": "Person", "name": p} for p in parts]
    kind = "Organization" if _ORG_WORDS.search(text) else "Person"
    return {"@type": kind, "name": text}


def _publisher_jsonld(publisher):
    """schema.org publisher as Organization objects: the models return names."""
    if isinstance(publisher, list):
        return [_publisher_jsonld(p) for p in publisher]
    if isinstance(publisher, dict):
        return {"@type": "Organization", **publisher}
    return {"@type": "Organization", "name": str(publisher).strip()}


_DATE_FORMATS = ("%B %Y", "%b %Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y")


def _iso_date(value) -> str | None:
    """schema.org Date (YYYY, YYYY-MM or YYYY-MM-DD). The models also return a
    bare number or text such as "November 2021"; without a year, None."""
    text = str(int(value)) if isinstance(value, (int, float)) else str(value).strip()
    if re.fullmatch(r"\d{4}(-\d{2}){0,2}", text):
        return text
    for fmt in _DATE_FORMATS:
        try:
            date = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return date.strftime("%Y-%m-%d" if "%d" in fmt else "%Y-%m")
    year = re.search(r"\b(19|20)\d{2}\b", text)
    return year.group(0) if year else None


def _build_croissant(metadata: dict, hf_dataset_id: str = "") -> dict:
    """Convert extracted metadata into Croissant JSON-LD. Only extracted values
    are emitted: nothing is filled with placeholders."""
    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "rai": "http://mlcommons.org/croissant/RAI/",
        },
        "@type": "sc:Dataset",
    }
    hf = (hf_dataset_id or "").strip().strip("/")
    if "/" in hf:
        croissant["@id"] = f"https://huggingface.co/datasets/{hf.split('datasets/')[-1]}"
    for key in ("name", "description", "license", "url", "publisher", "datePublished",
                "inLanguage"):
        if _is_valid(metadata.get(key)):
            croissant[key] = metadata[key]
    # mlcroissant rejects a plain-text publisher and dates such as 2021 (a number)
    if "publisher" in croissant:
        croissant["publisher"] = _publisher_jsonld(croissant["publisher"])
    if "datePublished" in croissant:
        date = _iso_date(croissant["datePublished"])
        if date:
            croissant["datePublished"] = date
        else:
            del croissant["datePublished"]
    if _is_valid(metadata.get("citeAs")):
        croissant["cr:citeAs"] = metadata["citeAs"]
    if _is_valid(metadata.get("creator")):
        croissant["creator"] = _creator_jsonld(metadata["creator"])
    is_live = metadata.get("isLiveDataset")
    if isinstance(is_live, bool):
        croissant["cr:isLiveDataset"] = is_live
    elif isinstance(is_live, str) and is_live.strip().lower() in ("yes", "true", "no", "false"):
        croissant["cr:isLiveDataset"] = is_live.strip().lower() in ("yes", "true")
    for key, _ in RAI_FIELDS:
        if _is_valid(metadata.get(key)):
            croissant[key] = metadata[key]
    return croissant


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------


def extract_metadata(pdf_file, paper_text: str, card_text: str, method_label: str,
                     api_key: str, hf_dataset_id: str, progress=gr.Progress()):
    method = METHODS_BY_LABEL[method_label]

    if pdf_file is not None:
        progress(0.05, desc="Reading PDF...")
        try:
            file_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
            paper_text = pipelines.paper_text_from_pdf(file_path)
        except Exception as e:
            raise gr.Error(f"Failed to read PDF: {e}")

    if not paper_text or not paper_text.strip():
        raise gr.Error("Please upload a PDF or paste paper text before extracting.")
    if not api_key or not api_key.strip():
        raise gr.Error(f"Please provide your {_key_name(method)}.")

    combined = paper_text.strip()
    if card_text and card_text.strip():
        combined += "\n\n--- DATASET CARD ---\n\n" + card_text.strip()

    progress(0.2, desc=f"Running {method.label} (typically {method.typical})...")
    try:
        result = pipelines.run(method_label, combined, api_key, hf_dataset_id)
    except pipelines.InvalidKey:
        raise gr.Error(f"Invalid {_key_name(method)}. Please check and try again.")
    except Exception as e:
        msg = str(e)
        if "401" in msg or "authentication" in msg.lower() or "api_key" in msg.lower():
            raise gr.Error(f"Invalid {_key_name(method)}. Please check and try again.")
        if "429" in msg or "rate" in msg.lower():
            raise gr.Error("Rate limit hit. Please wait a moment and retry.")
        raise gr.Error(f"Extraction failed: {msg[:300]}")

    progress(0.9, desc="Building outputs...")
    metadata = {k: result.fields.get(k) for k in ALL_FIELD_KEYS}
    return (
        _summary_md(metadata, method, result),
        _build_field_cards(metadata, GENERAL_FIELDS, result.evidence, result.null_reasons),
        _build_field_cards(metadata, RAI_FIELDS, result.evidence, result.null_reasons),
        _build_croissant(metadata, hf_dataset_id),
    )


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def _key_name(method) -> str:
    return "OpenAI API key" if method.provider == "openai" else "Anthropic API key"


def _method_info(method_label: str) -> str:
    m = METHODS_BY_LABEL[method_label]
    return (f"**{m.architecture}** · paper score **{m.paper_score:.3f}** · {m.typical}\n\n"
            f"{m.summary}")


def _on_method_change(method_label: str):
    m = METHODS_BY_LABEL[method_label]
    placeholder = "sk-..." if m.provider == "openai" else "sk-ant-..."
    return _method_info(method_label), gr.update(label=_key_name(m), placeholder=placeholder)


_SCORE_ROWS = "\n".join(
    f"| {m.label} | {m.paper_score:.3f} |" for m in METHODS
)

ABOUT_MD = f"""
## CroissantMiner

**Automated RAI metadata extraction for ML dataset papers**

CroissantMiner extracts 30 metadata fields (10 general + 20 Responsible AI) from the paper
that introduces a dataset, following the [MLCommons Croissant RAI schema](https://github.com/mlcommons/croissant).

### Methods

Every method here runs the same code and configuration as its row in the paper's results table.
Paper score is the composite (core + RAI) on the 88-paper test split.

| Method | Paper score |
|---|---|
{_SCORE_ROWS}

Uploaded PDFs go through the benchmark's preprocessing (PyPDF2 text extraction and cleaning).
Triage + Critique runs its triage step with Claude Sonnet 4.6 so that one key covers the method;
the paper's run used Gemini 2.5 Flash for triage.

### Fields

**General (10):** name, description, url, license, creator, publisher, datePublished, inLanguage, citeAs, isLiveDataset

**Responsible AI (20):** dataCollection, dataCollectionType, dataCollectionMissingData, dataCollectionRawData, dataCollectionTimeframe, dataImputationProtocol, dataManipulationProtocol, dataPreprocessingProtocol, dataAnnotationProtocol, dataAnnotationPlatform, dataAnnotationAnalysis, annotationsPerItem, annotatorDemographics, machineAnnotationTools, dataReleaseMaintenancePlan, personalSensitiveInformation, dataSocialImpact, dataBiases, dataLimitations, dataUseCases

### Links
- **Code:** [github.com/berkearda/croissantminer](https://github.com/berkearda/croissantminer)

---

*Research demo. Review extracted metadata before use. Your API key is sent only to the model provider and is not stored.*
"""

CUSTOM_CSS = """
.gradio-container { max-width: 1100px !important; margin: 0 auto !important; }
#extract-btn button { font-size: 1.05em; padding: 12px; }
.field-card-list { max-height: 65vh; overflow-y: auto; padding-right: 8px; }
#method-info { font-size: 0.92em; }
"""

_DEFAULT_METHOD = METHODS[0].label

with gr.Blocks(title="CroissantMiner") as demo:
    gr.Markdown("# 🥐 CroissantMiner")
    gr.Markdown(
        "*Automated RAI metadata extraction for ML dataset papers.* "
        "Research demo — review extracted metadata before use. "
        "Your API key is sent directly to the model provider and is not stored."
    )

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("Upload PDF"):
                    pdf_input = gr.File(file_types=[".pdf"], label="Dataset paper PDF",
                                        height=120)
                with gr.Tab("Paste Text"):
                    paper_input = gr.Textbox(
                        label="Paper text",
                        placeholder="Paste the full text of a dataset paper here...",
                        lines=6,
                    )
            card_input = gr.Textbox(
                label="Dataset card text (optional)",
                placeholder="Optional: paste the Hugging Face dataset card or README...",
                lines=3,
            )
            hf_id_input = gr.Textbox(
                label="Hugging Face dataset id (optional)",
                placeholder="e.g. openai/gsm8k — lets the agentic methods look up license and URL",
                lines=1,
            )
        with gr.Column(scale=1):
            method_selector = gr.Dropdown(
                choices=[m.label for m in METHODS],
                value=_DEFAULT_METHOD,
                label="Method",
            )
            method_info = gr.Markdown(_method_info(_DEFAULT_METHOD), elem_id="method-info")
            api_key_input = gr.Textbox(
                label=_key_name(METHODS[0]),
                placeholder="sk-ant-...",
                type="password",
            )
            with gr.Row(elem_id="extract-btn"):
                extract_btn = gr.Button("Extract Metadata", variant="primary", size="lg")

    summary_output = gr.Markdown(_summary_md())

    with gr.Tabs():
        with gr.Tab("Extracted Fields"):
            with gr.Accordion("General Fields (10)", open=True):
                general_box = gr.HTML(_build_field_cards({}, GENERAL_FIELDS))
            with gr.Accordion("Responsible AI Fields (20)", open=True):
                rai_box = gr.HTML(_build_field_cards({}, RAI_FIELDS))

        with gr.Tab("Croissant JSON-LD"):
            croissant_output = gr.JSON(label="Croissant JSON-LD", value=None)
            download_btn = gr.DownloadButton(label="Download Croissant JSON-LD", visible=False)

        with gr.Tab("About"):
            gr.Markdown(ABOUT_MD)

    method_selector.change(
        fn=_on_method_change,
        inputs=[method_selector],
        outputs=[method_info, api_key_input],
    )

    extract_btn.click(
        fn=extract_metadata,
        inputs=[pdf_input, paper_input, card_input, method_selector, api_key_input, hf_id_input],
        outputs=[summary_output, general_box, rai_box, croissant_output],
    )

    def _make_download(croissant_dict):
        if not croissant_dict:
            return gr.update(visible=False)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix="_croissant.json", delete=False, prefix="croissantminer_"
        )
        tmp.write(json.dumps(croissant_dict, indent=2, ensure_ascii=False))
        tmp.close()
        return gr.update(label="Download Croissant JSON-LD", value=tmp.name, visible=True)

    croissant_output.change(fn=_make_download, inputs=[croissant_output], outputs=[download_btn])

    gr.Examples(
        examples=[[EXAMPLE_PAPER, "", "openai/gsm8k"]],
        inputs=[paper_input, card_input, hf_id_input],
        label="Example: GSM8K dataset paper (excerpt)",
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=CUSTOM_CSS, ssr_mode=False)
