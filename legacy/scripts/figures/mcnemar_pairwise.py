#!/usr/bin/env python3
"""McNemar pairwise + BH FDR across the 22-system test-88 lineup.

For every pair (A, B) of systems and every (paper, field) cell scored by both:
  - binarise score: 1 if score >= 0.5, else 0
  - tally b = #cells A=1 & B=0; c = #cells A=0 & B=1
  - exact McNemar p-value (binomial test on b vs b+c, two-sided)

Then BH FDR-adjust all p-values across all pairs at q=0.05.

Output:
  - results/mcnemar_pairwise.csv (full pairwise table)
  - docs/mcnemar_headline.csv (subset against single-pass Sonnet 4.6 reference)
"""

from __future__ import annotations

import json, sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

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

THRESHOLD = 0.5  # binarisation threshold per pre-reg


SYSTEMS = [
    'claude_sonnet_4_5',
    'claude_sonnet_4_6',
    'claude_opus_4_7',
    'gpt5_4_full',
    'gpt5_4_mini',
    'gemini_3_1_pro',
    'gemini_2_5_flash',
    'deepseek_v3_2',
    'glm_5_1',
    'llama4_scout',
    'mistral_small_4',
    'qwen3_6_35b_a3b',
    'agentic_v2_sonnet_4_5',
    'agentic_v2_sonnet_4_6_v4',
    'agentic_v2_gpt5_4_full_v4',
    'agentic_v2_gemini_3_1_pro_v4',
    'agentic_lev_sonnet_4_5',
    'agentic_lev_gpt5_4_full',
    'agentic_lev_gemini_3_1_pro',
    'agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3',
    'agentic_lev_sonnet_4_6_sonnet_4_6_v3',
    'agentic_specialist_premium_v4',
    'agentic_specialist_mixed_v4',
    'agentic_react_sonnet_4_6',
    'agentic_react_sonnet_4_6_v3',
    'agentic_react_ahmetcan_iter5',
]


import re as _re
# fixed 2026-09-26: whole-value match only (see build_test88_headline_table.py)
_NULL_GOLD_RE = _re.compile(
    r'^(\[null|(null|n/?a|none|unknown)[\s.,;:-]*$|not (disclosed|found|mentioned|specified|applicable|available)\b)',
    _re.IGNORECASE,
)


def is_null_gold(s):
    if s is None: return True
    if isinstance(s, float) and pd.isna(s): return True
    s_str = str(s).strip()
    if not s_str: return True
    s_low = s_str.lower()
    if s_low in ('null','none','n/a','na','unknown','not disclosed','not found','not mentioned','not specified','not applicable','not available'):
        return True
    if _NULL_GOLD_RE.match(s_low): return True
    if 'not found in paper' in s_low or 'not mentioned in paper' in s_low: return True
    if s_low.startswith('[null') or s_low.startswith('[na') or s_low.startswith('[n/a'): return True
    return False


def per_cell_scores(sys_id: str) -> pd.DataFrame:
    """Locked methodology (2026-05-03): correct-null skip, hallucination=0, miss=0,
    judge for Tier-2 gold-real+pred-nonnull, score_field for Tier-1."""
    sdir = STRATEGY_DIRS[sys_id]
    j = judges[(judges.system_id == sys_id) & judges.score.notna() & judges.paper_id.isin(test)].copy()
    j['mapped'] = j['score'].map(SCORE_MAP)
    judge_lookup = {(r['paper_id'], r['field_id']): r['mapped'] for _, r in j.iterrows()}
    rows = []
    for _, g in GOLD_TEST.iterrows():
        ext_path = sdir / f"{g['paper_id']}.json"
        if not ext_path.exists():
            continue
        try:
            payload = json.load(open(ext_path))
            ext = payload.get('extraction', payload) if isinstance(payload, dict) else {}
        except:
            continue
        fid = g['field_id']
        short = fid.split(':')[-1] if ':' in fid else fid
        cand = ext.get(fid, ext.get(short))
        cand_empty = cand is None or not str(cand).strip()
        gold_null = is_null_gold(g['gold_value'])
        if gold_null:
            if cand_empty:
                continue
            rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': 0.0})
            continue
        if fid in TIER1:
            r = score_field(cand, g['gold_value'], fid)
            if r['skipped']:
                continue
            rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': r['score']})
        else:
            if cand_empty:
                rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': 0.0})
            else:
                jscore = judge_lookup.get((g['paper_id'], fid))
                if jscore is not None:
                    rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': jscore})
    both = pd.DataFrame(rows)
    return both


def mcnemar_pair(scores_a: pd.DataFrame, scores_b: pd.DataFrame, threshold: float = THRESHOLD):
    """Return (b, c, n_paired_cells, p_value) for the pair."""
    a = scores_a.copy()
    a['hit_a'] = (a['score'] >= threshold).astype(int)
    b = scores_b.copy()
    b['hit_b'] = (b['score'] >= threshold).astype(int)
    merged = a.merge(b, on=['paper_id', 'field_id'], how='inner', suffixes=('_a', '_b'))
    if len(merged) == 0:
        return 0, 0, 0, 1.0
    bb = int(((merged['hit_a'] == 1) & (merged['hit_b'] == 0)).sum())
    cc = int(((merged['hit_a'] == 0) & (merged['hit_b'] == 1)).sum())
    n = len(merged)
    if bb + cc == 0:
        return bb, cc, n, 1.0
    res = binomtest(bb, bb + cc, p=0.5, alternative='two-sided')
    return bb, cc, n, res.pvalue


def bh_fdr(pvals: list[float], alpha: float = 0.05) -> tuple[list[bool], list[float]]:
    """Benjamini-Hochberg FDR. Returns (reject_flags, q_values_adjusted)."""
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = np.array(pvals)[order]
    qs = np.array(ranked) * n / (np.arange(n) + 1)
    qs_running = np.minimum.accumulate(qs[::-1])[::-1]
    reject = qs_running < alpha
    reject_full = np.zeros(n, dtype=bool)
    qs_full = np.zeros(n)
    for i, ord_idx in enumerate(order):
        reject_full[ord_idx] = reject[i]
        qs_full[ord_idx] = qs_running[i]
    return reject_full.tolist(), qs_full.tolist()


def main():
    print(f'Loading per-cell scores for {len(SYSTEMS)} systems...')
    cache = {}
    for sid in SYSTEMS:
        cache[sid] = per_cell_scores(sid)
        n = len(cache[sid])
        print(f'  {sid:48s} {n} cells')

    print(f'\nComputing pairwise McNemar for {len(SYSTEMS)*(len(SYSTEMS)-1)//2} pairs...')
    rows = []
    for a, b in combinations(SYSTEMS, 2):
        bb, cc, n_paired, p = mcnemar_pair(cache[a], cache[b])
        delta = (cache[a]['score'].mean() - cache[b]['score'].mean()) if len(cache[a]) and len(cache[b]) else 0.0
        rows.append({
            'system_a': a, 'system_b': b,
            'n_paired_cells': n_paired,
            'b_a_wins': bb, 'c_b_wins': cc,
            'mean_score_a': float(cache[a]['score'].mean()) if len(cache[a]) else 0.0,
            'mean_score_b': float(cache[b]['score'].mean()) if len(cache[b]) else 0.0,
            'delta_mean': delta,
            'p_mcnemar': p,
        })

    df = pd.DataFrame(rows)
    rejects, qs = bh_fdr(df['p_mcnemar'].tolist(), alpha=0.05)
    df['q_bh'] = qs
    df['significant_at_q005'] = rejects

    df = df.sort_values('p_mcnemar')

    out_full = ROOT / 'results' / 'mcnemar_pairwise.csv'
    out_full.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_full, index=False)
    print(f'\nWrote {out_full.relative_to(ROOT)} ({len(df)} pairs)')

    # Headline subset: every system vs single-pass Sonnet 4.6 (the strongest single-pass non-seed baseline)
    ref = 'claude_sonnet_4_6'
    headline = df[(df.system_a == ref) | (df.system_b == ref)].copy()
    headline['vs_ref'] = headline.apply(
        lambda r: r['system_a'] if r['system_b'] == ref else r['system_b'], axis=1)
    headline['delta_vs_ref'] = headline.apply(
        lambda r: r['mean_score_a'] - r['mean_score_b'] if r['system_b'] == ref else r['mean_score_b'] - r['mean_score_a'], axis=1)
    headline = headline[['vs_ref', 'delta_vs_ref', 'p_mcnemar', 'q_bh', 'significant_at_q005']]
    headline = headline.sort_values('delta_vs_ref', ascending=False)
    out_head = ROOT / 'docs' / 'mcnemar_headline_vs_sonnet_4_6.csv'
    headline.to_csv(out_head, index=False)
    print(f'Wrote {out_head.relative_to(ROOT)} (headline subset, {len(headline)} pairs)')

    print('\n=== Pairs significant at q=0.05 ===')
    sig = df[df['significant_at_q005']].sort_values('delta_mean', ascending=False)
    for _, r in sig.head(30).iterrows():
        print(f"  {r['system_a']:46s} > {r['system_b']:46s}  Δ={r['delta_mean']:+.3f}  p={r['p_mcnemar']:.2e}  q={r['q_bh']:.2e}")
    print(f'  ... ({len(sig)} significant pairs total)')


if __name__ == '__main__':
    main()
