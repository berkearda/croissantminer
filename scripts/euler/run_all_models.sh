#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Submit all open-source model extraction jobs
# Run from Euler: bash scripts/euler/run_all_models.sh
# ═══════════════════════════════════════════════════════════════

set -e
mkdir -p logs

echo "Submitting open-source model extraction jobs..."

# ── Model 1: Qwen3-32B (best for structured JSON) ──
sbatch --job-name=cm_qwen3 \
    --gpus=nvidia_a100_80gb_pcie:1 \
    --mem-per-cpu=16G --cpus-per-task=8 --time=08:00:00 \
    --account=<euler_account> \
    --output=logs/qwen3_%j.out --error=logs/qwen3_%j.err \
    --wrap="
module load python/3.11.6 eth_proxy
source \$SCRATCH/croissantminer_venv/bin/activate
export HF_HOME=\$SCRATCH/.huggingface PYTHONUNBUFFERED=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
cd \$SCRATCH/croissantminer
python scripts/euler/extract_openmodels.py \
    --model Qwen/Qwen3-32B-FP8 --model-name qwen3_32b \
    --quantization fp8 --max-model-len 32768 --batch-size 4
"
echo "Submitted: Qwen3-32B"

# ── Model 2: Gemma 4 31B (Google open model) ──
# Note: if Gemma 4 not yet on HF, use google/gemma-3-27b-it as fallback
sbatch --job-name=cm_gemma4 \
    --gpus=nvidia_a100_80gb_pcie:1 \
    --mem-per-cpu=16G --cpus-per-task=8 --time=08:00:00 \
    --account=<euler_account> \
    --output=logs/gemma4_%j.out --error=logs/gemma4_%j.err \
    --wrap="
module load python/3.11.6 eth_proxy
source \$SCRATCH/croissantminer_venv/bin/activate
export HF_HOME=\$SCRATCH/.huggingface PYTHONUNBUFFERED=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
cd \$SCRATCH/croissantminer
python scripts/euler/extract_openmodels.py \
    --model google/gemma-3-27b-it --model-name gemma3_27b \
    --max-model-len 32768 --batch-size 4 --temperature 0.0
"
echo "Submitted: Gemma 3 27B"

# ── Model 3: Llama 4 Scout (Meta MoE — needs more VRAM) ──
# Scout is 109B total / 17B active. Needs ~110GB FP8 = 2x A100 80GB
# Fallback: use Llama 3.3 70B which fits on 1x A100 80GB with INT4
sbatch --job-name=cm_llama \
    --gpus=nvidia_a100_80gb_pcie:1 \
    --mem-per-cpu=16G --cpus-per-task=8 --time=08:00:00 \
    --account=<euler_account> \
    --output=logs/llama_%j.out --error=logs/llama_%j.err \
    --wrap="
module load python/3.11.6 eth_proxy
source \$SCRATCH/croissantminer_venv/bin/activate
export HF_HOME=\$SCRATCH/.huggingface PYTHONUNBUFFERED=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
cd \$SCRATCH/croissantminer
python scripts/euler/extract_openmodels.py \
    --model meta-llama/Llama-3.3-70B-Instruct --model-name llama3_70b \
    --quantization fp8 --max-model-len 16384 --batch-size 2 --temperature 0.0
"
echo "Submitted: Llama 3.3 70B"

echo ""
echo "All jobs submitted. Monitor with: squeue --me"
echo "Results will be in data/extractions/{model_name}/"
