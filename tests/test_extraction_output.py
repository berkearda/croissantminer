"""Post-processing of model output shared by all extraction systems
(scripts/_agentic_helpers.py). No API calls."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import _agentic_helpers as h  # noqa: E402
from validation.validate_extraction import CANONICAL_FIELDS  # noqa: E402


def test_canonical_prompt_is_the_one_used_in_the_paper():
    # Every released output records this prefix in its _meta block.
    assert h.PROMPT_HASH == "1e1cfdd99246bbf5"


def test_thirty_canonical_fields():
    assert len(CANONICAL_FIELDS) == 30
    assert sum(f.startswith("rai:") for f in CANONICAL_FIELDS) == 20


@pytest.mark.parametrize("raw", [
    '{"license": "MIT"}',
    'Here is the metadata:\n```json\n{"license": "MIT"}\n```',
    '```\n{"license": "MIT"}\n```',
    'Sure. {"license": "MIT"} Hope this helps.',
    '{"license": "M\x01IT"}',  # stray control character
])
def test_parse_json_response(raw):
    assert h.parse_json_response(raw) == {"license": "MIT"}


def test_prefixes_stripped_from_core_fields_only():
    out = h.normalize_field_names({"sc:license": "MIT", "cr:citeAs": "x", "rai:dataBiases": "y"})
    assert out == {"license": "MIT", "citeAs": "x", "rai:dataBiases": "y"}


def test_fill_canonical_adds_missing_fields_as_null():
    out = h.fill_canonical({"license": "MIT"})
    assert set(out) == set(CANONICAL_FIELDS)
    assert out["license"] == "MIT"
    assert all(v is None for k, v in out.items() if k != "license")


def test_filled_output_passes_validation():
    ok, errors = h.validate_extraction(h.fill_canonical({"license": "MIT"}))
    assert ok, errors


class _StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"Error code: {status_code}")
        self.status_code = status_code


@pytest.mark.parametrize("status, calls", [(529, 3), (500, 3), (400, 1)])
def test_call_llm_retries_server_errors_only(monkeypatch, status, calls):
    # SDK errors carry an integer status_code: retry 5xx, raise the rest at once.
    seen = []

    def fail(*args):
        seen.append(1)
        raise _StatusError(status)

    monkeypatch.setattr(h, "_call_anthropic", fail)
    monkeypatch.setattr(h.time, "sleep", lambda s: None)
    with pytest.raises(_StatusError):
        h.call_llm({"provider": "anthropic"}, "system", "user")
    assert len(seen) == calls


def test_triage_critique_uses_the_scorers_field_list():
    # The package keeps a copy of LONG_TEXT_RAI_FIELDS so that it does not need the scorer (evaluation/).
    import importlib.util
    spec = importlib.util.spec_from_file_location("field_metrics", REPO / "evaluation" / "field_metrics.py")
    field_metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(field_metrics)
    from croissantminer.systems import triage_critique
    assert triage_critique.LONG_TEXT_RAI_FIELDS == field_metrics.LONG_TEXT_RAI_FIELDS
