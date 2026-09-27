"""Tool implementations for the ReAct agent.

Each tool has:
  - a JSON schema (Anthropic tool_use format) exposed via TOOL_SCHEMAS
  - a handler function (state, **kwargs) -> dict  called by the agent loop

State is a ToolState dataclass passed around per-paper to carry paper text,
extracted fields, and call stats.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests

from .schemas import CANONICAL_FIELDS, FIELD_DEFINITIONS


# ═══════════════════════════════════════════════════════════════════════
# Per-paper state
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ToolState:
    paper_text: str
    paragraphs: list[str] = field(default_factory=list)
    paper_word_grams: set = field(default_factory=set)  # 5-grams for evidence validation
    extracted: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)  # field -> supporting paper quote
    null_reasons: dict[str, str] = field(default_factory=dict)
    read_full_paper_called: bool = False
    tool_call_counts: Counter = field(default_factory=Counter)

    def fields_decided(self) -> set[str]:
        return set(self.extracted) | set(self.null_reasons)

    def progress(self) -> str:
        return f"{len(self.fields_decided())}/30 fields decided"


# ═══════════════════════════════════════════════════════════════════════
# Paragraph indexing (for search_paper)
# ═══════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]+")


def split_paragraphs(text: str, min_len: int = 60) -> list[str]:
    paras = re.split(r"\n\s*\n+", text)
    out = []
    for p in paras:
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= min_len:
            out.append(p)
    return out


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


def tfidf_top_k(query: str, paragraphs: list[str], k: int = 3) -> list[tuple[int, float, str]]:
    """Rank paragraphs by TF-IDF cosine similarity to the query. Pure stdlib."""
    if not paragraphs:
        return []
    docs = [_tokenize(p) for p in paragraphs]
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    N = len(docs)
    df = Counter()
    for doc in docs:
        for t in set(doc):
            df[t] += 1
    idf = {t: math.log((N + 1) / (df_t + 1)) + 1 for t, df_t in df.items()}

    def vec(tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        return {t: (c / len(tokens)) * idf.get(t, math.log(N + 1) + 1) for t, c in tf.items()}

    def cos(a: dict, b: dict) -> float:
        common = set(a) & set(b)
        num = sum(a[t] * b[t] for t in common)
        da = math.sqrt(sum(v * v for v in a.values()))
        db = math.sqrt(sum(v * v for v in b.values()))
        return num / (da * db) if da and db else 0.0

    qv = vec(q_tokens)
    scored = [(i, cos(qv, vec(d))) for i, d in enumerate(docs)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(i, s, paragraphs[i]) for i, s in scored[:k] if s > 0]


# ═══════════════════════════════════════════════════════════════════════
# Tool schemas (Anthropic tool_use JSON)
# ═══════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_full_paper",
        "description": (
            "Return the full cleaned text of the paper (references section stripped). "
            "Call this once at the start to get the overall context. Subsequent calls "
            "return a note saying the text is already in context."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_paper",
        "description": (
            "Search the paper for a natural-language query and return the top 3 most "
            "relevant paragraphs (ranked by TF-IDF). Use this to find sections discussing "
            "a specific field (e.g., 'annotation platform', 'license terms', 'data biases')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (keywords or phrase)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "extract_field",
        "description": (
            "Store an extracted value for one of the 30 Croissant metadata fields, "
            "ALONG WITH the verbatim paper text that supports it. The supporting "
            "quote is validated against the paper at call time — fabricated quotes "
            "are rejected. If you cannot point to real paper text, use mark_null."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "Field name — must be one of the 30 canonical Croissant fields.",
                    "enum": sorted(CANONICAL_FIELDS),
                },
                "value": {
                    "description": "Extracted value (string, or list/dict for structured fields). "
                                   "Never pass 'null' / 'N/A' / '' as a string — use mark_null instead.",
                },
                "evidence_quote": {
                    "type": "string",
                    "description": (
                        "Verbatim 1-3 sentences from the paper that support the value. "
                        "Must contain at least 5 consecutive words present in the paper "
                        "(case-insensitive). The tool stores this alongside value and "
                        "rejects extractions where no real paper text is quoted."
                    ),
                },
            },
            "required": ["field", "value", "evidence_quote"],
        },
    },
    {
        "name": "mark_null",
        "description": (
            "Mark a field as genuinely absent from the paper. Use this when you have "
            "searched and confirmed the information is not present or not applicable. "
            "Do NOT mark null just because you haven't looked — search first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": sorted(CANONICAL_FIELDS),
                },
                "reason": {
                    "type": "string",
                    "description": "Short reason (e.g., 'no license discussed in paper').",
                },
            },
            "required": ["field", "reason"],
        },
    },
    {
        "name": "search_huggingface",
        "description": (
            "Look up a dataset on HuggingFace Hub by name. Returns metadata including "
            "license, downloads, tags, and a subset of cardData. Useful when the paper "
            "doesn't state the license / URL / publisher explicitly. Returns an error "
            "string if the dataset is not found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "HuggingFace dataset id, e.g., 'squad', 'allenai/sciq', 'cais/mmlu'.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "verify_url",
        "description": (
            "Verify that a URL is reachable. Returns the final URL (after redirects) "
            "and HTTP status. Use after extracting a `url` field to confirm it's live. "
            "Timeout 8s; uses HEAD then falls back to GET if HEAD is rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "lookup_spdx",
        "description": (
            "Normalize a license string to its SPDX identifier. Pass the raw license text "
            "from the paper (e.g., 'Creative Commons Attribution 4.0') and get back the "
            "SPDX id (e.g., 'CC-BY-4.0'). Returns null if no match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Tool handlers
# ═══════════════════════════════════════════════════════════════════════


# Cap what read_full_paper returns so we stay well under the 200K-token context
# limit for Claude Sonnet 4.5. search_paper still indexes the full paper_text,
# so no information is lost — the agent just has to use search_paper for anything
# past the truncation point.
MAX_PAPER_CHARS_IN_CONTEXT = 200_000  # ITER 5 / FREEZE — 200K is the empirical sweet spot. Iter 6 (800K) → 0.622 mean (-0.06); iter 7 (800K + section filter) → 0.649; iter 8 (400K) → 0.641. The cap forces the agent's attention onto the dataset-relevant first ~50K tokens; the 10/102 papers that exceed 200K still extract well via search_paper for the truncated tail.


def _h_read_full_paper(state: ToolState) -> dict:
    if state.read_full_paper_called:
        return {
            "note": "Paper text already returned in an earlier turn — it is in your context. "
                    "Use search_paper for targeted lookups.",
            "length_chars": len(state.paper_text),
        }
    state.read_full_paper_called = True
    full_len = len(state.paper_text)
    if full_len <= MAX_PAPER_CHARS_IN_CONTEXT:
        return {"paper_text": state.paper_text, "length_chars": full_len}
    truncated = state.paper_text[:MAX_PAPER_CHARS_IN_CONTEXT]
    return {
        "paper_text": truncated,
        "length_chars": full_len,
        "truncated_to_chars": MAX_PAPER_CHARS_IN_CONTEXT,
        "note": (
            f"The paper is {full_len} chars; only the first {MAX_PAPER_CHARS_IN_CONTEXT} chars "
            "are returned here to fit the context window. The rest (appendix, supplementary) "
            "is still indexed for search_paper — use it for anything you cannot find above."
        ),
    }


def _h_search_paper(state: ToolState, query: str) -> dict:
    if not state.paragraphs:
        state.paragraphs = split_paragraphs(state.paper_text)
    hits = tfidf_top_k(query, state.paragraphs, k=3)
    if not hits:
        return {"query": query, "results": [], "note": "No matching paragraphs."}
    return {
        "query": query,
        "results": [
            {"rank": r + 1, "score": round(s, 3), "paragraph": para}
            for r, (_, s, para) in enumerate(hits)
        ],
    }


EVIDENCE_NGRAM = 5  # 5-word window for verbatim evidence-quote validation


def _evidence_ngrams(text: str, n: int = EVIDENCE_NGRAM) -> set[tuple[str, ...]]:
    """Build all n-grams of normalized lowercase word tokens for verbatim matching."""
    toks = _tokenize(text)
    if len(toks) < n:
        return set()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _quote_in_paper(quote: str, state: ToolState) -> bool:
    """True if at least one EVIDENCE_NGRAM-word run of the quote appears verbatim in the paper.

    Lowercases and tokenizes both, so it tolerates whitespace/punctuation
    differences from PDF parsing artifacts but rejects fabricated text.
    """
    if not state.paper_word_grams:
        state.paper_word_grams = _evidence_ngrams(state.paper_text)
    quote_grams = _evidence_ngrams(quote)
    if not quote_grams:
        return False
    return bool(quote_grams & state.paper_word_grams)


def _h_extract_field(state: ToolState, field: str, value: Any, evidence_quote: str = "") -> dict:
    if field not in CANONICAL_FIELDS:
        return {"error": f"Unknown field '{field}'. Must be one of the 30 canonical fields."}
    if not evidence_quote or not str(evidence_quote).strip():
        return {
            "error": (
                f"extract_field for '{field}' requires evidence_quote — paste 1-3 "
                f"verbatim sentences from the paper that support the value. "
                f"If no supporting text exists, use mark_null instead."
            )
        }
    if not _quote_in_paper(str(evidence_quote), state):
        return {
            "error": (
                f"evidence_quote for '{field}' does not appear verbatim in the paper "
                f"(no {EVIDENCE_NGRAM}-word run matches). Either paste a real "
                f"~{EVIDENCE_NGRAM}+ word phrase from the paper, or call mark_null "
                f"if no supporting text exists."
            )
        }
    overwrote = False
    if field in state.fields_decided():
        overwrote = True
    state.extracted[field] = value
    state.evidence[field] = str(evidence_quote)[:600]
    state.null_reasons.pop(field, None)
    return {
        "ok": True,
        "field": field,
        "overwrote": overwrote,
        "progress": state.progress(),
    }


def _h_mark_null(state: ToolState, field: str, reason: str) -> dict:
    if field not in CANONICAL_FIELDS:
        return {"error": f"Unknown field '{field}'. Must be one of the 30 canonical fields."}
    state.null_reasons[field] = reason
    state.extracted.pop(field, None)
    return {"ok": True, "field": field, "marked_null": True, "progress": state.progress()}


_HF_API = "https://huggingface.co/api/datasets/{name}"


def _h_search_huggingface(state: ToolState, name: str) -> dict:
    try:
        r = requests.get(
            _HF_API.format(name=name),
            timeout=8,
            headers={"User-Agent": "croissantminer-react-agent/0.1"},
        )
        if r.status_code == 404:
            return {"error": f"Dataset '{name}' not found on HuggingFace Hub."}
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return {"error": f"HF API error: {e}"}

    card = data.get("cardData") or {}
    return {
        "id": data.get("id"),
        "author": data.get("author"),
        "license": card.get("license") or data.get("license"),
        "downloads": data.get("downloads"),
        "likes": data.get("likes"),
        "tags": data.get("tags", [])[:20],
        "language": card.get("language"),
        "task_categories": card.get("task_categories"),
        "pretty_name": card.get("pretty_name"),
    }


def _h_verify_url(state: ToolState, url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"error": f"Invalid URL scheme: {parsed.scheme or 'none'}"}
    headers = {"User-Agent": "croissantminer-react-agent/0.1"}
    try:
        r = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
        if r.status_code in (405, 403, 501):
            r = requests.get(url, headers=headers, timeout=8, allow_redirects=True, stream=True)
            r.close()
        return {"status": r.status_code, "final_url": r.url, "ok": 200 <= r.status_code < 400}
    except requests.RequestException as e:
        return {"error": str(e), "ok": False}


# Minimal SPDX table — covers the licenses that actually appear in ML dataset papers.
_SPDX_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("MIT", re.compile(r"\bmit license\b|\bmit\b", re.I)),
    ("Apache-2.0", re.compile(r"apache\s*(license)?\s*(v|version)?\s*2(\.0)?|apache-2", re.I)),
    ("BSD-3-Clause", re.compile(r"bsd[\s\-]*3[\s\-]*clause|new bsd|modified bsd", re.I)),
    ("BSD-2-Clause", re.compile(r"bsd[\s\-]*2[\s\-]*clause|simplified bsd", re.I)),
    ("GPL-3.0", re.compile(r"gpl[\s\-]*(v|version)?\s*3|gnu general public license.*3", re.I)),
    ("GPL-2.0", re.compile(r"gpl[\s\-]*(v|version)?\s*2|gnu general public license.*2", re.I)),
    ("LGPL-3.0", re.compile(r"lgpl[\s\-]*(v|version)?\s*3|lesser general public license.*3", re.I)),
    ("AGPL-3.0", re.compile(r"agpl[\s\-]*(v|version)?\s*3|affero.*3", re.I)),
    ("CC0-1.0", re.compile(r"cc0|creative commons zero|public domain dedication", re.I)),
    ("CC-BY-4.0", re.compile(r"cc[\s\-]*by[\s\-]*4(\.0)?|creative commons attribution(?!.*(share|noncommercial|noderiv)).*4", re.I)),
    ("CC-BY-SA-4.0", re.compile(r"cc[\s\-]*by[\s\-]*sa[\s\-]*4(\.0)?|attribution[\s\-]*sharealike\s*4", re.I)),
    ("CC-BY-NC-4.0", re.compile(r"cc[\s\-]*by[\s\-]*nc[\s\-]*4(\.0)?|attribution[\s\-]*noncommercial\s*4", re.I)),
    ("CC-BY-NC-SA-4.0", re.compile(r"cc[\s\-]*by[\s\-]*nc[\s\-]*sa[\s\-]*4(\.0)?", re.I)),
    ("CC-BY-ND-4.0", re.compile(r"cc[\s\-]*by[\s\-]*nd[\s\-]*4(\.0)?", re.I)),
    ("CC-BY-3.0", re.compile(r"cc[\s\-]*by[\s\-]*3(\.0)?", re.I)),
    ("ODbL-1.0", re.compile(r"open database license|odbl", re.I)),
    ("ODC-BY-1.0", re.compile(r"odc[\s\-]*by", re.I)),
    ("OpenRAIL", re.compile(r"openrail|responsible ai license", re.I)),
    ("Llama-2", re.compile(r"llama[\s\-]*2.*license|llama 2 community", re.I)),
    ("Llama-3", re.compile(r"llama[\s\-]*3.*license|llama 3 community", re.I)),
]


def _h_lookup_spdx(state: ToolState, text: str) -> dict:
    if not text:
        return {"spdx": None, "reason": "empty input"}
    for spdx, pat in _SPDX_PATTERNS:
        if pat.search(text):
            return {"spdx": spdx, "matched": pat.pattern}
    return {"spdx": None, "reason": "no match in local SPDX table"}


HANDLERS = {
    "read_full_paper": _h_read_full_paper,
    "search_paper": _h_search_paper,
    "extract_field": _h_extract_field,
    "mark_null": _h_mark_null,
    "search_huggingface": _h_search_huggingface,
    "verify_url": _h_verify_url,
    "lookup_spdx": _h_lookup_spdx,
}


def dispatch(state: ToolState, name: str, tool_input: dict) -> str:
    """Run a tool and return its output as a JSON string (for tool_result blocks)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool '{name}'."})
    state.tool_call_counts[name] += 1
    try:
        result = handler(state, **tool_input)
    except TypeError as e:
        return json.dumps({"error": f"Bad arguments to '{name}': {e}"})
    except Exception as e:
        return json.dumps({"error": f"Tool '{name}' raised {type(e).__name__}: {e}"})
    return json.dumps(result, ensure_ascii=False, default=str)
