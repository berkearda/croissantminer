#!/usr/bin/env python3
"""
6c: Fine-Tuning Script using Unsloth + QLoRA

Loads Qwen 2.5-7B-Instruct (4-bit quantized), applies LoRA,
trains on CroissantMiner extraction data.

Requirements:
  pip install unsloth transformers datasets trl peft bitsandbytes

Usage:
  python finetuning/train.py
  python finetuning/train.py --epochs 5 --data finetuning/data/combined.jsonl
  python finetuning/train.py --resume finetuning/checkpoints/checkpoint-500
"""

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_DATA = ROOT / "finetuning" / "data" / "combined.jsonl"
CHECKPOINT_DIR = ROOT / "finetuning" / "checkpoints"
MODEL_DIR = ROOT / "finetuning" / "models" / "croissantminer-qwen-7b"
LOG_DIR = ROOT / "finetuning" / "logs"

# Model
BASE_MODEL = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
MAX_SEQ_LENGTH = 8192

# LoRA
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.15

# Training
DEFAULT_EPOCHS = 3
BATCH_SIZE = 2
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.03
NEFTUNE_ALPHA = 5.0
SEED = 42

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("train")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen for CroissantMiner")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--resume", type=Path, default=None)
    parser.add_argument("--lr", type=float, default=LEARNING_RATE)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--max-seq-length", type=int, default=MAX_SEQ_LENGTH)
    parser.add_argument("--dry-run", action="store_true", help="Load data only, skip training")
    args = parser.parse_args()

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── Validate data ──
    if not args.data.exists():
        log.error(f"Training data not found: {args.data}")
        log.info("Run `python finetuning/prepare_data.py` first.")
        sys.exit(1)

    with open(args.data) as f:
        n_examples = sum(1 for _ in f)
    log.info(f"Training data: {args.data} ({n_examples} examples)")

    if args.dry_run:
        log.info("Dry run — data validated, skipping training.")
        # Show a sample
        with open(args.data) as f:
            sample = json.loads(f.readline())
        log.info(f"  System prompt: {len(sample['messages'][0]['content'])} chars")
        log.info(f"  User content: {len(sample['messages'][1]['content'])} chars")
        log.info(f"  Assistant content: {len(sample['messages'][2]['content'])} chars")
        return

    # ── Load model ──
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        log.error("Unsloth not installed. Install with: pip install unsloth")
        log.info("Alternative: use transformers + peft directly (modify this script).")
        sys.exit(1)

    log.info(f"Loading {BASE_MODEL}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.resume or BASE_MODEL,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        dtype=None,  # auto-detect
    )

    # ── Apply LoRA ──
    log.info("Applying LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules="all-linear",
        use_gradient_checkpointing="unsloth",
    )

    # ── Load data ──
    from datasets import load_dataset
    dataset = load_dataset("json", data_files=str(args.data), split="train")
    log.info(f"Dataset loaded: {len(dataset)} examples")

    # Format for chat template
    def format_chat(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    dataset = dataset.map(format_chat, remove_columns=dataset.column_names)

    # ── Train ──
    from trl import SFTTrainer
    from transformers import TrainingArguments

    training_args = TrainingArguments(
        output_dir=str(CHECKPOINT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=args.lr,
        warmup_ratio=WARMUP_RATIO,
        lr_scheduler_type="cosine",
        logging_dir=str(LOG_DIR),
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        seed=SEED,
        bf16=True,
        optim="adamw_8bit",
        report_to="none",
        neftune_noise_alpha=NEFTUNE_ALPHA,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=True,
    )

    log.info(f"Starting training: {args.epochs} epochs, lr={args.lr}, batch={args.batch_size}×{GRAD_ACCUM}")
    trainer.train(resume_from_checkpoint=str(args.resume) if args.resume else None)

    # ── Save ──
    log.info(f"Saving model to {MODEL_DIR}...")
    model.save_pretrained_merged(
        str(MODEL_DIR),
        tokenizer,
        save_method="merged_16bit",
    )
    log.info("Training complete.")


if __name__ == "__main__":
    main()
