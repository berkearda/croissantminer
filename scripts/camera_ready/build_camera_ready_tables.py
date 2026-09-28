"""Regenerate the numbers in Table 2 (table2_test88_headline.tex) and Tables 5/6
(per_field_tables.tex) of the Overleaf source from the complete current data.

Uses the canonical per-cell scorer and bootstrap of
scripts/figures/build_test88_headline_table.py (imported, main() not run), so the
composites and CIs equal results/composite_ci_test88_post_fix.csv. Core and RAI
are field-macro means over the 10 Tier-1 and 20 RAI fields, as in the paper.

Only the numeric cells of existing rows are replaced; labels, order, bold
markers and layout stay as they are. Bold is re-derived with the paper's rule:
best Core / RAI / Composite among single-pass rows, and among agentic rows.

Writes results/camera_ready/{table2_camera_ready.csv, per_field_camera_ready.csv}
and, with --apply, the two .tex files in paper/overleaf/.
Decision: decisions.md 2026-09-25 (D1: regenerate from complete data).
"""
import re
import sys
import importlib.util
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
OVERLEAF = ROOT / "paper" / "overleaf"
OUT = ROOT / "results" / "camera_ready"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("h", ROOT / "scripts/figures/build_test88_headline_table.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

T2_LABELS = {
    "Claude Sonnet 4.6": "claude_sonnet_4_6", "Claude Opus 4.7": "claude_opus_4_7", "GPT-5.4": "gpt5_4_full",
    "Qwen 3.6 35B-A3B": "qwen3_6_35b_a3b", "GLM-5.1": "glm_5_1", "Gemini 2.5 Flash": "gemini_2_5_flash",
    "GPT-5.4 Mini": "gpt5_4_mini", "Gemini 3.1 Pro Preview": "gemini_3_1_pro", "DeepSeek V3.2": "deepseek_v3_2",
    "Mistral Small 4": "mistral_small_4", "Llama 4 Scout 17B": "llama4_scout",
    "ReAct (Sonnet 4.6)": "agentic_react_sonnet_4_6_v3", "ReAct (GPT-5.4)": "agentic_react_gpt_5_4_v3",
    "ReAct (Gemini 3.1 Pro)": "agentic_react_gemini_3_1_pro_v3",
    "Parallel Specialists (Sonnet 4.6)": "agentic_specialist_premium_v4",
    "Parallel Specialists (GPT-5.4)": "agentic_specialist_gpt5_4_full_v4",
    "Parallel Specialists (Gemini 3.1 Pro)": "agentic_specialist_gemini_3_1_pro_v4",
    "Triage + Critique (Sonnet 4.6)": "agentic_v2_sonnet_4_6_v4", "Triage + Critique (GPT-5.4)": "agentic_v2_gpt5_4_full_v4",
    "Triage + Critique (Gemini 3.1 Pro)": "agentic_v2_gemini_3_1_pro_v4",
    "Locator-Extractor (Sonnet 4.6)": "agentic_lev_sonnet_4_6_sonnet_4_6_v3",
    "Locator-Extractor (GPT-5.4)": "agentic_lev_gpt5_4_full",
    # These two use the re-run of the papers whose API calls failed on quota in the original
    # runs (decisions.md 2026-09-26 (6), (11); scripts/camera_ready/merge_lev_rerun.py).
    "Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini)": "agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3_rerun2609",
    "Locator-Extractor (Gemini 3.1 Pro)": "agentic_lev_gemini_3_1_pro_rerun2609",
}
PF_LABELS = {
    "Claude Sonnet 4.6": "claude_sonnet_4_6", "Claude Opus 4.7": "claude_opus_4_7", "GPT-5.4": "gpt5_4_full",
    "ReAct (4.6)": "agentic_react_sonnet_4_6_v3", "PSpec (4.6)": "agentic_specialist_premium_v4",
    "Qwen 3.6 35B-A3B": "qwen3_6_35b_a3b", "GLM-5.1": "glm_5_1", "Triage+Critique (4.6)": "agentic_v2_sonnet_4_6_v4",
    "Gemini 2.5 Flash": "gemini_2_5_flash", "GPT-5.4 Mini": "gpt5_4_mini", "Gemini 3.1 Pro": "gemini_3_1_pro",
    "DeepSeek V3.2": "deepseek_v3_2", "Locator-Extr (4.6)": "agentic_lev_sonnet_4_6_sonnet_4_6_v3",
    "Mistral Small 4": "mistral_small_4", "Llama 4 Scout": "llama4_scout",
}
CORE_COLS = ["sc:name", "sc:description", "sc:url", "sc:license", "sc:creator", "sc:publisher",
             "sc:datePublished", "sc:inLanguage", "cr:citeAs", "cr:isLiveDataset"]
RAI_COLS = ["rai:" + f for f in [
    "annotationsPerItem", "annotatorDemographics", "dataAnnotationAnalysis", "dataAnnotationPlatform",
    "dataAnnotationProtocol", "dataBiases", "dataCollection", "dataCollectionMissingData",
    "dataCollectionRawData", "dataCollectionTimeframe", "dataCollectionType", "dataImputationProtocol",
    "dataLimitations", "dataManipulationProtocol", "dataPreprocessingProtocol", "dataReleaseMaintenancePlan",
    "dataSocialImpact", "dataUseCases", "machineAnnotationTools", "personalSensitiveInformation"]]

_cache = {}


def cells(sid):
    if sid not in _cache:
        _cache[sid] = h.per_cell_scores_test88(sid)
    return _cache[sid]


def table2_numbers():
    rows = []
    for label, sid in T2_LABELS.items():
        df = cells(sid)
        comp, lo, hi = h.bootstrap_ci(df)
        pf = df.groupby("field_id")["score"].mean()
        rows.append(dict(label=label, sid=sid, core=pf[pf.index.isin(h.TIER1)].mean(),
                         rai=pf[pf.index.isin(h.LONG_TEXT_RAI_FIELDS)].mean(),
                         composite=comp, ci_lo=lo, ci_hi=hi,
                         n_papers=df.paper_id.nunique(), n_cells=len(df)))
    return pd.DataFrame(rows)


def per_field_numbers():
    return pd.DataFrame({label: cells(sid).groupby("field_id")["score"].mean()
                         for label, sid in PF_LABELS.items()}).T


def bold(x, flag):
    return f"\\textbf{{{x}}}" if flag else x


def render_table2(tex, t2):
    single = t2[t2.sid.isin([T2_LABELS[k] for k in list(T2_LABELS)[:11]])]
    agentic = t2[~t2.index.isin(single.index)]
    best = {}
    for grp in (single, agentic):
        for col in ("core", "rai", "composite"):
            best[(tuple(grp.sid), col)] = grp[col].round(3).max()
    out, n = [], 0
    for line in tex.split("\n"):
        m = re.match(r"^(\d+) & (.+?) & (.+?) & .+ \\\\\s*$", line)
        star = "$^{*}$" if m and "$^{*}$" in m.group(2) else ""      # Anthropic-family mark
        label = re.sub(r"\\textbf\{(.+)\}", r"\1", m.group(2).replace("$^{*}$", "")) if m else None
        if not m or label not in T2_LABELS:
            out.append(line)
            continue
        r = t2[t2.label == label].iloc[0]
        grp = single if r.sid in set(single.sid) else agentic
        is_best = {c: round(r[c], 3) == best[(tuple(grp.sid), c)] for c in ("core", "rai", "composite")}
        name = bold(label, is_best["composite"] and grp is single) + star
        out.append(f"{m.group(1)} & {name} & {m.group(3)} & {bold(f'{r.core:.3f}', is_best['core'])} & "
                   f"{bold(f'{r.rai:.3f}', is_best['rai'])} & {bold(f'{r.composite:.3f}', is_best['composite'])}"
                   f"\\, [{r.ci_lo:.3f}, {r.ci_hi:.3f}] \\\\")
        n += 1
    assert n == len(T2_LABELS), n
    return "\n".join(out)


def render_per_field(tex, pf):
    out, which, n = [], None, 0
    for line in tex.split("\n"):
        if "label{tab:perfield-general}" in line:
            which = CORE_COLS
        elif "label{tab:perfield-rai}" in line:
            which = RAI_COLS
        label = line.split(" & ")[0].strip()
        if which and label in PF_LABELS and line.rstrip().endswith("\\\\"):
            vals = " & ".join(f"{pf.loc[label, c]:.2f}" for c in which)
            out.append(f"{label} & {vals} \\\\")
            n += 1
        else:
            out.append(line)
    assert n == 2 * len(PF_LABELS), n
    return "\n".join(out)


def main(apply):
    OUT.mkdir(parents=True, exist_ok=True)
    t2 = table2_numbers()
    pf = per_field_numbers()
    t2.to_csv(OUT / "table2_camera_ready.csv", index=False)
    pf[CORE_COLS + RAI_COLS].to_csv(OUT / "per_field_camera_ready.csv")
    canon = pd.read_csv(ROOT / "results/composite_ci_test88_post_fix.csv").set_index("sid")
    bad = [r.sid for r in t2.itertuples() if abs(canon.loc[r.sid, "composite"] - r.composite) > 1e-12
           or abs(canon.loc[r.sid, "ci_lo"] - r.ci_lo) > 1e-12 or abs(canon.loc[r.sid, "ci_hi"] - r.ci_hi) > 1e-12]
    print("composites and CIs equal results/composite_ci_test88_post_fix.csv:", "yes" if not bad else f"NO {bad}")
    t2_path, pf_path = OVERLEAF / "table2_test88_headline.tex", OVERLEAF / "per_field_tables.tex"
    new_t2 = render_table2(t2_path.read_text(), t2)
    new_pf = render_per_field(pf_path.read_text(), pf)
    if apply:
        t2_path.write_text(new_t2)
        pf_path.write_text(new_pf)
        print("wrote", t2_path.name, "and", pf_path.name)
    else:
        (OUT / "table2_test88_headline.preview.tex").write_text(new_t2)
        (OUT / "per_field_tables.preview.tex").write_text(new_pf)
        print("dry run: previews in results/camera_ready/")


if __name__ == "__main__":
    main("--apply" in sys.argv)
