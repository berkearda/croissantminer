#!/usr/bin/env python3
"""Build cost-quality Pareto figure for §5.4.

Scatter: x = USD/paper (log scale), y = test-88 composite (judge GLM-5).
Color/marker by family (single-pass / V2 / LEV / Specialist / ReAct).
Pareto frontier traced; non-frontier points faded.

Output: docs/fig_cost_quality_pareto_2026-05-02.png
"""

from __future__ import annotations

import json, sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.field_metrics import (CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, score_field)
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS

# Composites already computed; just hard-code the test-88 numbers we have.
# Composites updated 2026-05-03 after encoded-null + miss-zero audit fix.
SYSTEMS = [
    # (sys_id, label, family, cost/paper, composite, gold_seed)
    ('claude_sonnet_4_5',                  'Sonnet 4.5',                 'single',     0.120, 0.909, True),
    ('claude_sonnet_4_6',                  'Sonnet 4.6',                 'single',     0.126, 0.626, False),
    ('claude_opus_4_7',                    'Opus 4.7',                   'single',     0.803, 0.604, False),
    ('gpt5_4_full',                        'GPT-5.4',                    'single',     0.164, 0.590, False),
    ('gpt5_4_mini',                        'GPT-5.4 Mini',               'single',     0.009, 0.513, False),
    ('gemini_3_1_pro',                     'Gemini 3.1 Pro',             'single',     0.043, 0.512, False),
    ('gemini_2_5_flash',                   'Gemini 2.5 Flash',           'single',     0.003, 0.548, False),
    ('deepseek_v3_2',                      'DeepSeek V3.2',              'single',     0.009, 0.506, False),
    ('glm_5_1',                            'GLM 5.1',                    'single',     0.022, 0.547, False),
    ('llama4_scout',                       'Llama 4 Scout',              'open',       0.000, 0.356, False),
    ('mistral_small_4',                    'Mistral Small 4',            'open',       0.000, 0.469, False),
    ('qwen3_6_35b_a3b',                    'Qwen 3.6 35B',               'open',       0.000, 0.552, False),
    # V2
    ('agentic_v2_sonnet_4_5',              'V2 × Sonnet 4.5',            'v2',         0.110, 0.624, True),
    ('agentic_v2_sonnet_4_6_v4',           'V2 × Sonnet 4.6 [v4]',       'v2',         0.201, 0.555, False),
    ('agentic_v2_gpt5_4_full_v4',          'V2 × GPT-5.4 [v4]',          'v2',         0.079, 0.494, False),
    ('agentic_v2_gemini_3_1_pro_v4',       'V2 × Gemini 3.1 Pro [v4]',   'v2',         0.086, 0.399, False),
    # LEV
    ('agentic_lev_sonnet_4_5',             'LEV × Sonnet 4.5',           'lev',        0.069, 0.509, True),
    ('agentic_lev_gpt5_4_full',            'LEV × GPT-5.4',              'lev',        0.055, 0.463, False),
    ('agentic_lev_gemini_3_1_pro',         'LEV × Gemini 3.1 Pro',       'lev',        0.054, 0.260, False),
    ('agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3', 'LEV × Gemini × GPT-Mini',  'lev', 0.008, 0.365, False),
    ('agentic_lev_sonnet_4_6_sonnet_4_6_v3', 'LEV × Sonnet 4.6',         'lev',        0.201, 0.498, False),
    # Specialist
    ('agentic_specialist_premium_v4',      'Specialist (Sonnet 4.6)',    'spec',       0.40,  0.575, False),
    ('agentic_specialist_mixed_v4',        'Specialist (mixed)',         'spec',       0.422, 0.561, False),
    # ReAct
    ('agentic_react_sonnet_4_6',           'ReAct (Sonnet 4.6) [v1]',    'react',      0.247, 0.596, False),
    ('agentic_react_sonnet_4_6_v3',        'ReAct (Sonnet 4.6) [v3]',    'react',      0.247, 0.602, False),
    ('agentic_react_ahmetcan_iter5',       'ReAct (Sonnet 4.6) [iter-5]', 'react',     0.903, 0.571, False),
]

FAMILY_STYLE = {
    'single': dict(color='#1F77B4', marker='o',  label='Single-call frontier'),
    'open':   dict(color='#2CA02C', marker='s',  label='Single-call open-weight'),
    'v2':     dict(color='#9467BD', marker='^',  label='Multi-agent extraction (V2)'),
    'lev':    dict(color='#FF7F0E', marker='D',  label='Locator-extractor (LEV)'),
    'spec':   dict(color='#8C564B', marker='P',  label='Multi-agent specialist'),
    'react':  dict(color='#E377C2', marker='*',  label='ReAct agent'),
}


def pareto_frontier(points):
    """Given list of (x, y) sorted by x asc, return frontier points (max y so far)."""
    pts = sorted(points, key=lambda p: p[0])
    frontier = []
    best_y = -np.inf
    for x, y, idx in pts:
        if y > best_y:
            frontier.append((x, y, idx))
            best_y = y
    return frontier


def main():
    df = pd.DataFrame(SYSTEMS, columns=['sid', 'label', 'family', 'cost', 'composite', 'gold_seed'])
    df = df[df['composite'].notna()]

    fig, ax = plt.subplots(figsize=(11, 7), dpi=160)

    # Build Pareto frontier from non-gold-seed systems only
    non_seed = df[~df['gold_seed']].reset_index(drop=True)
    pts = [(r['cost'], r['composite'], i) for i, r in non_seed.iterrows()]
    front = pareto_frontier(pts)
    front_idx = {f[2] for f in front}
    front_xy = sorted([(f[0], f[1]) for f in front], key=lambda p: p[0])

    # Plot frontier as step-line
    if front_xy:
        xs = [front_xy[0][0]] + [p[0] for p in front_xy]
        ys = [front_xy[0][1]] + [p[1] for p in front_xy]
        ax.plot([p[0] for p in front_xy], [p[1] for p in front_xy], '--', color='#444', lw=1.0,
                alpha=0.7, label='Pareto frontier (non-seed)', zorder=1)

    # Scatter
    for fam, style in FAMILY_STYLE.items():
        sub = df[df['family'] == fam]
        if len(sub) == 0: continue
        for _, r in sub.iterrows():
            x = max(r['cost'], 0.0005)  # plot $0 systems at $0.0005 for log-scale
            edge = 'gold' if r['gold_seed'] else 'black'
            zorder = 4 if r['gold_seed'] else 3
            ax.scatter(x, r['composite'], color=style['color'], marker=style['marker'],
                       s=180, edgecolors=edge, linewidths=1.5 if r['gold_seed'] else 0.6,
                       alpha=0.95, zorder=zorder)
            # Label every system, with offset adjustment for crowded points
            ax.annotate(r['label'], (x, r['composite']), xytext=(8, 4),
                        textcoords='offset points', fontsize=8, color='#333', alpha=0.9)

    # Legend handles
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], marker=s['marker'], color='w', markerfacecolor=s['color'],
               markersize=10, label=s['label']) for s in FAMILY_STYLE.values()
    ]
    legend_handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                                  markersize=10, markeredgecolor='gold', markeredgewidth=2,
                                  label='Gold-seed reference (excluded from frontier)'))
    legend_handles.append(Line2D([0], [0], color='#444', lw=1.0, ls='--',
                                  label='Pareto frontier'))
    ax.legend(handles=legend_handles, loc='lower right', fontsize=9, frameon=True)

    ax.set_xscale('log')
    ax.set_xlabel('USD / paper (log scale; $0 self-hosted plotted at $0.0005)', fontsize=11)
    ax.set_ylabel('Test-88 composite score (judge GLM-5)', fontsize=11)
    ax.set_title('Cost vs. Quality Pareto: 25 extraction systems on the held-out 88 papers',
                 fontsize=13, fontweight='bold', pad=10)
    ax.grid(True, which='both', alpha=0.25)

    out = ROOT / 'docs' / 'fig_cost_quality_pareto_2026-05-02.png'
    out_pdf = ROOT / 'paper' / 'overleaf' / 'figures' / 'cost_quality_pareto.pdf'
    fig.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches='tight', facecolor='white')
    fig.savefig(out_pdf, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)')
    print(f'wrote {out_pdf.relative_to(ROOT)} ({out_pdf.stat().st_size // 1024} KB)')

    # Print frontier
    print('\nPareto frontier (non-seed):')
    for x, y, idx in front:
        r = non_seed.iloc[idx]
        print(f'  ${x:>7.3f}/paper  comp={y:.3f}  {r["label"]}')


if __name__ == '__main__':
    main()
