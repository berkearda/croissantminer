#!/usr/bin/env python3
"""Build Tab 2: test-88 headline LaTeX table.

Per-system 2,000-replicate paper-clustered bootstrap CI on the composite,
using the same per-cell scoring logic as render_final_table.compose_test88
(post-2026-05-03 audit fix: correct-null skip, hallucination=0, miss=0).

Output:
  - results/composite_ci_test88_post_fix.csv   (per-system mean + CI)
  - paper/overleaf/table2_test88_headline.tex  (LaTeX table)
"""

from __future__ import annotations

import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

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
LONG_TEXT_RAI_FIELDS = sorted(set(GOLD['field_id'].unique()) - set(TIER1))
# Headline judge is v2min GLM-5 (locked 2026-05-04, decisions.md). The v2min
# parquet stores its verdict in a 'v2min_score' column; rename to 'score' so the
# downstream per-cell logic (SCORE_MAP, judge_lookup) is unchanged. Using the
# plain judge_scores_glm_5.parquet (v1) here would reproduce the discarded 0.650
# scale instead of the submitted 0.704 headline.
judges = pd.read_parquet(ROOT / 'data/judged/judge_scores_v2min_glm5.parquet')
if 'v2min_score' in judges.columns and 'score' not in judges.columns:
    judges = judges.rename(columns={'v2min_score': 'score'})
# Camera-ready re-run (decisions.md 2026-09-26 (6)): Locator-Extractor Gemini papers whose API
# calls failed on quota were re-run into new folders (scripts/camera_ready/merge_lev_rerun.py)
# and judged into a new file (scripts/camera_ready/judge_lev_rerun.py). The original folders and
# the pinned judge file are unchanged; the re-run systems carry the suffix _rerun2609.
_RERUN_JUDGE = ROOT / 'data/judged/judge_scores_v2min_glm5_lev_rerun_2026-09.parquet'
for _sid in ('agentic_lev_gemini_3_1_pro', 'agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3'):
    STRATEGY_DIRS[_sid + '_rerun2609'] = STRATEGY_DIRS[_sid].parent / (_sid + '_rerun2609')
if _RERUN_JUDGE.exists():
    judges = pd.concat([judges, pd.read_parquet(_RERUN_JUDGE)[judges.columns]], ignore_index=True)
# RAI cells the scorer needs but that had no verdict (DEVIATIONS D3 cells never judged for six
# agentic systems), judged on 2026-09-26 with the same judge by scripts/camera_ready/judge_gapfill.py.
_GAPFILL_JUDGE = ROOT / 'data/judged/judge_scores_v2min_glm5_gapfill_2026-09.parquet'
if _GAPFILL_JUDGE.exists():
    judges = pd.concat([judges, pd.read_parquet(_GAPFILL_JUDGE)[judges.columns]], ignore_index=True)

import re as _re
# A gold value counts as missing only if the WHOLE value is a missing marker.
# Fixed 2026-09-26 (decisions.md): the earlier pattern had no end anchor, so any
# value merely starting with "na", "none", "null" or "unknown" (e.g. "Natural
# Questions", "National University of Singapore") was treated as missing
# (14 of 3,060 gold cells).
_NULL_GOLD_RE = _re.compile(
    r'^(\[null|(null|n/?a|none|unknown)[\s.,;:-]*$|not (disclosed|found|mentioned|specified|applicable|available)\b)',
    _re.IGNORECASE,
)


def is_null_gold(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return True
    s_str = str(s).strip()
    if not s_str:
        return True
    s_low = s_str.lower()
    if s_low in ('null', 'none', 'n/a', 'na', 'unknown',
                 'not disclosed', 'not found', 'not mentioned',
                 'not specified', 'not applicable', 'not available'):
        return True
    if _NULL_GOLD_RE.match(s_low):
        return True
    if 'not found in paper' in s_low or 'not mentioned in paper' in s_low or 'not specified in paper' in s_low:
        return True
    if s_low.startswith('[null') or s_low.startswith('[na') or s_low.startswith('[n/a'):
        return True
    return False


def per_cell_scores_test88(sys_id):
    """Replicates render_final_table.compose_test88 cell-level logic, returns DataFrame."""
    sdir = STRATEGY_DIRS.get(sys_id)
    if sdir is None or not sdir.exists():
        return pd.DataFrame(columns=['paper_id', 'field_id', 'score'])

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
        except Exception:
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
        elif fid in LONG_TEXT_RAI_FIELDS:
            if cand_empty:
                rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': 0.0})
            else:
                jscore = judge_lookup.get((g['paper_id'], fid))
                if jscore is not None:
                    rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': jscore})

    return pd.DataFrame(rows)


def composite_from_matrix(m):
    with np.errstate(all='ignore'):
        per_field = np.nanmean(m, axis=0)
    per_field = per_field[~np.isnan(per_field)]
    return float('nan') if len(per_field) == 0 else float(np.nanmean(per_field))


BOOT_N = 2000
SEED = 42


def bootstrap_ci(df, n_boot=BOOT_N):
    if len(df) == 0:
        return float('nan'), float('nan'), float('nan')
    papers = sorted(df['paper_id'].unique())
    fields = sorted(df['field_id'].unique())
    p2i = {p: i for i, p in enumerate(papers)}
    f2i = {f: i for i, f in enumerate(fields)}
    m = np.full((len(papers), len(fields)), np.nan)
    pi = df['paper_id'].map(p2i).values
    fi = df['field_id'].map(f2i).values
    m[pi, fi] = df['score'].values
    point = composite_from_matrix(m)
    rng = np.random.default_rng(SEED)
    n = len(papers)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[b] = composite_from_matrix(m[idx])
    boots = boots[~np.isnan(boots)]
    lo = float(np.quantile(boots, 0.025))
    hi = float(np.quantile(boots, 0.975))
    return point, lo, hi


SYSTEMS = [
    ('claude_sonnet_4_5',                            'Claude Sonnet 4.5 \\textit{(gold-seed)}', 'Single-pass', 'gold_seed'),
    ('claude_sonnet_4_6',                            'Claude Sonnet 4.6',                                          'Single-pass', 'single'),
    ('claude_opus_4_7',                              'Claude Opus 4.7',                                            'Single-pass', 'single'),
    ('gpt5_4_full',                                  'GPT-5.4',                                                    'Single-pass', 'single'),
    ('gpt5_4_mini',                                  'GPT-5.4 Mini',                                               'Single-pass', 'single'),
    ('gemini_3_1_pro',                               'Gemini 3.1 Pro',                                             'Single-pass', 'single'),
    ('gemini_2_5_flash',                             'Gemini 2.5 Flash',                                           'Single-pass', 'single'),
    ('deepseek_v3_2',                                'DeepSeek V3.2',                                              'Single-pass', 'single'),
    ('glm_5_1',                                      'GLM-5.1',                                                    'Single-pass', 'single'),
    ('llama4_scout',                                 'Llama 4 Scout 17B',                                          'Single-pass', 'single'),
    ('mistral_small_4',                              'Mistral Small 4',                                            'Single-pass', 'single'),
    ('qwen3_6_35b_a3b',                              'Qwen3.6 35B-A3B',                                            'Single-pass', 'single'),
    ('agentic_v2_sonnet_4_5',                        'V2 (Sonnet 4.5) $^{\\dagger}$',              'V2',          'gold_seed'),
    ('agentic_v2_sonnet_4_6_v4',                     'V2 (Sonnet 4.6)',                                            'V2',          'agentic'),
    ('agentic_v2_gpt5_4_full_v4',                    'V2 (GPT-5.4)',                                               'V2',          'agentic'),
    ('agentic_v2_gemini_3_1_pro_v4',                 'V2 (Gemini 3.1 Pro)',                                        'V2',          'agentic'),
    ('agentic_specialist_premium_v4',                'Specialist (Sonnet 4.6)',                                    'Specialist',  'agentic'),
    ('agentic_specialist_mixed_v4',                  'Specialist (mixed)',                                         'Specialist',  'agentic'),
    ('agentic_specialist_gpt5_4_full_v4',            'Specialist (GPT-5.4)',                                       'Specialist',  'agentic'),
    ('agentic_specialist_gemini_3_1_pro_v4',         'Specialist (Gemini 3.1 Pro)',                                'Specialist',  'agentic'),
    ('agentic_lev_sonnet_4_5',                       'LEV (Sonnet 4.5) $^{\\dagger}$',             'LEV',         'gold_seed'),
    ('agentic_lev_gpt5_4_full',                      'LEV (GPT-5.4)',                                              'LEV',         'agentic'),
    ('agentic_lev_gemini_3_1_pro',                   'LEV (Gemini 3.1 Pro)',                                       'LEV',         'agentic'),
    ('agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3',    'LEV (Gemini 3.1 Pro + GPT-5.4 Mini)',                        'LEV',         'agentic'),
    ('agentic_lev_gemini_3_1_pro_rerun2609',         'LEV (Gemini 3.1 Pro), quota failures re-run',               'LEV',         'agentic'),
    ('agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3_rerun2609', 'LEV (Gemini 3.1 Pro + GPT-5.4 Mini), quota failures re-run', 'LEV',  'agentic'),
    ('agentic_lev_sonnet_4_6_sonnet_4_6_v3',         'LEV (Sonnet 4.6)',                                           'LEV',         'agentic'),
    ('agentic_react_sonnet_4_6_v3',                  'ReAct (Sonnet 4.6) [v3]',                                    'ReAct',       'agentic'),
    ('agentic_react_sonnet_4_6',                     'ReAct (Sonnet 4.6) [v1]',                                    'ReAct',       'agentic'),
    ('agentic_react_ahmetcan_iter5',                 'ReAct (Sonnet 4.6) [iter-5]',                                'ReAct',       'agentic'),
    ('agentic_react_gpt_5_4_v3',                     'ReAct (GPT-5.4)',                                            'ReAct',       'agentic'),
    ('agentic_react_gemini_3_1_pro_v3',              'ReAct (Gemini 3.1 Pro)',                                     'ReAct',       'agentic'),
]


def main():
    t0 = time.time()
    results = []
    for sid, label, arch, family in SYSTEMS:
        df = per_cell_scores_test88(sid)
        if len(df) == 0:
            print(f'  {sid:48s} SKIP (no data)')
            continue
        point, lo, hi = bootstrap_ci(df)
        n_papers = df['paper_id'].nunique()
        results.append({
            'sid': sid, 'label': label, 'arch': arch, 'family': family,
            'composite': point, 'ci_lo': lo, 'ci_hi': hi,
            'n_cells': len(df), 'n_papers': n_papers,
        })
        print(f'  {sid:48s} {point:.3f} [{lo:.3f}, {hi:.3f}]  n={len(df):4d}  papers={n_papers}')

    out_csv = ROOT / 'results' / 'composite_ci_test88_post_fix.csv'
    pd.DataFrame(results).to_csv(out_csv, index=False)
    print(f'\nWrote {out_csv}  ({time.time()-t0:.1f}s)')

    # Sort: gold-seed first (Sonnet 4.5 only), rule line, then non-seed by composite desc
    seed_rows = [r for r in results if r['sid'] == 'claude_sonnet_4_5']
    other_rows = [r for r in results if r['sid'] != 'claude_sonnet_4_5']
    other_rows.sort(key=lambda r: -r['composite'])

    # Build LaTeX
    lines = []
    lines.append(r'\begin{table}[!t]')
    lines.append(r'\centering')
    lines.append(r'\small')
    lines.append(r'\caption{Test-88 composite accuracy across 26 evaluated systems. Composite weights all 30 Croissant fields equally; CIs are 2{,}000-replicate paper-clustered bootstrap. Sonnet 4.5 (top row, gold-tinted) seeded the gold annotations and is reported as a top-line reference rather than ranked. Among non-seed systems, Sonnet 4.6 single-pass is the strongest configuration; all four agentic patterns underperform single-pass with the same backbone (\S\ref{sec:architectural-isolation}).}')
    lines.append(r'\label{tab:test88-headline}')
    lines.append(r'\begin{tabular}{lll@{\hskip 8pt}r@{\,}l}')
    lines.append(r'\toprule')
    lines.append(r'Rank & System & Architecture & \multicolumn{2}{c}{Composite [95\% CI]} \\')
    lines.append(r'\midrule')

    if seed_rows:
        r = seed_rows[0]
        lines.append(f'\\textit{{ref}} & \\textit{{{r["label"]}}} & \\textit{{{r["arch"]}}} & \\textit{{{r["composite"]:.3f}}} & \\textit{{[{r["ci_lo"]:.3f}, {r["ci_hi"]:.3f}]}} \\\\')
        lines.append(r'\midrule')

    for idx, r in enumerate(other_rows, start=1):
        bf = r'\textbf{' if idx == 1 else ''
        ef = r'}' if idx == 1 else ''
        lines.append(f'{idx} & {bf}{r["label"]}{ef} & {r["arch"]} & {bf}{r["composite"]:.3f}{ef} & {bf}[{r["ci_lo"]:.3f}, {r["ci_hi"]:.3f}]{ef} \\\\')

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\vspace{2pt}')
    lines.append(r'\par\smallskip\footnotesize')
    lines.append(r'$^{\dagger}$ V2 and LEV variants with the Sonnet 4.5 backbone share the gold-seed caveat and are listed for completeness; the headline analysis (\S\ref{sec:architectural-isolation}) compares architectures on the Sonnet 4.6 backbone only.')
    lines.append(r'\end{table}')

    # NOTE (2026-05-29): do NOT write paper/overleaf/table2_test88_headline.tex.
    # The submitted Table 2 is a hand-assembled Core/RAI/Composite, architecture-
    # grouped layout (see git c0a9309); this script emits a different flat single-
    # column layout and previously CLOBBERED the submitted table. It now writes a
    # side artifact only. The CSV below is the canonical machine-readable output.
    out_tex = ROOT / 'results' / 'table2_test88_headline_AUTOGEN_DO_NOT_USE_IN_PAPER.tex'
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {out_tex}  (side artifact — NOT the paper table)')


if __name__ == '__main__':
    main()
