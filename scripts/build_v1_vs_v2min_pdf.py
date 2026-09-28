"""Build a focused side-by-side PDF: v1 vs v2min composite scores per system,
plus illustrated v2min failure modes.
"""
import json, html, datetime, os, pandas as pd
from pathlib import Path

ROOT = Path('croissantminer')
os.chdir(ROOT)
NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def esc(s): return html.escape(str(s) if s is not None else '')
def trunc(s, n=2000):
    s = str(s) if s is not None else ''
    return s if len(s) <= n else s[:n] + ' …'

# === Load existing composite comparison ===
comp_csv = ROOT / 'results/composite_judge_comparison.csv'
comp = pd.read_csv(comp_csv)

# Pull v1 and v2min columns. The CSV has system + per-judge composite.
# Verify columns
print("comp cols:", comp.columns.tolist())
print(comp.head())

# === Load v2min clean examples ===
ex_data = json.load(open('/tmp/judge_audit2/v2min_clean_examples.json'))

# === Build composite table ===
# Rank by v1 composite descending
comp_sorted = comp.sort_values('v1_score', ascending=False).reset_index(drop=True)
rows = []
for _, r in comp_sorted.iterrows():
    sys = r['sid']
    v1 = r['v1_score']; v2 = r['v2min_score']
    v1_lo, v1_hi = r['v1_lo'], r['v1_hi']
    v2_lo, v2_hi = r['v2min_lo'], r['v2min_hi']
    delta = v2 - v1
    color = '#16a34a' if delta > 0.005 else ('#dc2626' if delta < -0.005 else '#1F2937')
    rows.append(f"<tr><td>{sys}</td>"
                f"<td>{v1:.3f} <span style='color:#888;font-size:8pt'>[{v1_lo:.3f}, {v1_hi:.3f}]</span></td>"
                f"<td>{v2:.3f} <span style='color:#888;font-size:8pt'>[{v2_lo:.3f}, {v2_hi:.3f}]</span></td>"
                f"<td style='color:{color}'>{delta:+.3f}</td></tr>")
comp_table = f"""<table>
<thead><tr><th>System</th><th>v1 composite (test-88, 95% CI)</th><th>v2min composite (95% CI)</th><th>Δ (v2min − v1)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""

# === Build example sections ===
def ex_html(ex, badge):
    return f"""<div class="example">
<div class="ex-head">[{badge}] {esc(ex['paper_id'])} / {esc(ex['field_id'])} — system: <code>{esc(ex['system'])}</code></div>
<div class="ex-row"><div class="lbl">Gold (reference)</div><div class="text">{esc(trunc(ex.get('gold','')))}</div></div>
<div class="ex-row"><div class="lbl">Sonnet 4.5 extraction (for context)</div><div class="text">{esc(trunc(ex.get('sonnet_4_5_extraction','')))}</div></div>
<div class="ex-row"><div class="lbl">{esc(ex['system'])} extraction</div><div class="text">{esc(trunc(ex.get('system_extraction','')))}</div></div>
<table class="judge-table">
<thead><tr><th>Judge</th><th>Score</th><th>Reason</th></tr></thead>
<tbody>
<tr><td><b>v1 (production)</b></td><td>{esc(ex.get('v1_score'))}</td><td>{esc(trunc(ex.get('v1_reason'), 600))}</td></tr>
<tr><td><b>v2min</b></td><td>{esc(ex.get('v2min_score'))}</td><td>{esc(trunc(ex.get('v2min_reason'), 600))}</td></tr>
</tbody></table>
<div class="audit-row">
<b>Audit (v2min):</b> {esc(ex.get('v2min_verdict'))} — {esc(ex.get('v2min_rationale'))}<br>
<b>Audit (v1):</b> {esc(ex.get('v1_verdict'))} — {esc(ex.get('v1_rationale'))}<br>
<b>Pattern:</b> <code>{esc(ex.get('shared_pattern_tag'))}</code>
</div>
</div>"""

lenient_section = '\n'.join(ex_html(e, 'v2min LENIENT') for e in ex_data['lenient'])
harsh_section = '\n'.join(ex_html(e, 'v2min HARSH') for e in ex_data['harsh']) if ex_data.get('harsh') else '<p><i>None observed (v2min HARSH bias is rare).</i></p>'

# v2min problems list
v2min_problems = """
<ul>
<li><b>Drops central claims silently.</b> Accepts extractions whose surface form mimics gold but omits a central quantitative anchor or whole protocol step. Documented examples: target says "346 subjects" vs gold "3 subjects" → still Correct; "implicit through 77k → 53k → 12k" hand-wave instead of describing the actual validation pass.</li>
<li><b>Accepts unverifiable factual additions.</b> When extraction adds specific numbers, names, dates, or URLs that aren't in the reference, v2min waves them through as "additional helpful detail." Cannot distinguish hallucinated specifics from genuine paper-grounded content.</li>
<li><b>NULL-gold abstention rule missing</b> (same as v1). When gold is <code>[NULL - not found in paper]</code>, any non-null extraction is forced to Wrong. No credit for "field doesn't apply" or "we couldn't find this" answers.</li>
<li><b>Enum-list rubric missing</b> (same as v1). Multi-value enum fields (e.g., <code>rai:dataCollectionType</code>) score holistically. Extraction with 4 of 5 enum values plus an extra one → still Partial regardless of substance.</li>
<li><b>JSON parse fragility</b>. Bare array outputs like <code>[1]</code> cause silent <code>None</code> scores. Affects both v1 and v2min — ~3 cells per batch lose their score this way.</li>
<li><b>Empty rationales returned occasionally</b>. v2min sometimes outputs <code>score: 1, reason: ""</code> with no justification. No retry or fallback in production code.</li>
<li><b>No claim-count anchor in score bands.</b> Score 1/2/3 isn't tied to "% of central claims captured" — the model has too much latitude to map scores to its own intuition.</li>
<li><b>Trades penalises_paraphrase for accepts_paraphrase_too_easily.</b> v2min closed v1's bias by becoming permissive on surface form, but doesn't gate on substance preservation.</li>
</ul>
"""

html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>v1 vs v2min — Per-system composites + v2min failure modes</title>
<style>
@page {{ size: A4; margin: 14mm; }}
body {{ font-family: "Source Serif Pro", serif; font-size: 9.5pt; line-height: 1.4; color: #1F2937; }}
h1 {{ color: #0F2D4F; font-size: 16pt; border-bottom: 2px solid #C19A49; padding-bottom: 3mm; }}
h2 {{ color: #0F2D4F; font-size: 12pt; margin-top: 8mm; border-bottom: 1px solid #ccc; padding-bottom: 1mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9pt; }}
th {{ background: #F5F1E8; color: #0F2D4F; padding: 1.5mm 3mm; border: 0.5px solid #aaa; text-align: left; }}
td {{ padding: 1.5mm 3mm; border: 0.5px solid #ddd; vertical-align: top; }}
.summary {{ background: #F5F1E8; padding: 4mm; border-left: 3px solid #C19A49; margin: 3mm 0; }}
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
<h1>v1 vs v2min — Per-system composites + v2min failure modes</h1>
<p><i>Generated {NOW} — current test-88 composite scores under both judge prompts, plus 8 LENIENT and {len(ex_data.get('harsh',[]))} HARSH v2min failure cases from the audit.</i></p>

<div class="summary">
<b>Snapshot:</b> v2min raises non-seed system composites by 4-6 points on average vs v1 (closing ~30% of the 4.5↔target gap). Sonnet 4.5 itself moves only +0.002. The trade-off: v2min has known LENIENT failure modes — accepts paraphrase that drops central claims, hand-waves missing protocol steps, and waves through unverifiable additions. Documented in §3 below.
</div>

<h2>1. Per-system composite scores (test-88, full lineup)</h2>
{comp_table}

<h2>2. v2min's specific problems (catalog)</h2>
{v2min_problems}

<h2>3. v2min LENIENT failure cases (judge said Correct, audit disagreed)</h2>
<p>These show v2min's permissiveness on substance loss. Each example has both judges' scores+reasons + the audit verdict. The pattern is consistent: v2min accepts the surface-form similarity but doesn't catch dropped claims.</p>
{lenient_section}

<h2>4. v2min HARSH failure cases (judge said Partial/Wrong, audit said biased)</h2>
<p>Rare — most v2min bias is leniency, not harshness.</p>
{harsh_section}

<hr>
<p><i>Generated {NOW}. Source: data/judged/judge_scores_glm_5.parquet + judge_scores_v2min_glm5.parquet (corrected gold). Audit: /tmp/judge_audit/proposals_*.json + /tmp/judge_audit2/proposals_*.json.</i></p>
</body></html>
"""

out_html = ROOT / 'docs/CroissantMiner_V1vsV2min_2026-05-04.html'
out_html.write_text(html_doc)
print(f"HTML written: {out_html}  ({len(html_doc):,} bytes)")
