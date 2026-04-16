#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Euler Extraction Job (2x RTX 4090 fallback)
# Use this if A100 80GB nodes are not available
# Submit: sbatch scripts/euler/run_extraction_4090.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_qwen3_4090
#SBATCH --account=<euler_account>
#SBATCH --output=logs/euler_%j.out
#SBATCH --error=logs/euler_%j.err
#SBATCH --gpus=rtx_4090:2
#SBATCH --gres=gpumem:24g
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00

# ── Environment ──
module load python/3.11.6
module load eth_proxy

source $SCRATCH/croissantminer_venv/bin/activate

export HF_HOME=$SCRATCH/.huggingface
export TRANSFORMERS_CACHE=$SCRATCH/.huggingface
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONUNBUFFERED=1

mkdir -p logs
cd $SCRATCH/croissantminer

python scripts/euler/extract_openmodels.py \
    --model Qwen/Qwen3-32B-FP8 \
    --model-name qwen3_32b \
    --quantization fp8 \
    --max-model-len 16384 \
    --batch-size 2 \
    --gpu-memory-utilization 0.90 \
    --tensor-parallel-size 2

echo "Job complete."
