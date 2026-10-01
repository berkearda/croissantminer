"""The 30 Croissant fields and the conversion of extracted values to a Croissant 1.1 JSON-LD file."""
from __future__ import annotations

import json
import re
from datetime import datetime

CORE_FIELDS = [
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

ALL_FIELDS = [f[0] for f in CORE_FIELDS + RAI_FIELDS]


def is_filled(val):
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


def value_text(val) -> str:
    if isinstance(val, dict):
        return val.get("name") or json.dumps(val, ensure_ascii=False)
    if isinstance(val, list):
        return ", ".join(value_text(v) for v in val)
    return str(val)


_ORG_WORDS = re.compile(r"\b(inc|corp|llc|ltd|university|institute|lab|labs|laboratory|"
                        r"research|foundation|google|openai|meta|microsoft|deepmind|"
                        r"anthropic|nvidia|allen|team|group|center|centre)\b", re.I)


def _creator_jsonld(creator):
    """schema.org creator: a list of Person for comma-separated names, an
    Organization for a single organisation name."""
    if isinstance(creator, dict):
        return creator
    text = value_text(creator).strip()
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


def to_croissant(metadata: dict, hf_dataset_id: str = "") -> dict:
    """Convert extracted metadata into Croissant JSON-LD. Only extracted values
    are emitted: nothing is filled with placeholders."""
    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "rai": "http://mlcommons.org/croissant/RAI/",
            "dct": "http://purl.org/dc/terms/",
            "conformsTo": "dct:conformsTo",
        },
        "@type": "sc:Dataset",
        # without a version, mlcroissant applies Croissant 0.8 rules (no spaces in names)
        "conformsTo": "http://mlcommons.org/croissant/1.1",
    }
    hf = (hf_dataset_id or "").strip().strip("/")
    if "/" in hf:
        croissant["@id"] = f"https://huggingface.co/datasets/{hf.split('datasets/')[-1]}"
    for key in ("name", "description", "license", "url", "publisher", "datePublished",
                "inLanguage"):
        if is_filled(metadata.get(key)):
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
    if is_filled(metadata.get("citeAs")):
        croissant["cr:citeAs"] = metadata["citeAs"]
    if is_filled(metadata.get("creator")):
        croissant["creator"] = _creator_jsonld(metadata["creator"])
    is_live = metadata.get("isLiveDataset")
    if isinstance(is_live, bool):
        croissant["cr:isLiveDataset"] = is_live
    elif isinstance(is_live, str) and is_live.strip().lower() in ("yes", "true", "no", "false"):
        croissant["cr:isLiveDataset"] = is_live.strip().lower() in ("yes", "true")
    for key, _ in RAI_FIELDS:
        if is_filled(metadata.get(key)):
            croissant[key] = metadata[key]
    return croissant


def validate(croissant: dict) -> tuple[bool | None, list[str]]:
    """Check a Croissant file with mlcroissant, the MLCommons reference library.
    Returns (passed, messages); passed is None when mlcroissant is not installed."""
    try:
        import mlcroissant as mlc
        from absl import logging as absl_logging
    except ImportError:
        return None, ['mlcroissant is not installed: pip install "croissantminer[validate]"']
    except Exception as e:  # noqa: BLE001 - a broken install, e.g. on an unsupported Python version
        return None, [f"mlcroissant could not be loaded ({type(e).__name__}: {e})"]
    import os
    import tempfile
    absl_logging.set_verbosity(absl_logging.ERROR)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(croissant, f)
    try:
        dataset = mlc.Dataset(jsonld=f.name)
        return True, [str(w) for w in sorted(dataset.metadata.ctx.issues.warnings)]
    except mlc.ValidationError as e:
        return False, [line.strip(" -") for line in str(e).splitlines() if line.strip().startswith("-")]
    finally:
        os.unlink(f.name)


HF_CROISSANT = "https://huggingface.co/api/datasets/{}/croissant"
_HF_ID = re.compile(r"^[A-Za-z0-9][\w.-]*/[\w.-]+$")


def load(source: str) -> dict:
    """A Croissant file from a path, a URL, or a Hugging Face dataset id ("org/name"),
    whose file Hugging Face generates. HF_TOKEN is used for private or gated datasets."""
    import os
    from pathlib import Path
    if Path(source).is_file():
        return json.loads(Path(source).read_text(encoding="utf-8"))
    url = source
    if source.startswith("https://huggingface.co/datasets/"):
        url = HF_CROISSANT.format("/".join(source.split("/datasets/", 1)[1].strip("/").split("/")[:2]))
    elif _HF_ID.match(source):
        url = HF_CROISSANT.format(source)
    elif not source.startswith(("http://", "https://")):
        raise ValueError(f"{source!r} is not a file, a URL or a Hugging Face dataset id (org/name)")
    import requests
    headers = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"} if os.environ.get("HF_TOKEN") else {}
    r = requests.get(url, headers=headers, timeout=60)
    if r.status_code in (401, 403, 404) and url.startswith(HF_CROISSANT.split("{")[0]):
        raise ValueError(f"Hugging Face has no Croissant file for {source} (HTTP {r.status_code}). It generates one "
                         "for datasets it can read; a private or gated dataset needs HF_TOKEN.")
    r.raise_for_status()
    return r.json()


def merge(host: dict, ours: dict) -> tuple[dict, list[str], list[str]]:
    """Add the extracted fields to the host's file (the one with the data files and columns).
    Every rai: field and every core field the host lacks is added; a value the host already
    has is kept. Returns (merged file, fields added, fields kept from the host)."""
    merged = json.loads(json.dumps(host))
    context = merged.setdefault("@context", {})
    if isinstance(context, dict):
        context.setdefault("rai", "http://mlcommons.org/croissant/RAI/")
        aliases = {v: k for k, v in context.items() if isinstance(v, str) and not k.startswith("@")}
    else:
        aliases = {}
    added, kept = [], []
    for key, value in ours.items():
        if key.startswith("@") or key == "conformsTo":
            continue
        target = aliases.get(key, key)          # e.g. cr:citeAs is written "citeAs" when the host defines that name
        if target in merged or key in merged:
            kept.append(target)
        else:
            merged[target] = value
            added.append(target)
    return merged, added, kept
