"""The leaderboard website is built from leaderboard/leaderboard.csv and shows every row. No network."""
import importlib.util
import json
import re
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("build_site", REPO / "scripts/build_site.py")
    site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site)
    return site, site.build(tmp_path / "site").read_text(encoding="utf-8")


def test_every_leaderboard_row_is_on_the_page_in_order(tmp_path):
    site, page = _build(tmp_path)
    board = pd.read_csv(REPO / "leaderboard/leaderboard.csv")
    names = re.findall(r'<tr class="sys-row[^"]*" data-key="s\d+" data-slug="[^"]*" data-system="([^"]*)"', page)
    ranked = board[board.role == "ranked"].sort_values("composite", ascending=False).system.tolist()
    assert names == board[board.role == "reference"].system.tolist() + ranked
    for f in ("index.html", "style.css", "app.js", "logo.svg", "logo-dark.svg", "icon.svg", "preview.png"):
        assert (tmp_path / "site" / f).exists(), f


def test_field_scores_match_the_leaderboard(tmp_path):
    site, page = _build(tmp_path)
    data = json.loads(re.search(r'<script id="field-data" type="application/json">(.*?)</script>', page).group(1))
    board = pd.read_csv(REPO / "leaderboard/leaderboard.csv")
    assert len(data["systems"]) == len(board) and len(data["labels"]) == 30
    keys = dict(re.findall(r'data-key="(s\d+)" data-slug="[^"]*" data-system="([^"]*)"', page))
    for key, label in keys.items():
        row = board[board.system == label].iloc[0]
        scores = data["systems"][key]
        assert abs(sum(scores[f] for f in data["core"]) / 10 - row.core) < 1e-3
        assert abs(sum(scores[f] for f in data["rai"]) / 20 - row.rai) < 1e-3


def test_a_new_entry_in_the_evaluate_format_gets_its_field_panel(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("build_site_new", REPO / "scripts/build_site.py")
    site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site)
    board = tmp_path / "leaderboard"
    (board / "paper").mkdir(parents=True)
    (board / "paper" / "per_field.csv").write_text((REPO / "leaderboard/paper/per_field.csv").read_text())
    rows = pd.read_csv(REPO / "leaderboard/leaderboard.csv")
    new = rows.iloc[[1]].copy()
    new["system"], new["team"], new["results"], new["composite"] = "My System", "Some Lab", "my-system", 0.99
    pd.concat([rows, new]).to_csv(board / "leaderboard.csv", index=False)
    (board / "my-system").mkdir()
    fields = pd.read_csv(REPO / "leaderboard/paper/per_field.csv")
    one = fields[fields.system == rows.iloc[1].system][["field_id", "score"]]
    one.to_csv(board / "my-system" / "per_field.csv", index=False)       # the file make evaluate writes
    monkeypatch.setattr(site, "BOARD", board)
    page = site.build(tmp_path / "site").read_text(encoding="utf-8")
    first = re.search(r'<tr class="sys-row" data-key="(s\d+)" data-slug="[^"]*" data-system="([^"]*)"', page)
    assert first.group(2) == "My System" and "Some Lab" in page
    data = json.loads(re.search(r'<script id="field-data" type="application/json">(.*?)</script>', page).group(1))
    assert len(data["systems"][first.group(1)]) == 30
