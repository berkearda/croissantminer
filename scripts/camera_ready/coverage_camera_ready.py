"""Rebuild the benchmark coverage numbers on today's human gold (camera-ready).

data/analysis/coverage.parquet was built on 30 April from the gold as it stood
then, with a narrower "missing" rule than the scorer
(scripts/analysis/sec3_5_compute.py: is_null).

This rebuild uses ONE rule everywhere, the scorer's is_null_gold
(scripts/figures/build_test88_headline_table.py, fixed 2026-09-26), for:
  gold    current data/annotations/gold.parquet (102 papers x 30 fields)
  silver  silver/extractions/*.json (500 papers x 30 fields)
Domains are kept from the original coverage.parquet (inferred from descriptions).

Writes results/camera_ready/coverage_camera_ready.parquet and
results/camera_ready/coverage_facts.json, and prints every number the paper
derives from coverage, old vs new.
Decision: decisions.md 2026-09-26 (T-103).
"""
import json
import sys
import importlib.util
import warnings
from pathlib import Path

import pandas as pd
from scipy.stats import pearsonr, spearmanr

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "camera_ready"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = _load("h", "scripts/figures/build_test88_headline_table.py")
s35 = _load("s35", "scripts/analysis/sec3_5_compute.py")


def is_missing(v):
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return h.is_null_gold(v)


def build():
    old = pd.read_parquet(ROOT / "data/analysis/coverage.parquet")
    domain = dict(zip(old.paper_id, old.domain))
    rows = []
    gold = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    for r in gold.itertuples():
        fid = s35.normalize_field(r.field_id)
        rows.append((r.paper_id, "gold", fid, not is_missing(r.gold_value)))
    for f in sorted((ROOT / "silver/extractions").glob("*.json")):
        d = json.load(open(f))
        for k, v in (d.get("extraction") or {}).items():
            rows.append((d["dataset_id"], "silver", s35.normalize_field(k), not is_missing(v)))
    new = pd.DataFrame(rows, columns=["paper_id", "split", "field_id", "populated"])
    new["domain"] = new.paper_id.map(domain)
    new["field_group"] = ["core" if f in s35.CORE_FIELDS else "rai" for f in new.field_id]
    new = new[old.columns.tolist()]
    assert len(new) == len(old) == 18060 and new.domain.notna().all()
    assert new.groupby("split").paper_id.nunique().to_dict() == {"gold": 102, "silver": 500}
    return old, new


def facts(cov):
    pp = lambda d: d.groupby("paper_id").populated.sum().mean()
    f = {"all_mean": pp(cov), "gold_mean": pp(cov[cov.split == "gold"]), "silver_mean": pp(cov[cov.split == "silver"])}
    f["all_pct"] = 100 * f["all_mean"] / 30
    dom = cov.groupby(["domain", "paper_id"]).populated.sum().groupby("domain").mean()
    rai = cov[cov.field_group == "rai"].groupby(["domain", "paper_id"]).populated.sum().groupby("domain").mean()
    f["domain_mean"] = dom.round(2).to_dict()
    f["domain_rai_mean"] = rai.round(2).to_dict()
    gs = cov[cov.split == "gold"]
    f["gold_undoc"] = 100 * (1 - gs.populated.mean())
    f["gold_undoc_rai"] = 100 * (1 - gs[gs.field_group == "rai"].populated.mean())
    f["gold_undoc_core"] = 100 * (1 - gs[gs.field_group == "core"].populated.mean())
    gr = 100 * gs.groupby("field_id").populated.mean()
    sr = 100 * cov[cov.split == "silver"].groupby("field_id").populated.mean().reindex(gr.index)
    ar = 100 * cov.groupby("field_id").populated.mean().reindex(gr.index)
    f["pearson"], f["pearson_p"] = pearsonr(gr, sr)
    sp = spearmanr(gr, sr)
    f["spearman"], f["spearman_p"] = sp.correlation, sp.pvalue
    f["gold_field_pct"] = gr.round(1).to_dict()
    f["silver_field_pct"] = sr.round(1).to_dict()
    f["all_field_pct"] = ar.round(1).to_dict()
    f["gold_field_avg"] = gr.mean()        # Table 3 "Average": mean of the unrounded per-field rates
    f["silver_field_avg"] = sr.mean()
    return f


def main():
    old, new = build()
    OUT.mkdir(parents=True, exist_ok=True)
    new.to_parquet(OUT / "coverage_camera_ready.parquet", index=False)
    key = ["paper_id", "split", "field_id"]
    m = old.merge(new, on=key, suffixes=("_old", "_new"))
    assert len(m) == 18060
    for split in ("gold", "silver"):
        s = m[m.split == split]
        print(f"{split}: documented flag changed in {(s.populated_old != s.populated_new).sum()} of {len(s)} cells "
              f"(old->new documented: {((~s.populated_old) & s.populated_new).sum()}, "
              f"documented->missing: {(s.populated_old & ~s.populated_new).sum()})")
    fo, fn = facts(old), facts(new)
    json.dump({k: (float(v) if isinstance(v, (int, float)) else v) for k, v in fn.items()},
              open(OUT / "coverage_facts.json", "w"), indent=1)
    for k in ["all_mean", "all_pct", "gold_mean", "silver_mean", "gold_undoc", "gold_undoc_rai", "gold_undoc_core",
              "pearson", "pearson_p", "spearman", "spearman_p", "gold_field_avg", "silver_field_avg"]:
        print(f"{k:16s} old {fo[k]:.4g}   new {fn[k]:.4g}")
    print("domain mean (new):", dict(sorted(fn["domain_mean"].items(), key=lambda x: -x[1])))
    print("domain RAI mean (new):", dict(sorted(fn["domain_rai_mean"].items(), key=lambda x: -x[1])))
    for k in ["gold_field_pct", "silver_field_pct", "all_field_pct"]:
        d = {f: (fo[k][f], fn[k][f]) for f in fn[k] if fo[k][f] != fn[k][f]}
        print(f"{k} changed (old, new):", d)


if __name__ == "__main__":
    main()
