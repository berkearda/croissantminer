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


# A small host file in the shape data hosts generate: data files and columns, no RAI fields.
HOST = {
    "@context": {"@language": "en", "@vocab": "https://schema.org/", "sc": "https://schema.org/",
                 "cr": "http://mlcommons.org/croissant/", "dct": "http://purl.org/dc/terms/",
                 "citeAs": "cr:citeAs", "column": "cr:column", "conformsTo": "dct:conformsTo",
                 "data": {"@id": "cr:data", "@type": "@json"}, "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
                 "extract": "cr:extract", "field": "cr:field", "fileObject": "cr:fileObject",
                 "isLiveDataset": "cr:isLiveDataset", "recordSet": "cr:recordSet", "source": "cr:source"},
    "@type": "sc:Dataset", "conformsTo": "http://mlcommons.org/croissant/1.1",
    "name": "toy", "url": "https://example.org/toy", "license": "https://spdx.org/licenses/MIT.html",
    "creator": {"@type": "Organization", "name": "Toy Lab"},
    "distribution": [{"@type": "cr:FileObject", "@id": "data.csv", "name": "data.csv",
                      "contentUrl": "https://example.org/data.csv", "encodingFormat": "text/csv", "sha256": "0" * 64}],
    "recordSet": [{"@type": "cr:RecordSet", "@id": "rows", "name": "rows", "field": [
        {"@type": "cr:Field", "@id": "rows/text", "name": "text", "dataType": "sc:Text",
         "source": {"fileObject": {"@id": "data.csv"}, "extract": {"column": "text"}}}]}],
}


def test_merge_adds_fields_and_keeps_the_hosts_values():
    from croissantminer.croissant import merge
    merged, added, kept = merge(HOST, to_croissant(FIELDS, "openai/gsm8k"))
    assert merged["name"] == "toy" and merged["url"] == "https://example.org/toy"       # the host's values stay
    assert merged["creator"] == HOST["creator"] and {"name", "url", "creator"} <= set(kept)
    assert merged["rai:dataCollection"] == "Written by contractors." and merged["@context"]["rai"]
    assert merged["citeAs"] == "Cobbe et al. (2021)" and "cr:citeAs" not in merged     # written with the host's name
    assert merged["isLiveDataset"] is False and merged["datePublished"] == "2021-11"
    assert merged["distribution"] == HOST["distribution"] and merged["recordSet"] == HOST["recordSet"]
    assert "@id" not in merged and "rai" not in HOST["@context"]                         # the host is not modified


def test_merged_file_passes_mlcroissant():
    from croissantminer.croissant import merge
    try:
        import mlcroissant  # noqa: F401
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"mlcroissant unavailable: {e}")
    passed, messages = validate(merge(HOST, to_croissant(FIELDS))[0])
    assert passed, messages


def test_load_finds_the_hugging_face_file(monkeypatch, tmp_path):
    import json
    import requests
    from croissantminer import croissant
    urls = []

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"name": "x"}

    monkeypatch.setattr(requests, "get", lambda url, **kw: urls.append(url) or Response())
    for source in ("openai/gsm8k", "https://huggingface.co/datasets/openai/gsm8k", "https://huggingface.co/datasets/openai/gsm8k/tree/main"):
        assert croissant.load(source) == {"name": "x"}
    assert set(urls) == {"https://huggingface.co/api/datasets/openai/gsm8k/croissant"}
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"name": "local"}))
    assert croissant.load(str(path)) == {"name": "local"}
    with pytest.raises(ValueError):
        croissant.load("not a source")
