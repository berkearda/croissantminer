"""
CroissantMiner — Automated RAI Metadata Extraction for ML Dataset Papers
HuggingFace Space Demo (Gradio)
"""

import json
import re
import gradio as gr
import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Prompts (copied from croissantminer/config.py for self-contained deployment)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = '''You are an expert researcher specializing in "Responsible AI" and metadata extraction for Machine Learning datasets.

**Your Task:**
Extract structured metadata from the provided academic paper according to the MLCommons Croissant RAI schema described below.

**Extraction Guidelines:**
1. **Accuracy First:** Only extract information explicitly stated in the paper.
2. **No Guessing:** If information is not found, return null. Do not fill fields with your own background information or assumptions that are not explicitly given in the paper.
3. **Formatting Rules:**
   - Return ONLY valid JSON.
   - Use null for missing fields.
   - No markdown formatting.

4. **RAI Field-Specific Information:**
   *Use the following official definitions to guide your extraction. Use them as matching criteria when scanning the text:*

   - **rai:dataCollection**: Description of the data collection process.
   - **rai:dataCollectionType**: Define the data collection type(s). Choose one or multiple values from: Surveys, Secondary Data analysis, Physical data collection, Direct measurement, Document analysis, Manual Human Curator, Software Collection, Experiments, Web Scraping, Web API, Focus groups, Self-reporting, Customer feedback data, User-generated content data, Passive Data Collection, Others.
   - **rai:dataCollectionMissingData**: Description of missing data in textual form. Only if missingness is explicitly discussed.
   - **rai:dataCollectionRawData**: Description of the raw data collection (i.e., source of the data).
   - **rai:dataCollectionTimeframe**: Timeframe in terms of start and end date of the collection process.
   - **rai:dataImputationProtocol**: Description of data imputation process if applicable, i.e., how missing or incomplete data were imputed or filled.
   - **rai:dataManipulationProtocol**: Description of data manipulation process if applicable.
   - **rai:dataPreprocessingProtocol**: Description of the steps that were required to bring collected data to a state that can be processed by an ML model/algorithm (e.g., filtering out incomplete entries).
   - **rai:dataAnnotationProtocol**: Description of annotations (labels, ratings), and how these were created or authored.
   - **rai:dataAnnotationPlatform**: Platform, tool, or library used to collect annotations by human annotators.
   - **rai:dataAnnotationAnalysis**: Considerations related to the process of converting the "raw" annotations into the final labels (e.g., uncertainty, disagreement analysis).
   - **rai:dataReleaseMaintenancePlan**: Versioning information in terms of the updating timeframe, the maintainers, and the deprecation policies.
   - **rai:personalSensitiveInformation**: Any sensitive human attribute(s) collected as part of this dataset (e.g., gender, socio-economic status, geography, language, age, culture, experience).
   - **rai:dataSocialImpact**: Discussion of social implications, if applicable.
   - **rai:dataBiases**: Description of biases in the dataset, if applicable.
   - **rai:dataLimitations**: Known limitations (e.g., data generalization limits, quality issues) and non-recommended uses.
   - **rai:dataUseCases**: Dataset use case(s) (e.g., Training, Testing, Validation, Fine Tuning) and Usage Guidelines.
   - **rai:annotationsPerItem**: Number of human labels per dataset item.
   - **rai:annotatorDemographics**: List of demographics specifications about the annotators.
   - **rai:machineAnnotationTools**: List of software used for data annotation (e.g., NER tools, automated labelers).'''

USER_PROMPT_TEMPLATE = '''Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{
  "name": "string",
  "description": "string",
  "url": "string",
  "license": "string",
  "creator": "object or string",
  "publisher": "string",
  "datePublished": "string (YYYY-MM-DD or YYYY)",
  "inLanguage": "string (ISO codes)",
  "citeAs": "string",
  "isLiveDataset": "string (Yes/No)",

  "rai:dataCollection": "string",
  "rai:dataCollectionType": "string (Select from recommended values)",
  "rai:dataCollectionMissingData": "string",
  "rai:dataCollectionRawData": "string",
  "rai:dataCollectionTimeframe": "string",
  "rai:dataImputationProtocol": "string",
  "rai:dataManipulationProtocol": "string",
  "rai:dataPreprocessingProtocol": "string",

  "rai:dataAnnotationProtocol": "string",
  "rai:dataAnnotationPlatform": "string",
  "rai:dataAnnotationAnalysis": "string",
  "rai:annotationsPerItem": "string",
  "rai:annotatorDemographics": "string",
  "rai:machineAnnotationTools": "string",

  "rai:dataReleaseMaintenancePlan": "string",
  "rai:personalSensitiveInformation": "string",
  "rai:dataSocialImpact": "string",
  "rai:dataBiases": "string",
  "rai:dataLimitations": "string",
  "rai:dataUseCases": "string"
}

PAPER TEXT:
%s

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations.'''

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

EXAMPLE_CARD = ""  # No dataset card for example

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
    return json.loads(text)


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


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

    # Optional top-level fields
    for key in ("datePublished", "inLanguage", "url", "publisher", "citeAs"):
        if _is_valid(metadata.get(key)):
            croissant[key] = metadata[key]

    # isLiveDataset
    is_live = metadata.get("isLiveDataset", "")
    if isinstance(is_live, bool):
        croissant["isLiveDataset"] = is_live
    elif isinstance(is_live, str) and is_live.lower() in ("yes", "true"):
        croissant["isLiveDataset"] = True

    # Creator
    creator = metadata.get("creator")
    if creator:
        if isinstance(creator, dict) and _is_valid(creator.get("name", "")):
            croissant["creator"] = {
                "@type": creator.get("@type", "Organization"),
                "name": creator["name"],
            }
        elif isinstance(creator, str) and _is_valid(creator):
            croissant["creator"] = {"@type": "Organization", "name": creator}

    # Data modality inference
    desc = (metadata.get("description") or "").lower()
    if any(k in desc for k in ("text", "nlp", "language", "corpus", "math")):
        modality = ["cro:TextData"]
    elif any(k in desc for k in ("image", "vision", "visual", "picture")):
        modality = ["cro:ImageData"]
    else:
        modality = ["cro:TabularData"]
    croissant["cro:dataModality"] = modality

    # RAI metadata block — include ALL 20 RAI fields
    rai_metadata = {}
    for key, _ in RAI_FIELDS:
        if _is_valid(metadata.get(key)):
            rai_metadata[key] = metadata[key]

    if rai_metadata:
        rai_metadata["@type"] = "rai:ResponsibleAIMetadata"
        croissant["rai:responsibleAIMetadata"] = rai_metadata

    return croissant


def _format_grouped(metadata: dict) -> dict:
    """Group extracted metadata for display."""
    general = {}
    for key, desc in GENERAL_FIELDS:
        general[key] = metadata.get(key)
    rai = {}
    for key, desc in RAI_FIELDS:
        rai[key] = metadata.get(key)
    return {"General Fields (10)": general, "RAI Fields (20)": rai}


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------


def extract_metadata(pdf_file, paper_text: str, card_text: str, model_name: str, api_key: str):
    """Run extraction pipeline and return results for all output tabs."""

    # Resolve paper text from PDF upload or pasted text
    if pdf_file is not None:
        try:
            # gr.File returns a filepath string in Gradio 5+
            file_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
            paper_text = _extract_text_from_pdf(file_path)
        except Exception as e:
            raise gr.Error(f"Failed to read PDF: {e}")

    if not paper_text or not paper_text.strip():
        raise gr.Error("Please upload a PDF or paste paper text before extracting.")
    if not api_key or not api_key.strip():
        raise gr.Error("Please provide your API key.")

    # Combine paper + optional card text
    combined = paper_text.strip()
    if card_text and card_text.strip():
        combined += "\n\n--- DATASET CARD ---\n\n" + card_text.strip()

    user_prompt = USER_PROMPT_TEMPLATE % combined

    # Call the selected model
    try:
        if model_name == "Claude Sonnet 4.5":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key.strip())
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
    try:
        metadata = _parse_json_response(raw)
    except (json.JSONDecodeError, IndexError) as e:
        raise gr.Error(f"Failed to parse model response as JSON: {e}")

    # Ensure all fields present
    for key in ALL_FIELD_KEYS:
        metadata.setdefault(key, None)

    # Build outputs
    grouped = _format_grouped(metadata)
    croissant = _build_croissant(metadata)

    return (
        json.dumps(grouped, indent=2, ensure_ascii=False),
        json.dumps(croissant, indent=2, ensure_ascii=False),
    )


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

with gr.Blocks(
    title="CroissantMiner",
    theme=gr.themes.Soft(),
) as demo:
    gr.Markdown("# CroissantMiner\n*Automated RAI Metadata Extraction for ML Dataset Papers*")
    gr.Markdown(
        "> **Research demo.** Review extracted metadata before use. "
        "Your API key is sent directly to the model provider and is not stored."
    )

    with gr.Row():
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

        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("Extracted Metadata"):
                    metadata_output = gr.Code(
                        label="30 fields (General + RAI)",
                        language="json",
                        lines=25,
                    )
                with gr.Tab("Croissant JSON-LD"):
                    croissant_output = gr.Code(
                        label="Croissant JSON-LD",
                        language="json",
                        lines=25,
                    )
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
        outputs=[metadata_output, croissant_output],
    )

    # Enable download when croissant output is populated
    def _make_download(croissant_json: str):
        if not croissant_json or not croissant_json.strip():
            return gr.DownloadButton(visible=False)
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix="_croissant.json", delete=False, prefix="croissantminer_"
        )
        tmp.write(croissant_json)
        tmp.close()
        return gr.DownloadButton(label="Download Croissant JSON-LD", value=tmp.name, visible=True)

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
    import inspect
    launch_kwargs = {}
    if "ssr_mode" in inspect.signature(demo.launch).parameters:
        launch_kwargs["ssr_mode"] = False
    demo.launch(**launch_kwargs)
