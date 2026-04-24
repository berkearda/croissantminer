#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Mistral Small 4 119B MoE (128 experts, 4 active ≈ 6.5B active)
# on 2× RTX Pro 6000. Apache 2.0. 256K native context.
#   Released March 2026. Replaces Mistral Small 3.2 (context-capped)
#   and Gemma 4 31B (vLLM #39914 hang) in the open-weight matrix.
#   Same operational envelope as Llama 4 Scout (109B MoE); uses
#   expert-parallel + online FP8 (Marlin) on 2× Pro 6000.
# Submit:  sbatch scripts/euler/run_mistral_small_4.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_mistral_s4_119b
#SBATCH --account=<euler_account>
#SBATCH --output=logs/mistral_s4_%j.out
#SBATCH --error=logs/mistral_s4_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:2
#SBATCH --mem-per-cpu=12G
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00

source /etc/profile
module load stack/2024-05 gcc/13.2.0 python/3.11.6_cuda
module load eth_proxy
source $SCRATCH/croissantminer_venv/bin/activate

export HF_HOME=$SCRATCH/.huggingface
export TRANSFORMERS_CACHE=$SCRATCH/.huggingface
[ -f "$HOME/.cache/huggingface/token" ] && export HUGGING_FACE_HUB_TOKEN="$(cat $HOME/.cache/huggingface/token)"
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONUNBUFFERED=1

mkdir -p logs
cd $SCRATCH/croissantminer

# Mistral Small 4 at FP8 fits 2× 96GB with expert-parallel (mirrors
# Llama 4 Scout). Native context 256K; cap at 200K for KV-cache
# safety (matches Qwen/Llama operational pattern).
python scripts/euler/extract_openmodels.py \
    --model mistralai/Mistral-Small-4-119B-2603 \
    --model-name mistral_small_4 \
    --quantization fp8 \
    --max-model-len 200000 \
    --tensor-parallel-size 2 \
    --enable-expert-parallel \
    --batch-size 2 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0

echo "Mistral Small 4 119B extraction complete."
