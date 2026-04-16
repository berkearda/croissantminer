#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Euler Extraction Job (A100 80GB)
# Submit: sbatch scripts/euler/run_extraction.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_qwen3
#SBATCH --account=<euler_account>
#SBATCH --output=logs/euler_%j.out
#SBATCH --error=logs/euler_%j.err
#SBATCH --gpus=nvidia_a100_80gb_pcie:1
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00

# ── Environment ──
module load python/3.11.6_cuda
module load eth_proxy

source $SCRATCH/croissantminer_venv/bin/activate

export HF_HOME=$SCRATCH/.huggingface
export TRANSFORMERS_CACHE=$SCRATCH/.huggingface
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONUNBUFFERED=1

# ── Create log dir ──
mkdir -p logs

# ── Run ──
cd $SCRATCH/croissantminer

python scripts/euler/extract_openmodels.py \
    --model Qwen/Qwen3-32B-FP8 \
    --model-name qwen3_32b \
    --quantization fp8 \
    --max-model-len 32768 \
    --batch-size 4 \
    --gpu-memory-utilization 0.90

echo "Job complete."
