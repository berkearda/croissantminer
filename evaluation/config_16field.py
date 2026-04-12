"""
16-field evaluation configuration for CroissantMiner.

These are the 16 fields with validated ground truth from the AAAI paper
(10 General + 6 RAI). The remaining 14 RAI fields require Phase 2 annotation.

Field categories determine the evaluation metric:
  Constrained (7) → exact match after normalization
  Short-text  (3) → token-level F1
  RAI Judge   (6) → LLM-as-judge 1-5 scale
"""

# ── Constrained fields: exact match after normalization ──
CONSTRAINED_FIELDS_16 = [
    "sc:name",
    "sc:license",
    "sc:inLanguage",
    "cr:isLiveDataset",
    "sc:datePublished",
    "sc:publisher",
    "sc:url",
]

# ── Short-text fields: token-level F1 ──
SHORT_TEXT_FIELDS_16 = [
    "sc:creator",
    "cr:citeAs",
    "sc:description",
]

# ── RAI fields: LLM-as-judge 1-5 scale ──
RAI_JUDGE_FIELDS_16 = [
    "rai:dataCollection",
    "rai:dataCollectionType",
    "rai:dataCollectionMissingData",
    "rai:dataBiases",
    "rai:dataAnnotationProtocol",
    "rai:personalSensitiveInformation",
]

# ── All 16 fields ──
ALL_16_FIELDS = CONSTRAINED_FIELDS_16 + SHORT_TEXT_FIELDS_16 + RAI_JUDGE_FIELDS_16

# ── Benchmark datasets (8) ──
BENCHMARK_DATASETS = [
    "MLS", "FLORES", "CIFAR", "Visual Genome",
    "MSCOCO", "MMLU", "MMMU", "MathVista",
]
