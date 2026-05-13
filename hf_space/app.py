"""
CroissantMiner — Automated RAI Metadata Extraction for ML Dataset Papers
HuggingFace Space Demo (Gradio)
"""

import json
import re
import tempfile
import gradio as gr

# ---------------------------------------------------------------------------
# Prompts (canonical source: croissantminer/config.py)
# Loaded directly to avoid heavy __init__.py imports (anthropic, scipy, etc.)
# ---------------------------------------------------------------------------

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "croissantminer.config",
    str(__import__("pathlib").Path(__file__).resolve().parent.parent / "croissantminer" / "config.py"),
)
_config_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_config_mod)
SYSTEM_PROMPT = _config_mod.SYSTEM_PROMPT
USER_PROMPT_TEMPLATE = _config_mod.USER_PROMPT_TEMPLATE
del _ilu, _spec, _config_mod


# ---------------------------------------------------------------------------
# Field definitions for the About tab
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

EXAMPLE_CARD = ""

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


def _parse_json_response(text: str) -> dict:
    """Extract JSON from an LLM response that may contain markdown fences."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    raw = json.loads(text)
    # Normalize keys: the prompt uses sc:/cr: prefixes but internal keys don't
    normalized = {}
    for k, v in raw.items():
        if k.startswith("sc:"):
            normalized[k[3:]] = v
        elif k.startswith("cr:"):
            normalized[k[3:]] = v
        else:
            normalized[k] = v
    return normalized


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF (imported lazily)."""
    import pymupdf
    doc = pymupdf.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def _compute_coverage(metadata: dict) -> str:
    """Compute extraction coverage and return a Markdown summary."""
    general_filled = sum(1 for k, _ in GENERAL_FIELDS if _is_valid(metadata.get(k)))
    rai_filled = sum(1 for k, _ in RAI_FIELDS if _is_valid(metadata.get(k)))
    total_filled = general_filled + rai_filled
    total = len(GENERAL_FIELDS) + len(RAI_FIELDS)
    pct = int(100 * total_filled / total)

    return (
        f"### Extraction Coverage: {total_filled}/{total} fields ({pct}%)\n\n"
        f"**General:** {general_filled}/{len(GENERAL_FIELDS)} &nbsp;|&nbsp; "
        f"**RAI:** {rai_filled}/{len(RAI_FIELDS)}"
    )


def _build_field_table(metadata: dict, fields: list) -> list:
    """Build a table of [Field, Description, Value] rows for gr.Dataframe."""
    rows = []
    for key, desc in fields:
        val = metadata.get(key)
        if val is None or not _is_valid(val):
            display_val = "—"
        elif isinstance(val, str):
            display_val = val
        elif isinstance(val, dict):
            display_val = val.get("name", json.dumps(val, ensure_ascii=False))
        else:
            display_val = str(val)
        rows.append([key, desc, display_val])
    return rows


def _build_croissant(metadata: dict) -> dict:
    """Convert extracted metadata dict into Croissant JSON-LD."""
    name = metadata.get("name") or "unknown"
    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "cro": "https://w3id.org/cro/",
            "rai": "https://w3id.org/cro/rai/",
        },
        "@type": "cro:Dataset",
        "@id": f"https://huggingface.co/datasets/{name.lower().replace(' ', '_')}",
        "name": name,
        "description": metadata.get("description"),
        "license": metadata.get("license") if _is_valid(metadata.get("license")) else "unknown",
    }

    for key in ("datePublished", "inLanguage", "url", "publisher", "citeAs"):
        if _is_valid(metadata.get(key)):
            croissant[key] = metadata[key]

    is_live = metadata.get("isLiveDataset", "")
    if isinstance(is_live, bool):
        croissant["isLiveDataset"] = is_live
    elif isinstance(is_live, str) and is_live.lower() in ("yes", "true"):
        croissant["isLiveDataset"] = True

    creator = metadata.get("creator")
    if creator:
        if isinstance(creator, dict) and _is_valid(creator.get("name", "")):
            croissant["creator"] = {
                "@type": creator.get("@type", "Organization"),
                "name": creator["name"],
            }
        elif isinstance(creator, str) and _is_valid(creator):
            croissant["creator"] = {"@type": "Organization", "name": creator}

    desc = (metadata.get("description") or "").lower()
    if any(k in desc for k in ("text", "nlp", "language", "corpus", "math")):
        modality = ["cro:TextData"]
    elif any(k in desc for k in ("image", "vision", "visual", "picture")):
        modality = ["cro:ImageData"]
    else:
        modality = ["cro:TabularData"]
    croissant["cro:dataModality"] = modality

    rai_metadata = {}
    for key, _ in RAI_FIELDS:
        if _is_valid(metadata.get(key)):
            rai_metadata[key] = metadata[key]

    if rai_metadata:
        rai_metadata["@type"] = "rai:ResponsibleAIMetadata"
        croissant["rai:responsibleAIMetadata"] = rai_metadata

    return croissant


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------


def extract_metadata(pdf_file, paper_text: str, card_text: str, model_name: str, api_key: str, progress=gr.Progress()):
    """Run extraction pipeline and return results for all output tabs."""

    # Resolve paper text from PDF upload or pasted text
    if pdf_file is not None:
        progress(0.1, desc="Reading PDF...")
        try:
            file_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
            paper_text = _extract_text_from_pdf(file_path)
        except Exception as e:
            raise gr.Error(f"Failed to read PDF: {e}")

    if not paper_text or not paper_text.strip():
        raise gr.Error("Please upload a PDF or paste paper text before extracting.")
    if not api_key or not api_key.strip():
        raise gr.Error("Please provide your API key.")

    progress(0.15, desc="Preparing prompt...")

    # Combine paper + optional card text
    combined = paper_text.strip()
    if card_text and card_text.strip():
        combined += "\n\n--- DATASET CARD ---\n\n" + card_text.strip()

    user_prompt = USER_PROMPT_TEMPLATE % combined

    # Call the selected model
    progress(0.2, desc=f"Calling {model_name}...")
    try:
        if model_name == "Claude Sonnet 4.5":
            import anthropic

            client = anthropic.Anthropic(
                api_key=api_key.strip(),
                base_url="https://api.anthropic.com",
            )
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                temperature=0.0,
                system=[{"type": "text", "text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text

        elif model_name == "GPT-4o-mini":
            from openai import OpenAI

            client = OpenAI(api_key=api_key.strip())
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4096,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content

        else:
            raise gr.Error(f"Unknown model: {model_name}")

    except gr.Error:
        raise
    except Exception as e:
        msg = str(e)
        if "401" in msg or "auth" in msg.lower() or "invalid" in msg.lower():
            raise gr.Error("Invalid API key. Please check and try again.")
        if "429" in msg or "rate" in msg.lower():
            raise gr.Error("Rate limit hit. Please wait a moment and retry.")
        raise gr.Error(f"API error: {msg[:300]}")

    # Parse response
    progress(0.8, desc="Parsing response...")
    try:
        metadata = _parse_json_response(raw)
    except (json.JSONDecodeError, IndexError) as e:
        raise gr.Error(f"Failed to parse model response as JSON: {e}")

    # Ensure all fields present
    for key in ALL_FIELD_KEYS:
        metadata.setdefault(key, None)

    # Build outputs
    progress(0.9, desc="Building outputs...")
    coverage_md = _compute_coverage(metadata)
    general_table = _build_field_table(metadata, GENERAL_FIELDS)
    rai_table = _build_field_table(metadata, RAI_FIELDS)
    croissant = _build_croissant(metadata)

    return coverage_md, general_table, rai_table, croissant


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

ABOUT_MD = """
## CroissantMiner

**Automated RAI Metadata Extraction for ML Dataset Papers**

CroissantMiner uses Large Language Models to extract structured metadata from academic papers describing ML datasets, following the [MLCommons Croissant RAI schema](https://github.com/mlcommons/croissant).

### How it works
1. Upload a PDF or paste the text of a dataset paper (and optionally a dataset card).
2. Select a model and provide your API key.
3. CroissantMiner extracts 30 metadata fields (10 General + 20 Responsible AI).
4. Download the result as a valid Croissant JSON-LD file.

### Extracted Fields

**General (10):** name, description, url, license, creator, publisher, datePublished, inLanguage, citeAs, isLiveDataset

**Responsible AI (20):** dataCollection, dataCollectionType, dataCollectionMissingData, dataCollectionRawData, dataCollectionTimeframe, dataImputationProtocol, dataManipulationProtocol, dataPreprocessingProtocol, dataAnnotationProtocol, dataAnnotationPlatform, dataAnnotationAnalysis, annotationsPerItem, annotatorDemographics, machineAnnotationTools, dataReleaseMaintenancePlan, personalSensitiveInformation, dataSocialImpact, dataBiases, dataLimitations, dataUseCases

### Links
- **GitHub:** [github.com/berkearda/croissantminer](https://github.com/berkearda/croissantminer)

---

*Research demo. Review extracted metadata before use.*
"""

_INITIAL_GENERAL_TABLE = [[k, desc, "—"] for k, desc in GENERAL_FIELDS]
_INITIAL_RAI_TABLE = [[k, desc, "—"] for k, desc in RAI_FIELDS]

with gr.Blocks(title="CroissantMiner") as demo:
    gr.Markdown("# CroissantMiner\n*Automated RAI Metadata Extraction for ML Dataset Papers*")
    gr.Markdown(
        "> **Research demo.** Review extracted metadata before use. "
        "Your API key is sent directly to the model provider and is not stored."
    )

    with gr.Row():
        # ===== LEFT COLUMN: Inputs =====
        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("Upload PDF"):
                    pdf_input = gr.File(
                        file_types=[".pdf"],
                        label="Upload dataset paper PDF",
                    )
                with gr.Tab("Paste Text"):
                    paper_input = gr.Textbox(
                        label="Paste paper text",
                        placeholder="Paste the full text of a dataset paper here...",
                        lines=14,
                    )
            card_input = gr.Textbox(
                label="Paste dataset card text (optional)",
                placeholder="Optional: paste HuggingFace dataset card or README...",
                lines=5,
            )
            model_selector = gr.Dropdown(
                choices=["Claude Sonnet 4.5", "GPT-4o-mini"],
                value="Claude Sonnet 4.5",
                label="Model",
            )
            api_key_input = gr.Textbox(
                label="API Key",
                placeholder="sk-... or your Anthropic key",
                type="password",
            )
            extract_btn = gr.Button("Extract Metadata", variant="primary")

        # ===== RIGHT COLUMN: Outputs =====
        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("Extracted Fields"):
                    coverage_output = gr.Markdown(
                        value="### Extraction Coverage: 0/30 fields (0%)\n\n**General:** 0/10 &nbsp;|&nbsp; **RAI:** 0/20"
                    )
                    with gr.Accordion("General Fields", open=True):
                        general_df = gr.Dataframe(
                            value=_INITIAL_GENERAL_TABLE,
                            headers=["Field", "Description", "Extracted Value"],
                            datatype=["str", "str", "str"],
                            column_count=(3, "fixed"),
                            wrap=True,
                            interactive=False,
                        )
                    with gr.Accordion("RAI Fields", open=False):
                        rai_df = gr.Dataframe(
                            value=_INITIAL_RAI_TABLE,
                            headers=["Field", "Description", "Extracted Value"],
                            datatype=["str", "str", "str"],
                            column_count=(3, "fixed"),
                            wrap=True,
                            interactive=False,
                        )

                with gr.Tab("Croissant JSON-LD"):
                    croissant_output = gr.JSON(label="Croissant JSON-LD", value=None)
                    download_btn = gr.DownloadButton(
                        label="Download Croissant JSON-LD",
                        visible=False,
                    )

                with gr.Tab("About"):
                    gr.Markdown(ABOUT_MD)

    # Wire up extraction
    extract_btn.click(
        fn=extract_metadata,
        inputs=[pdf_input, paper_input, card_input, model_selector, api_key_input],
        outputs=[coverage_output, general_df, rai_df, croissant_output],
    )

    # Enable download when croissant output is populated
    def _make_download(croissant_dict):
        if not croissant_dict:
            return gr.update(visible=False)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix="_croissant.json", delete=False, prefix="croissantminer_"
        )
        tmp.write(json.dumps(croissant_dict, indent=2, ensure_ascii=False))
        tmp.close()
        return gr.update(label="Download Croissant JSON-LD", value=tmp.name, visible=True)

    croissant_output.change(
        fn=_make_download,
        inputs=[croissant_output],
        outputs=[download_btn],
    )

    # Pre-loaded example
    gr.Examples(
        examples=[[EXAMPLE_PAPER, EXAMPLE_CARD]],
        inputs=[paper_input, card_input],
        label="Example: GSM8K Dataset Paper (excerpt)",
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), ssr_mode=False)
