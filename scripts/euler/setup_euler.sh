#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Euler Setup
# Run this ONCE on an Euler login node (or after a venv reset) to
# install dependencies and pre-cache the open-weight model lineup.
#
# Lineup (April 2026, from decisions.md):
#   1. Qwen 3.6-35B-A3B-FP8          (Apr 2026, Apache 2.0, 262K ctx, MoE 3B active)
#   2. Gemma 4 31B-IT Dense          (Apr 2,  2026, Apache 2.0, 256K ctx)
#   3. Llama 4 Scout 17B-16E (109B)  (Apr 2025, Llama 4 license, 10M ctx)
#
# Hardware: 2× RTX Pro 6000 (96GB each, 192GB total).
# ═══════════════════════════════════════════════════════════════

set -e

echo "=== CroissantMiner Euler Setup ==="

# 1. Load modules
module load stack/2024-05 gcc/13.2.0 python/3.11.6_cuda
module load eth_proxy  # required for pip + HF downloads

# 2. Venv on SCRATCH (HOME quota is tight)
VENV_DIR="$SCRATCH/croissantminer_venv"
if [ -d "$VENV_DIR" ]; then
    echo "Venv exists at $VENV_DIR"
    echo "  To rebuild from scratch:  rm -rf $VENV_DIR && rerun this script"
else
    echo "Creating venv at $VENV_DIR..."
    python -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 3. Install dependencies
echo ""
echo "Installing Python packages..."
pip install --upgrade pip wheel

# vllm 0.11.1 is needed for Gemma 4 support; also covers Qwen 3.5 and Llama 4 Scout.
pip install "vllm==0.11.1"
pip install "transformers>=4.50"
pip install pypdf2==3.0.1
pip install python-dotenv huggingface_hub tqdm openai

# 4. Pre-cache models
export HF_HOME="$SCRATCH/.huggingface"
export TRANSFORMERS_CACHE="$SCRATCH/.huggingface"
mkdir -p "$HF_HOME"

# Llama 4 Scout and Gemma 4 are gated on HuggingFace. Login with a read-only
# token before this script runs, OR export HF_TOKEN in the environment.
# If neither is present, gated downloads will 401 and we note the model as
# "not cached" — the sbatch will still try to download at job time.
if [ -z "$HF_TOKEN" ] && [ ! -f "$HOME/.cache/huggingface/token" ]; then
    echo "WARNING: no HF_TOKEN in env and no huggingface-cli login found."
    echo "  Gated models (Llama 4 Scout, Gemma 4) may fail to download."
    echo "  Fix:  huggingface-cli login  (or  export HF_TOKEN=hf_...)"
    echo "  Continuing anyway — non-gated models will cache fine."
fi
if [ -n "$HF_TOKEN" ]; then
    export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

echo ""
echo "Pre-caching open-weight models to $HF_HOME..."
echo "  (Skipped if already cached. Llama 4 Scout requires gated-access approval on HuggingFace.)"

python - <<'PYEOF'
import os
from huggingface_hub import snapshot_download

cache_dir = os.environ["HF_HOME"]
for model_id, label in [
    ("Qwen/Qwen3.6-35B-A3B-FP8",                  "Qwen 3.6-35B-A3B FP8 (~35GB)"),
    ("google/gemma-4-31B-it",                     "Gemma 4 31B-IT       (~62GB)"),
    ("meta-llama/Llama-4-Scout-17B-16E-Instruct", "Llama 4 Scout        (~218GB)"),
]:
    print(f"\n→ {label}: {model_id}")
    try:
        snapshot_download(model_id, cache_dir=cache_dir)
        print(f"   ✓ cached")
    except Exception as e:
        print(f"   ✗ failed: {e}")
        print(f"     (If gated, request access at https://huggingface.co/{model_id} then re-run.)")
PYEOF

echo ""
echo "=== Setup complete ==="
echo "Venv:         $VENV_DIR"
echo "Model cache:  $HF_HOME"
echo ""
echo "Next steps:"
echo "  1. Sync repo:       rsync -avz ./croissantminer/ euler:$SCRATCH/croissantminer/"
echo "  2. Sync PDFs:       rsync -avz data/raw/ euler:$SCRATCH/croissantminer/data/raw/"
echo "  3. Smoke test:      sbatch scripts/euler/run_test.sbatch"
echo "  4. Full extraction: sbatch scripts/euler/run_qwen36_35b.sbatch"
echo "                      sbatch scripts/euler/run_gemma4_31b.sbatch"
echo "                      sbatch scripts/euler/run_llama4_scout.sbatch"
