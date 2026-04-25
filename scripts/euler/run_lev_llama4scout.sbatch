#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Agentic LEV × Llama 4 Scout (vLLM-served, OpenAI-compatible)
#   Self-host meta-llama/Llama-4-Scout-17B-16E-Instruct on 2× RTX Pro 6000
#   then run scripts/agentic_lev.py against http://localhost:8000/v1.
#   LEV makes 5 specialist calls per paper (vs V2's ~1.5), so allow a
#   longer time budget than the V2 run.
# Submit: sbatch scripts/euler/run_lev_llama4scout.sbatch
# ═══════════════════════════════════════════════════════════════

#SBATCH --job-name=cm_lev_llama4
#SBATCH --account=<euler_account>
#SBATCH --output=logs/lev_llama4scout_%j.out
#SBATCH --error=logs/lev_llama4scout_%j.err
#SBATCH --partition=cuda13pr.4h
#SBATCH --gpus=nvidia_rtx_pro_6000:2
#SBATCH --mem-per-cpu=12G
#SBATCH --cpus-per-task=8
#SBATCH --time=12:00:00

source /etc/profile
module load stack/2024-05 gcc/13.2.0 python/3.11.6_cuda
module load eth_proxy
source $SCRATCH/croissantminer_venv/bin/activate

export HF_HOME=$SCRATCH/.huggingface
export TRANSFORMERS_CACHE=$SCRATCH/.huggingface
[ -f "$HOME/.cache/huggingface/token" ] && export HUGGING_FACE_HUB_TOKEN="$(cat $HOME/.cache/huggingface/token)"
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export PYTHONUNBUFFERED=1
export VLLM_BASE_URL="http://localhost:8000/v1"
export VLLM_API_KEY="EMPTY"

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
    > logs/vllm_serve_lev_${SLURM_JOB_ID}.log 2>&1 &
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

# ── Run agentic LEV against the local endpoint ──
# Skip-existing picks up where prior runs left off.
python scripts/agentic_lev.py --backbone llama-4-scout

echo "Agentic LEV × Llama 4 Scout complete."
