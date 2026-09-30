"""Croissant 1.1 file built from extracted values (shared by the command line and the demo)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from croissantminer.croissant import ALL_FIELDS, to_croissant, validate  # noqa: E402

FIELDS = {"name": "GSM8K (Grade School Math 8K)", "description": "Grade school math word problems.",
          "url": "https://github.com/openai/grade-school-math", "creator": "Karl Cobbe, Vineet Kosaraju",
          "publisher": "OpenAI", "datePublished": "November 2021", "inLanguage": "English",
          "citeAs": "Cobbe et al. (2021)", "isLiveDataset": "false", "license": "not specified",
          "rai:dataCollection": "Written by contractors.", "rai:dataBiases": None}


def test_thirty_fields():
    assert len(ALL_FIELDS) == 30 and sum(f.startswith("rai:") for f in ALL_FIELDS) == 20


def test_values_become_schema_org_types():
    c = to_croissant(FIELDS, "openai/gsm8k")
    assert c["@id"] == "https://huggingface.co/datasets/openai/gsm8k"
    assert c["conformsTo"] == "http://mlcommons.org/croissant/1.1"
    assert c["publisher"] == {"@type": "Organization", "name": "OpenAI"}
    assert c["creator"] == [{"@type": "Person", "name": "Karl Cobbe"}, {"@type": "Person", "name": "Vineet Kosaraju"}]
    assert c["datePublished"] == "2021-11" and c["cr:isLiveDataset"] is False
    assert "license" not in c and "rai:dataBiases" not in c      # placeholders and empty values are left out


@pytest.mark.parametrize("value, expected", [(2021, "2021"), ("2021-11-18", "2021-11-18"), ("Nov 18, 2021", "2021-11-18"),
                                             ("2021 (arXiv v1)", "2021"), ("unknown date", None)])
def test_dates(value, expected):
    assert to_croissant({"name": "x", "datePublished": value}).get("datePublished") == expected


def test_file_passes_mlcroissant():
    try:
        import mlcroissant  # noqa: F401
    except Exception as e:  # noqa: BLE001 - not installed, or not loadable on this Python version
        pytest.skip(f"mlcroissant unavailable: {e}")
    passed, messages = validate(to_croissant(FIELDS, "openai/gsm8k"))
    assert passed, messages
    passed, _ = validate({"@type": "sc:Dataset", "name": "x"})
    assert passed is False
