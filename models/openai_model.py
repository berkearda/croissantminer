"""Backward-compatibility shim. Canonical source: croissantminer.models.openai_model

This file re-exports from the croissantminer package so existing scripts
that do `from config import X` or `from models.claude_model import Y`
keep working while the actual code lives in croissantminer/.

DO NOT add logic here. Edit the canonical file at:
  croissantminer/models/openai_model.py
"""

from croissantminer.models.openai_model import *  # noqa: F401, F403
