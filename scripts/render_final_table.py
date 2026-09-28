#!/usr/bin/env python3
"""Render the final test-88 evaluation table.

Output: docs/eval_table_final_2026-05-02.png
"""

import json, sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.field_metrics import (CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS, score_field)
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS

GOLD = pd.read_parquet(ROOT / 'data/annotations/gold.parquet')
GOLD = GOLD[GOLD['gold_method'].isin(DEFAULT_GOLD_METHODS)]
GOLD = GOLD[GOLD['gold_value'].notna()]
test = frozenset(json.loads((ROOT / 'data/agentic/dev_test_split.json').read_text())['test'])
GOLD_TEST = GOLD[GOLD['paper_id'].isin(test)]
TIER1 = CONSTRAINED_FIELDS + SHORT_TEXT_FIELDS

SCORE_MAP = {1: 1.0, 2: 0.5, 3: 0.0}
judges = pd.read_parquet(ROOT / 'data/judged/judge_scores_glm_5.parquet')


import re as _re
# fixed 2026-09-26: whole-value match only (see build_test88_headline_table.py)
_NULL_GOLD_RE = _re.compile(
    r'^(\[null|(null|n/?a|none|unknown)[\s.,;:-]*$|not (disclosed|found|mentioned|specified|applicable|available)\b)',
    _re.IGNORECASE,
)


def is_null_gold(s):
    """Mirror of score_field's gt_unknown logic — used to short-circuit Tier-2
    cells without invoking score_llm_judge (which would re-trigger API calls)."""
    if s is None:
        return True
    if isinstance(s, float) and pd.isna(s):
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
    if 'not found in paper' in s_low:
        return True
    if 'not mentioned in paper' in s_low:
        return True
    if 'not specified in paper' in s_low:
        return True
    if s_low.startswith('[null') or s_low.startswith('[na') or s_low.startswith('[n/a'):
        return True
    return False


def compose_test88(sys_id):
    """Composite per locked methodology (2026-05-02 audit). Every (paper, field) gold
    cell processed with proper null handling. Does NOT trigger LLM-judge calls —
    Tier 2 non-null/non-null cells use cached judge_lookup; null-handling is local."""
    sdir = STRATEGY_DIRS.get(sys_id)
    if sdir is None or not sdir.exists():
        return None, 0, 0

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
                continue  # correct-null → skip
            else:
                rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': 0.0})  # hallucination
            continue

        # Real gold value present
        if fid in TIER1:
            # Tier 1 is rule-based, no LLM call — safe to use score_field directly
            r = score_field(cand, g['gold_value'], fid)
            if r['skipped']:
                continue
            rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': r['score']})
        elif fid in LONG_TEXT_RAI_FIELDS:
            if cand_empty:
                rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': 0.0})  # miss
            else:
                jscore = judge_lookup.get((g['paper_id'], fid))
                if jscore is not None:
                    rows.append({'paper_id': g['paper_id'], 'field_id': fid, 'score': jscore})

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return None, 0, 0
    pf = df.groupby('field_id')['score'].mean()
    return pf.mean(), pf.shape[0], df['paper_id'].nunique()


# (system_id, display_name, family) — family ∈ {single, agent_v2, agent_lev, gold_seed}
SYSTEMS = [
    # Single-call LLMs (frontier)
    ('claude_sonnet_4_5',  'Claude Sonnet 4.5',          'gold_seed'),
    ('claude_sonnet_4_6',  'Claude Sonnet 4.6',          'single'),
    ('claude_opus_4_7',    'Claude Opus 4.7',            'single'),
    ('gpt5_4_full',        'GPT-5.4',                    'single'),
    ('gpt5_4_mini',        'GPT-5.4 Mini',               'single'),
    ('gemini_3_1_pro',     'Gemini 3.1 Pro',             'single'),
    ('gemini_2_5_flash',   'Gemini 2.5 Flash',           'single'),
    ('deepseek_v3_2',      'DeepSeek V3.2',              'single'),
    ('glm_5_1',            'GLM 5.1',                    'single'),
    # Single-call LLMs (open-weight)
    ('llama4_scout',       'Llama 4 Scout',              'single'),
    ('mistral_small_4',    'Mistral Small 4',            'single'),
    ('qwen3_6_35b_a3b',    'Qwen 3.6 35B',               'single'),
    # Multi-agent extraction (V2)
    ('agentic_v2_sonnet_4_5',         'Multi-agent extraction (Claude Sonnet 4.5)',  'gold_seed'),
    ('agentic_v2_sonnet_4_6_v4',      'Multi-agent extraction (Claude Sonnet 4.6)',  'agent_v2'),
    ('agentic_v2_gpt5_4_full_v4',     'Multi-agent extraction (GPT-5.4)',            'agent_v2'),
    ('agentic_v2_gemini_3_1_pro_v4',  'Multi-agent extraction (Gemini 3.1 Pro)',     'agent_v2'),
    # Locator-extractor (LEV)
    ('agentic_lev_sonnet_4_5',                       'Locator-extractor (Claude Sonnet 4.5)',         'gold_seed'),
    ('agentic_lev_gpt5_4_full',                      'Locator-extractor (GPT-5.4)',                   'agent_lev'),
    ('agentic_lev_gemini_3_1_pro',                   'Locator-extractor (Gemini 3.1 Pro)',            'agent_lev'),
    ('agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3',    'Locator-extractor (Gemini 3.1 Pro + GPT-5.4 Mini)', 'agent_lev'),
    # Multi-agent specialist (Paul)
    ('agentic_specialist_premium_v4',                'Multi-agent specialist (Claude Sonnet 4.6)',  'agent_spec'),
    ('agentic_specialist_mixed_v4',                  'Multi-agent specialist (mixed: GPT-5.4 Mini + Claude Sonnet 4.6)', 'agent_spec'),
    # ReAct (Ahmetcan)
    ('agentic_react_sonnet_4_6_v3',                  'ReAct agent (Claude Sonnet 4.6) [v3]',        'agent_react'),
    ('agentic_react_sonnet_4_6',                     'ReAct agent (Claude Sonnet 4.6) [v1]',        'agent_react'),
    ('agentic_react_ahmetcan_iter5',                 'ReAct agent (Claude Sonnet 4.6) [iter-5: evidence + LLM audit]', 'agent_react'),
    # Locator-extractor (Sonnet × Sonnet)
    ('agentic_lev_sonnet_4_6_sonnet_4_6_v3',         'Locator-extractor (Claude Sonnet 4.6)',       'agent_lev'),
]

FAMILY_LABEL = {
    'single':    'Single-call LLM',
    'agent_v2':  'Multi-agent',
    'agent_lev': 'Locator-extractor',
    'gold_seed': 'Single-call LLM',  # display label; family handled separately for shading
}

rows = []
for sid, label, family in SYSTEMS:
    c, nf, np_ = compose_test88(sid)
    if c is None:
        continue
    # Map display family by SID prefix for the Architecture column
    if sid.startswith('agentic_v2'):
        arch = 'Multi-agent'
    elif sid.startswith('agentic_lev'):
        arch = 'Locator-extractor'
    elif sid.startswith('agentic_specialist'):
        arch = 'Multi-agent specialist'
    elif sid.startswith('agentic_react'):
        arch = 'ReAct agent'
    else:
        arch = 'Single-call LLM'
    rows.append((sid, label, family, arch, c, nf, np_))

rows.sort(key=lambda x: -x[4])

df = pd.DataFrame(rows, columns=['sid', 'label', 'family', 'arch', 'composite', 'n_fields', 'n_papers'])
df['rank'] = range(1, len(df) + 1)

# Render ────────────────────────────────────────────────────────────
n_rows = len(df)
fig_h = 0.36 * (n_rows + 5)
fig_w = 12
fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=160)
ax.axis('off')

title = "Test-88 Evaluation"
subtitle = ("Composite score = equal weight across 30 metadata fields  ·  "
            "Tier 1 (10 fields): rule-based  ·  Tier 2 (20 RAI fields): LLM-judge ensemble (GLM 5)")
fig.text(0.5, 0.965, title, ha='center', va='bottom', fontsize=16, fontweight='bold')
fig.text(0.5, 0.945, subtitle, ha='center', va='bottom', fontsize=9, color='#555')

# Locked metadata: tuning_iters and $/paper per system
META = {
    # single-pass: 0 iters, $/paper from token logs (public list pricing 2026-04)
    'claude_sonnet_4_5':  (0, 0.120),
    'claude_sonnet_4_6':  (0, 0.126),
    'claude_opus_4_7':    (0, 0.803),
    'gpt5_4_full':        (0, 0.164),
    'gpt5_4_mini':        (0, 0.009),
    'gemini_3_1_pro':     (0, 0.043),
    'gemini_2_5_flash':   (0, 0.003),
    'deepseek_v3_2':      (0, 0.009),
    'glm_5_1':            (0, 0.022),
    'llama4_scout':       (0, 0.000),
    'mistral_small_4':    (0, 0.000),
    'qwen3_6_35b_a3b':    (0, 0.000),
    # V2: 5 iter (v1..v5 ablation), best frozen
    'agentic_v2_sonnet_4_5':         (0, 0.110),  # gold-seed reference, no tuning
    'agentic_v2_sonnet_4_6_v4':      (5, 0.201),
    'agentic_v2_gpt5_4_full_v4':     (5, 0.079),
    'agentic_v2_gemini_3_1_pro_v4':  (5, 0.086),
    # LEV
    'agentic_lev_sonnet_4_5':                       (0, 0.069),
    'agentic_lev_gpt5_4_full':                      (0, 0.055),
    'agentic_lev_gemini_3_1_pro':                   (0, 0.054),
    'agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3':    (5, 0.008),
    'agentic_lev_sonnet_4_6_sonnet_4_6_v3':         (5, 0.201),
    # Specialist (Paul)
    'agentic_specialist_premium_v4':  (5, 0.40),
    'agentic_specialist_mixed_v4':    (5, 0.422),
    # ReAct (Ahmetcan)
    'agentic_react_sonnet_4_6':       (5, 0.247),  # v1 frozen per pre-reg
    'agentic_react_sonnet_4_6_v3':    (5, 0.247),  # mean-best dev variant
    'agentic_react_ahmetcan_iter5':   (5, 0.903),  # Ahmetcan's pushed iter-5: evidence_quote + LLM audit
}

cell_data = [
    [
        str(r['rank']),
        r['label'],
        r['arch'],
        f"{r['composite']:.3f}",
        str(r['n_papers']),
        str(META.get(r['sid'], (0, 0))[0]),
        f"${META.get(r['sid'], (0, 0))[1]:.3f}",
    ]
    for _, r in df.iterrows()
]
cols = ['#', 'System', 'Architecture', 'Composite', 'Papers', 'Tuning iters', '$/paper']
col_widths = [0.04, 0.36, 0.16, 0.10, 0.07, 0.09, 0.09]
table = ax.table(
    cellText=cell_data, colLabels=cols, loc='center', cellLoc='left',
    colWidths=col_widths,
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.45)

NAVY = '#1F2A44'
GOLD_TINT  = '#FFE8B0'
V2_TINT    = '#D4F1D4'
LEV_TINT   = '#FFE3CC'
SPEC_TINT  = '#E8DCFB'
REACT_TINT = '#CCE5FF'
ALT_BG     = '#F8F8F8'

# header
for j in range(len(cols)):
    c = table[(0, j)]
    c.set_facecolor(NAVY)
    c.set_text_props(color='white', fontweight='bold')
    c.set_height(0.06)

# body shading
for i, r in df.iterrows():
    ridx = i + 1
    if r['family'] == 'gold_seed':
        color = GOLD_TINT
    elif r['family'] == 'agent_v2':
        color = V2_TINT
    elif r['family'] == 'agent_lev':
        color = LEV_TINT
    elif r['family'] == 'agent_spec':
        color = SPEC_TINT
    elif r['family'] == 'agent_react':
        color = REACT_TINT
    else:
        color = '#FFFFFF' if i % 2 == 0 else ALT_BG
    for j in range(len(cols)):
        table[(ridx, j)].set_facecolor(color)
    # Centre-align Architecture / Composite / Papers; bold composite for top-3 non-seed
    table[(ridx, 0)]._loc = 'center'
    if r['family'] != 'gold_seed':
        non_seed_rank = sum(1 for k in range(i + 1) if df.iloc[k]['family'] != 'gold_seed')
        if non_seed_rank <= 3:
            table[(ridx, 3)].set_text_props(fontweight='bold')

# legend / footnotes
legend = [
    "Shading:  gold = reference systems built on Claude Sonnet 4.5 (also the source of the gold annotations; not directly comparable)",
    "          green = multi-agent extraction   ·   orange = locator-extractor   ·   purple = multi-agent specialist",
    "Notes:    Gemini 3.1 Pro multi-agent run covers 33 of 88 papers (Google API quota) — partial figure.",
    "          Locator-extractor underperforms the same backbone used as a single call across all four configurations.",
]
fig.text(0.04, 0.02, '\n'.join(legend), fontsize=8.5, color='#333', va='bottom')
plt.subplots_adjust(top=0.92, bottom=0.16, left=0.04, right=0.98)

out = ROOT / 'docs/eval_table_final_2026-05-02.png'
fig.savefig(out, dpi=160, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
