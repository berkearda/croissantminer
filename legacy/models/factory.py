"""Backward-compatibility shim. Canonical source: croissantminer.models.factory

This file re-exports from the croissantminer package so existing scripts
that do `from config import X` or `from models.claude_model import Y`
keep working while the actual code lives in croissantminer/.

DO NOT add logic here. Edit the canonical file at:
  croissantminer/models/factory.py
"""

from croissantminer.models.factory import *  # noqa: F401, F403
