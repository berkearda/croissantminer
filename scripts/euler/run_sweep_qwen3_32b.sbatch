#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Qwen3-32B single-pass size sweep.
#   Dense Qwen3 ladder, canonical prompt, temp 0, no truncation.
#   32K-native model served at 131K via YaRN (factor 4.0), per the
#   Qwen3 model card. Thinking mode disabled by extract_openmodels.
# Submit: sbatch scripts/euler/run_sweep_qwen3_32b.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_sweep_qwen3_32b
#SBATCH --account=<euler_account>
#SBATCH --output=logs/sweep_qwen3_32b_%j.out
#SBATCH --error=logs/sweep_qwen3_32b_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=2
#SBATCH --gres=gpumem:90g
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
    --model Qwen/Qwen3-32B \
    --model-name qwen3_32b_sweep \
    --max-model-len 131072 \
    --rope-scaling '{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}' \
    --tensor-parallel-size 2 \
    --batch-size 2 \
    --gpu-memory-utilization 0.90 \
    --max-tokens 16384 \
    --temperature 0.0

echo "Qwen3-32B sweep extraction complete."
