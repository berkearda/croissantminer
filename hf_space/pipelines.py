"""Run the paper's extraction systems on one uploaded paper.

Each method calls the same code and configuration as the corresponding row of
the paper's Table 2 (all on Claude Sonnet 4.6 unless noted):

  single-pass   canonical prompt, one call            (extract_all_models.py)
  ReAct         prompt variant v3                     (croissantminer/react_agent)
  Parallel Sp.  config "premium", prompt variant v4   (scripts/multi_agents)
  Triage+Crit.  prompt variant v4                     (scripts/agentic_v2.py)
  Locator-Ext.  Sonnet 4.6 locator, prompt variant v3 (scripts/agentic_lev.py)

The benchmark scripts look papers up by dataset id and read precomputed
section chunks / triage from data/agentic/. Here those loaders are pointed at
the uploaded paper instead:
  - section chunks come from agentic_phase0's detect_sections + chunk_text;
  - Triage + Critique's triage comes from the Locator-Extractor locator prompt
    run with Sonnet 4.6 (the paper's run used precomputed Gemini 2.5 Flash
    triage), so the whole method needs only an Anthropic key.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import time
import types
from argparse import Namespace
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
for _p in (REPO_ROOT, SCRIPTS, SCRIPTS / "multi_agents"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Register these packages without running their __init__.py, which import
# scipy/scikit-learn/numpy (not installed in the Space). Only light submodules
# are used: croissantminer.react_agent and evaluation.field_metrics.
for _name in ("croissantminer", "evaluation"):
    if _name not in sys.modules:
        _pkg = types.ModuleType(_name)
        _pkg.__path__ = [str(REPO_ROOT / _name)]
        sys.modules[_name] = _pkg

BACKBONE = "sonnet-4-6"
UPLOAD_ID = "uploaded_paper"

# The benchmark code reads API keys from the environment and patches module
# globals, so runs are serialised; one user's key is never visible to another.
_RUN_LOCK = threading.Lock()


@dataclass
class Method:
    key: str
    label: str
    architecture: str
    paper_score: float          # Table 2 composite on the 88-paper test split
    provider: str               # which API key the user must supply
    summary: str
    typical: str                # rough wall-clock time


METHODS = [
    Method("single_sonnet", "Single-pass · Claude Sonnet 4.6", "Single-pass", 0.709, "anthropic",
           "One model call over the full paper text. Best system in the paper.",
           "about 30\u00a0s"),
    Method("single_gpt", "Single-pass · GPT-5.4", "Single-pass", 0.665, "openai",
           "The same single call, with OpenAI GPT-5.4.",
           "about 30\u00a0s"),
    Method("react", "ReAct · Claude Sonnet 4.6", "ReAct", 0.652, "anthropic",
           "An agent that searches the paper, checks Hugging Face, license names and URLs, "
           "and gives a reason for every field it leaves empty.",
           "1 to 2\u00a0min"),
    Method("specialists", "Parallel Specialists · Claude Sonnet 4.6", "Parallel Specialists", 0.647,
           "anthropic",
           "Five calls (core, collection, annotation, impact, processing) each read the full "
           "paper for their own fields; a last pass checks and corrects the answers.",
           "about 1\u00a0min"),
    Method("triage_critique", "Triage + Critique · Claude Sonnet 4.6", "Triage + Critique", 0.624,
           "anthropic",
           "A first call guesses which field groups the paper covers; one call extracts all "
           "fields with supporting quotes; a review call checks the missing fields; values "
           "without a quote are removed.",
           "about 1\u00a0min"),
    Method("locator_extractor", "Locator-Extractor · Claude Sonnet 4.6", "Locator-Extractor", 0.566,
           "anthropic",
           "A first call finds the relevant sections for each field group; five calls then read "
           "only those sections and quote their evidence.",
           "about 1\u00a0min"),
]
METHODS_BY_LABEL = {m.label: m for m in METHODS}


@dataclass
class RunResult:
    fields: dict
    evidence: dict = field(default_factory=dict)      # field -> supporting quote
    null_reasons: dict = field(default_factory=dict)  # field -> why left empty
    cost_usd: float | None = None
    elapsed_s: float = 0.0


def _load_definitions(path: Path, wanted: set) -> dict:
    """Load selected top-level definitions from a source file without running
    the rest of the module (agentic_phase0 reads benchmark data at import;
    croissantminer.pdf.processor imports scikit-learn)."""
    nodes = [
        n for n in ast.parse(path.read_text()).body
        if (isinstance(n, ast.FunctionDef) and n.name in wanted)
        or (isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets))
    ]
    ns: dict = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


_PHASE0 = _load_definitions(SCRIPTS / "agentic_phase0.py",
                            {"KNOWN_SECTIONS", "detect_sections", "estimate_tokens", "chunk_text"})
_CLEAN_TEXT = _load_definitions(REPO_ROOT / "croissantminer" / "pdf" / "processor.py",
                                {"clean_text"})["clean_text"]


def paper_text_from_pdf(pdf_path: str) -> str:
    """The benchmark's preprocessing (_agentic_helpers.get_paper_text):
    PyPDF2 text extraction, clean_text, UTF-8 sanitising."""
    spec = importlib.util.spec_from_file_location(
        "_cm_pdf_reader", REPO_ROOT / "croissantminer" / "pdf" / "reader.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    from _agentic_helpers import sanitize_utf8
    return sanitize_utf8(_CLEAN_TEXT(reader.extract_text_from_pdf(pdf_path)))


def _section_text(paper_text: str) -> dict[str, str]:
    """Same structure agentic_lev.load_section_text() builds from Phase 0 files."""
    sections = _PHASE0["detect_sections"](paper_text)
    out: defaultdict[str, str] = defaultdict(str)
    for chunk in _PHASE0["chunk_text"](paper_text, sections):
        name = str(chunk.get("section", "unknown")).strip().upper()
        if name and chunk.get("text"):
            out[name] += " " + chunk["text"]
    return dict(out)


def _dataset_id(hf_dataset_id: str | None) -> str:
    # Benchmark ids are "org_name"; the pipelines turn them back into "org/name"
    # for the Hugging Face lookup. Without an id that lookup finds nothing.
    hf = (hf_dataset_id or "").strip().strip("/")
    if hf.startswith("https://huggingface.co/datasets/"):
        hf = hf.split("/datasets/", 1)[1]
    return hf.replace("/", "_", 1) if "/" in hf else UPLOAD_ID


class _patched:
    """Temporarily replace module attributes and environment variables."""

    def __init__(self, env: dict, attrs: list):
        self.env, self.attrs, self.saved_env, self.saved_attrs = env, attrs, {}, []

    def __enter__(self):
        for k, v in self.env.items():
            self.saved_env[k] = os.environ.get(k)
            os.environ[k] = v
        for obj, name, value in self.attrs:
            self.saved_attrs.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)
        return self

    def __exit__(self, *exc):
        for obj, name, value in reversed(self.saved_attrs):
            setattr(obj, name, value)
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _read_payload(out_dir: Path, ds_id: str) -> dict:
    return json.loads((out_dir / f"{ds_id.replace('/', '__')}.json").read_text())


def _evidence_from(payload: dict) -> dict:
    details = payload.get("_meta", {}).get("extraction_details", {}) or {}
    return {f: d.get("evidence") for f, d in details.items() if d.get("evidence")}


# ── Methods ─────────────────────────────────────────────────────────────────
def _single_pass(text: str, backbone: str) -> RunResult:
    from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
    from _agentic_helpers import (call_llm, estimate_cost, fill_canonical,
                                  normalize_field_names, parse_json_response, resolve_backbone)
    cfg = resolve_backbone(backbone)
    raw, usage = call_llm(cfg, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE % text, 8192)
    fields = fill_canonical(normalize_field_names(parse_json_response(raw)))
    return RunResult(fields, cost_usd=estimate_cost(cfg, usage))


def _react(text: str, api_key: str, ds_id: str) -> RunResult:
    import anthropic
    from croissantminer.react_agent.agent import run_agent
    from croissantminer.react_agent.schemas import coerce_nulls
    from _agentic_helpers import resolve_backbone
    result = run_agent(
        paper_text=text,
        client=anthropic.Anthropic(api_key=api_key),
        dataset_id=None if ds_id == UPLOAD_ID else ds_id,
        max_turns=20,
        trace=False,
        model_id=resolve_backbone(BACKBONE)["model_id"],
        backbone_key=BACKBONE,
        prompt_variant="v3",
    )
    return RunResult(coerce_nulls(dict(result.extracted)),
                     null_reasons=dict(result.null_reasons),
                     cost_usd=result.meta.get("cost_usd"))


def _specialists(text: str) -> RunResult:
    from agents import ALL_FIELDS, build_specialists, simple_merge
    from _agentic_helpers import estimate_cost, resolve_backbone
    specialists = build_specialists("premium", "v4")
    # The five specialists are independent calls; run them concurrently.
    with ThreadPoolExecutor(max_workers=len(specialists)) as pool:
        first = list(pool.map(lambda a: a.run(text), specialists))
        second = list(pool.map(lambda ar: ar[0].verify_correct(text, ar[1][0]),
                               zip(specialists, first)))
    merged = simple_merge({a.name: out for a, (out, _) in zip(specialists, second)})
    usage = {"input_tokens": 0, "output_tokens": 0}
    for _, u in first + second:
        usage["input_tokens"] += u["input_tokens"]
        usage["output_tokens"] += u["output_tokens"]
    if usage["input_tokens"] == 0:
        # agents.py turns failed calls into empty fields; don't show that as a result
        raise RuntimeError("all specialist calls failed")
    fields = {f: merged.get(f) for f in ALL_FIELDS}
    return RunResult(fields, cost_usd=estimate_cost(resolve_backbone(BACKBONE), usage))


def _triage_critique(text: str, ds_id: str) -> RunResult:
    import agentic_v2 as v2
    import agentic_lev as lev
    from _agentic_helpers import resolve_backbone
    cfg = resolve_backbone(BACKBONE)
    sections = _section_text(text)
    with _patched({}, [(lev, "load_section_text", lambda _id: sections)]):
        triage, _ = lev.locate_with_llm(cfg, ds_id, text)
    args = Namespace(no_verification=False, no_correction=False, no_enrichment=False,
                     prompt_variant="v4")
    with tempfile.TemporaryDirectory() as tmp, _patched({}, [
        (v2, "get_paper_text", lambda _id: text),
        (v2, "load_triage", lambda _id: triage),
    ]):
        v2.process_paper(cfg, ds_id, args, Path(tmp))
        payload = _read_payload(Path(tmp), ds_id)
    return RunResult(payload["extraction"], evidence=_evidence_from(payload),
                     cost_usd=payload.get("_meta", {}).get("cost_usd"))


def _locator_extractor(text: str, ds_id: str) -> RunResult:
    import agentic_lev as lev
    from _agentic_helpers import resolve_backbone
    cfg = resolve_backbone(BACKBONE)
    sections = _section_text(text)
    with tempfile.TemporaryDirectory() as tmp, _patched({}, [
        (lev, "get_paper_text", lambda _id: text),
        (lev, "load_section_text", lambda _id: sections),
    ]):
        lev.process_paper(cfg, ds_id, Path(tmp), locator_cfg=cfg, prompt_variant="v3")
        payload = _read_payload(Path(tmp), ds_id)
    if not payload.get("usage", {}).get("output_tokens"):
        # agentic_lev turns failed extractor calls into empty groups
        raise RuntimeError("all extractor calls failed")
    return RunResult(payload["extraction"], evidence=_evidence_from(payload),
                     cost_usd=payload.get("_meta", {}).get("cost_usd"))


class InvalidKey(Exception):
    pass


def _check_key(provider: str, api_key: str) -> None:
    """Fail fast on a wrong key with a free models-list call. Several benchmark
    code paths turn API failures into empty fields instead of raising."""
    try:
        if provider == "openai":
            from openai import OpenAI
            OpenAI(api_key=api_key).models.list()
        else:
            import anthropic
            anthropic.Anthropic(api_key=api_key).models.list(limit=1)
    except Exception as e:
        if getattr(e, "status_code", None) in (401, 403) or "auth" in type(e).__name__.lower():
            raise InvalidKey(str(e)) from e
        raise


def run(method_label: str, paper_text: str, api_key: str,
        hf_dataset_id: str | None = None) -> RunResult:
    method = METHODS_BY_LABEL[method_label]
    from _agentic_helpers import sanitize_utf8
    text = sanitize_utf8(paper_text)
    ds_id = _dataset_id(hf_dataset_id)
    key_var = "OPENAI_API_KEY" if method.provider == "openai" else "ANTHROPIC_API_KEY"
    _check_key(method.provider, api_key.strip())
    t0 = time.time()
    with _RUN_LOCK, _patched({key_var: api_key.strip()}, []):
        if method.key == "single_sonnet":
            result = _single_pass(text, "sonnet-4-6")
        elif method.key == "single_gpt":
            result = _single_pass(text, "gpt-5.4")
        elif method.key == "react":
            result = _react(text, api_key.strip(), ds_id)
        elif method.key == "specialists":
            result = _specialists(text)
        elif method.key == "triage_critique":
            result = _triage_critique(text, ds_id)
        elif method.key == "locator_extractor":
            result = _locator_extractor(text, ds_id)
        else:
            raise ValueError(method.key)
    result.elapsed_s = time.time() - t0
    return result
