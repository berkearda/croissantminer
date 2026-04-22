#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Llama 4 Scout 17B-16E-Instruct on 2× RTX Pro 6000
#   109B total, 17B active, 10M context, Llama 4 license.
#   Released 2025-04. MoE — uses expert-parallel for throughput.
# Submit: sbatch scripts/euler/run_llama4_scout.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_llama4_scout
#SBATCH --account=<euler_account>
#SBATCH --output=logs/llama4_scout_%j.out
#SBATCH --error=logs/llama4_scout_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:2
#SBATCH --mem-per-cpu=12G
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

# Llama 4 Scout at FP8 fits 2× 96GB. Expert-parallel distributes experts
# across GPUs rather than sharding them (vLLM recommendation for MoE).
python scripts/euler/extract_openmodels.py \
    --model meta-llama/Llama-4-Scout-17B-16E-Instruct \
    --model-name llama4_scout \
    --quantization fp8 \
    --max-model-len 131072 \
    --tensor-parallel-size 2 \
    --enable-expert-parallel \
    --batch-size 2 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0

echo "Llama 4 Scout extraction complete."
