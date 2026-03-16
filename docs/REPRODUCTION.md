# Reproduction Guide

Step-by-step instructions to reproduce all results in the paper.

## Prerequisites

```bash
# Clone and install
git clone https://github.com/croissantminer/croissantminer.git
cd croissantminer
pip install -e .

# Set up API keys
export ANTHROPIC_API_KEY=your_key_here    # For Claude Sonnet 4.5
export OPENAI_API_KEY=your_key_here       # For GPT-4o-mini (evaluation judge)
```

## Step 1: Download Papers

The 8 benchmark papers are from arXiv. Place PDFs in `data/raw/`:

| Dataset | arxiv ID | File |
|---------|----------|------|
| MLS | 2012.03411v2 | `data/raw/2012.03411v2.pdf` |
| MMLU | 2009.03300v3 | `data/raw/2009.03300v3.pdf` |
| FLORES | 2106.03193v1 | `data/raw/2106.03193v1.pdf` |
| CIFAR | 2404.00498v2 | `data/raw/2404.00498v2.pdf` |
| MSCOCO | 1405.0312v3 | `data/raw/1405.0312v3.pdf` |
| MMMU | 2311.16502v4 | `data/raw/2311.16502v4.pdf` |
| Visual Genome | 1602.07332v1 | `data/raw/1602.07332v1.pdf` |
| MathVista | 2310.02255v3 | `data/raw/2310.02255v3.pdf` |

## Step 2: Run Extraction (Table 1)

```bash
python scripts/run_extraction.py --extraction-mode full-pdf
```

Extracts metadata from all 8 papers using Claude Sonnet 4.5. Results saved to `evaluation_outputs/`.

**Expected time:** ~5 minutes (8 papers, 1 API call each)
**Expected cost:** ~$0.50 (Claude Sonnet 4.5)

## Step 3: Run Evaluation (Table 2)

```bash
python scripts/run_evaluation.py
```

Evaluates extractions against human-annotated ground truth using LLM-as-judge (GPT-4o-mini).

**Expected output:** Per-dataset and per-field accuracy tables.

## Step 4: Statistical Significance Tests (Table 2, confidence intervals)

```bash
python -c "
from croissantminer.metrics import run_all_significance_tests
run_all_significance_tests('evaluation_outputs')
"
```

Computes bootstrap 95% CIs, McNemar's tests, and Cohen's h effect sizes.

## Step 5: Ablation Experiments (Tables 3-5)

```bash
# Run all 10 ablation variants (~90 min)
./scripts/run_all_ablations.sh

# Or run individually:
python scripts/run_ablations.py --type prompt --all       # Prompt ablation (4 variants)
python scripts/run_ablations.py --type context --all      # Context ablation (3 variants)
python scripts/run_ablations.py --type few_shot --all     # Few-shot ablation (3 variants)

# View comparison tables:
python scripts/run_ablations.py --compare prompt
python scripts/run_ablations.py --compare context
python scripts/run_ablations.py --compare few_shot
```

**Expected time:** ~90 minutes for all 10 variants
**Expected cost:** ~$4 (80 Claude API calls + 80 GPT-4o-mini evaluation calls)

## Step 6: 30-Field Ground Truth (Table 6)

```bash
python scripts/build_30field_groundtruth.py
```

Builds 30-field ground truth by extracting missing 14 RAI fields from papers and merging with existing 16-field human annotations.

## Step 7: Fine-tuning Data (for LoRA experiments)

```bash
python scripts/prepare_finetuning_data.py --max-tokens 4096
python scripts/validate_finetuning_data.py
```

Prepares ChatML and Alpaca format training data from 111 papers.

## Total Reproduction Cost

| Step | API | Cost |
|------|-----|------|
| Extraction | Claude Sonnet 4.5 | ~$0.50 |
| Evaluation | GPT-4o-mini | ~$0.10 |
| Ablations (10 variants) | Claude + GPT | ~$4.00 |
| 30-field GT extraction | Claude | ~$0.50 |
| **Total** | | **~$5.10** |

## Troubleshooting

**Import errors:** Make sure you installed with `pip install -e .`

**API rate limits:** The scripts include automatic retry logic. If you hit rate limits, wait 60 seconds and retry.

**MSCOCO JSON parse error:** The MSCOCO paper sometimes produces unescaped quotes in the citation field. The extraction script includes a regex fallback that handles this automatically.
