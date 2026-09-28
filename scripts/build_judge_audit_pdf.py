"""Build the Mubashara-facing judge-bias-audit PDF (HTML → wkhtmltopdf or chrome).

Reads /tmp/judge_audit/deliverable.json and renders an HTML report with:
- Executive summary + headline impact on the 4.5↔target gap.
- Per-system bias rates table.
- Top pattern tags + prompt-problem observations.
- 20 worst v1 bias examples with full extractions + judge reasons + audit verdict.
"""
import json, html, datetime
from pathlib import Path

D = json.load(open('/tmp/judge_audit/deliverable.json'))
NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def esc(s):
    return html.escape(str(s) if s is not None else '')

def truncate(s, n=2000):
    s = str(s) if s is not None else ''
    return s if len(s) <= n else s[:n] + ' …'

# Tier-2-only projection table values (from the previous Bash run)
GAP_TABLE = """
<table>
<thead>
<tr><th>System</th><th>Tier-2 mean (current)</th><th>If JUDGE_BIASED→Correct</th><th>If +UNCLEAR→Correct</th><th># biased</th><th># unclear</th></tr>
</thead>
<tbody>
<tr><td>Sonnet 4.5 (gold-seed)</td><td>0.917</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Sonnet 4.6</td><td>0.661</td><td>0.709 (+0.048)</td><td>0.751 (+0.090)</td><td>126</td><td>112</td></tr>
<tr><td>Opus 4.7</td><td>0.712</td><td>0.759 (+0.047)</td><td>0.811 (+0.099)</td><td>109</td><td>118</td></tr>
<tr><td>ReAct Sonnet 4.6 v3</td><td>0.715</td><td>0.750 (+0.035)</td><td>0.789 (+0.074)</td><td>77</td><td>83</td></tr>
<tr><td>V2 × Sonnet 4.5</td><td>0.699</td><td>0.740 (+0.041)</td><td>0.796 (+0.097)</td><td>92</td><td>132</td></tr>
</tbody>
</table>
<p><b>v1 gap (4.5 − Sonnet 4.6):</b> currently 0.256 → 0.208 if biased fixed (−19% gap)
→ 0.166 if +UNCLEAR fixed (−35% gap).</p>
"""

# Per-system table from JSON
sys_rows = []
for s, st in D['per_system_stats'].items():
    sys_rows.append(f"<tr><td>{s}</td><td>{st['n']}</td>"
                    f"<td>{st['v1_BIASED']} ({st['v1_BIASED_%']}%)</td>"
                    f"<td>{st['v2min_BIASED']} ({st['v2min_BIASED_%']}%)</td>"
                    f"<td>{st['v1_CORRECT']}</td><td>{st['v1_UNCLEAR']}</td></tr>")
sys_table = f"""
<table>
<thead><tr><th>System</th><th>n cells audited</th><th>v1 BIASED</th><th>v2min BIASED</th><th>v1 CORRECT</th><th>v1 UNCLEAR</th></tr></thead>
<tbody>{''.join(sys_rows)}</tbody>
</table>
"""

# Pattern tags
pat_rows = ''.join(f"<tr><td>{t}</td><td>{n}</td></tr>" for t, n in D['top_pattern_tags'].items())
pat_table = f"<table><thead><tr><th>Pattern tag</th><th>Count</th></tr></thead><tbody>{pat_rows}</tbody></table>"

# Distinct prompt problems (dedupe similar)
all_probs = D['all_prompt_problems_observed']
# Cluster manually — show top 15 most informative
distinct_probs = []
seen_keywords = set()
for p in all_probs:
    p_low = p.lower()
    # take first 5 words as key
    key = ' '.join(p_low.split()[:6])
    if key in seen_keywords: continue
    seen_keywords.add(key)
    distinct_probs.append(p)
    if len(distinct_probs) >= 20: break

probs_html = '<ul>' + ''.join(f"<li>{esc(p)}</li>" for p in distinct_probs) + '</ul>'

# Examples
examples_html = []
for i, ex in enumerate(D['top_examples'], 1):
    examples_html.append(f"""
<div class="example">
  <div class="ex-head">[{i}] {esc(ex['paper_id'])} / {esc(ex['field_id'])} — system: <code>{esc(ex['system'])}</code></div>
  <div class="ex-row"><div class="lbl">Gold</div><div class="text">{esc(truncate(ex['gold']))}</div></div>
  <div class="ex-row"><div class="lbl">Sonnet 4.5 extraction (scored Correct)</div><div class="text">{esc(truncate(ex['sonnet_4_5_extraction']))}</div></div>
  <div class="ex-row"><div class="lbl">{esc(ex['system'])} extraction (audited as JUDGE_BIASED)</div><div class="text">{esc(truncate(ex['system_extraction']))}</div></div>
  <table class="judge-table">
    <thead><tr><th>Judge</th><th>Score</th><th>Reason</th></tr></thead>
    <tbody>
      <tr><td><b>v1 (production)</b></td><td>{esc(ex.get('v1_score'))}</td><td>{esc(truncate(ex.get('v1_reason'), 600))}</td></tr>
      <tr><td><b>v2min</b></td><td>{esc(ex.get('v2min_score'))}</td><td>{esc(truncate(ex.get('v2min_reason'), 600))}</td></tr>
    </tbody>
  </table>
  <div class="audit-row">
    <b>Audit verdict (v1):</b> {esc(ex.get('v1_verdict'))} — {esc(ex.get('v1_rationale'))}<br>
    <b>Audit verdict (v2min):</b> {esc(ex.get('v2min_verdict'))} — {esc(ex.get('v2min_rationale'))}<br>
    <b>Pattern tag:</b> <code>{esc(ex.get('shared_pattern_tag'))}</code>
  </div>
</div>
""")
examples_section = '\n'.join(examples_html)

html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CroissantMiner Judge-Bias Audit — {NOW}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  body {{ font-family: "Source Serif Pro", "Georgia", "Times New Roman", serif; font-size: 9.5pt; line-height: 1.4; color: #1F2937; }}
  h1 {{ color: #0F2D4F; font-size: 16pt; border-bottom: 2px solid #C19A49; padding-bottom: 3mm; }}
  h2 {{ color: #0F2D4F; font-size: 12pt; margin-top: 8mm; border-bottom: 1px solid #ccc; padding-bottom: 1mm; }}
  h3 {{ color: #0F2D4F; font-size: 10.5pt; margin-top: 5mm; }}
  table {{ border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9pt; }}
  th {{ background: #F5F1E8; color: #0F2D4F; padding: 1.5mm 3mm; border: 0.5px solid #aaa; text-align: left; }}
  td {{ padding: 1.5mm 3mm; border: 0.5px solid #ddd; vertical-align: top; }}
  .summary {{ background: #F5F1E8; padding: 4mm; border-left: 3px solid #C19A49; margin: 3mm 0; font-size: 9.5pt; }}
  .example {{ border: 1px solid #aaa; border-radius: 2mm; margin: 6mm 0; padding: 4mm; page-break-inside: avoid; }}
  .ex-head {{ font-family: "JetBrains Mono", "Menlo", monospace; font-size: 9.5pt; color: #0F2D4F; font-weight: 700; margin-bottom: 2mm; }}
  .ex-row {{ margin: 2mm 0; }}
  .lbl {{ font-size: 8pt; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1mm; }}
  .text {{ font-size: 9pt; padding: 1.5mm 3mm; background: #F9FAFB; border-left: 2px solid #ccc; }}
  .judge-table {{ font-size: 8.5pt; }}
  .judge-table td {{ font-family: "JetBrains Mono", "Menlo", monospace; font-size: 8pt; }}
  .audit-row {{ margin-top: 3mm; padding: 2mm 3mm; background: #FEF3C7; border-left: 3px solid #F59E0B; font-size: 8.5pt; }}
  code {{ font-family: "JetBrains Mono", "Menlo", monospace; font-size: 8.5pt; background: #f0f0f0; padding: 0.5mm 1.5mm; border-radius: 1mm; }}
  ul li {{ margin-bottom: 1.5mm; font-size: 9pt; }}
</style>
</head>
<body>
<h1>CroissantMiner Judge-Bias Audit Report</h1>
<p><i>Generated {NOW} — based on {D['total_audited']} (system, cell) judgments by 8 parallel Opus 4.7 agents.</i></p>

<div class="summary">
<b>Headline finding:</b> The v1 (production) GLM-5 judge prompt unfairly penalises ~29% of audited gap-cells — extractions that are substantively equivalent to gold get scored Partial/Wrong. v2min (paraphrase-permissive variant) only mis-scores ~5%, but it has the opposite bias (occasionally too lenient on incomplete content). Together with the gold corrections applied earlier today, fixing the v1 bias would close another <b>19-35%</b> of the 4.5↔Sonnet-4.6 gap.
</div>

<h2>1. Projected impact on the headline gap</h2>
<p>If JUDGE_BIASED cells were rescored as Correct under v1, Tier-2 means would shift as follows:</p>
{GAP_TABLE}

<h2>2. Per-system bias rates</h2>
{sys_table}
<p>Sonnet 4.6 has the highest v1 bias (35.6%), followed by Opus 4.7 (30.7%). v2min is much fairer across all systems.</p>

<h2>3. Top systematic patterns the v1 prompt mishandles</h2>
{pat_table}
<p>The two dominant bias mechanisms are:</p>
<ul>
<li><b>penalises_superset</b> (277 cells) — extraction reproduces all of gold's content AND adds further on-topic, paper-grounded detail. v1 penalises this as "hallucination" or "extra unsupported content."</li>
<li><b>penalises_minor_omission</b> (165 cells) — extraction captures the central claim but drops one peripheral number, citation, or sub-bullet. v1 marks Partial.</li>
<li><b>penalises_paraphrase</b> (113 cells) — extraction expresses the same meaning in different words. v1 dings the surface-form mismatch.</li>
</ul>

<h2>4. Prompt-level problems observed</h2>
{probs_html}

<h2>5. Recommended prompt fixes</h2>
<ul>
<li><b>v1 — add explicit superset clause</b>: "If the candidate restates the reference's content AND adds further on-topic detail consistent with the field, score Correct. Do not penalise additions that are substantively aligned with the field."</li>
<li><b>v1 — clarify substance vs detail</b>: "Score on substantive equivalence, not exact-content overlap. Missing a peripheral number or citation does not by itself drop a candidate to Partial."</li>
<li><b>v1 — separate enum-field rubric</b>: Multi-value enum fields (dataCollectionType, etc.) should be scored as set-membership: Correct if the candidate's set is a superset of gold's; Partial if subset; Wrong if disjoint or contradictory.</li>
<li><b>v2min — add central-claim presence check</b>: "Even when surface form matches, mark Partial if the candidate omits the central claim or quantitative anchor of the reference."</li>
<li><b>Both — distinguish off-topic from on-topic extras</b>: Currently both prompts conflate "extra content" with "hallucination". Add: "Extra content that addresses the field (even if not in the reference) is acceptable; only off-topic content is penalised."</li>
</ul>

<h2>6. Top 20 worst v1 bias examples</h2>
<p>Each example shows the gold value, Sonnet 4.5's extraction (which scored Correct), the target system's extraction (audited as biased-against), and both judges' scores + reasons. Stratified across 4 systems and ~8 fields.</p>
{examples_section}

<hr>
<p><i>Generated by 8-agent Opus 4.7 audit, 2026-05-04. Source data: /tmp/judge_audit/proposals_*.json. Headline projections: data/judged/judge_scores_glm_5.parquet (corrected gold, 2026-05-04).</i></p>
</body>
</html>
"""

out_html = Path('docs/CroissantMiner_JudgeBiasAudit_2026-05-04.html')
out_html.write_text(html_doc)
print(f"HTML written: {out_html}")
print(f"Bytes: {len(html_doc):,}")
