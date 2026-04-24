#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Gemma 4 31B-IT Dense on 1× RTX Pro 6000 (Apache 2.0, 256K ctx)
#   Released 2026-04-02. Beats Llama 4 on AIME/GPQA/LiveCodeBench.
# Submit:    sbatch scripts/euler/run_gemma4_31b.sbatch
# Fallback:  sbatch scripts/euler/run_gemma4_31b_4090.sbatch (if Pro 6000 queue too long)
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_gemma4_31b
#SBATCH --account=<euler_account>
#SBATCH --output=logs/gemma4_%j.out
#SBATCH --error=logs/gemma4_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:1
#SBATCH --mem-per-cpu=8G
#SBATCH --cpus-per-task=8
#SBATCH --time=06:00:00

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

python scripts/euler/extract_openmodels.py \
    --model google/gemma-4-31B-it \
    --model-name gemma4_31b \
    --max-model-len 131072 \
    --tensor-parallel-size 1 \
    --batch-size 1 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0 \
    --enforce-eager \
    --max-num-batched-tokens 4096

echo "Gemma 4 31B extraction complete."
