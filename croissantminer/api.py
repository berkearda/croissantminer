"""Python API: extract the 30 Croissant fields from one paper with one of the paper's systems."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .croissant import ALL_FIELDS, CORE_FIELDS, RAI_FIELDS, is_filled, to_croissant

# Names used by the command line and the API -> systems of the paper's Table 2
METHOD_NAMES = {
    "single-pass": "single_sonnet",
    "single-pass-gpt": "single_gpt",
    "react": "react",
    "parallel-specialists": "specialists",
    "triage-critique": "triage_critique",
    "locator-extractor": "locator_extractor",
}
KEY_VARIABLES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


class MissingKey(ValueError):
    """No API key for the method's provider."""


@dataclass
class Extraction:
    method: str                                          # e.g. "single-pass"
    fields: dict                                         # the 30 fields, None where not found
    croissant: dict                                      # Croissant 1.1 JSON-LD
    evidence: dict = field(default_factory=dict)         # field -> supporting quote (some methods)
    null_reasons: dict = field(default_factory=dict)     # field -> why it was left empty (ReAct)
    cost_usd: float | None = None
    elapsed_s: float = 0.0

    def found(self, fields=None) -> int:
        """Number of fields with a value (all 30 by default)."""
        return sum(is_filled(self.fields.get(k)) for k in (fields or ALL_FIELDS))

    @property
    def missing(self) -> list[str]:
        return [k for k in ALL_FIELDS if not is_filled(self.fields.get(k))]

    def summary(self) -> str:
        core = self.found([k for k, _ in CORE_FIELDS])
        rai = self.found([k for k, _ in RAI_FIELDS])
        return (f"Found {self.found()} of {len(ALL_FIELDS)} fields "
                f"(core {core} of {len(CORE_FIELDS)}, Responsible AI {rai} of {len(RAI_FIELDS)})")


def read_paper(paper: str | Path) -> str:
    """Text of a paper. A PDF goes through the benchmark's preprocessing (PyPDF2 and
    cleaning); a text or Markdown file is read as it is."""
    path = Path(paper)
    if path.suffix.lower() == ".pdf":
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {path}")
        from . import methods
        return methods.paper_text_from_pdf(str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def api_key_for(method: str) -> str:
    """The provider key for a method, from the environment or a .env file."""
    from . import methods
    provider = methods.METHODS_BY_KEY[METHOD_NAMES[method]].provider
    variable = KEY_VARIABLES[provider]
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True))  # .env in the working directory; set variables win
    except ImportError:
        pass
    key = os.environ.get(variable, "").strip()
    if not key:
        raise MissingKey(f"{method} needs {variable}: set it in your environment or in a .env file")
    return key


def extract(paper: str | Path, method: str = "single-pass", *, text: str | None = None,
            api_key: str | None = None, hf_dataset_id: str | None = None,
            dataset_card: str | Path | None = None) -> Extraction:
    """Extract the 30 Croissant fields from a paper and build its Croissant file.

    paper          path to the paper (PDF, text or Markdown); ignored when `text` is given
    method         one of METHOD_NAMES; "single-pass" is the best system in the paper
    api_key        provider key; by default ANTHROPIC_API_KEY or OPENAI_API_KEY
    hf_dataset_id  "org/name" on Hugging Face; lets the agentic methods check the license and URL
    dataset_card   dataset card or README (path or text), appended to the paper text
    """
    if method not in METHOD_NAMES:
        raise ValueError(f"Unknown method {method!r}; choose one of: {', '.join(METHOD_NAMES)}")
    from . import methods
    paper_text = text if text is not None else read_paper(paper)
    if not paper_text.strip():
        raise ValueError("The paper has no text (a scanned PDF needs OCR first)")
    if dataset_card:
        card = Path(dataset_card)
        card_text = card.read_text(encoding="utf-8", errors="replace") if card.is_file() else str(dataset_card)
        paper_text = paper_text.strip() + "\n\n--- DATASET CARD ---\n\n" + card_text.strip()
    key = api_key or api_key_for(method)
    label = methods.METHODS_BY_KEY[METHOD_NAMES[method]].label
    result = methods.run(label, paper_text, key, hf_dataset_id)
    fields = {k: result.fields.get(k) for k in ALL_FIELDS}
    return Extraction(method=method, fields=fields, croissant=to_croissant(fields, hf_dataset_id or ""),
                      evidence=result.evidence or {}, null_reasons=result.null_reasons or {},
                      cost_usd=result.cost_usd, elapsed_s=result.elapsed_s)
