# Per-Field Accuracy Breakdown

**Last Updated:** 2025-11-02

This document provides detailed accuracy for each metadata field across all datasets.

---

## General Fields

### `isLiveDataset`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | MISSING 📭 | MISSING 📭 | Tie |
| FLORES | MISSING 📭 | MISSING 📭 | Tie |
| MLS | MISSING 📭 | MISSING 📭 | Tie |
| MMLU | MISSING 📭 | MISSING 📭 | Tie |
| MMMU | MISSING 📭 | CORRECT ✅ | GPT-4o-mini |
| MSCOCO | MISSING 📭 | MISSING 📭 | Tie |
| MathVista | CORRECT ✅ | CORRECT ✅ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **25.0%** (2.0/8) | **37.5%** (3.0/8) | **GPT-4o-mini (+12.5pp)** |

### `creator`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| MMMU | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | PARTIALLY_CORRECT ⚠️ | INCORRECT ❌ | Gemini |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **81.2%** (6.5/8) | **75.0%** (6.0/8) | **Gemini (+6.2pp)** |

### `datePublished`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | N/A | CORRECT ✅ | GPT-4o-mini |
| FLORES | MISSING 📭 | MISSING 📭 | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | CORRECT ✅ | CORRECT ✅ | Tie |
| MMMU | INCORRECT ❌ | INCORRECT ❌ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | CORRECT ✅ | CORRECT ✅ | Tie |
| Visual Genome | MISSING 📭 | CORRECT ✅ | GPT-4o-mini |
| **Overall** | **57.1%** (4.0/7) | **75.0%** (6.0/8) | **GPT-4o-mini (+17.9pp)** |

### `description`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | CORRECT ✅ | PARTIALLY_CORRECT ⚠️ | Gemini |
| MMMU | PARTIALLY_CORRECT ⚠️ | INCORRECT ❌ | Gemini |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **87.5%** (7.0/8) | **75.0%** (6.0/8) | **Gemini (+12.5pp)** |

### `inLanguage`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | INCORRECT ❌ | INCORRECT ❌ | Tie |
| MLS | PARTIALLY_CORRECT ⚠️ | CORRECT ✅ | GPT-4o-mini |
| MMLU | CORRECT ✅ | MISSING 📭 | Gemini |
| MMMU | CORRECT ✅ | CORRECT ✅ | Tie |
| MSCOCO | CORRECT ✅ | MISSING 📭 | Gemini |
| MathVista | PARTIALLY_CORRECT ⚠️ | MISSING 📭 | Gemini |
| Visual Genome | CORRECT ✅ | MISSING 📭 | Gemini |
| **Overall** | **75.0%** (6.0/8) | **37.5%** (3.0/8) | **Gemini (+37.5pp)** |

### `license`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | INCORRECT ❌ | INCORRECT ❌ | Tie |
| MMMU | INCORRECT ❌ | INCORRECT ❌ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | INCORRECT ❌ | INCORRECT ❌ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **62.5%** (5.0/8) | **62.5%** (5.0/8) | **Tie** |

### `name`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | CORRECT ✅ | CORRECT ✅ | Tie |
| MMMU | CORRECT ✅ | INCORRECT ❌ | Gemini |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | CORRECT ✅ | CORRECT ✅ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **100.0%** (8.0/8) | **87.5%** (7.0/8) | **Gemini (+12.5pp)** |

### `publisher`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | N/A | N/A | Tie |
| FLORES | MISSING 📭 | MISSING 📭 | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | MISSING 📭 | MISSING 📭 | Tie |
| MMMU | MISSING 📭 | INCORRECT ❌ | Tie |
| MSCOCO | MISSING 📭 | MISSING 📭 | Tie |
| MathVista | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| Visual Genome | MISSING 📭 | CORRECT ✅ | GPT-4o-mini |
| **Overall** | **21.4%** (1.5/7) | **35.7%** (2.5/7) | **GPT-4o-mini (+14.3pp)** |

### `url`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | CORRECT ✅ | INCORRECT ❌ | Gemini |
| MMMU | CORRECT ✅ | PARTIALLY_CORRECT ⚠️ | Gemini |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | CORRECT ✅ | INCORRECT ❌ | Gemini |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **100.0%** (8.0/8) | **68.8%** (5.5/8) | **Gemini (+31.2pp)** |

## RAI Fields

### `annotatorDemographics`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | MISSING 📭 | MISSING 📭 | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | MISSING 📭 | CORRECT ✅ | GPT-4o-mini |
| MMMU | CORRECT ✅ | CORRECT ✅ | Tie |
| MSCOCO | MISSING 📭 | CORRECT ✅ | GPT-4o-mini |
| MathVista | PARTIALLY_CORRECT ⚠️ | CORRECT ✅ | GPT-4o-mini |
| Visual Genome | CORRECT ✅ | MISSING 📭 | Gemini |
| **Overall** | **56.2%** (4.5/8) | **75.0%** (6.0/8) | **GPT-4o-mini (+18.8pp)** |

### `dataAnnotationPlatform`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | MISSING 📭 | MISSING 📭 | Tie |
| MMLU | INCORRECT ❌ | MISSING 📭 | Tie |
| MMMU | CORRECT ✅ | CORRECT ✅ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | INCORRECT ❌ | INCORRECT ❌ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **62.5%** (5.0/8) | **62.5%** (5.0/8) | **Tie** |

### `dataCollection`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | PARTIALLY_CORRECT ⚠️ | INCORRECT ❌ | Gemini |
| MMMU | PARTIALLY_CORRECT ⚠️ | INCORRECT ❌ | Gemini |
| MSCOCO | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| MathVista | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **68.8%** (5.5/8) | **56.2%** (4.5/8) | **Gemini (+12.5pp)** |

### `dataCollectionTimeframe`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | CORRECT ✅ | CORRECT ✅ | Tie |
| MMMU | CORRECT ✅ | CORRECT ✅ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | CORRECT ✅ | CORRECT ✅ | Tie |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **100.0%** (8.0/8) | **100.0%** (8.0/8) | **Tie** |

### `dataUseCases`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | CORRECT ✅ | Tie |
| MMLU | PARTIALLY_CORRECT ⚠️ | PARTIALLY_CORRECT ⚠️ | Tie |
| MMMU | CORRECT ✅ | CORRECT ✅ | Tie |
| MSCOCO | CORRECT ✅ | CORRECT ✅ | Tie |
| MathVista | PARTIALLY_CORRECT ⚠️ | INCORRECT ❌ | Gemini |
| Visual Genome | CORRECT ✅ | CORRECT ✅ | Tie |
| **Overall** | **81.2%** (6.5/8) | **75.0%** (6.0/8) | **Gemini (+6.2pp)** |

### `personalSensitiveInformation`

| Dataset | Gemini 2.5 Flash | GPT-4o-mini | Winner |
|---------|------------------|-------------|--------|
| CIFAR | CORRECT ✅ | CORRECT ✅ | Tie |
| FLORES | CORRECT ✅ | CORRECT ✅ | Tie |
| MLS | CORRECT ✅ | MISSING 📭 | Gemini |
| MMLU | CORRECT ✅ | CORRECT ✅ | Tie |
| MMMU | CORRECT ✅ | MISSING 📭 | Gemini |
| MSCOCO | CORRECT ✅ | MISSING 📭 | Gemini |
| MathVista | INCORRECT ❌ | MISSING 📭 | Tie |
| Visual Genome | CORRECT ✅ | MISSING 📭 | Gemini |
| **Overall** | **87.5%** (7.0/8) | **37.5%** (3.0/8) | **Gemini (+50.0pp)** |

---

## Legend

- ✅ **CORRECT**: Fully correct extraction
- ⚠️ **PARTIALLY_CORRECT**: Partially correct (semantic similarity)
- ❌ **INCORRECT**: Incorrect extraction
- 📭 **MISSING**: Field not extracted

---

**Generated:** 2025-11-02
