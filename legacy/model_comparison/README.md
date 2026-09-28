# Model Comparison Directory

This directory contains comprehensive model comparison analysis for the CroissantMiner metadata extraction pipeline.

## 📁 Files

### 1. `EXECUTIVE_SUMMARY.md` ⭐ **START HERE**
**Quick overview and recommendations** for model selection

**Contents:**
- Quick results table (4 models)
- Decision tree for model selection
- Performance by category
- Use case recommendations
- Cost comparison
- 5-minute read

**Key Finding:** Claude Sonnet 4.5 achieves **70.6% accuracy** (tied #1) with 100% reliability

---

### 2. `model_comparison.md` (Detailed Analysis)
**Comprehensive comparison** of 4 LLM models (Claude 4.5, Gemini Pro, Gemini Flash, GPT-4o-mini)

**Contents:**
- Executive summary with key metrics
- Performance by field category (General vs RAI)
- Dataset-by-dataset breakdown
- Per-field performance analysis
- Model deep dives
- Strengths & weaknesses
- Cost-benefit analysis
- Recommendations
- Next steps & roadmap

**Key Finding:** Claude Sonnet 4.5 and Gemini Pro tied at **70.6% accuracy**, but Claude has 100% reliability

---

### 2. `per_field_breakdown.md`
**Detailed field-by-field accuracy** across all datasets

**Contents:**
- General fields (10 fields): name, description, url, license, etc.
- RAI fields (6 fields): dataCollection, annotatorDemographics, etc.
- Dataset-by-dataset comparison for each field
- Overall accuracy per field

**Use this for:**
- Identifying which fields need improvement
- Understanding field-specific model performance
- Debugging extraction issues

---

### 3. `gemini_field_analysis.json`
**Raw analysis data for Gemini 2.5 Flash**

**Structure:**
```json
{
  "DATASET_NAME": {
    "general": {
      "correct": 7,
      "partial": 1,
      "incorrect": 0,
      "missing": 1,
      "total": 9,
      "accuracy": 83.3
    },
    "rai": {
      "correct": 5,
      "partial": 0,
      "incorrect": 0,
      "missing": 1,
      "total": 6,
      "accuracy": 83.3
    },
    "field_details": {
      "general": {...},
      "rai": {...}
    }
  }
}
```

---

### 4. `gpt4o_mini_field_analysis.json`
**Raw analysis data for GPT-4o-mini**

Same structure as `gemini_field_analysis.json`

---

## 📊 Quick Stats

| Rank | Model | Overall | General (10) | RAI (6) | Reliability |
|------|-------|---------|--------------|---------|-------------|
| 🥇 | **Claude Sonnet 4.5** | **70.6%** | 67.3% | 76.0% | ✅ 100% |
| 🥇 | Gemini 2.5 Pro | **70.6%** | 66.7% | 76.0% | ⚠️ Issues |
| 🥈 | Gemini 2.5 Flash | 70.2% | **68.6%** | 76.0% | ✅ Good |
| 🥉 | GPT-4o-mini | 64.7% | 62.0% | 67.7% | ✅ Good |

### Key Insights

1. **Claude 4.5 = Best production choice** (tied #1 accuracy + 100% reliability)
2. **All top models excel at RAI** (76% vs 67-69% on general fields)
3. **Flash nearly matches Pro** (only -0.4pp, but 4-5x cheaper)
4. **GPT-4o-mini trades accuracy for speed** (4x faster, -6pp accuracy)

---

## 🔄 Update Process

This directory is **continuously updated** as new models are tested.

### To add a new model:

1. **Run extraction:**
   ```bash
   python run_full_pdf_extraction.py --model-id <model-name>
   ```

2. **Run evaluation:**
   ```bash
   python run_evaluation_full_pdf.py
   ```

3. **Generate analysis:**
   ```bash
   python generate_model_comparison.py --new-model <model-name>
   ```

4. **Update this README** with new stats

---

## 📈 Model Testing Roadmap

### Completed ✅
- [x] GPT-4o-mini (64.7% - baseline)
- [x] Gemini 2.5 Flash (70.2% - best value)
- [x] Gemini 2.5 Pro (70.6% - tied #1)
- [x] **Claude Sonnet 4.5 (70.6% - production ready)** ⭐

### In Progress 🔄
- [ ] Prompt engineering for weak fields (publisher, isLiveDataset)
- [ ] Hybrid approach (Claude + GPT for specific fields)
- [ ] citeAs optimization (50% → 65%)

### Planned 📋
- [ ] Ensemble approach (Claude + Flash voting, expected: 75-78%)
- [ ] RAG enhancement for publication metadata
- [ ] Fine-tuned models (expected: 80-85%)

---

## 📝 Field Categories

### General Fields (10 total)
Schema.org and Croissant metadata:
- `sc:name` - Dataset name
- `sc:description` - Dataset description
- `sc:url` - Dataset URL
- `sc:license` - License information
- `sc:datePublished` - Publication date
- `sc:inLanguage` - Language(s)
- `sc:citeAs` - Citation format
- `cr:isLiveDataset` - Is dataset live/updating
- `sc:creator` - Creator/author
- `sc:publisher` - Publisher

### RAI Fields (6 total)
Responsible AI metadata:
- `rai:dataCollection` - Data collection methodology
- `rai:dataCollectionTimeframe` - When data was collected
- `rai:dataAnnotationPlatform` - Annotation platform used
- `rai:annotatorDemographics` - Annotator demographics
- `rai:dataUseCases` - Intended use cases
- `rai:personalSensitiveInformation` - Personal/sensitive info handling

---

## 🎯 Recommendations

### 🏆 Primary Recommendation: **Claude Sonnet 4.5**

**Use for production deployments.**

**Why Claude 4.5:**
- ✅ Tied #1 accuracy (70.6%)
- ✅ 100% reliability (8/8 datasets, 0 failures)
- ✅ Best developer experience (simpler API, better debugging)
- ✅ Prompt caching (90% cost savings on repeated use)

**Configuration:**
```python
{
  "model_id": "claude-sonnet-4-5",
  "temperature": 0.0,
  "max_tokens": 4096,
  "use_caching": True
}
```

### 💰 Budget Alternative: **Gemini 2.5 Flash**

**Use for high-volume / cost-constrained projects.**

**Why Flash:**
- Nearly identical accuracy (70.2%, only -0.4pp)
- 4-5x cheaper than alternatives
- Best accuracy-to-cost ratio
- ⚠️ Cannot extract citeAs field (0%)

### ⚡ Speed Option: **GPT-4o-mini**

**Use only when speed is critical (<10s requirement).**

**Tradeoffs:**
- 4x faster than Claude (8s vs 19s)
- -6pp accuracy penalty (64.7% vs 70.6%)

---

**Last Updated:** 2025-11-02 18:59:00
**Models Evaluated:** 4 (Claude Sonnet 4.5, Gemini 2.5 Pro, Gemini 2.5 Flash, GPT-4o-mini)
**Datasets:** 8 (CIFAR, FLORES, MLS, MMLU, MMMU, MSCOCO, MathVista, Visual Genome)
**Extraction Mode:** Full-PDF (1 LLM call per paper)
**Claude 4.5 Success Rate:** 100% (8/8, 0 errors)
