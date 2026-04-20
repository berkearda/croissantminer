#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Test job: 1 paper on 2× RTX Pro 6000
# Used to verify Qwen3-Next-80B-A3B loads before committing to the
# full 102-paper run.
#
# Submit: sbatch scripts/euler/run_test.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_test_qwen3_next
#SBATCH --account=<euler_account>
#SBATCH --output=logs/test_%j.out
#SBATCH --error=logs/test_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:2
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00

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

python scripts/euler/extract_openmodels.py \
    --model Qwen/Qwen3-Next-80B-A3B-Instruct \
    --model-name qwen3_next_80b \
    --quantization fp8 \
    --max-model-len 262144 \
    --tensor-parallel-size 2 \
    --batch-size 1 \
    --paper AI4Math_MathVista

echo "Test complete."
