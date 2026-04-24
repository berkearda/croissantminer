#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Mistral Small 3.2 24B-Instruct Dense on 1× RTX Pro 6000
#   Released June 2025. Apache 2.0. 128K native context.
#   Replaces Gemma 4 31B in the matrix (blocked by vLLM #39914).
#   3.2 > 3.1: structured-output + function-calling improvements,
#   Arena Hard 19.56% → 43.10%, WildBench +10 pts.
# Submit:  sbatch scripts/euler/run_mistral_small_3_24b.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_mistral_s3_24b
#SBATCH --account=<euler_account>
#SBATCH --output=logs/mistral_s3_24b_%j.out
#SBATCH --error=logs/mistral_s3_24b_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:1
#SBATCH --mem-per-cpu=8G
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

# Mistral Small 3.2 at bf16 fits 1× 96GB with headroom for KV cache
# at 128K context. No quantization, no bug workarounds needed.
python scripts/euler/extract_openmodels.py \
    --model mistralai/Mistral-Small-3.2-24B-Instruct-2506 \
    --model-name mistral_small_3_24b \
    --max-model-len 131072 \
    --tensor-parallel-size 1 \
    --batch-size 4 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0

echo "Mistral Small 3.2 24B extraction complete."
