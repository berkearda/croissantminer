#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Gemma 4 31B-IT INT4/AWQ on 1× RTX 4090 — FALLBACK sbatch.
#   Use only if Pro 6000 queue is too long.
# Tradeoff: INT4 (~8GB) is measurably less accurate than FP8.
# Submit: sbatch scripts/euler/run_gemma4_31b_4090.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_gemma4_31b_4090
#SBATCH --account=<euler_account>
#SBATCH --output=logs/gemma4_4090_%j.out
#SBATCH --error=logs/gemma4_4090_%j.err
#SBATCH --gpus=nvidia_geforce_rtx_4090:1
#SBATCH --mem-per-cpu=8G
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00

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

# NVIDIA publishes an NVFP4 (near-INT4) variant; vllm 0.11.1+ supports it.
python scripts/euler/extract_openmodels.py \
    --model nvidia/Gemma-4-31B-IT-NVFP4 \
    --model-name gemma4_31b_nvfp4 \
    --quantization nvfp4 \
    --max-model-len 65536 \
    --tensor-parallel-size 1 \
    --batch-size 2 \
    --gpu-memory-utilization 0.92 \
    --temperature 0.0

echo "Gemma 4 31B-IT NVFP4 (4090 fallback) extraction complete."
