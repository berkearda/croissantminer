"""
CroissantMiner: extract Croissant metadata from ML dataset papers
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

# the Space runs from a copy of the repository without installing it
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from croissantminer import methods as pipelines  # noqa: E402
from croissantminer.croissant import (  # noqa: E402
    ALL_FIELDS as ALL_FIELD_KEYS, CORE_FIELDS as GENERAL_FIELDS, RAI_FIELDS,
    is_filled as _is_valid, to_croissant as _build_croissant, value_text as _value_text)
from croissantminer.methods import METHODS, METHODS_BY_LABEL  # noqa: E402

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------


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


def _compute_coverage(metadata: dict) -> tuple[int, int, int]:
    general = sum(1 for k, _ in GENERAL_FIELDS if _is_valid(metadata.get(k)))
    rai = sum(1 for k, _ in RAI_FIELDS if _is_valid(metadata.get(k)))
    return general + rai, general, rai


def _summary_md(metadata: dict | None = None, method=None, result=None) -> str:
    if metadata is None:
        return ""
    total, general, rai = _compute_coverage(metadata)
    n = len(ALL_FIELD_KEYS)
    lines = [f"### Found {total} of {n} fields",
             f"Core {general} of {len(GENERAL_FIELDS)} · Responsible AI {rai} of {len(RAI_FIELDS)}"]
    if method is not None and result is not None:
        run = f"{method.label} · {result.elapsed_s:.0f} s"
        if result.cost_usd:
            run += f" · ≈ ${result.cost_usd:.2f}"
        lines.append(f'<span class="run-info">{html.escape(run)}</span>')
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
        body = (html.escape(_value_text(val)) if filled
                else '<span class="fc-none">Not found</span>')
        extra = ""
        if filled and evidence.get(key):
            quote = html.escape(str(evidence[key]).strip())
            extra = f'<div class="fc-extra"><b>Evidence</b> “{quote}”</div>'
        elif not filled and null_reasons.get(key):
            extra = f'<div class="fc-extra">{html.escape(str(null_reasons[key]))}</div>'
        blocks.append(
            f'<div class="fc{"" if filled else " fc-empty"}">'
            f'<div class="fc-head"><code>{key}</code><span>{desc}</span></div>'
            f'<div class="fc-val">{body}</div>{extra}</div>'
        )
    return f'<div class="field-card-list">{"".join(blocks)}</div>'


def _fields_html(metadata: dict | None = None, evidence: dict | None = None,
                 null_reasons: dict | None = None) -> str:
    """Both field groups as collapsible sections; before the first run, a short
    note. (Showing and hiding Gradio accordions instead broke the page in
    Gradio 6.14, so everything stays in one HTML value.)"""
    if metadata is None:
        return ('<p id="empty-note">Results will appear here after you click '
                '<b>Extract Metadata</b>.</p>')
    groups = [("Core Fields (10)", GENERAL_FIELDS), ("Responsible AI Fields (20)", RAI_FIELDS)]
    return "".join(f'<details class="fc-group" open><summary>{title}</summary>'
                   f'{_build_field_cards(metadata, fields, evidence, null_reasons)}</details>'
                   for title, fields in groups)



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
        _fields_html(metadata, result.evidence, result.null_reasons),
        _build_croissant(metadata, hf_dataset_id),
    )


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def _key_name(method) -> str:
    return "OpenAI API key" if method.provider == "openai" else "Anthropic API key"


def _method_info(method_label: str) -> str:
    m = METHODS_BY_LABEL[method_label]
    return (f"**{m.architecture}** · score in the paper: **{m.paper_score:.3f}** · {m.typical}\n\n"
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

**Extract Croissant metadata from ML dataset papers**

CroissantMiner extracts 30 metadata fields (10 core + 20 Responsible AI) from the paper
that introduces a dataset, following the [MLCommons Croissant RAI schema](https://github.com/mlcommons/croissant).

### Methods

Every method here runs the same code and settings as its row in the paper's results table.
The score in the paper is the composite score over all 30 fields on the 88 test papers (higher is better).

| Method | Score in the paper |
|---|---|
{_SCORE_ROWS}

Uploaded PDFs go through the benchmark's preprocessing (PyPDF2 text extraction and cleaning).
Triage + Critique runs its triage step with Claude Sonnet 4.6 so that one key covers the method;
the paper's run used Gemini 2.5 Flash for triage.

### Fields

**Core (10):** name, description, url, license, creator, publisher, datePublished, inLanguage, citeAs, isLiveDataset

**Responsible AI (20):** dataCollection, dataCollectionType, dataCollectionMissingData, dataCollectionRawData, dataCollectionTimeframe, dataImputationProtocol, dataManipulationProtocol, dataPreprocessingProtocol, dataAnnotationProtocol, dataAnnotationPlatform, dataAnnotationAnalysis, annotationsPerItem, annotatorDemographics, machineAnnotationTools, dataReleaseMaintenancePlan, personalSensitiveInformation, dataSocialImpact, dataBiases, dataLimitations, dataUseCases

### Links
- **Code:** [github.com/berkearda/croissantminer](https://github.com/berkearda/croissantminer)
- **Dataset:** [huggingface.co/datasets/bearda/croissantminer](https://huggingface.co/datasets/bearda/croissantminer)

---

*Research demo. Review extracted metadata before use. Your API key is sent only to the model provider and is not stored.*
"""

CUSTOM_CSS = """
.gradio-container { max-width: 1100px !important; margin: 0 auto !important; }
.step-card { background: var(--background-fill-secondary); border: 1px solid var(--border-color-primary);
             border-radius: var(--radius-lg); padding: 14px 16px !important; justify-content: flex-start !important; }
.step-card > * { flex-grow: 0 !important; }
.step-card .flat, .step-card .form { background: transparent !important; border: none !important;
                                     box-shadow: none !important; }
.step-card .flat { padding: 0 !important; }
.step-title h3 { margin: 0; font-size: 1.05em; }
#fields-box .html-container, #app-title .html-container { padding: 0 !important; }
.app-title { display: flex; align-items: center; gap: 10px; margin: 0; }
.app-title svg { width: 1.5em; height: 1.5em; flex: none; }
#method-info { font-size: 0.92em; }
#empty-note, .run-info { color: var(--body-text-color-subdued); }
#empty-note { padding: 8px 2px; }
.fc-group summary { cursor: pointer; font-weight: 600; margin: 12px 0 4px; }
.fc { border-left: 3px solid var(--color-accent); padding: 8px 14px; margin: 6px 0;
      background: var(--background-fill-secondary); border-radius: 4px; }
.fc-empty { border-left-color: var(--border-color-primary); }
.fc-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.fc-head code { font-family: var(--font-mono); font-weight: 600; color: var(--body-text-color);
               background: none; padding: 0; }
.fc-head span { font-size: 0.8em; color: var(--body-text-color-subdued); text-align: right; }
.fc-val { margin-top: 6px; line-height: 1.5; color: var(--body-text-color); white-space: pre-wrap; }
.fc-none, .fc-extra { color: var(--body-text-color-subdued); }
.fc-extra { margin-top: 6px; font-size: 0.85em; }
"""

THEME = gr.themes.Default(
    primary_hue="blue", neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
).set(
    block_label_background_fill="transparent", block_label_background_fill_dark="transparent",
    block_label_text_color="*neutral_600", block_label_text_color_dark="*neutral_300",
    block_title_background_fill="transparent", block_title_background_fill_dark="transparent",
    block_title_text_color="*neutral_700", block_title_text_color_dark="*neutral_200",
    button_primary_text_color="white", button_primary_text_color_dark="white",
    button_primary_background_fill="*primary_600", button_primary_background_fill_hover="*primary_700",
    button_primary_background_fill_dark="*primary_600", button_primary_background_fill_hover_dark="*primary_500",
)

_DEFAULT_METHOD = METHODS[0].label

with gr.Blocks(title="CroissantMiner") as demo:
    # logo next to the title: on huggingface.co the browser tab shows Hugging Face's icon
    _logo = (Path(__file__).resolve().parent / "favicon.svg").read_text()
    gr.HTML(f'<h1 class="app-title">{_logo}CroissantMiner</h1>', padding=False, elem_id="app-title")
    gr.Markdown(
        "*Extract Croissant metadata from ML dataset papers.* "
        "Research demo: review the extracted metadata before use. "
        "Your API key is sent only to the model provider and is not stored.\n\n"
        "[Code](https://github.com/berkearda/croissantminer) · "
        "[Dataset](https://huggingface.co/datasets/bearda/croissantminer)"
    )

    with gr.Row(equal_height=True):
        with gr.Column(scale=3, elem_classes="step-card"):
            gr.Markdown("### 1. Paper", elem_classes="step-title")
            with gr.Tabs() as input_tabs:
                with gr.Tab("Upload PDF", id="pdf"):
                    pdf_input = gr.File(file_types=[".pdf"], label="Dataset paper PDF",
                                        height=120)
                with gr.Tab("Paste Text", id="paste"):
                    paper_input = gr.Textbox(
                        label="Paper text",
                        placeholder="Paste the full text of a dataset paper here...",
                        lines=6,
                        elem_classes="flat",
                    )
            with gr.Row():
                example_btn = gr.Button("Load example paper (GSM8K)", size="sm", scale=0, min_width=230)
            with gr.Accordion("Optional: dataset card and Hugging Face dataset id", open=False):
                card_input = gr.Textbox(
                    label="Dataset card text",
                    placeholder="Paste the Hugging Face dataset card or README...",
                    lines=3,
                )
                hf_id_input = gr.Textbox(
                    label="Hugging Face dataset id",
                    placeholder="e.g. openai/gsm8k (lets the agentic methods look up the license and URL)",
                    lines=1,
                )
        with gr.Column(scale=2, elem_classes="step-card"):
            gr.Markdown("### 2. Method", elem_classes="step-title")
            method_selector = gr.Dropdown(
                choices=[m.label for m in METHODS],
                value=_DEFAULT_METHOD,
                label="Method",
                show_label=False,
                elem_classes="flat",
            )
            method_info = gr.Markdown(_method_info(_DEFAULT_METHOD), elem_id="method-info")
            api_key_input = gr.Textbox(
                label=_key_name(METHODS[0]),
                placeholder="sk-ant-...",
                type="password",
                elem_classes="flat",
            )
            extract_btn = gr.Button("Extract Metadata", variant="primary", size="lg")

    summary_output = gr.Markdown(_summary_md())

    with gr.Tabs():
        with gr.Tab("Extracted Fields"):
            fields_box = gr.HTML(_fields_html(), padding=False, elem_id="fields-box")

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
        outputs=[summary_output, fields_box, croissant_output],
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

    # A button rather than gr.Examples: with gr.Examples on the page, Gradio 6.14
    # froze the browser when switching to the Croissant JSON-LD or About tab.
    example_btn.click(lambda: (None, EXAMPLE_PAPER, "openai/gsm8k", gr.Tabs(selected="paste")),
                      outputs=[pdf_input, paper_input, hf_id_input, input_tabs])

if __name__ == "__main__":
    demo.launch(theme=THEME, css=CUSTOM_CSS, ssr_mode=False,
                favicon_path=str(Path(__file__).resolve().parent / "favicon.svg"))
