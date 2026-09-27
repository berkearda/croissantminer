"""Per-paper orchestration: PDF -> fitz text -> agent -> validate -> save."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import PyPDF2

from .agent import AgentResult, run_agent
from .audit import audit_extractions
from .schemas import coerce_nulls

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.validate_extraction import validate_extraction  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
EXTRACTIONS_DIR = ROOT / "data" / "extractions" / "agentic_react_sonnet_4_6"
TRACES_DIR = EXTRACTIONS_DIR / "_traces"
FAILURES_PATH = EXTRACTIONS_DIR / "_failures.json"
COST_LOG_PATH = EXTRACTIONS_DIR / "_cost_log.json"


_REF_HEADING_RE = re.compile(
    r"\n\s*(?:\d+\s*[.\s]*)?(references|bibliography)\s*\n",
    re.IGNORECASE,
)


_APPENDIX_HEADING_RE = re.compile(
    r"\n\s*(appendix|supplementary|supplemental|a\.?\s+[A-Z])",
    re.IGNORECASE,
)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF and strip only the references section itself.

    Handles the common "main text -> references -> appendix" layout: we locate
    the References heading and the NEXT appendix-style heading after it, and
    excise just the citations list in between. If no appendix follows, strip
    from References to EOF. If no References heading at all, return the full
    text unchanged.
    """
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        pages = [(page.extract_text() or "") for page in reader.pages]
    raw = "\n".join(pages)
    # PyPDF2 occasionally emits lone UTF-16 surrogates (especially on CJK
    # papers) that the Anthropic API rejects with UnicodeEncodeError.
    # Round-trip through utf-8 with errors="replace" drops them safely.
    raw = raw.encode("utf-8", errors="replace").decode("utf-8")
    raw = re.sub(r"\r\n?", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    matches = list(_REF_HEADING_RE.finditer(raw))
    if not matches:
        return raw.strip()

    # Use the FIRST occurrence of References (pre-appendix), not the last —
    # the appendix itself may cite more things and match again.
    ref_start = matches[0].start()
    # Guard: ignore a match that's implausibly early (<30% of the doc).
    if ref_start < 0.3 * len(raw):
        return raw.strip()

    # Is there an appendix after the References heading?
    tail = raw[ref_start:]
    app_match = _APPENDIX_HEADING_RE.search(tail, pos=80)  # skip the "References" line itself
    if app_match:
        # Drop just the references section; keep everything before + everything from appendix onwards.
        app_abs = ref_start + app_match.start()
        return (raw[:ref_start] + "\n\n" + raw[app_abs:]).strip()
    # No appendix — strip from References to EOF.
    return raw[:ref_start].strip()


def _save_trace(ds_id: str, trace: list[dict[str, Any]]) -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACES_DIR / f"{ds_id}.json", "w") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False, default=str)


def _append_cost_log(entry: dict[str, Any]) -> None:
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    if COST_LOG_PATH.exists():
        log = json.loads(COST_LOG_PATH.read_text())
    else:
        log = {"entries": [], "totals": {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "papers": 0}}
    log["entries"].append(entry)
    log["totals"]["cost_usd"] = round(log["totals"]["cost_usd"] + entry.get("cost_usd", 0.0), 4)
    log["totals"]["input_tokens"] += entry.get("total_input_tokens", 0)
    log["totals"]["output_tokens"] += entry.get("total_output_tokens", 0)
    log["totals"]["papers"] += 1
    COST_LOG_PATH.write_text(json.dumps(log, indent=2))


def _append_failure(ds_id: str, reason: str, details: Any = None) -> None:
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    failures = json.loads(FAILURES_PATH.read_text()) if FAILURES_PATH.exists() else []
    failures.append({
        "ds_id": ds_id,
        "reason": reason,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    FAILURES_PATH.write_text(json.dumps(failures, indent=2, default=str))


def extract_paper(
    ds_id: str,
    *,
    client: anthropic.Anthropic | None = None,
    max_turns: int = 20,
    save_trace: bool = False,
    overwrite: bool = False,
) -> dict[str, Any] | None:
    """Run the ReAct agent on one paper and save the extraction.

    Returns the saved extraction dict, or None on validation / runtime failure.
    """
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTIONS_DIR / f"{ds_id}.json"
    if out_path.exists() and not overwrite:
        return json.loads(out_path.read_text())

    pdf_path = RAW_DIR / f"{ds_id}.pdf"
    if not pdf_path.exists():
        _append_failure(ds_id, "pdf_missing", str(pdf_path))
        return None

    try:
        paper_text = extract_pdf_text(pdf_path)
    except Exception as e:
        _append_failure(ds_id, "pdf_extract_failed", f"{type(e).__name__}: {e}")
        return None

    if not paper_text or len(paper_text) < 500:
        _append_failure(ds_id, "pdf_text_too_short", {"len": len(paper_text)})
        return None

    if client is None:
        client = anthropic.Anthropic()

    t0 = time.time()
    try:
        result: AgentResult = run_agent(
            paper_text=paper_text,
            client=client,
            dataset_id=ds_id,
            max_turns=max_turns,
            trace=True,
        )
    except Exception as e:
        _append_failure(ds_id, "agent_raised", f"{type(e).__name__}: {e}")
        return None
    elapsed = time.time() - t0

    # Per-field LLM audit pass: each non-null RAI field is reviewed in isolation
    # by a separate Haiku call that sees only (field, value, evidence_quote).
    # The auditor either KEEPs the value or NULLs it.
    audit = audit_extractions(
        extracted=result.extracted,
        evidence=result.evidence,
        client=client,
        rai_only=True,
    )
    final_null_reasons = dict(result.null_reasons)
    final_extracted = dict(result.extracted)  # all 30 keys, None for un-set
    for f, decision in audit.decisions.items():
        if decision == "null":
            final_extracted[f] = None  # keep the key, blank the value
            final_null_reasons[f] = audit.null_reasons.get(f, "audit: not supported")

    # Post-process: coerce string-nulls → None.
    extraction = coerce_nulls(final_extracted)

    # Build the saved payload: 30 fields + _meta.
    payload = dict(extraction)
    payload["_meta"] = {
        **result.meta,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(elapsed, 2),
        "pdf_chars": len(paper_text),
        "null_reasons": final_null_reasons,
        "evidence": result.evidence,
        "audit": {
            "decisions": audit.decisions,
            "n_calls": audit.n_calls,
            "input_tokens": audit.input_tokens,
            "output_tokens": audit.output_tokens,
            "cost_usd": audit.cost_usd,
        },
    }

    # Validate (use the stripped 30-field dict, not the one with _meta).
    ok, errors = validate_extraction(extraction, ds_id)
    if not ok:
        _append_failure(ds_id, "schema_invalid", errors)
        # Still save the payload under a .invalid suffix so we can debug.
        bad_path = EXTRACTIONS_DIR / f"{ds_id}.invalid.json"
        bad_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return None

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))

    if save_trace:
        _save_trace(ds_id, result.trace)

    _append_cost_log({
        "ds_id": ds_id,
        "timestamp": payload["_meta"]["timestamp"],
        "elapsed_sec": payload["_meta"]["elapsed_sec"],
        "num_turns": result.meta["num_turns"],
        "num_tool_calls": result.meta["num_tool_calls"],
        "tool_call_counts": result.meta["tool_call_counts"],
        "total_input_tokens": result.meta["total_input_tokens"],
        "total_output_tokens": result.meta["total_output_tokens"],
        "cost_usd": result.meta["cost_usd"],
        "fields_decided": result.meta["fields_decided"],
    })

    return payload
