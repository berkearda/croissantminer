"""Command line and Python API of the extraction tool. No API calls; runs with the light install."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

HEAVY = ("pandas", "numpy", "scipy", "sklearn", "matplotlib", "anthropic", "openai")


def run_cli(*args, cwd=REPO):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(REPO), "HOME": os.environ.get("HOME", "")}
    return subprocess.run([sys.executable, "-m", "croissantminer", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def test_import_is_light():
    code = f"import croissantminer, sys; print([m for m in {HEAVY!r} if m in sys.modules])"
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True).stdout
    assert out.strip() == "[]"


def test_version():
    import croissantminer
    assert run_cli("--version").stdout.strip() == f"croissantminer {croissantminer.__version__}"


def test_methods_lists_the_six_systems_with_their_scores():
    out = run_cli("methods").stdout
    for name, score in [("single-pass", "0.709"), ("single-pass-gpt", "0.665"), ("react", "0.652"),
                        ("parallel-specialists", "0.647"), ("triage-critique", "0.624"),
                        ("locator-extractor", "0.566")]:
        line = next(l for l in out.splitlines() if l.startswith(name + " "))
        assert score in line


def test_extract_without_a_key_says_which_one(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text("Title: A toy dataset\nWe collected 100 images.")
    r = run_cli("extract", str(paper), cwd=tmp_path)          # no .env in tmp_path, no key in env
    assert r.returncode == 1 and "needs ANTHROPIC_API_KEY" in r.stderr
    assert not (tmp_path / "paper.croissant.json").exists()


def test_extract_reports_a_missing_file(tmp_path):
    r = run_cli("extract", "no_such_paper.pdf", cwd=tmp_path)
    assert r.returncode == 1 and "no such file" in r.stderr


def test_unknown_method_is_rejected(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text("text")
    r = run_cli("extract", str(paper), "--method", "magic", cwd=tmp_path)
    assert r.returncode == 1 and "unknown method" in r.stderr


def test_single_pass_end_to_end_with_a_stubbed_model(monkeypatch):
    """The API path of the default method, with the model call replaced by a fixed answer."""
    from croissantminer import api, methods
    import _agentic_helpers as helpers   # importable once croissantminer.methods is loaded
    answer = {"name": "Toy Images", "publisher": "OpenAI", "datePublished": 2021, "license": "CC BY 4.0",
              "rai:dataCollection": "Crowdsourced on a web platform.", "rai:dataBiases": "not specified"}
    seen = {}

    def fake_call(cfg, system_prompt, user_content, max_tokens):
        seen["model"], seen["prompt"] = cfg["model_id"], system_prompt
        return json.dumps(answer), {"input_tokens": 1000, "output_tokens": 200}

    monkeypatch.setattr(methods, "_check_key", lambda provider, key: None)
    monkeypatch.setattr(helpers, "call_llm", fake_call)
    result = api.extract(None, text="Title: Toy Images\nA dataset of toy images.", api_key="test-key")
    from croissantminer.config import SYSTEM_PROMPT
    assert seen["prompt"] == SYSTEM_PROMPT and seen["model"] == "claude-sonnet-4-6"
    assert result.fields["name"] == "Toy Images" and result.found() == 5   # "not specified" is not a value
    assert len(result.fields) == 30 and "rai:dataBiases" in result.missing
    c = result.croissant
    assert c["conformsTo"] == "http://mlcommons.org/croissant/1.1"
    assert c["publisher"] == {"@type": "Organization", "name": "OpenAI"} and c["datePublished"] == "2021"
    assert "rai:dataBiases" not in c and c["rai:dataCollection"].startswith("Crowdsourced")
