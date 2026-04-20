#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Euler Extraction Job
# Qwen3-Next-80B-A3B on 2× RTX Pro 6000 (96GB each, 192GB total)
#
# Model choice rationale (decisions.md 2026-04-20):
#   Qwen3-Next-80B-A3B is the largest open-weight model we can run
#   on Euler with native 262K context. Since SuperGPQA is excluded
#   (344K), every paper fits without truncation or chunking.
#
# Submit: sbatch scripts/euler/run_extraction.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_qwen3_next
#SBATCH --account=<euler_account>
#SBATCH --output=logs/euler_%j.out
#SBATCH --error=logs/euler_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:2
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=16
#SBATCH --time=08:00:00

# ── Environment ──
source /etc/profile
module load stack/2024-05 gcc/13.2.0 python/3.11.6_cuda
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
    --model Qwen/Qwen3-Next-80B-A3B-Instruct \
    --model-name qwen3_next_80b \
    --quantization fp8 \
    --max-model-len 262144 \
    --tensor-parallel-size 2 \
    --batch-size 2 \
    --gpu-memory-utilization 0.90

echo "Job complete."
