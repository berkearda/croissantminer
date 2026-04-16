#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Test job: 1 paper on A100 80GB
# Submit: sbatch scripts/euler/run_test.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_test
#SBATCH --account=<euler_account>
#SBATCH --output=logs/test_%j.out
#SBATCH --error=logs/test_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:1
#SBATCH --mem-per-cpu=16G
#SBATCH --cpus-per-task=8
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
    --model Qwen/Qwen3-32B-FP8 \
    --model-name qwen3_32b \
    --quantization fp8 \
    --max-model-len 32768 \
    --batch-size 1 \
    --paper AI4Math_MathVista

echo "Test complete."
