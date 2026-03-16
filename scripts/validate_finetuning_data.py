#!/usr/bin/env python3
"""
Validate fine-tuning data files.

Checks:
  - All JSONL entries parse correctly
  - Required fields present in each format
  - Token length distribution (min, max, mean, p50, p95)
  - Flags entries exceeding target context length
  - Validates JSON output in assistant responses

Usage:
    python scripts/validate_finetuning_data.py
    python scripts/validate_finetuning_data.py --max-context 8192
    python scripts/validate_finetuning_data.py --format chatml
"""

import sys
import json
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("data/finetuning")


def estimate_tokens(text: str) -> int:
    """Rough token count: ~4 chars per token."""
    return len(text) // 4


def validate_chatml_entry(entry, idx, errors):
    """Validate a single ChatML entry."""
    if "messages" not in entry:
        errors.append(f"  Entry {idx}: missing 'messages' key")
        return None

    msgs = entry["messages"]
    if not isinstance(msgs, list) or len(msgs) < 2:
        errors.append(f"  Entry {idx}: 'messages' must be a list with >= 2 entries")
        return None

    roles = [m.get("role") for m in msgs]
    if roles[0] != "system":
        errors.append(f"  Entry {idx}: first message should be 'system', got '{roles[0]}'")
    if "user" not in roles:
        errors.append(f"  Entry {idx}: no 'user' message found")
    if "assistant" not in roles:
        errors.append(f"  Entry {idx}: no 'assistant' message found")

    for m in msgs:
        if "content" not in m or not m["content"]:
            errors.append(f"  Entry {idx}: message with role '{m.get('role')}' has empty content")

    # Extract total tokens
    total_text = " ".join(m.get("content", "") for m in msgs)
    return estimate_tokens(total_text)


def validate_alpaca_entry(entry, idx, errors):
    """Validate a single Alpaca entry."""
    for key in ["instruction", "input", "output"]:
        if key not in entry:
            errors.append(f"  Entry {idx}: missing '{key}' key")
            return None
        if not entry[key]:
            errors.append(f"  Entry {idx}: '{key}' is empty")

    total_text = entry["instruction"] + " " + entry["input"] + " " + entry["output"]
    return estimate_tokens(total_text)


def validate_output_json(entry, fmt, idx, warnings):
    """Check that the assistant/output field contains valid JSON."""
    if fmt == "chatml":
        assistant_msgs = [m for m in entry.get("messages", []) if m.get("role") == "assistant"]
        content = assistant_msgs[0]["content"] if assistant_msgs else ""
    else:
        content = entry.get("output", "")

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            warnings.append(f"  Entry {idx}: output JSON is not a dict (got {type(parsed).__name__})")
        return True
    except json.JSONDecodeError as e:
        warnings.append(f"  Entry {idx}: output is not valid JSON — {e}")
        return False


def validate_file(filepath, fmt, max_context):
    """Validate a single JSONL file."""
    if not filepath.exists():
        print(f"  NOT FOUND: {filepath}")
        return

    print(f"\n  {filepath.name}")
    print(f"  {'─' * 60}")

    errors = []
    warnings = []
    token_counts = []
    valid_json = 0
    total = 0

    validator = validate_chatml_entry if fmt == "chatml" else validate_alpaca_entry

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            total += 1
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"  Line {i+1}: invalid JSON — {e}")
                continue

            tokens = validator(entry, i + 1, errors)
            if tokens is not None:
                token_counts.append(tokens)

            if validate_output_json(entry, fmt, i + 1, warnings):
                valid_json += 1

    # Report
    print(f"  Entries: {total}")
    print(f"  Parse errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print(f"  Valid output JSON: {valid_json}/{total}")

    if token_counts:
        toks = np.array(token_counts)
        exceeds = int(np.sum(toks > max_context))
        print(f"\n  Token distribution:")
        print(f"    Min:  {int(np.min(toks)):>8}")
        print(f"    Mean: {int(np.mean(toks)):>8}")
        print(f"    P50:  {int(np.median(toks)):>8}")
        print(f"    P95:  {int(np.percentile(toks, 95)):>8}")
        print(f"    Max:  {int(np.max(toks)):>8}")
        print(f"    Exceeds {max_context} tokens: {exceeds}/{total}", end="")
        if exceeds > 0:
            print(f" ⚠ ({exceeds/total*100:.0f}% would be truncated)")
        else:
            print(" ✓")

    if errors:
        print(f"\n  ERRORS:")
        for e in errors[:10]:
            print(f"    {e}")
        if len(errors) > 10:
            print(f"    ... and {len(errors)-10} more")

    if warnings:
        print(f"\n  WARNINGS:")
        for w in warnings[:5]:
            print(f"    {w}")
        if len(warnings) > 5:
            print(f"    ... and {len(warnings)-5} more")

    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(description="Validate fine-tuning data")
    parser.add_argument("--max-context", type=int, default=8192,
                        help="Target context length in tokens (default: 8192)")
    parser.add_argument("--format", choices=["chatml", "alpaca", "both"], default="both",
                        help="Which format to validate")
    args = parser.parse_args()

    print("=" * 70)
    print("VALIDATE FINE-TUNING DATA")
    print(f"Target context: {args.max_context} tokens")
    print("=" * 70)

    # Load metadata if available
    meta_file = DATA_DIR / "metadata.json"
    if meta_file.exists():
        with open(meta_file) as f:
            meta = json.load(f)
        print(f"\nMetadata: {meta['total_examples']} examples, "
              f"max_tokens={meta['max_tokens']}, "
              f"sources: {meta['sources']}")

    all_ok = True
    formats = ["chatml", "alpaca"] if args.format == "both" else [args.format]

    for fmt in formats:
        fmt_dir = DATA_DIR / fmt
        print(f"\n{'='*70}")
        print(f"FORMAT: {fmt.upper()}")
        print(f"{'='*70}")

        if not fmt_dir.exists():
            print(f"  Directory not found: {fmt_dir}")
            all_ok = False
            continue

        for split in ["train", "val", "test"]:
            filepath = fmt_dir / f"{split}.jsonl"
            ok = validate_file(filepath, fmt, args.max_context)
            if ok is False:
                all_ok = False

    print(f"\n{'='*70}")
    if all_ok:
        print("ALL VALIDATIONS PASSED ✓")
    else:
        print("SOME VALIDATIONS FAILED ✗")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
