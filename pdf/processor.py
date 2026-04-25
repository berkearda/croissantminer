"""Backward-compatibility shim. Canonical source: croissantminer.pdf.processor

This file re-exports from the croissantminer package so existing scripts
that do `from config import X` or `from models.claude_model import Y`
keep working while the actual code lives in croissantminer/.

DO NOT add logic here. Edit the canonical file at:
  croissantminer/pdf/processor.py
"""

from croissantminer.pdf.processor import *  # noqa: F401, F403
