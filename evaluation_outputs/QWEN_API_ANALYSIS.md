# Qwen API Analysis for Metadata Extraction

## Executive Summary

**Qwen** (Alibaba Cloud's large language model series) offers a compelling alternative to OpenAI models for metadata extraction tasks, with several key advantages:

- ✅ **OpenAI-Compatible API** - Drop-in replacement, minimal code changes
- ✅ **Ultra-Long Context** - Up to 1M tokens (vs GPT-4o's 128k)
- ✅ **Competitive Performance** - Outperforms GPT-4/GPT-4o on many benchmarks
- ✅ **Lower Cost** - ~75-80% cheaper than GPT-4o
- ✅ **No Rate Limits** (on most tiers) - No 30k TPM restrictions like gpt-4o

**Recommended for testing:** Qwen2.5-Max or Qwen3-Max could potentially match or exceed gpt-4o-mini's 72.4% accuracy while handling larger papers.

---

## Available Models (2025)

### Premium Models (Recommended for Metadata Extraction)

| Model | Context Window | Price (Input) | Price (Output) | Best For |
|-------|---------------|---------------|----------------|----------|
| **Qwen3-Max** | 128k tokens | ~$0.0012/1k | ~$0.006/1k | Highest accuracy, complex reasoning |
| **Qwen2.5-Max** | 128k tokens | ~$0.0016/1k | ~$0.0064/1k | Balanced performance |
| **Qwen2.5-Turbo** | **1M tokens** | Lower | Lower | Ultra-long documents |
| Qwen-Plus | 1M tokens | Mid-range | Mid-range | Long documents, high quality |
| Qwen-Turbo | 1M tokens | Lowest | Lowest | Cost-optimized |

### Comparison to OpenAI Pricing

- **GPT-4o-mini**: ~$0.15/1M input, ~$0.60/1M output
- **Qwen3-Max**: ~$1.20/1M input, ~$6.00/1M output (8x more expensive)
- **Qwen2.5-Max**: ~$1.60/1M input, ~$6.40/1M output (10x more expensive)
- **Qwen-Turbo**: Significantly cheaper than GPT-4o-mini

**Note:** Qwen's premium models (Max variants) are actually MORE expensive than GPT-4o-mini, but offer better performance. Qwen-Turbo/Qwen-Plus are cheaper alternatives.

---

## Context Window Capabilities

### Ultra-Long Context Support

**Major Advantage over GPT-4o:**

| Model | Context Window | Equivalent To |
|-------|---------------|---------------|
| Qwen2.5-Turbo | **1M tokens** | ~1M English words / 1.5M Chinese chars |
| Qwen2.5-7B-Instruct-1M | 1M tokens | Same as above |
| Qwen3-32B, 14B, 8B | 128k tokens | 4x gpt-4o-mini (32k) |
| GPT-4o | 128k tokens | Standard |
| GPT-4o-mini | 128k tokens | Standard |

**Performance:**
- Qwen2.5-Turbo achieves **100% accuracy** on 1M length Passkey Retrieval task
- Scores **93.1 on RULER benchmark** (vs GPT-4's 91.6)

**Impact on Our Use Case:**
- ✅ Can handle ALL papers without truncation (our longest is 247k chars = ~60-80k tokens)
- ✅ No need for 300k character limit workaround
- ✅ No risk of exceeding context like gpt-4o (30k TPM limit) or o1-mini (128k total)

---

## Performance Benchmarks

### Qwen vs GPT-4/GPT-4o

#### Arena-Hard (General Capabilities)
- **Qwen3-Max**: 91.0 ✅
- **Qwen2.5-Max**: 89.4 ✅
- GPT-4o: 85.3
- GPT-4: Lower

#### Mathematical Reasoning (MATH Benchmark)
- **Qwen2.5-Max**: 72.3 ✅
- GPT-4o: 68.1

#### Coding (LiveCodeBench)
- **Qwen2.5-Max**: 38.7 ✅
- GPT-4-0806: 30.2

#### AIME 2024/2025 (Advanced Math)
- **Qwen3-Max**: 80.4 ✅

#### MMLU (General Knowledge)
- Qwen2.5-Max: Competitive with GPT-4o
- Qwen3-Max: Strong performance

**Conclusion:** Qwen models consistently outperform GPT-4/GPT-4o on most benchmarks, suggesting they could achieve higher accuracy than our current 72.4% with gpt-4o-mini.

---

## API Integration

### OpenAI SDK Compatible

**Key Advantage:** Minimal code changes required - only need to update `api_key` and `base_url`.

### Python Integration Example

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),  # Alibaba Cloud API key
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # Singapore endpoint
)

completion = client.chat.completions.create(
    model="qwen-max",  # or qwen2.5-max, qwen3-max, qwen-plus, qwen-turbo
    messages=[
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Extract metadata from this PDF...'}
    ],
    temperature=0.3,
    max_tokens=2048
)

print(completion.choices[0].message.content)
```

### Endpoints

- **Singapore (International):** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- **China (Beijing):** `https://dashscope.aliyuncs.com/compatible-mode/v1`

### Streaming Support

```python
stream = client.chat.completions.create(
    model="qwen-plus",
    messages=[{"role": "user", "content": "Extract metadata..."}],
    stream=True,
)

for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

---

## Implementation for CroissantMiner

### Option 1: Create QwenModel Class (Recommended)

```python
# models/qwen_model.py

from .base import BaseModel
from openai import OpenAI
import os

class QwenModel(BaseModel):
    """Alibaba Qwen models using OpenAI-compatible API"""

    def __init__(self, model_id="qwen-max", **kwargs):
        super().__init__(model_id, **kwargs)
        self.client = None
        self.temperature = kwargs.get('temperature', 0.3)
        self.max_tokens = kwargs.get('max_tokens', 2048)

        # Use international endpoint
        self.base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def setup(self):
        """Setup the Qwen model client"""
        try:
            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY environment variable not set")

            self.client = OpenAI(
                api_key=api_key,
                base_url=self.base_url
            )
            print(f"✅ Qwen {self.model_id} ready")
            return True
        except Exception as e:
            print(f"❌ Error loading Qwen {self.model_id}: {e}")
            raise

    def cleanup(self):
        """Cleanup resources"""
        pass

    def generate(self, prompt: str) -> str:
        """Generate response using Qwen model"""
        if not self.client:
            raise ValueError("Model not loaded. Call setup() first.")

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            raise
```

### Option 2: Extend OpenAIModel Class (Quick Implementation)

Since Qwen is OpenAI-compatible, you could simply modify `models/openai_model.py` to accept custom `base_url`:

```python
class OpenAIModel(BaseModel):
    def __init__(self, model_id="gpt-4o-mini", base_url=None, **kwargs):
        super().__init__(model_id, **kwargs)
        self.base_url = base_url  # Allow custom base URL
        self.client = None
        # ... rest of init

    def setup(self):
        try:
            if self.base_url:
                # Custom endpoint (e.g., Qwen)
                api_key = os.getenv("DASHSCOPE_API_KEY")
                self.client = OpenAI(api_key=api_key, base_url=self.base_url)
            else:
                # Standard OpenAI
                self.client = OpenAI()
            # ... rest of setup
```

### Update factory.py

```python
from .qwen_model import QwenModel

MODELS = {
    # Qwen models
    'qwen-max': QwenModel,
    'qwen2.5-max': QwenModel,
    'qwen3-max': QwenModel,
    'qwen-plus': QwenModel,
    'qwen-turbo': QwenModel,
    'qwen2.5-turbo': QwenModel,

    # Existing models...
    'gpt-4o': OpenAIModel,
    'gpt-4o-mini': OpenAIModel,
    # ...
}

MODEL_IDS = {
    'qwen-max': 'qwen-max',
    'qwen2.5-max': 'qwen2.5-max',
    'qwen3-max': 'qwen3-max',
    'qwen-plus': 'qwen-plus',
    'qwen-turbo': 'qwen-turbo',
    'qwen2.5-turbo': 'qwen2.5-turbo',
    # ...
}
```

### Update config.py

```python
DEFAULT_MODEL_ID = "qwen-max"  # Test Qwen model
MAX_PDF_CHARS = 300000  # Can increase if using Qwen2.5-Turbo (1M tokens)
```

### Environment Setup

```bash
# Add to .env file
export DASHSCOPE_API_KEY="your-alibaba-cloud-api-key"
```

---

## Access & Pricing Details

### Getting Started

1. **Create Alibaba Cloud Account**
   - Visit: https://www.alibabacloud.com/
   - Sign up for international account

2. **Access Model Studio**
   - Navigate to DashScope / Model Studio
   - Generate API key

3. **Free Tier**
   - Alibaba Cloud provides generous free tier
   - Exact limits vary by region and account type

4. **Paid Tier**
   - Pay-as-you-go token-based pricing
   - No minimum commitment
   - Significantly cheaper than OpenAI for most models

### Alternative: Third-Party Access

**OpenRouter** (https://openrouter.ai)
- Provides unified API for multiple LLMs including Qwen
- Free tier includes Qwen3-30B-A3B and Qwen3-235B-A22B
- Rate limits and lower priority on free tier
- May have different pricing than direct Alibaba access

**Groq** (https://groq.com)
- Fast inference for some Qwen models
- Different pricing structure

---

## Advantages for Our Use Case

### 1. Context Window (MAJOR ADVANTAGE)

**Problem with Current Setup:**
- gpt-4o: 30k TPM limit → fails on 4/8 papers
- o1-mini: 128k tokens total → would fail on FLORES (133k tokens)
- gpt-4o-mini: Works but needed 300k char workaround

**Qwen Solution:**
- **Qwen2.5-Turbo: 1M tokens** → Can handle 10x our longest paper
- **Qwen3-Max: 128k tokens** → Same as gpt-4o-mini but potentially better accuracy
- No TPM rate limits (unlike gpt-4o's 30k limit)

### 2. Performance (POTENTIAL IMPROVEMENT)

**Current Best:** gpt-4o-mini @ 72.4% accuracy

**Expected with Qwen:**
- Qwen3-Max outperforms GPT-4o on Arena-Hard (91.0 vs 85.3)
- Qwen2.5-Max outperforms GPT-4o on MATH benchmark (72.3 vs 68.1)
- Qwen models trained on 36T tokens (2x GPT-4's training data)

**Hypothesis:** Qwen3-Max could achieve **74-78% accuracy** (estimated +2-6pp improvement)

### 3. Cost (MIXED)

**Premium Models (Qwen3-Max, Qwen2.5-Max):**
- 8-10x MORE expensive than gpt-4o-mini
- Similar to GPT-4 pricing
- Worth it if accuracy improvement is significant

**Budget Models (Qwen-Turbo, Qwen-Plus):**
- Significantly CHEAPER than gpt-4o-mini
- May sacrifice some accuracy
- Good for cost-conscious deployments

### 4. Reliability

**Current Issues:**
- gpt-5-mini: 75% failure rate (JSON errors)
- gpt-4o: 50% failure rate (rate limits)

**Expected with Qwen:**
- ✅ No known JSON formatting issues
- ✅ No TPM rate limits (unlike gpt-4o)
- ✅ OpenAI-compatible → same error handling

### 5. Integration Effort

**Minimal Code Changes:**
- Qwen uses OpenAI SDK → Drop-in replacement
- Only need to change: `api_key` and `base_url`
- Same parameters: temperature, max_tokens, messages format
- Estimated implementation time: **30 minutes**

---

## Recommended Testing Plan

### Phase 1: Quick Validation (1-2 hours)

1. **Setup Alibaba Cloud account** and get API key
2. **Create QwenModel class** (30 min implementation)
3. **Test on 1 paper** (CIFAR) to validate JSON output format
4. **If successful**, proceed to Phase 2

### Phase 2: Full Comparison (2-3 hours)

Test these models on all 8 papers:

| Model | Expected Success | Expected Accuracy | Cost/Run |
|-------|-----------------|-------------------|----------|
| **qwen3-max** | 8/8 (100%) | 74-78% | ~$0.20 |
| **qwen2.5-max** | 8/8 (100%) | 72-76% | ~$0.25 |
| **qwen-plus** | 8/8 (100%) | 68-72% | ~$0.10 |
| **qwen-turbo** | 8/8 (100%) | 64-68% | ~$0.05 |
| **qwen2.5-turbo (1M)** | 8/8 (100%) | 70-74% | ~$0.08 |

### Phase 3: Final Report Update

Add Qwen results to existing `MODEL_COMPARISON_REPORT.md`:
- Compare accuracy vs gpt-4o-mini
- Analyze cost-performance tradeoff
- Update recommendations

---

## Expected Results

### Best Case Scenario

**If Qwen3-Max performs as well as benchmarks suggest:**

- ✅ Accuracy: **75-78%** (+3-6pp improvement over gpt-4o-mini)
- ✅ Success: **8/8 papers** (100%)
- ✅ No rate limit failures (unlike gpt-4o)
- ✅ No context length issues (128k tokens enough)
- ⚠️ Cost: 8-10x more expensive than gpt-4o-mini

**Recommendation:** Use Qwen3-Max if accuracy improvement justifies cost

### Moderate Case Scenario

**If Qwen-Plus matches gpt-4o-mini:**

- ✅ Accuracy: **72-74%** (similar to gpt-4o-mini)
- ✅ Success: **8/8 papers** (100%)
- ✅ Lower cost than gpt-4o-mini
- ✅ Better context window (1M tokens)

**Recommendation:** Switch to Qwen-Plus for cost savings with same accuracy

### Worst Case Scenario

**If Qwen models underperform:**

- ⚠️ Accuracy: **<70%** (worse than gpt-4o-mini)
- Possible JSON formatting issues
- API stability concerns

**Recommendation:** Stick with gpt-4o-mini (72.4% accuracy)

---

## Risks & Mitigations

### Risk 1: API Access Restrictions

**Risk:** Alibaba Cloud may have regional restrictions or require verification

**Mitigation:**
- Use international endpoint (Singapore)
- Alternative: Use OpenRouter's free Qwen access
- Fallback: Stick with OpenAI models

### Risk 2: JSON Output Format Differences

**Risk:** Qwen may produce different JSON formatting than GPT models

**Mitigation:**
- Test on 1 paper first (CIFAR)
- Validate JSON parsing works
- Adjust prompts if needed

### Risk 3: API Stability

**Risk:** Qwen API may have downtime or slower response times

**Mitigation:**
- Test response times during Phase 1
- Monitor error rates
- Keep OpenAI models as backup

### Risk 4: Cost Overruns

**Risk:** Qwen3-Max is 8-10x more expensive than gpt-4o-mini

**Mitigation:**
- Start with cheaper models (qwen-plus, qwen-turbo)
- Only use Qwen3-Max if accuracy improvement is significant
- Set budget alerts in Alibaba Cloud console

---

## Implementation Checklist

### Prerequisites
- [ ] Alibaba Cloud account created
- [ ] DashScope API key obtained
- [ ] API key added to environment variables (`DASHSCOPE_API_KEY`)

### Code Changes
- [ ] Create `models/qwen_model.py`
- [ ] Update `models/factory.py` with Qwen models
- [ ] Update `config.py` with Qwen model IDs
- [ ] Test on 1 paper (CIFAR) to validate

### Testing
- [ ] Phase 1: Single paper validation (CIFAR)
- [ ] Phase 2: Full 8-paper comparison
- [ ] Phase 3: Evaluation with LLM-as-judge
- [ ] Phase 4: Update MODEL_COMPARISON_REPORT.md

### Estimated Timeline
- Setup: 30 minutes
- Implementation: 30 minutes
- Testing (Phase 1): 30 minutes
- Testing (Phase 2): 2-3 hours
- Report update: 30 minutes
- **Total: 4-5 hours**

---

## Conclusion

Qwen API represents a **compelling alternative** to OpenAI models for metadata extraction:

### Strong Advantages:
1. ✅ **Ultra-long context** (1M tokens) - handles all papers without truncation
2. ✅ **Superior benchmarks** - outperforms GPT-4/GPT-4o on most tasks
3. ✅ **OpenAI-compatible** - minimal code changes required
4. ✅ **No rate limits** - unlike gpt-4o's 30k TPM restriction

### Potential Drawbacks:
1. ⚠️ **Higher cost** (premium models 8-10x more expensive)
2. ⚠️ **Unknown metadata extraction performance** (need testing)
3. ⚠️ **Potential API access restrictions** (regional/verification)

### Recommendation:

**Test Qwen models to potentially improve from 72.4% to 75-78% accuracy.**

**Priority Models to Test:**
1. **qwen3-max** - Highest accuracy potential
2. **qwen-plus** - Cost-effective with 1M context
3. **qwen2.5-turbo** - Budget option with 1M context

**If Qwen3-Max achieves >75% accuracy, it becomes the new recommended model despite higher cost.**

---

**Date:** 2025-10-29
**Current Best Model:** gpt-4o-mini @ 72.4% accuracy
**Potential with Qwen:** 75-78% accuracy (estimated)
**Implementation Effort:** 4-5 hours total
**Recommended Action:** Test in Phase 1 with single paper validation
