#!/usr/bin/env python3
"""Vectorized paired bootstrap + Wilcoxon for all pairs.

Strategy:
  - For each system: build (paper, field) -> score matrix (sparse).
  - For each pair (A, B): inner-join on (paper, field), get per-paper field-score
    matrices for A and B, do 2000 paper-resamples on numpy arrays directly.
  - Wilcoxon: scipy on the per-cell delta vector.
  - BH FDR over all pairs.

Reuses results/composite_ci.csv from the prior (slow) run for per-system bounds.

Output:
  - results/bootstrap_pairwise.csv
  - docs/headline_vs_sonnet_4_6_bootstrap_wilcoxon.csv
"""

from __future__ import annotations

import json, sys, time
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.field_metrics import (CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, score_field)
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS

GOLD = pd.read_parquet(ROOT / 'data/annotations/gold.parquet')
GOLD = GOLD[GOLD['gold_method'].isin(DEFAULT_GOLD_METHODS)]
GOLD = GOLD[GOLD['gold_value'].notna()]
test = frozenset(json.loads((ROOT / 'data/agentic/dev_test_split.json').read_text())['test'])
GOLD_TEST = GOLD[GOLD['paper_id'].isin(test)]
TIER1 = CONSTRAINED_FIELDS + SHORT_TEXT_FIELDS
SCORE_MAP = {1: 1.0, 2: 0.5, 3: 0.0}
judges = pd.read_parquet(ROOT / 'data/judged/judge_scores_glm_5.parquet')

BOOT_N = 2000
SEED = 42

SYSTEMS = [
    'claude_sonnet_4_5','claude_sonnet_4_6','claude_opus_4_7',
    'gpt5_4_full','gpt5_4_mini',
    'gemini_3_1_pro','gemini_2_5_flash',
    'deepseek_v3_2','glm_5_1',
    'llama4_scout','mistral_small_4','qwen3_6_35b_a3b',
    'agentic_v2_sonnet_4_5','agentic_v2_sonnet_4_6_v4',
    'agentic_v2_gpt5_4_full_v4','agentic_v2_gemini_3_1_pro_v4',
    'agentic_lev_sonnet_4_5','agentic_lev_gpt5_4_full',
    'agentic_lev_gemini_3_1_pro','agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3',
    'agentic_lev_sonnet_4_6_sonnet_4_6_v3',
    'agentic_specialist_premium_v4','agentic_specialist_mixed_v4',
    'agentic_react_sonnet_4_6','agentic_react_sonnet_4_6_v3',
    'agentic_react_ahmetcan_iter5',
]


def per_cell_scores(sys_id: str) -> pd.DataFrame:
    sdir = STRATEGY_DIRS[sys_id]
    rows1 = []
    for _, g in GOLD_TEST[GOLD_TEST['field_id'].isin(TIER1)].iterrows():
        ext_path = sdir / f"{g['paper_id']}.json"
        if not ext_path.exists():
            continue
        try:
            payload = json.load(open(ext_path))
            ext = payload.get('extraction', payload) if isinstance(payload, dict) else {}
        except Exception:
            continue
        fid = g['field_id']
        short = fid.split(':')[-1] if ':' in fid else fid
        cand = ext.get(fid, ext.get(short))
        r = score_field(cand, g['gold_value'], fid)
        if r['skipped']:
            continue
        rows1.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': r['score']})
    t1 = pd.DataFrame(rows1)
    t2 = judges[(judges.system_id == sys_id) & judges.score.notna() & judges.paper_id.isin(test)].copy()
    t2['score'] = t2['score'].map(SCORE_MAP)
    t2 = t2[['paper_id', 'field_id', 'score']]
    return pd.concat([t1, t2], ignore_index=True)


def bh_fdr(pvals, alpha=0.05):
    pvals = np.asarray(pvals, dtype=float)
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    qs = ranked * n / (np.arange(n) + 1)
    qs_running = np.minimum.accumulate(qs[::-1])[::-1]
    reject = qs_running < alpha
    out_reject = np.zeros(n, dtype=bool)
    out_q = np.zeros(n)
    for i, ord_idx in enumerate(order):
        out_reject[ord_idx] = reject[i]
        out_q[ord_idx] = qs_running[i]
    return out_reject.tolist(), out_q.tolist()


def composite_from_array(score_matrix: np.ndarray) -> float:
    """score_matrix: (n_papers, n_fields), NaN for missing.
    Composite = mean across fields of (mean across papers of non-NaN scores per field)."""
    with np.errstate(all='ignore'):
        per_field = np.nanmean(score_matrix, axis=0)
    per_field = per_field[~np.isnan(per_field)]
    if len(per_field) == 0:
        return float('nan')
    return float(np.nanmean(per_field))


def paired_bootstrap_vectorized(matrix_a: np.ndarray, matrix_b: np.ndarray,
                                 paper_idx: np.ndarray, n_boot: int = BOOT_N):
    """Resample paper indices with replacement, recompute composite_a - composite_b each replicate.
    matrix_a/matrix_b: (n_papers, n_fields). paper_idx: original paper indices.
    Returns: (delta_point, ci_lo, ci_hi, p)."""
    delta_point = composite_from_array(matrix_a) - composite_from_array(matrix_b)
    n = len(paper_idx)
    rng = np.random.default_rng(SEED)
    deltas = np.zeros(n_boot, dtype=float)
    for i in range(n_boot):
        sample = rng.integers(0, n, size=n)
        deltas[i] = composite_from_array(matrix_a[sample]) - composite_from_array(matrix_b[sample])
    deltas = deltas[~np.isnan(deltas)]
    if len(deltas) == 0:
        return float('nan'), float('nan'), float('nan'), 1.0
    lo = float(np.quantile(deltas, 0.025))
    hi = float(np.quantile(deltas, 0.975))
    p = 2.0 * min((deltas <= 0).mean(), (deltas > 0).mean())
    p = max(p, 1.0 / n_boot)
    return delta_point, lo, hi, p


def main():
    t0 = time.time()
    print(f'Loading per-cell scores for {len(SYSTEMS)} systems...')
    cache = {}
    all_papers = set()
    all_fields = set()
    for sid in SYSTEMS:
        cache[sid] = per_cell_scores(sid)
        all_papers |= set(cache[sid]['paper_id'])
        all_fields |= set(cache[sid]['field_id'])
        print(f'  {sid:48s} {len(cache[sid])} cells')

    papers = sorted(all_papers)
    fields = sorted(all_fields)
    paper_to_idx = {p: i for i, p in enumerate(papers)}
    field_to_idx = {f: i for i, f in enumerate(fields)}
    n_papers, n_fields = len(papers), len(fields)
    print(f'Universe: {n_papers} papers × {n_fields} fields')

    # Build dense matrices (n_papers × n_fields), NaN for unseen cells
    matrices = {}
    for sid in SYSTEMS:
        m = np.full((n_papers, n_fields), np.nan, dtype=float)
        df = cache[sid]
        pi = df['paper_id'].map(paper_to_idx).values
        fi = df['field_id'].map(field_to_idx).values
        m[pi, fi] = df['score'].values
        matrices[sid] = m
    print(f'Loaded matrices in {time.time()-t0:.1f}s')

    n_pairs = len(SYSTEMS) * (len(SYSTEMS) - 1) // 2
    print(f'\nPairwise bootstrap + Wilcoxon for {n_pairs} pairs (vectorized)...')
    rows = []
    paper_idx = np.arange(n_papers)
    t1 = time.time()
    for k, (a, b) in enumerate(combinations(SYSTEMS, 2)):
        ma = matrices[a]
        mb = matrices[b]
        # Inner-join: only cells where BOTH have a score (mask)
        both_mask = ~np.isnan(ma) & ~np.isnan(mb)
        # Use NaN where either is missing
        masked_a = np.where(both_mask, ma, np.nan)
        masked_b = np.where(both_mask, mb, np.nan)
        n_paired = int(both_mask.sum())

        # Bootstrap
        if n_paired > 0:
            delta, lo, hi, p_boot = paired_bootstrap_vectorized(masked_a, masked_b, paper_idx)
        else:
            delta, lo, hi, p_boot = float('nan'), float('nan'), float('nan'), 1.0

        # Wilcoxon on per-cell deltas
        diffs = (ma - mb)[both_mask]
        nonzero = diffs[diffs != 0]
        if len(nonzero) >= 5:
            try:
                p_wilcox = float(wilcoxon(nonzero, alternative='two-sided', zero_method='wilcox').pvalue)
            except Exception:
                p_wilcox = 1.0
        else:
            p_wilcox = 1.0

        rows.append({
            'system_a': a, 'system_b': b,
            'n_paired_cells': n_paired,
            'delta': delta, 'ci_lo': lo, 'ci_hi': hi,
            'p_bootstrap': p_boot,
            'p_wilcoxon': p_wilcox,
        })

        if (k + 1) % 25 == 0 or k == n_pairs - 1:
            elapsed = time.time() - t1
            print(f'  {k+1:>3}/{n_pairs}  elapsed {elapsed:.1f}s  ({elapsed/(k+1):.2f}s/pair)')

    df = pd.DataFrame(rows)
    rejects_b, qs_b = bh_fdr(df['p_bootstrap'].tolist())
    rejects_w, qs_w = bh_fdr(df['p_wilcoxon'].tolist())
    df['q_bh_bootstrap'] = qs_b
    df['q_bh_wilcoxon'] = qs_w
    df['sig_bootstrap'] = rejects_b
    df['sig_wilcoxon'] = rejects_w
    df = df.sort_values('p_bootstrap')

    out_pair = ROOT / 'results' / 'bootstrap_pairwise.csv'
    df.to_csv(out_pair, index=False)
    print(f'\nWrote {out_pair.relative_to(ROOT)} ({len(df)} pairs)')

    # Headline subset vs single-pass Sonnet 4.6
    ref = 'claude_sonnet_4_6'
    head = df[(df.system_a == ref) | (df.system_b == ref)].copy()
    head['system'] = head.apply(lambda r: r['system_a'] if r['system_b'] == ref else r['system_b'], axis=1)
    head['delta_vs_ref'] = head.apply(lambda r: r['delta'] if r['system_b'] == ref else -r['delta'], axis=1)
    head['ci_lo_vs_ref'] = head.apply(lambda r: r['ci_lo'] if r['system_b'] == ref else -r['ci_hi'], axis=1)
    head['ci_hi_vs_ref'] = head.apply(lambda r: r['ci_hi'] if r['system_b'] == ref else -r['ci_lo'], axis=1)
    head = head[['system', 'delta_vs_ref', 'ci_lo_vs_ref', 'ci_hi_vs_ref',
                  'p_bootstrap', 'q_bh_bootstrap', 'sig_bootstrap',
                  'p_wilcoxon', 'q_bh_wilcoxon', 'sig_wilcoxon']]
    head = head.sort_values('delta_vs_ref', ascending=False)
    out_head = ROOT / 'docs' / 'headline_vs_sonnet_4_6_bootstrap_wilcoxon.csv'
    head.to_csv(out_head, index=False)
    print(f'Wrote {out_head.relative_to(ROOT)}')

    print(f'\nTotal time: {time.time()-t0:.1f}s')


if __name__ == '__main__':
    main()
