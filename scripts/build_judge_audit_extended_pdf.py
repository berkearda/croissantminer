"""Build the extended Mubashara-facing judge-audit PDF.

Combines Round 1 (gap-driving cells) and Round 2 (full Tier-2 coverage) into
one report. Shows: per-system bias rates across ALL 5 systems including
Sonnet 4.5, system-vs-system gap matrices (current vs bias-fixed), Tier-2
projections, top examples, prompt-fix recommendations.
"""
import json, html, datetime, os
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path('croissantminer')
NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def esc(s): return html.escape(str(s) if s is not None else '')
def truncate(s, n=2000):
    s = str(s) if s is not None else ''
    return s if len(s) <= n else s[:n] + ' …'

# === Load all audit records (both rounds) ===
all_records = []
for round_dir in ['/tmp/judge_audit', '/tmp/judge_audit2']:
    for i in range(1, 9):
        p = f'{round_dir}/proposals_{i}.json'
        if os.path.exists(p):
            with open(p) as f:
                all_records.extend(json.load(f)['records'])

# === Load Round 1 batch payloads (for top examples) ===
all_payloads = {}
for round_dir in ['/tmp/judge_audit', '/tmp/judge_audit2']:
    for i in range(1, 9):
        p = f'{round_dir}/batch_{i}.json'
        if os.path.exists(p):
            with open(p) as f:
                for r in json.load(f)['records']:
                    all_payloads[(r['paper_id'], r['field_id'], r['system'])] = r

# Stitch
detailed = []
for r in all_records:
    k = (r['paper_id'], r['field_id'], r['system'])
    if k in all_payloads:
        detailed.append({**all_payloads[k], **r})

# === Per-system stats ===
sys_v1 = defaultdict(Counter)
sys_v2 = defaultdict(Counter)
for r in all_records:
    sys_v1[r['system']][r['v1_verdict']] += 1
    sys_v2[r['system']][r['v2min_verdict']] += 1

# === Projections ===
proj = json.load(open('/tmp/judge_audit2/projections.json'))['tier2_per_system']

# === Top examples (Round 1) ===
biased_v1_harsh = [d for d in detailed if d.get('v1_verdict') == 'JUDGE_BIASED' and d.get('v1_score') in (2,3)]
def sort_key(d):
    v2_correct = (d.get('v2min_score') == 1)
    ext_len = len(d.get('system_extraction',''))
    return (-int(v2_correct), -ext_len)
biased_v1_harsh.sort(key=sort_key)

# Stratified pick: 24 examples across 4 non-4.5 systems × ~6 fields
TOP_TARGETS = ['claude_sonnet_4_6','claude_opus_4_7','agentic_react_sonnet_4_6_v3','agentic_v2_sonnet_4_5']
top_examples = []
sys_picked, field_picked = Counter(), Counter()
for d in biased_v1_harsh:
    if sum(sys_picked.values()) >= 24: break
    if sys_picked[d['system']] >= 6: continue
    if field_picked[d['field_id']] >= 4: continue
    top_examples.append(d)
    sys_picked[d['system']] += 1
    field_picked[d['field_id']] += 1

# === Lenient examples: judge said Correct but agent said BIASED ===
lenient_v2 = [d for d in detailed if d.get('v2min_verdict') == 'JUDGE_BIASED' and d.get('v2min_score') == 1]
lenient_v2.sort(key=lambda d: -len(d.get('system_extraction','')))
lenient_picked = []
lp_sys = Counter()
for d in lenient_v2:
    if len(lenient_picked) >= 8: break
    if lp_sys[d['system']] >= 3: continue
    lenient_picked.append(d)
    lp_sys[d['system']] += 1

# === Pattern tags ===
tag_counts = Counter(r.get('shared_pattern_tag') for r in all_records)

# === Distinct prompt problems (from both rounds) ===
all_problems = []
for round_dir in ['/tmp/judge_audit', '/tmp/judge_audit2']:
    for i in range(1, 9):
        p = f'{round_dir}/proposals_{i}.json'
        if os.path.exists(p):
            with open(p) as f:
                all_problems.extend(json.load(f).get('prompt_problems_observed', []))

distinct_probs = []
seen = set()
for p in all_problems:
    key = ' '.join(p.lower().split()[:6])
    if key in seen: continue
    seen.add(key)
    distinct_probs.append(p)
    if len(distinct_probs) >= 25: break

# === Build HTML ===
SYSTEMS = ['claude_sonnet_4_5','claude_sonnet_4_6','claude_opus_4_7',
           'agentic_react_sonnet_4_6_v3','agentic_v2_sonnet_4_5']

# Per-system table
sys_rows = []
for s in SYSTEMS:
    c1 = sys_v1[s]; c2 = sys_v2[s]
    n = sum(c1.values())
    sys_rows.append(f"<tr><td>{s}</td><td>{n}</td>"
                    f"<td>{c1['JUDGE_BIASED']} ({100*c1['JUDGE_BIASED']/n:.1f}%)</td>"
                    f"<td>{c2['JUDGE_BIASED']} ({100*c2['JUDGE_BIASED']/n:.1f}%)</td>"
                    f"<td>{c1['JUDGE_CORRECT']}</td>"
                    f"<td>{c1['UNCLEAR']}</td></tr>")
sys_table = f"""<table>
<thead><tr><th>System</th><th>n cells</th><th>v1 BIASED</th><th>v2min BIASED</th><th>v1 CORRECT</th><th>v1 UNCLEAR</th></tr></thead>
<tbody>{''.join(sys_rows)}</tbody></table>"""

# Tier-2 projection table
proj_rows = []
for s in SYSTEMS:
    p = proj[s]
    proj_rows.append(f"<tr><td>{s}</td>"
                     f"<td>{p['v1_curr']:.3f}</td>"
                     f"<td>{p['v1_bias_fixed']:.3f} (+{p['v1_bias_fixed']-p['v1_curr']:.3f})</td>"
                     f"<td>{p['v1_unclear_fixed']:.3f} (+{p['v1_unclear_fixed']-p['v1_curr']:.3f})</td>"
                     f"<td>{p['v2_curr']:.3f}</td>"
                     f"<td>{p['v2_bias_fixed']:.3f} (+{p['v2_bias_fixed']-p['v2_curr']:.3f})</td>"
                     f"<td>{p['v2_unclear_fixed']:.3f} (+{p['v2_unclear_fixed']-p['v2_curr']:.3f})</td></tr>")
proj_table = f"""<table>
<thead>
<tr><th rowspan="2">System</th><th colspan="3">v1 Tier-2 mean</th><th colspan="3">v2min Tier-2 mean</th></tr>
<tr><th>current</th><th>BIASED→Correct</th><th>+UNCLEAR→Correct</th><th>current</th><th>BIASED→Correct</th><th>+UNCLEAR→Correct</th></tr>
</thead>
<tbody>{''.join(proj_rows)}</tbody></table>"""

# Gap matrix (current v1)
def gap_table(key):
    rows = ['<tr><th>From \\ To</th>' + ''.join(f"<th>{s.replace('agentic_','').replace('claude_','')[:18]}</th>" for s in SYSTEMS) + '</tr>']
    for s1 in SYSTEMS:
        cells = [f"<td><b>{s1.replace('agentic_','').replace('claude_','')[:18]}</b></td>"]
        for s2 in SYSTEMS:
            gap = proj[s1][key] - proj[s2][key]
            color = '#1F2937'
            if abs(gap) > 0.05: color = '#dc2626' if gap < 0 else '#16a34a'
            cells.append(f"<td style='color:{color}'>{gap:+.3f}</td>")
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    return '<table class="gap-matrix">' + ''.join(rows) + '</table>'

curr_gap = gap_table('v1_curr')
fixed_gap = gap_table('v1_bias_fixed')

# Pattern tags
pat_rows = ''.join(f"<tr><td>{t}</td><td>{n}</td></tr>" for t, n in tag_counts.most_common(20))
pat_table = f"<table><thead><tr><th>Pattern tag</th><th>Count</th></tr></thead><tbody>{pat_rows}</tbody></table>"

probs_html = '<ul>' + ''.join(f"<li>{esc(p)}</li>" for p in distinct_probs) + '</ul>'

# Examples
def ex_html(ex, badge='HARSH BIAS'):
    return f"""<div class="example">
<div class="ex-head">[{badge}] {esc(ex['paper_id'])} / {esc(ex['field_id'])} — system: <code>{esc(ex['system'])}</code></div>
<div class="ex-row"><div class="lbl">Gold (reference)</div><div class="text">{esc(truncate(ex.get('gold','')))}</div></div>
<div class="ex-row"><div class="lbl">Sonnet 4.5 extraction</div><div class="text">{esc(truncate(ex.get('sonnet_4_5_extraction','')))}</div></div>
<div class="ex-row"><div class="lbl">{esc(ex['system'])} extraction (audit verdict: {esc(ex.get('v1_verdict'))})</div><div class="text">{esc(truncate(ex.get('system_extraction','')))}</div></div>
<table class="judge-table">
<thead><tr><th>Judge</th><th>Score</th><th>Reason</th></tr></thead>
<tbody>
<tr><td><b>v1 (production)</b></td><td>{esc(ex.get('v1_score'))}</td><td>{esc(truncate(ex.get('v1_reason'), 600))}</td></tr>
<tr><td><b>v2min</b></td><td>{esc(ex.get('v2min_score'))}</td><td>{esc(truncate(ex.get('v2min_reason'), 600))}</td></tr>
</tbody></table>
<div class="audit-row">
<b>Audit (v1):</b> {esc(ex.get('v1_verdict'))} — {esc(ex.get('v1_rationale'))}<br>
<b>Audit (v2min):</b> {esc(ex.get('v2min_verdict'))} — {esc(ex.get('v2min_rationale'))}<br>
<b>Pattern:</b> <code>{esc(ex.get('shared_pattern_tag'))}</code>
</div>
</div>"""

harsh_section = '\n'.join(ex_html(e, 'HARSH') for e in top_examples)
lenient_section = '\n'.join(ex_html(e, 'LENIENT') for e in lenient_picked)

html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>CroissantMiner Judge-Bias Audit (Extended) — {NOW}</title>
<style>
@page {{ size: A4; margin: 14mm; }}
body {{ font-family: "Source Serif Pro", "Georgia", serif; font-size: 9.5pt; line-height: 1.4; color: #1F2937; }}
h1 {{ color: #0F2D4F; font-size: 16pt; border-bottom: 2px solid #C19A49; padding-bottom: 3mm; }}
h2 {{ color: #0F2D4F; font-size: 12pt; margin-top: 8mm; border-bottom: 1px solid #ccc; padding-bottom: 1mm; }}
h3 {{ color: #0F2D4F; font-size: 10.5pt; margin-top: 5mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9pt; }}
th {{ background: #F5F1E8; color: #0F2D4F; padding: 1.5mm 3mm; border: 0.5px solid #aaa; text-align: left; }}
td {{ padding: 1.5mm 3mm; border: 0.5px solid #ddd; vertical-align: top; }}
.gap-matrix td, .gap-matrix th {{ font-family: "JetBrains Mono", monospace; font-size: 8pt; text-align: center; }}
.summary {{ background: #F5F1E8; padding: 4mm; border-left: 3px solid #C19A49; margin: 3mm 0; font-size: 9.5pt; }}
.example {{ border: 1px solid #aaa; border-radius: 2mm; margin: 6mm 0; padding: 4mm; page-break-inside: avoid; }}
.ex-head {{ font-family: "JetBrains Mono", monospace; font-size: 9.5pt; color: #0F2D4F; font-weight: 700; margin-bottom: 2mm; }}
.ex-row {{ margin: 2mm 0; }}
.lbl {{ font-size: 8pt; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1mm; }}
.text {{ font-size: 9pt; padding: 1.5mm 3mm; background: #F9FAFB; border-left: 2px solid #ccc; }}
.judge-table {{ font-size: 8.5pt; }}
.judge-table td {{ font-family: "JetBrains Mono", monospace; font-size: 8pt; }}
.audit-row {{ margin-top: 3mm; padding: 2mm 3mm; background: #FEF3C7; border-left: 3px solid #F59E0B; font-size: 8.5pt; }}
code {{ font-family: "JetBrains Mono", monospace; font-size: 8.5pt; background: #f0f0f0; padding: 0.5mm 1.5mm; border-radius: 1mm; }}
ul li {{ margin-bottom: 1.5mm; font-size: 9pt; }}
</style></head><body>
<h1>CroissantMiner Judge-Bias Audit Report (Extended)</h1>
<p><i>Generated {NOW} — based on <b>{len(all_records)} (system, cell) judgments</b> across 5 systems × 88 papers × 20 Tier-2 fields, executed by 16 parallel Opus 4.7 agents over 2 rounds.</i></p>

<div class="summary">
<b>Headline finding:</b> The v1 (production) GLM-5 judge prompt unfairly penalises <b>7.4% of all Tier-2 cells</b> across the four target systems (HARSH bias rate). On the gap-driving cells specifically (where Sonnet 4.5 was Correct but others weren't), the v1 HARSH bias rate is <b>29.1%</b>. The v2min (paraphrase-permissive) variant is much fairer overall (1.5% bias rate) but trades the harsh bias for occasional <b>over-leniency</b> on factually-incomplete extractions. Critically, Sonnet 4.5 itself has the lowest v1 bias rate (0.45%) — confirming the judge prompt is implicitly tuned to Sonnet-4.5-style phrasing.
</div>

<h2>1. Audit scope</h2>
<ul>
<li><b>Round 1:</b> 1,390 gap-driving cells (Sonnet 4.5 = Correct AND any of 4 target systems ≤ Partial). 8 parallel Opus agents.</li>
<li><b>Round 2:</b> 4,450 remaining cells across all 5 systems, including Sonnet 4.5 self-judgments and cells where target systems scored Correct (to catch over-lenient bias). 8 parallel Opus agents.</li>
<li><b>Total:</b> 5,840 (system, cell) judgments — <b>full coverage of every judged Tier-2 cell across the 5 key systems on test-88</b>.</li>
</ul>

<h2>2. Per-system bias rates (full corpus)</h2>
{sys_table}
<p><b>Key observation:</b> Sonnet 4.5 has 22× lower v1 bias rate (0.45%) than Sonnet 4.6 (10.18%). The judge is tuned to Sonnet-4.5-style content even after we corrected the gold values. The 4 target systems all have v1 bias rates between 7.5% and 10.2% — suggesting the bias is systematic, not driven by any one system's output style.</p>

<h2>3. Tier-2 projections per system</h2>
<p>If JUDGE_BIASED cells were rescored as Correct, Tier-2 means would shift as follows:</p>
{proj_table}
<p>Under v1, fixing biased cells alone gains: Sonnet 4.6 +5.1pp, Opus +4.8pp, ReAct +3.6pp, V2-4.5 +4.1pp. If we also resolve UNCLEAR cells in favor of the systems, the gains roughly double. Sonnet 4.5 barely moves either way (+0.2pp), confirming the bias is target-system-specific.</p>

<h2>4. System-vs-system gap matrix (Tier-2)</h2>
<p>Each cell shows row's mean − column's mean. Positive = row scores higher.</p>
<h3>Current (under v1)</h3>
{curr_gap}
<h3>If JUDGE_BIASED → Correct (under v1)</h3>
{fixed_gap}
<p>The 4.5 ↔ 4.6 gap shrinks from <b>+0.256 → +0.207</b> (-19% of gap) just from fixing biased cells. The 4.5 ↔ Opus gap shrinks from +0.205 → +0.159 (-22%). Internally, Opus and ReAct become essentially tied with 4.6 (within ±0.05), meaning the perceived ordering of non-seed systems is unstable under judge-bias correction.</p>

<h2>5. Top systematic patterns observed across both rounds</h2>
{pat_table}

<h2>6. Distilled prompt problems</h2>
{probs_html}

<h2>7. Recommended prompt fixes</h2>
<ul>
<li><b>v1 — add explicit superset clause:</b> "If the candidate restates the reference's content AND adds further on-topic detail consistent with the field, score Correct. Do not penalise additions that are substantively aligned with the field."</li>
<li><b>v1 — clarify substance vs detail:</b> "Score on substantive equivalence, not exact-content overlap. Missing peripheral numbers or citations does not by itself drop a candidate to Partial."</li>
<li><b>v1 — separate enum-field rubric:</b> Multi-value enum fields (dataCollectionType, etc.) should use set-membership scoring: Correct if candidate's set is a superset of gold's; Partial if a strict subset; Wrong if disjoint or contradictory.</li>
<li><b>Both — handle NULL gold properly:</b> When gold is `[NULL ...]`, allow Correct verdict for either (a) candidate is also null/empty, OR (b) candidate explicitly states the field doesn't apply or wasn't found. Currently both prompts force Wrong on any non-null candidate against null gold.</li>
<li><b>v2min — add central-claim presence check:</b> "Even when surface form matches, mark Partial if the candidate omits the central claim or a quantitative anchor of the reference. Paraphrase tolerance does not extend to dropped key facts."</li>
<li><b>v2min — add factual-additions provenance check:</b> "Mark Partial if the candidate adds factual content (specific numbers, names, URLs) not present in the reference; only stylistic/connective additions are acceptable."</li>
<li><b>Both — fix JSON parse fragility:</b> Currently bare arrays like `[1]` cause silent None scores. Either harden the parser or add a one-shot example in the prompt enforcing object output.</li>
<li><b>Both — anchor 1/2/3 to claim count:</b> "Score 1 if all central claims of the reference are captured. Score 2 if some central claims missing or detail loss is moderate. Score 3 if most central claims missing, contradicted, or off-topic."</li>
</ul>

<h2>8. Top 24 worst v1 HARSH bias examples</h2>
<p>v1 marked Partial/Wrong but agent audit found the extraction substantively equivalent to gold. Stratified across 4 target systems and ~6 fields. Each example shows gold + 4.5's extraction (which scored Correct) + target system's extraction + both judges' scores+reasons + audit verdict.</p>
{harsh_section}

<h2>9. Top 8 v2min LENIENT bias examples</h2>
<p>v2min marked Correct but agent audit found the extraction missing key gold content or contradicting it. These show the opposite failure mode: v2min's paraphrase tolerance occasionally accepts substantively-incomplete extractions.</p>
{lenient_section}

<hr>
<p><i>Generated by 16-agent Opus 4.7 audit, 2026-05-04. Source: /tmp/judge_audit/proposals_*.json + /tmp/judge_audit2/proposals_*.json. Headline projections: data/judged/judge_scores_glm_5.parquet (corrected gold).</i></p>
</body></html>
"""

out_html = ROOT / 'docs/CroissantMiner_JudgeBiasAudit_Extended_2026-05-04.html'
out_html.write_text(html_doc)
print(f"HTML written: {out_html}  ({len(html_doc):,} bytes)")
