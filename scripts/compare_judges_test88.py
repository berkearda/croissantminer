"""Compare composite test-88 scores across judge variants (v1 / BI / v2min).

Mirrors build_test88_headline_table.per_cell_scores_test88 but parameterizes
the judge parquet + score column. Outputs a side-by-side table.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.field_metrics import CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, score_field
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS
from scripts.figures.build_test88_headline_table import (
    is_null_gold, GOLD_TEST, TIER1, LONG_TEXT_RAI_FIELDS, SCORE_MAP, test
)

SYSTEMS = [
    'claude_sonnet_4_5', 'claude_sonnet_4_6', 'claude_opus_4_7',
    'gpt5_4_full', 'gpt5_4_mini', 'gemini_3_1_pro', 'gemini_2_5_flash',
    'deepseek_v3_2', 'glm_5_1', 'llama4_scout', 'mistral_small_4', 'qwen3_6_35b_a3b',
    'agentic_v2_sonnet_4_5', 'agentic_v2_sonnet_4_6_v4',
    'agentic_v2_gpt5_4_full_v4', 'agentic_v2_gemini_3_1_pro_v4',
    'agentic_specialist_premium_v4', 'agentic_specialist_mixed_v4',
    'agentic_lev_sonnet_4_5', 'agentic_lev_gpt5_4_full',
    'agentic_lev_gemini_3_1_pro', 'agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3',
    'agentic_lev_sonnet_4_6_sonnet_4_6_v3',
    'agentic_react_sonnet_4_6_v3', 'agentic_react_sonnet_4_6',
    'agentic_react_ahmetcan_iter5',
]


def load_judge_lookup(parquet_path, score_col, sys_id):
    j = pd.read_parquet(parquet_path)
    j = j[(j.system_id == sys_id) & j[score_col].notna() & j.paper_id.isin(test)].copy()
    j['mapped'] = j[score_col].map(SCORE_MAP)
    return {(r['paper_id'], r['field_id']): r['mapped'] for _, r in j.iterrows()}


def per_cell_scores_test88(sys_id, judge_lookup):
    sdir = STRATEGY_DIRS.get(sys_id)
    if sdir is None or not sdir.exists():
        return pd.DataFrame(columns=['paper_id', 'field_id', 'score'])
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


def composite(df):
    if len(df) == 0:
        return float('nan')
    per_field = df.groupby('field_id')['score'].mean()
    return per_field.mean()


def bootstrap_ci(df, n_boot=2000, seed=42):
    if len(df) == 0:
        return float('nan'), float('nan')
    papers = sorted(df['paper_id'].unique())
    fields = sorted(df['field_id'].unique())
    p2i = {p: i for i, p in enumerate(papers)}
    f2i = {f: i for i, f in enumerate(fields)}
    m = np.full((len(papers), len(fields)), np.nan)
    pi = df['paper_id'].map(p2i).values
    fi = df['field_id'].map(f2i).values
    m[pi, fi] = df['score'].values
    rng = np.random.default_rng(seed)
    n = len(papers)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        with np.errstate(all='ignore'):
            per_field = np.nanmean(m[idx], axis=0)
        per_field = per_field[~np.isnan(per_field)]
        boots[b] = float(np.nanmean(per_field)) if len(per_field) else float('nan')
    boots = boots[~np.isnan(boots)]
    return float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


JUDGE_VARIANTS = [
    ('v1',    ROOT / 'data/judged/judge_scores_glm_5.parquet',    'score'),
    ('v2min', ROOT / 'data/judged/judge_scores_v2min_glm5.parquet', 'score'),
    ('BI',    ROOT / 'data/judged/judge_scores_bi_glm5.parquet',    'bi_score'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', nargs='+', default=['v1', 'v2min'],
                    help='which judge variants to compare')
    ap.add_argument('--no-bootstrap', action='store_true')
    args = ap.parse_args()

    active = [v for v in JUDGE_VARIANTS if v[0] in args.variants]
    print(f'Comparing variants: {[v[0] for v in active]}')

    results = []
    t0 = time.time()
    for sid in SYSTEMS:
        row = {'sid': sid}
        for label, path, col in active:
            if not Path(path).exists():
                row[label] = float('nan')
                continue
            lk = load_judge_lookup(path, col, sid)
            df = per_cell_scores_test88(sid, lk)
            row[f'{label}_score'] = composite(df)
            row[f'{label}_n'] = len(df)
            if not args.no_bootstrap:
                lo, hi = bootstrap_ci(df)
                row[f'{label}_lo'] = lo
                row[f'{label}_hi'] = hi
        results.append(row)
        score_strs = '  '.join(f'{l}={row.get(f"{l}_score", float("nan")):.3f}' for l, _, _ in active)
        print(f'  {sid:48s}  {score_strs}')

    df = pd.DataFrame(results)
    out = ROOT / 'results/composite_judge_comparison.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f'\nWrote {out}  ({time.time()-t0:.1f}s)')

    # Summary
    print('\n=== Composite scores per system ===')
    print(f'{"system":48s}  ' + '  '.join(f'{l:>8s}' for l, _, _ in active) + '   '
          + '  '.join(f'Δ{l}vsv1' for l, _, _ in active if l != 'v1'))
    for r in results:
        line = f'{r["sid"]:48s}  '
        v1 = r.get('v1_score', float('nan'))
        for l, _, _ in active:
            v = r.get(f'{l}_score', float('nan'))
            line += f'{v:>8.3f}  '
        for l, _, _ in active:
            if l == 'v1':
                continue
            v = r.get(f'{l}_score', float('nan'))
            line += f'{v - v1:+.3f}  '
        print(line)


if __name__ == '__main__':
    main()
