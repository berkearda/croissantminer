#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Smoke test — 1 paper on Gemma 4 31B (smallest, fastest-loading).
# Verifies venv + vLLM 0.11.1 + HF cache + PDF pipeline end-to-end
# before committing to full 102-paper runs.
#
# Submit: sbatch scripts/euler/run_test.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_smoke_gemma4
#SBATCH --account=<euler_account>
#SBATCH --output=logs/test_%j.out
#SBATCH --error=logs/test_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:1
#SBATCH --mem-per-cpu=8G
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00

source /etc/profile
module load stack/2024-05 gcc/13.2.0 python/3.11.6_cuda
module load eth_proxy
source $SCRATCH/croissantminer_venv/bin/activate

export HF_HOME=$SCRATCH/.huggingface
export TRANSFORMERS_CACHE=$SCRATCH/.huggingface
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONUNBUFFERED=1

mkdir -p logs
cd $SCRATCH/croissantminer

python scripts/euler/extract_openmodels.py \
    --model google/gemma-4-31B-it \
    --model-name gemma4_31b_smoke \
    --max-model-len 131072 \
    --tensor-parallel-size 1 \
    --batch-size 1 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0 \
    --paper AI4Math_MathVista

echo "Smoke test complete. If successful, next:"
echo "  sbatch scripts/euler/run_qwen36_35b.sbatch"
echo "  sbatch scripts/euler/run_gemma4_31b.sbatch"
echo "  sbatch scripts/euler/run_llama4_scout.sbatch"
