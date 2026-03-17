#!/usr/bin/env python3
"""Cost and efficiency analysis for CroissantMiner."""
import sys
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT_DIR = Path("results/cost_analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# Pricing (as of March 2026)
# ═══════════════════════════════════════════════════════════════════════
PRICING = {
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4.5"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "name": "GPT-4o-mini"},
    "gpt-4o-mini-judge": {"input": 0.15, "output": 0.60, "name": "GPT-4o-mini (Judge)"},
    "hf-auto": {"input": 0, "output": 0, "name": "HF Auto-Croissant"},
}

# ═══════════════════════════════════════════════════════════════════════
# Paper sizes (from PDF extraction) — benchmark datasets only
# ═══════════════════════════════════════════════════════════════════════
PAPER_CHARS = {
    "MLS": 33704, "MMLU": 82972, "FLORES": 201674, "CIFAR": 62545,
    "MSCOCO": 56282, "MMMU": 247036, "Visual Genome": 140567, "MathVista": 236254,
}

# Extraction output sizes (from JSON files)
def get_output_sizes(ext_dir):
    sizes = {}
    for f in Path(ext_dir).glob("*_extraction.json"):
        ds = f.stem.replace("_extraction", "")
        sizes[ds] = f.stat().st_size
    return sizes

# Extraction timing (from rerun logs — approximate)
# Based on observed times during extraction runs
EXTRACTION_TIMES = {
    "claude": {"MLS": 41, "MMLU": 31, "FLORES": 57, "CIFAR": 13,
               "MSCOCO": 46, "MMMU": 43, "Visual Genome": 50, "MathVista": 52},
    "gpt": {"MLS": 21, "MMLU": 23, "FLORES": 34, "CIFAR": 11,
            "MSCOCO": 24, "MMMU": 36, "Visual Genome": 13, "MathVista": 37},
}


def estimate_tokens(chars):
    """Estimate tokens from character count (~4 chars/token for English)."""
    return chars // 4


def compute_cost(input_tokens, output_tokens, model):
    """Compute cost in USD."""
    p = PRICING[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def main():
    print("=" * 85)
    print("COST AND EFFICIENCY ANALYSIS")
    print("=" * 85)

    claude_outputs = get_output_sizes("evaluation_outputs_v2")
    gpt_outputs = get_output_sizes("results/gpt4o_mini")

    # System prompt tokens (same for both)
    with open("config.py") as f:
        config_text = f.read()
    # Extract SYSTEM_PROMPT length
    import config
    sys_prompt_tokens = estimate_tokens(len(config.SYSTEM_PROMPT))
    user_template_tokens = estimate_tokens(len(config.USER_PROMPT_TEMPLATE) - 2)  # minus %s

    # ── Per-dataset costs ──
    datasets = list(PAPER_CHARS.keys())

    print(f"\n{'Dataset':<18} {'Paper':>8} {'Input tok':>10} {'Out tok':>9} {'Claude $':>9} {'GPT $':>8} {'C time':>7} {'G time':>7}")
    print("-" * 85)

    claude_costs = []
    gpt_costs = []
    claude_times = []
    gpt_times = []

    for ds in datasets:
        paper_chars = min(PAPER_CHARS[ds], 300000)  # MAX_PDF_CHARS cap
        input_tokens = sys_prompt_tokens + user_template_tokens + estimate_tokens(paper_chars)

        claude_out = estimate_tokens(claude_outputs.get(ds, 2000))
        gpt_out = estimate_tokens(gpt_outputs.get(ds, 2000))

        c_cost = compute_cost(input_tokens, claude_out, "claude-sonnet-4-5")
        g_cost = compute_cost(input_tokens, gpt_out, "gpt-4o-mini")

        c_time = EXTRACTION_TIMES["claude"].get(ds, 40)
        g_time = EXTRACTION_TIMES["gpt"].get(ds, 25)

        claude_costs.append(c_cost)
        gpt_costs.append(g_cost)
        claude_times.append(c_time)
        gpt_times.append(g_time)

        print(f"{ds:<18} {paper_chars:>7} {input_tokens:>10} {claude_out:>9} ${c_cost:>7.4f} ${g_cost:>6.4f} {c_time:>5}s {g_time:>5}s")

    c_total = sum(claude_costs)
    g_total = sum(gpt_costs)
    c_avg = np.mean(claude_costs)
    g_avg = np.mean(gpt_costs)
    c_time_total = sum(claude_times)
    g_time_total = sum(gpt_times)

    print("-" * 85)
    print(f"{'TOTAL':<18} {'':>8} {'':>10} {'':>9} ${c_total:>7.4f} ${g_total:>6.4f} {c_time_total:>5}s {g_time_total:>5}s")
    print(f"{'AVERAGE':<18} {'':>8} {'':>10} {'':>9} ${c_avg:>7.4f} ${g_avg:>6.4f} {np.mean(claude_times):>5.0f}s {np.mean(gpt_times):>5.0f}s")

    # ── Judge costs ──
    print(f"\n{'='*85}")
    print("LLM JUDGE COSTS (field-type-aware evaluation)")
    print(f"{'='*85}")

    judge_cache_file = Path("results/field_type_eval/llm_judge_cache.json")
    judge_calls = 0
    if judge_cache_file.exists():
        with open(judge_cache_file) as f:
            cache = json.load(f)
        judge_calls = len(cache)

    # Each judge call: ~200 input tokens (prompt + values) + ~5 output tokens
    judge_input = judge_calls * 200
    judge_output = judge_calls * 5
    judge_cost = compute_cost(judge_input, judge_output, "gpt-4o-mini-judge")

    # Error taxonomy judge
    tax_cache_file = Path("results/error_taxonomy/classify_cache.json")
    tax_calls = 0
    if tax_cache_file.exists():
        with open(tax_cache_file) as f:
            tax_cache = json.load(f)
        tax_calls = len(tax_cache)

    tax_input = tax_calls * 300
    tax_output = tax_calls * 10
    tax_cost = compute_cost(tax_input, tax_output, "gpt-4o-mini-judge")

    print(f"\n  Field-type judge calls: {judge_calls}")
    print(f"  Error taxonomy calls:   {tax_calls}")
    print(f"  Judge cost (field-type): ${judge_cost:.4f}")
    print(f"  Judge cost (taxonomy):   ${tax_cost:.4f}")
    print(f"  Total judge cost:        ${judge_cost + tax_cost:.4f}")

    # ── Main comparison table ──
    print(f"\n{'='*85}")
    print("MAIN COMPARISON TABLE")
    print(f"{'='*85}")

    # Composite scores from field-type eval
    composites = {"Claude Sonnet 4.5": 49.4, "GPT-4o-mini": 31.3, "HF Auto-Croissant": 8.8}

    print(f"\n{'Method':<22} {'Composite':>10} {'$/dataset':>10} {'s/dataset':>10} {'Total (8)':>10} {'$/pp':>8}")
    print("-" * 75)

    for method, comp in composites.items():
        if method == "Claude Sonnet 4.5":
            avg_cost = c_avg
            avg_time = np.mean(claude_times)
            total = c_total
        elif method == "GPT-4o-mini":
            avg_cost = g_avg
            avg_time = np.mean(gpt_times)
            total = g_total
        else:
            avg_cost = 0
            avg_time = 0
            total = 0

        cpp = avg_cost / comp if comp > 0 else 0  # cost per percentage point
        print(f"{method:<22} {comp:>9.1f}% ${avg_cost:>8.4f} {avg_time:>8.0f}s ${total:>8.4f} ${cpp:>6.4f}")

    # ── Scaling projections ──
    print(f"\n{'='*85}")
    print("SCALING PROJECTIONS")
    print(f"{'='*85}")

    print(f"\n{'Datasets':>10} {'Claude cost':>12} {'Claude time':>12} {'GPT cost':>10} {'GPT time':>10}")
    print("-" * 60)
    for n in [8, 50, 100, 500, 1000]:
        c = c_avg * n
        ct = np.mean(claude_times) * n / 3600
        g = g_avg * n
        gt = np.mean(gpt_times) * n / 3600
        print(f"{n:>10} ${c:>10.2f} {ct:>10.1f}h ${g:>8.2f} {gt:>8.1f}h")

    # ── Save ──
    results = {
        "pricing": PRICING,
        "per_dataset": {
            ds: {
                "claude_cost": round(claude_costs[i], 5),
                "gpt_cost": round(gpt_costs[i], 5),
                "claude_time_s": claude_times[i],
                "gpt_time_s": gpt_times[i],
                "paper_chars": PAPER_CHARS[ds],
            }
            for i, ds in enumerate(datasets)
        },
        "totals": {
            "claude": {"total_cost": round(c_total, 4), "avg_cost": round(c_avg, 5), "total_time_s": c_time_total},
            "gpt": {"total_cost": round(g_total, 4), "avg_cost": round(g_avg, 5), "total_time_s": g_time_total},
            "judge": {"calls": judge_calls, "cost": round(judge_cost, 4)},
        },
        "composites": composites,
    }
    with open(OUT_DIR / "cost_analysis.json", "w") as f:
        json.dump(results, f, indent=2)

    # Markdown
    md = f"""# Cost Analysis

## Main Comparison

| Method | Composite | $/dataset | s/dataset | Total (8 DS) | $/pp |
|--------|-----------|-----------|-----------|-------------|------|
| Claude Sonnet 4.5 | {composites['Claude Sonnet 4.5']:.1f}% | ${c_avg:.4f} | {np.mean(claude_times):.0f}s | ${c_total:.4f} | ${c_avg/composites['Claude Sonnet 4.5']:.4f} |
| GPT-4o-mini | {composites['GPT-4o-mini']:.1f}% | ${g_avg:.4f} | {np.mean(gpt_times):.0f}s | ${g_total:.4f} | ${g_avg/composites['GPT-4o-mini']:.4f} |
| HF Auto-Croissant | {composites['HF Auto-Croissant']:.1f}% | $0.0000 | 0s | $0.0000 | free |

## Scaling Projections

| Datasets | Claude | GPT-4o-mini |
|----------|--------|-------------|
| 50 | ${c_avg*50:.2f} | ${g_avg*50:.2f} |
| 100 | ${c_avg*100:.2f} | ${g_avg*100:.2f} |
| 1000 | ${c_avg*1000:.2f} | ${g_avg*1000:.2f} |

## Judge Evaluation Cost
- Field-type judge: {judge_calls} calls = ${judge_cost:.4f}
- Error taxonomy: {tax_calls} calls = ${tax_cost:.4f}
"""
    with open(OUT_DIR / "cost_analysis_report.md", "w") as f:
        f.write(md)

    print(f"\nSaved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
