#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Submit all 3 self-hosted open-model jobs.
# Run from Euler login node: bash scripts/euler/run_all_models.sh
#
# Prereq: setup_euler.sh completed, sync'd repo + PDFs, smoke test passed.
# Lineup: Qwen 3.6-35B-A3B, Gemma 4 31B, Llama 4 Scout 17B-16E (109B).
# ═══════════════════════════════════════════════════════════════

set -e
mkdir -p logs

echo "Submitting open-model extraction jobs..."
JOB_QWEN=$(sbatch --parsable scripts/euler/run_qwen36_35b.sbatch)
echo "  Qwen 3.6-35B-A3B   → $JOB_QWEN"
JOB_GEMMA=$(sbatch --parsable scripts/euler/run_gemma4_31b.sbatch)
echo "  Gemma 4 31B        → $JOB_GEMMA"
JOB_LLAMA=$(sbatch --parsable scripts/euler/run_llama4_scout.sbatch)
echo "  Llama 4 Scout 109B → $JOB_LLAMA"

echo ""
echo "All 3 jobs submitted. Monitor: squeue --me"
echo "Outputs: \$SCRATCH/croissantminer/data/extractions/{qwen3_6_35b_a3b,gemma4_31b,llama4_scout}/"
echo ""
echo "If Pro 6000 queue drags, use the 4090 fallbacks:"
echo "  sbatch scripts/euler/run_qwen36_35b_4090.sbatch   (INT4/AWQ)"
echo "  sbatch scripts/euler/run_gemma4_31b_4090.sbatch   (INT4/AWQ)"
echo "  sbatch scripts/euler/run_llama4_scout_4090.sbatch (INT4/AWQ, needs 4× 4090)"
echo ""
echo "Separately, API-only models run locally (not on Euler):"
echo "  GLM-5.1:     python scripts/euler/extract_api_models.py --provider zai      --model glm-5.1       --model-name glm_5_1"
echo "  DeepSeek V3: python scripts/euler/extract_api_models.py --provider deepseek --model deepseek-chat --model-name deepseek_v3"
