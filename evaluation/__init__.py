"""
Evaluation module for CroissantMiner

This module provides tools for evaluating the quality of automatically extracted
Croissant metadata against human-annotated groundtruth.
"""

from .groundtruth_parser import parse_groundtruth, load_groundtruth
from .metrics import (
    exact_match,
    partial_match,
    field_f1_score,
    overall_accuracy,
    per_field_accuracy
)
from .evaluator import compare_extraction, evaluate_against_groundtruth, batch_evaluate
from .reporter import generate_report, visualize_results, export_results

__all__ = [
    'parse_groundtruth',
    'load_groundtruth',
    'exact_match',
    'partial_match',
    'field_f1_score',
    'overall_accuracy',
    'per_field_accuracy',
    'compare_extraction',
    'evaluate_against_groundtruth',
    'batch_evaluate',
    'generate_report',
    'visualize_results',
    'export_results'
]
