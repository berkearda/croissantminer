#!/bin/bash
# Run all 10 ablation variants sequentially and produce final summary.
#
# Estimated time: ~50 min extraction + ~40 min evaluation = ~90 min total
# Estimated cost: 10 variants × 8 datasets × ~$0.05/call = ~$4
#
# Usage:
#   ./scripts/run_all_ablations.sh           # full run
#   ./scripts/run_all_ablations.sh --dry-run # just check what would run

set -e
cd "$(dirname "$0")/.."

DRY_RUN=""
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "=== DRY RUN MODE ==="
fi

echo "========================================"
echo "CroissantMiner Ablation Experiments"
echo "========================================"
echo "Start: $(date)"
echo ""

# ── PROMPT ABLATION (4 variants) ──
echo "═══════════════════════════════════════"
echo "1/3: PROMPT ABLATION"
echo "═══════════════════════════════════════"
for variant in full no_rai_instructions no_extraction_guides minimal; do
    echo ""
    echo ">>> prompt / ${variant}"
    python3 scripts/run_ablations.py --type prompt --variant "$variant" $DRY_RUN
done

echo ""
echo "Prompt ablation comparison:"
python3 scripts/run_ablations.py --compare prompt 2>/dev/null || echo "(not enough data yet)"

# ── CONTEXT ABLATION (3 variants) ──
echo ""
echo "═══════════════════════════════════════"
echo "2/3: CONTEXT ABLATION"
echo "═══════════════════════════════════════"
for variant in full half quarter; do
    echo ""
    echo ">>> context / ${variant}"
    python3 scripts/run_ablations.py --type context --variant "$variant" $DRY_RUN
done

echo ""
echo "Context ablation comparison:"
python3 scripts/run_ablations.py --compare context 2>/dev/null || echo "(not enough data yet)"

# ── FEW-SHOT ABLATION (3 variants) ──
echo ""
echo "═══════════════════════════════════════"
echo "3/3: FEW-SHOT ABLATION"
echo "═══════════════════════════════════════"
for variant in zero_shot one_shot three_shot; do
    echo ""
    echo ">>> few_shot / ${variant}"
    python3 scripts/run_ablations.py --type few_shot --variant "$variant" $DRY_RUN
done

echo ""
echo "Few-shot ablation comparison:"
python3 scripts/run_ablations.py --compare few_shot 2>/dev/null || echo "(not enough data yet)"

# ── FINAL SUMMARY ──
echo ""
echo "========================================"
echo "ALL ABLATION COMPARISONS"
echo "========================================"
echo ""

for atype in prompt context few_shot; do
    python3 scripts/run_ablations.py --compare "$atype" 2>/dev/null || true
    echo ""
done

echo "========================================"
echo "Completed: $(date)"
echo "Results in: evaluation_outputs_ablations/"
echo "========================================"
