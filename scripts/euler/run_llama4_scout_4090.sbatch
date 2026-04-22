#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Llama 4 Scout 17B-16E INT4/AWQ on 4× RTX 4090 — FALLBACK sbatch.
#   Use only if Pro 6000 queue is too long.
# Tradeoff: INT4 (~28GB) is measurably less accurate than FP8.
#   Llama 4 Scout MoE benefits from expert-parallel on multi-GPU.
# Submit: sbatch scripts/euler/run_llama4_scout_4090.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_llama4_scout_4090
#SBATCH --account=<euler_account>
#SBATCH --output=logs/llama4_scout_4090_%j.out
#SBATCH --error=logs/llama4_scout_4090_%j.err
#SBATCH --gpus=nvidia_geforce_rtx_4090:4
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=16
#SBATCH --time=10:00:00

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

# vLLM will try the AWQ kernel; expert-parallel distributes MoE experts
# across GPUs instead of sharding — the recommended pattern for 4× 4090.
python scripts/euler/extract_openmodels.py \
    --model meta-llama/Llama-4-Scout-17B-16E-Instruct \
    --model-name llama4_scout_int4 \
    --quantization awq \
    --max-model-len 65536 \
    --tensor-parallel-size 4 \
    --enable-expert-parallel \
    --batch-size 2 \
    --gpu-memory-utilization 0.92 \
    --temperature 0.0

echo "Llama 4 Scout INT4 (4090 fallback) extraction complete."
