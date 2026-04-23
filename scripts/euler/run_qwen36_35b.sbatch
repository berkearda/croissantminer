#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Qwen 3.6-35B-A3B-FP8 on 1× RTX Pro 6000 (Apache 2.0, 262K ctx)
#   Released April 2026. MoE 35B total / 3B active, Gated Delta
#   Network + sparse MoE architecture. First open-weight Qwen 3.6.
# Submit: sbatch scripts/euler/run_qwen36_35b.sbatch
# Fallback: sbatch scripts/euler/run_qwen36_35b_4090.sbatch (if Pro 6000 queue too long)
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_qwen36_35b
#SBATCH --account=<euler_account>
#SBATCH --output=logs/qwen36_%j.out
#SBATCH --error=logs/qwen36_%j.err
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
    --model Qwen/Qwen3.6-35B-A3B-FP8 \
    --model-name qwen3_6_35b_a3b \
    --max-model-len 131072 \
    --tensor-parallel-size 1 \
    --batch-size 4 \
    --gpu-memory-utilization 0.90 \
    --temperature 0.0

echo "Qwen 3.6-35B-A3B extraction complete."
