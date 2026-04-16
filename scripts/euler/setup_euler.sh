#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CroissantMiner — Euler Setup Script
# Run this ONCE on the Euler login node to set up environment
# ═══════════════════════════════════════════════════════════════

set -e

echo "=== CroissantMiner Euler Setup ==="

# 1. Load modules
module load python/3.11.6
module load eth_proxy  # needed for pip install + HuggingFace downloads

# 2. Create venv on SCRATCH (not HOME — quota is limited)
VENV_DIR="$SCRATCH/croissantminer_venv"
if [ -d "$VENV_DIR" ]; then
    echo "Venv already exists at $VENV_DIR"
else
    echo "Creating venv at $VENV_DIR..."
    python -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 3. Install dependencies
echo "Installing packages..."
pip install --upgrade pip
pip install vllm==0.9.1 pymupdf python-dotenv huggingface_hub tqdm

# 4. Pre-download model to SCRATCH
export HF_HOME="$SCRATCH/.huggingface"
export TRANSFORMERS_CACHE="$SCRATCH/.huggingface"

echo "Downloading Qwen3-32B-FP8 (~32GB)..."
python -c "
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3-32B-FP8', cache_dir='$SCRATCH/.huggingface')
print('Model downloaded successfully.')
"

echo ""
echo "=== Setup complete ==="
echo "Venv: $VENV_DIR"
echo "Model cache: $SCRATCH/.huggingface"
echo ""
echo "Next steps:"
echo "  1. Copy your repo: rsync -avz ./croissantminer/ euler:$SCRATCH/croissantminer/"
echo "  2. Copy PDFs: rsync -avz data/raw/ euler:$SCRATCH/croissantminer/data/raw/"
echo "  3. Submit job: sbatch scripts/euler/run_extraction.sbatch"
