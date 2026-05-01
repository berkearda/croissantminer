#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Agentic LEV mixed-backbone — Llama 4 Scout LOCATOR + GPT-5.4-mini EXTRACTOR
#   Bake-off config C1 for the 2026-05-01 V2/LEV iteration plan.
#   Self-host meta-llama/Llama-4-Scout-17B-16E-Instruct on 2× RTX Pro 6000
#   for the LLM locator step; GPT-5.4-mini handles the 5 extract calls
#   (so this sbatch needs OPENAI_API_KEY exported and eth_proxy egress).
#   Output: data/extractions/agentic_lev_llama_4_scout_gpt5_4_mini/
# Submit: sbatch scripts/euler/run_lev_llama4scout_locator.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_lev_llama4_loc
#SBATCH --account=<euler_account>
#SBATCH --output=logs/lev_llama4scout_locator_%j.out
#SBATCH --error=logs/lev_llama4scout_locator_%j.err
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

# Local vLLM endpoint that Llama 4 Scout will serve on.
export VLLM_BASE_URL="http://localhost:8000/v1"
export VLLM_API_KEY="EMPTY"

# Extractor (GPT-5.4-mini) needs OpenAI access. Pull from .env if present.
if [ -f "$SCRATCH/croissantminer/.env" ]; then
    set -a; source "$SCRATCH/croissantminer/.env"; set +a
fi
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY not set; extractor will fail." >&2
    exit 1
fi

mkdir -p logs
cd $SCRATCH/croissantminer

# ── Start vLLM OpenAI-compatible server in the background ──
vllm serve meta-llama/Llama-4-Scout-17B-16E-Instruct \
    --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 2 \
    --enable-expert-parallel \
    --max-model-len 131072 \
    --quantization fp8 \
    --gpu-memory-utilization 0.90 \
    > logs/vllm_serve_lev_locator_${SLURM_JOB_ID}.log 2>&1 &
VLLM_PID=$!
trap "kill $VLLM_PID 2>/dev/null; wait 2>/dev/null" EXIT

# ── Wait for the server to come up ──
echo "Waiting for vllm to listen on :8000..."
for i in $(seq 1 720); do  # 720 * 30s = 6h max
    if curl -fsS http://localhost:8000/v1/models > /dev/null 2>&1; then
        echo "vllm ready after $((i*30))s"
        break
    fi
    sleep 30
done
curl -fsS http://localhost:8000/v1/models > /dev/null || { echo "vllm did not start in time" >&2; exit 1; }

# ── Run agentic LEV with mixed locator+extractor on dev only ──
# Locator: Llama 4 Scout (local vLLM)
# Extractor: GPT-5.4-mini (OpenAI API)
python scripts/agentic_lev.py \
    --locator-backbone llama-4-scout \
    --extractor-backbone gpt-5.4-mini \
    --dev-only

echo "Agentic LEV (Llama-locator + GPT-mini-extractor) complete."
