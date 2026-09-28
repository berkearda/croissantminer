"""Recompute the per-paper inference cost table (Table 8, appendix "Per-System Cost")
from the token counts recorded in the extraction files (camera-ready).

Systems: the 24 rows of Table 2 (T2_LABELS in build_camera_ready_tables.py, directories
from STRATEGY_DIRS via build_test88_headline_table.py) plus the Claude Sonnet 4.5
single-pass diagnostic. Papers: the 88-paper test split (data/agentic/dev_test_split.json);
the 14 dev papers are costed too where files exist, for the 102-paper total.

Where the tokens come from
  single-pass     top-level `usage` {input_tokens, output_tokens}
  Sonnet 4.5      data/extractions/claude_sonnet_4_5_repro/ (the scored directory has no
                  usage; the repro run was made for this table, decisions.md 2026-04-28)
  ReAct           _meta.total_input_tokens / total_output_tokens / cache_creation_input_tokens
                  / cache_read_input_tokens (Anthropic input excludes cache tokens)
  Parallel Spec.  _meta.agent_tokens per specialist, model from _meta.specialist_backbones
  Triage+Critique top-level usage + the Phase-1 Gemini 2.5 Flash triage it loads
                  (data/agentic/phase1/<paper>.json `usage`)
  Locator-Extr.   runs with an LLM locator: _meta.locator tokens at the locator model, the
                  rest of `usage` at the extractor model (_meta.model_id); runs without one
                  use the precomputed Phase-1 Gemini 2.5 Flash triage, added as for T+C.
_meta.cost_usd is NOT used: agentic runs priced it with placeholder rates
(scripts/_agentic_helpers.py, croissantminer/react_agent/agent.py).

Price basis: standard (non-batch, realtime) public list prices, USD per 1M tokens, as of
April-May 2026. The single-pass Anthropic/OpenAI/Google runs used the Batch API (50% off);
they are priced at standard rates so that they compare with the realtime agentic runs.
  Anthropic  https://platform.claude.com/docs/en/about-claude/pricing
             Sonnet 4.5 / 4.6 3 / 15 (5-min cache write 3.75, cache read 0.30); Opus 4.7 5 / 25
  OpenAI     https://developers.openai.com/api/docs/pricing
             GPT-5.4 2.50 / 15 (cached input 0.25, <272K context); GPT-5.4 mini 0.75 / 4.50 (0.075)
  Google     https://ai.google.dev/gemini-api/docs/pricing
             Gemini 3.1 Pro Preview 2 / 12 (prompts <=200k; 4 / 18 above; cache 0.20);
             Gemini 2.5 Flash 0.30 / 2.50 (cache 0.03). Output prices include thinking tokens.
  DeepSeek   deepseek-chat = DeepSeek-V3.2 non-thinking until the V4 switch on 2026-04-24
             (https://api-docs.deepseek.com/updates/); runs are from 2026-04-22.
             0.28 cache miss / 0.028 cache hit / 0.42 output, set 2025-09-29 and kept for V3.2
             (https://venturebeat.com/ai/deepseeks-new-v3-2-exp-model-cuts-api-pricing-in-half-to-less-than-3-cents;
             the official page now lists only V4 prices).
  Z.AI       GLM-5.1 1.40 / 4.40 (cached input 0.26), https://docs.z.ai/guides/overview/pricing
  vLLM on Euler (Qwen 3.6, Mistral Small 4, Llama 4 Scout): self-hosted, not billed.

Known gaps in what was recorded (see the notes column):
  - Gemini calls through the Google API record candidatesTokenCount only; thinking tokens
    (billed as output) were not saved, so Gemini costs are lower bounds on output.
  - OpenAI, Gemini, DeepSeek and Z.AI cached-input tokens were not saved, so all input is
    priced as uncached (upper bound on input).
  - Parallel Specialists (Gemini 3.1 Pro): papers run from 2026-05-28 on went through the
    OpenRouter route of _agentic_helpers.py, whose completion_tokens include reasoning; they are
    priced at Google's list rate (OpenRouter's own rate was not checked).
  - Papers whose LLM calls failed (HTTP 429, zero tokens, lost usage after a JSON error) are
    left out of the mean; the notes give how many and the all-paper mean.

Writes results/camera_ready/cost_camera_ready.csv and prints ratios and totals.
Decision: not yet logged in decisions.md (camera-ready Table 8).
"""
import json
import sys
import importlib.util
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "camera_ready"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = _load("cr", "scripts/camera_ready/build_camera_ready_tables.py")
h = cr.h  # build_test88_headline_table.py, loaded by cr; holds STRATEGY_DIRS
LABELS = dict(cr.T2_LABELS)
LABELS["Claude Sonnet 4.5"] = "claude_sonnet_4_5"
DIRS = dict(h.STRATEGY_DIRS)
DIRS["claude_sonnet_4_5"] = ROOT / "data/extractions/claude_sonnet_4_5_repro"
SPLIT = json.loads((ROOT / "data/agentic/dev_test_split.json").read_text())
PHASE1 = ROOT / "data/agentic/phase1"

# USD per 1M tokens, standard list prices April-May 2026 (sources in the docstring).
# inp = uncached input, cr = cached input / cache read, cw = cache write, out = output.
PRICES = {
    "claude-sonnet-4-5": dict(inp=3.00, cr=0.30, cw=3.75, out=15.00),
    "claude-sonnet-4-6": dict(inp=3.00, cr=0.30, cw=3.75, out=15.00),
    "claude-opus-4-7":   dict(inp=5.00, cr=0.50, cw=6.25, out=25.00),
    "gpt-5.4":           dict(inp=2.50, cr=0.25, cw=0.0, out=15.00),
    "gpt-5.4-mini":      dict(inp=0.75, cr=0.075, cw=0.0, out=4.50),
    "gemini-3.1-pro":    dict(inp=2.00, cr=0.20, cw=0.0, out=12.00, inp_long=4.00, out_long=18.00),
    "gemini-2.5-flash":  dict(inp=0.30, cr=0.03, cw=0.0, out=2.50),
    "deepseek-v3.2":     dict(inp=0.28, cr=0.028, cw=0.0, out=0.42),
    "glm-5.1":           dict(inp=1.40, cr=0.26, cw=0.0, out=4.40),
    "self-hosted":       dict(inp=0.0, cr=0.0, cw=0.0, out=0.0),
}
MODEL_KEY = {
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5", "sonnet-4-5": "claude-sonnet-4-5",
    "claude-sonnet-4-6": "claude-sonnet-4-6", "sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus-4-7": "claude-opus-4-7",
    "gpt-5.4-2026-03-05": "gpt-5.4", "gpt-5.4": "gpt-5.4",
    "gpt-5.4-mini-2026-03-17": "gpt-5.4-mini", "gpt-5.4-mini": "gpt-5.4-mini",
    "gemini-3.1-pro-preview": "gemini-3.1-pro", "gemini-3.1-pro": "gemini-3.1-pro",
    "gemini-2.5-flash": "gemini-2.5-flash", "deepseek-chat": "deepseek-v3.2", "glm-5.1": "glm-5.1",
}
GEMINI_LONG = 200_000   # Gemini 3.1 Pro prompt size above which the higher tier applies
GPT_LONG = 272_000      # GPT-5.4 list price above is for <272K context
OPENROUTER_ROUTE_DATE = "2026-05-28"  # _agentic_helpers.py sends Gemini calls via OpenRouter from this date
NO_CACHE_RECORD = {"gpt-5.4", "gpt-5.4-mini", "gemini-3.1-pro", "deepseek-v3.2", "glm-5.1"}

# Printed Table 8 (submitted version), for the old-vs-new printout only.
PRINTED = {
    "Claude Opus 4.7": 0.268, "Claude Sonnet 4.6": 0.126, "Claude Sonnet 4.5": 0.120, "GPT-5.4": 0.093,
    "Gemini 3.1 Pro Preview": 0.072, "GPT-5.4 Mini": 0.026, "Gemini 2.5 Flash": 0.003,
    "Triage + Critique (GPT-5.4)": 0.157, "Triage + Critique (Gemini 3.1 Pro)": 0.192,
    "Locator-Extractor (GPT-5.4)": 0.197, "Locator-Extractor (Gemini 3.1 Pro)": 0.066,
    "DeepSeek V3.2": 0.0, "Llama 4 Scout 17B": 0.0, "Mistral Small 4": 0.0, "Qwen 3.6 35B-A3B": 0.0,
    "GLM-5.1": 0.0,
}
BACKBONES = {"Sonnet 4.6": "Claude Sonnet 4.6", "GPT-5.4": "GPT-5.4", "Gemini 3.1 Pro": "Gemini 3.1 Pro Preview"}
ARCHS = ["ReAct", "Parallel Specialists", "Triage + Critique", "Locator-Extractor"]
HYBRID = "Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini)"


def model_key(mid, provider=None):
    if provider == "vllm":
        return "self-hosted"
    return MODEL_KEY[mid]


def comp(model, inp=0, cr_=0, cw=0, out=0, long_prompt=False, role="main"):
    return dict(model=model, inp=inp or 0, cr=cr_ or 0, cw=cw or 0, out=out or 0, long=long_prompt, role=role)


def price(c):
    p = PRICES[c["model"]]
    pin, pout = (p["inp_long"], p["out_long"]) if c["long"] else (p["inp"], p["out"])
    return (c["inp"] * pin + c["cr"] * p["cr"] + c["cw"] * p["cw"] + c["out"] * pout) / 1e6


def triage_comp(pid):
    u = json.loads((PHASE1 / f"{pid}.json").read_text())["usage"]
    return comp("gemini-2.5-flash", inp=u["input"], out=u["output"], role="triage")


def paper_components(j):
    """Return (components, failure reason or None, ReAct turn count or None) for one paper file."""
    m = j.get("_meta", {})
    if "total_input_tokens" in m:                                   # ReAct
        return [comp(model_key(m["model"]), m["total_input_tokens"], m.get("cache_read_input_tokens"),
                     m.get("cache_creation_input_tokens"), m["total_output_tokens"])], None, m.get("num_turns", 1)
    u = j["usage"]
    if u["input_tokens"] == 0:
        return [], "no tokens recorded (all calls failed)", None
    if "agent_tokens" in m:                                         # Parallel Specialists
        cs, fail = [], None
        for name, t in m["agent_tokens"].items():
            if t["input_tokens"] == 0:
                fail = "specialist call(s) failed, zero tokens"
            mk = model_key(m["specialist_backbones"][name])
            cs.append(comp(mk, t["input_tokens"], out=t["output_tokens"],
                           long_prompt=(mk == "gemini-3.1-pro" and t["input_tokens"] > GEMINI_LONG)))
        assert sum(c["inp"] for c in cs) == u["input_tokens"] and sum(c["out"] for c in cs) == u["output_tokens"]
        return cs, fail, None
    mk = model_key(m.get("model_id"), m.get("provider"))
    pipeline = m.get("pipeline")
    if pipeline == "agentic_v2":                                   # Triage + Critique
        return [comp(mk, u["input_tokens"], out=u["output_tokens"]), triage_comp(j["dataset_id"])], None, None
    if pipeline == "agentic_lev":                                  # Locator-Extractor
        gs = m.get("group_stats", {})
        fail = None
        if any("error" in g for g in gs.values()):
            fail = "extractor call(s) failed (HTTP 429 or JSON error), tokens not recorded"
        loc = m.get("locator", {})
        if "input_tokens" in loc:
            if loc["input_tokens"] == 0:
                fail = fail or "locator call failed (HTTP 429), keyword fallback"
            cs = [comp(model_key(loc["model_id"]), loc["input_tokens"], out=loc["output_tokens"], role="locator"),
                  comp(mk, u["input_tokens"] - loc["input_tokens"], out=u["output_tokens"] - loc["output_tokens"])]
        else:
            cs = [comp(mk, u["input_tokens"], out=u["output_tokens"]), triage_comp(j["dataset_id"])]
        g_in = sum(g.get("tokens_in", 0) for g in gs.values())
        assert g_in + loc.get("input_tokens", 0) == u["input_tokens"], j["dataset_id"]
        return cs, fail, None
    # single-pass: one call per paper, so the Gemini long-prompt tier is exact here
    return [comp(mk, u["input_tokens"], out=u["output_tokens"],
                 long_prompt=(mk == "gemini-3.1-pro" and u["input_tokens"] > GEMINI_LONG))], None, None


def single_pass_prompt(sid, pid):
    p = DIRS[sid] / f"{pid}.json"
    return json.loads(p.read_text())["usage"]["input_tokens"] if p.exists() else None


def cost_system(sid, ids):
    rows, fails = [], {}
    for p in sorted(DIRS[sid].glob("*.json")):
        if p.name.startswith("_") or p.stem not in ids:
            continue
        j = json.loads(p.read_text())
        m = j.get("_meta", {})
        cs, fail, turns = paper_components(j)
        r = dict(paper=p.stem, fail=fail, cost=sum(price(c) for c in cs), ts=m.get("timestamp", ""),
                 mode=m.get("mode"), recorded=m.get("cost_usd"),
                 inp=sum(c["inp"] for c in cs), cr=sum(c["cr"] for c in cs), cw=sum(c["cw"] for c in cs),
                 out=sum(c["out"] for c in cs), models=[c["model"] for c in cs])
        for c in cs:
            r[f"cost:{c['role']}"] = r.get(f"cost:{c['role']}", 0.0) + price(c)
        ref = {"gemini-3.1-pro": "gemini_3_1_pro", "gpt-5.4": "gpt5_4_full"}.get(cs[0]["model"]) if turns else None
        if ref:
            # ReAct re-sends a growing prompt each turn: max prompt <= total - (turns-1) * first prompt,
            # with the single-pass prompt of the same paper standing in for the first prompt.
            c, pr = cs[0], PRICES[cs[0]["model"]]
            p1 = single_pass_prompt(ref, p.stem)
            r["max_prompt_bound"] = c["inp"] - (turns - 1) * p1
            r["cost_if_cached_after_turn1"] = (p1 * pr["inp"] + (c["inp"] - p1) * pr["cr"] + c["out"] * pr["out"]) / 1e6
        if fail:
            fails[fail] = fails.get(fail, 0) + 1
        rows.append(r)
    return pd.DataFrame(rows), fails


def ordered_models(df):
    seen = []
    for ms in df.models:
        for x in ms:
            if x not in seen:
                seen.append(x)
    return seen


def describe(label, df, fails):
    ok = df[df.fail.isna()]
    models = ordered_models(df)
    billed = models != ["self-hosted"]
    notes = []
    if fails:
        notes.append(f"{len(df) - len(ok)} of {len(df)} papers left out of the mean ("
                     + "; ".join(f"{v}x {k}" for k, v in fails.items())
                     + f"); mean over all {len(df)} files incl. them ${df.cost.mean():.4f}")
    if "cost:locator" in ok:
        lm, em = df.models.iloc[0][:2]
        notes.append(f"locator {lm} ${ok['cost:locator'].mean():.4f} + extractor {em} "
                     f"${ok['cost:main'].mean():.4f} per paper")
    if "cost:triage" in ok:
        notes.append(f"includes precomputed Phase-1 Gemini 2.5 Flash triage ${ok['cost:triage'].mean():.4f}/paper "
                     f"(without it ${ok['cost:main'].mean():.4f})")
    gem = [x for x in models if x.startswith("gemini")]
    if gem:
        notes.append(f"{'/'.join(gem)}: thinking tokens not recorded (candidatesTokenCount only), output cost is a lower bound")
    late = df[df.ts >= OPENROUTER_ROUTE_DATE] if "gemini-3.1-pro" in models else df.iloc[0:0]
    if len(late):
        early, late_ok = ok[ok.ts < OPENROUTER_ROUTE_DATE], ok[ok.ts >= OPENROUTER_ROUTE_DATE]
        notes.append(f"{len(late)} papers run on/after {OPENROUTER_ROUTE_DATE} (OpenRouter route added to "
                     "_agentic_helpers.py that day; its token counts include reasoning) average "
                     f"{late_ok.out.mean():.0f} output tokens and ${late_ok.cost.mean():.4f}/paper vs "
                     f"{early.out.mean():.0f} and ${early.cost.mean():.4f} for the {len(early)} earlier papers")
    nocache = [x for x in models if x in NO_CACHE_RECORD]
    if nocache and not df.cr.any():
        notes.append(f"{'/'.join(nocache)}: cached-input tokens not recorded, all input priced uncached (upper bound)")
    if "max_prompt_bound" in df:
        lim = GEMINI_LONG if "gemini-3.1-pro" in models else GPT_LONG
        n = int((df.max_prompt_bound > lim).sum())
        notes.append(f"per-call tokens not saved; bound from turn count and single-pass prompt size: {n} papers "
                     f"could have a call above {lim // 1000}k (all priced at the base tier); if every prompt token "
                     f"after turn 1 had been a cache hit the mean would be ${ok.cost_if_cached_after_turn1.mean():.4f}")
    if ok.recorded.notna().any() and models[0].startswith("claude"):
        diff = (ok.recorded - ok["cost:main"] - ok.get("cost:locator", 0)).abs().max()
        notes.append(f"cross-check: recorded _meta.cost_usd matches to within ${diff:.4f}/paper")
    return dict(label=label, n_papers=len(ok), mean_input_tokens=round(ok.inp.mean()),
                mean_cached_or_cache_read_tokens=round(ok.cr.mean()), mean_cache_write_tokens=round(ok.cw.mean()),
                mean_output_tokens=round(ok.out.mean()), cost_per_paper_usd=round(ok.cost.mean(), 4) if billed else 0.0,
                billed=billed, _models=models, _notes=notes, _total_all=df.cost.sum(), _n_files=len(df),
                _batch=(df["mode"] == "batch").mean() > 0.5)


BASIS = {
    "claude-sonnet-4-5": "Anthropic $3/$15", "claude-sonnet-4-6": "Anthropic $3/$15",
    "claude-opus-4-7": "Anthropic $5/$25", "gpt-5.4": "OpenAI $2.50/$15",
    "gpt-5.4-mini": "OpenAI $0.75/$4.50", "gemini-3.1-pro": "Google $2/$12 (prompts <=200k)",
    "gemini-2.5-flash": "Google $0.30/$2.50", "deepseek-v3.2": "DeepSeek $0.28 cache-miss/$0.42",
    "glm-5.1": "Z.AI $1.40/$4.40", "self-hosted": "self-hosted vLLM on Euler, not billed",
}


def price_basis(label, d):
    parts = [BASIS[x] for x in d["_models"]]
    if label == "ReAct (Sonnet 4.6)":
        parts[0] += " + cache write $3.75, cache read $0.30"
    if len(parts) > 1 and d["_models"][-1] == "gemini-2.5-flash" and "Flash" not in label:
        parts[-1] = "triage " + parts[-1]
    s = "standard per 1M in/out: " + "; ".join(parts) if d["billed"] else parts[0]
    if d["_batch"]:
        s += "; run used Batch API, priced at standard realtime rates"
    return s


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    test, dev = set(SPLIT["test"]), set(SPLIT["dev"])
    res, dev_res, frames = [], {}, {}
    for label, sid in LABELS.items():
        df, fails = cost_system(sid, test)
        frames[label] = df
        d = describe(label, df, fails)
        d["sid"] = sid
        d["price_basis"] = price_basis(label, d)
        if label == "Claude Sonnet 4.5":
            d["_notes"].insert(0, "tokens from claude_sonnet_4_5_repro (same model, prompt, parser and Batch API; "
                                  "the scored claude_sonnet_4_5 directory has no usage)")
        d["notes"] = " | ".join(d["_notes"])
        res.append(d)
        ddf, dfails = cost_system(sid, dev)
        dev_res[label] = describe(label, ddf, dfails) if len(ddf) else None
    t = pd.DataFrame(res)
    cols = ["label", "sid", "n_papers", "mean_input_tokens", "mean_cached_or_cache_read_tokens",
            "mean_cache_write_tokens", "mean_output_tokens", "cost_per_paper_usd", "price_basis", "billed", "notes"]
    t[cols].to_csv(OUT / "cost_camera_ready.csv", index=False)

    print(f"{'label':52s} {'n':>3s} {'new':>8s} {'printed':>8s} billed")
    for r in t.sort_values("cost_per_paper_usd", ascending=False).itertuples():
        pr = PRINTED.get(r.label)
        print(f"{r.label:52s} {r.n_papers:3d} {r.cost_per_paper_usd:8.4f} {pr if pr is not None else '-':>8} {r.billed}")

    cost = t.set_index("label").cost_per_paper_usd
    low = {l: frames[l][frames[l].fail.isna()].cost_if_cached_after_turn1.mean()
           for l in cost.index if "cost_if_cached_after_turn1" in frames[l]}
    print("\nagentic / single-pass cost ratio, same backbone (ReAct GPT/Gemini: uncached, and if cached after turn 1):")
    ratios, ratios_low = {}, {}
    for bb, sp in BACKBONES.items():
        for a in ARCHS:
            lab = f"{a} ({bb})"
            ratios[lab] = cost[lab] / cost[sp]
            ratios_low[lab] = low.get(lab, cost[lab]) / cost[sp]
            extra = f"  ({ratios_low[lab]:.2f}x if cached)" if lab in low else ""
            print(f"  {lab:45s} {cost[lab]:.4f} / {cost[sp]:.4f} = {ratios[lab]:.2f}x{extra}")
    for name, rr in (("as priced", ratios), ("ReAct cached after turn 1", ratios_low)):
        lo, hi = min(rr, key=rr.get), max(rr, key=rr.get)
        print(f"  {name}: min {rr[lo]:.2f}x ({lo}), max {rr[hi]:.2f}x ({hi})")
    print(f"  {HYBRID} vs Gemini 3.1 Pro single-pass: {cost[HYBRID] / cost['Gemini 3.1 Pro Preview']:.2f}x")

    t2 = t[(t.label != "Claude Sonnet 4.5") & t.billed]
    tot88 = (t2.cost_per_paper_usd * 88).sum()
    batch = (t2.cost_per_paper_usd * 88 * t2._batch.map({True: 0.5, False: 1.0})).sum()
    print(f"\none pass of the {len(t2)} billed Table 2 systems over the 88 test papers (per-paper mean x 88): ${tot88:.2f}")
    print(f"  same, with the 50% Batch discount the single-pass runs actually got: ${batch:.2f}")
    print(f"  recorded spend in the 88 test files (failed calls count as $0): ${t2._total_all.sum():.2f}")
    have = [l for l in t2.label if dev_res[l] is not None]
    missing = [l for l in t2.label if dev_res[l] is None]
    dev_tot = sum(dev_res[l]["cost_per_paper_usd"] * 14 for l in have)
    print(f"  14 dev papers, {len(have)} systems with dev files: ${dev_tot:.2f}; no dev files for {missing}")
    print(f"  102 papers = 88-paper total + those dev files: ${tot88 + dev_tot:.2f}; "
          f"with the missing systems at their test mean x 14: ${tot88 + dev_tot + sum(cost[l] * 14 for l in missing):.2f}")
    sp = t[t.label == "Claude Sonnet 4.5"].iloc[0]
    print(f"  Claude Sonnet 4.5 diagnostic (not in the total): ${sp.cost_per_paper_usd * 88:.2f} over 88 papers")
    print("\nwrote", OUT / "cost_camera_ready.csv")


if __name__ == "__main__":
    main()
