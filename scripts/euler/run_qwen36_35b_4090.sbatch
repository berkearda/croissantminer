#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Qwen 3.6-35B-A3B INT4/AWQ on 1× RTX 4090 — FALLBACK sbatch.
#   Use only if Pro 6000 queue is too long. 80 nodes × 8 = 640 4090s on
#   Euler (vs 10 × 8 = 80 Pro 6000), so queue wait is ~8× shorter.
# Tradeoff: INT4 (~9GB) is measurably less accurate than FP8 — note
#   the quantization choice in the paper's Methods section.
# Submit: sbatch scripts/euler/run_qwen36_35b_4090.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_qwen36_35b_4090
#SBATCH --account=<euler_account>
#SBATCH --output=logs/qwen36_4090_%j.out
#SBATCH --error=logs/qwen36_4090_%j.err
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

# AWQ variant by community quantizer (QuantTrio) — Qwen does not publish
# an official AWQ yet for 3.6. Model card must note this.
python scripts/euler/extract_openmodels.py \
    --model QuantTrio/Qwen3.6-35B-A3B-AWQ \
    --model-name qwen3_6_35b_a3b_int4 \
    --quantization awq \
    --max-model-len 65536 \
    --tensor-parallel-size 1 \
    --batch-size 2 \
    --gpu-memory-utilization 0.92 \
    --temperature 0.0

echo "Qwen 3.6-35B-A3B INT4 (4090 fallback) extraction complete."
