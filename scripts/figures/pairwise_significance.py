#!/usr/bin/env python3
"""Pairwise significance tests between the Table 2 systems (paper appendix, "Statistical Comparisons").

For every pair of the 24 ranked systems, on the cells that both systems have a score for:
  - paired bootstrap of the composite difference (2,000 paper resamples, seed 42),
  - Wilcoxon signed-rank test on the per-cell differences,
  - McNemar's exact test on scores binarised at 0.5,
with Benjamini-Hochberg FDR adjustment across all pairs, separately for each test.

Per-cell scores come from the Table 2 scorer (scripts/figures/build_test88_headline_table.py),
unchanged. Writes results/pairwise_significance.csv and prints single-pass Claude Sonnet 4.6
against the four agentic architectures on the same backbone (Section 5.2). No API calls.

    python scripts/figures/pairwise_significance.py
"""
import importlib.util
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

warnings.filterwarnings("ignore", category=RuntimeWarning)  # empty-slice means in the bootstrap

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tables", ROOT / "scripts/camera_ready/build_camera_ready_tables.py")
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)

BOOT_N = 2000
SEED = 42
THRESHOLD = 0.5
SINGLE_PASS = "claude_sonnet_4_6"
AGENTIC = ["agentic_react_sonnet_4_6_v3", "agentic_specialist_premium_v4",
           "agentic_v2_sonnet_4_6_v4", "agentic_lev_sonnet_4_6_sonnet_4_6_v3"]


def bh_fdr(pvals):
    pvals = np.asarray(pvals, dtype=float)
    n = len(pvals)
    order = np.argsort(pvals)
    q = pvals[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = q
    return out


def composite(m):
    """Mean over fields of the per-field mean over papers (each field weighted equally)."""
    per_field = np.nanmean(m, axis=0)
    per_field = per_field[~np.isnan(per_field)]
    return float(np.mean(per_field)) if len(per_field) else float("nan")


def paired_bootstrap(ma, mb):
    rng = np.random.default_rng(SEED)
    n = ma.shape[0]
    deltas = np.empty(BOOT_N)
    for i in range(BOOT_N):
        s = rng.integers(0, n, size=n)
        deltas[i] = composite(ma[s]) - composite(mb[s])
    deltas = deltas[~np.isnan(deltas)]
    p = 2.0 * min((deltas <= 0).mean(), (deltas > 0).mean())
    return composite(ma) - composite(mb), max(p, 1.0 / BOOT_N)


def main():
    sids = list(tables.T2_LABELS.values())
    labels = {sid: label for label, sid in tables.T2_LABELS.items()}
    cells = {sid: tables.cells(sid) for sid in sids}
    papers = sorted(set().union(*(set(c.paper_id) for c in cells.values())))
    fields = sorted(set().union(*(set(c.field_id) for c in cells.values())))
    pi = {p: i for i, p in enumerate(papers)}
    fi = {f: i for i, f in enumerate(fields)}
    mats = {}
    for sid, c in cells.items():
        m = np.full((len(papers), len(fields)), np.nan)
        m[c.paper_id.map(pi).values, c.field_id.map(fi).values] = c.score.values
        mats[sid] = m

    rows = []
    for a, b in combinations(sids, 2):
        both = ~np.isnan(mats[a]) & ~np.isnan(mats[b])
        ma, mb = np.where(both, mats[a], np.nan), np.where(both, mats[b], np.nan)
        delta, p_boot = paired_bootstrap(ma, mb)
        diffs = (mats[a] - mats[b])[both]
        nonzero = diffs[diffs != 0]
        p_wil = float(wilcoxon(nonzero, alternative="two-sided", zero_method="wilcox").pvalue) if len(nonzero) >= 5 else 1.0
        hit_a, hit_b = mats[a][both] >= THRESHOLD, mats[b][both] >= THRESHOLD
        only_a, only_b = int((hit_a & ~hit_b).sum()), int((~hit_a & hit_b).sum())
        p_mc = binomtest(only_a, only_a + only_b, p=0.5).pvalue if only_a + only_b else 1.0
        rows.append(dict(system_a=labels[a], system_b=labels[b], n_cells=int(both.sum()), delta=delta,
                         p_bootstrap=p_boot, p_wilcoxon=p_wil, p_mcnemar=p_mc))
    df = pd.DataFrame(rows)
    for test in ("bootstrap", "wilcoxon", "mcnemar"):
        df[f"q_{test}"] = bh_fdr(df[f"p_{test}"])
    out = ROOT / "results" / "pairwise_significance.csv"
    df.to_csv(out, index=False)
    print(f"{len(sids)} systems, {len(df)} pairs -> {out.relative_to(ROOT)}")

    print(f"\n{labels[SINGLE_PASS]} (single-pass) vs the agentic architectures on the same backbone:")
    for sid in AGENTIC:
        r = df[((df.system_a == labels[SINGLE_PASS]) & (df.system_b == labels[sid])) |
               ((df.system_b == labels[SINGLE_PASS]) & (df.system_a == labels[sid]))].iloc[0]
        print(f"  {labels[sid]:36s} q_bootstrap={r.q_bootstrap:.4f}  q_wilcoxon={r.q_wilcoxon:.1e}  q_mcnemar={r.q_mcnemar:.1e}")


if __name__ == "__main__":
    main()
