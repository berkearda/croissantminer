"""
Model factory for creating LLM instances.
Supports: Claude (Anthropic), Gemini (Google), Qwen (Alibaba), OpenAI (GPT-4o)
"""

from .openai_model import OpenAIModel
from .gemini_model import GeminiModel
from .qwen_model import QwenModel
from .claude_model import ClaudeModel

MODELS = {
    # Claude models (Anthropic) - PRIMARY
    'claude-sonnet-4-5': ClaudeModel,
    'claude-4-sonnet': ClaudeModel,
    'claude-3-5-sonnet': ClaudeModel,
    'claude-3-opus': ClaudeModel,

    # Gemini models (Google)
    'gemini-2.5-pro': GeminiModel,
    'gemini-2.5-flash': GeminiModel,
    'gemini-2.0-flash': GeminiModel,
    'gemini-1.5-pro': GeminiModel,
    'gemini-1.5-flash': GeminiModel,

    # Qwen models (Alibaba Cloud)
    'qwen-max': QwenModel,
    'qwen-plus': QwenModel,
    'qwen-turbo': QwenModel,

    # OpenAI models
    'gpt-4o': OpenAIModel,
    'gpt-4o-mini': OpenAIModel,
}

MODEL_IDS = {
    # Claude models
    'claude-sonnet-4-5': 'claude-sonnet-4-5-20250929',
    'claude-4-sonnet': 'claude-4-sonnet-20250514',
    'claude-3-5-sonnet': 'claude-3-5-sonnet-20241022',
    'claude-3-opus': 'claude-3-opus-20240229',

    # Gemini models
    'gemini-2.5-pro': 'gemini-2.5-pro',
    'gemini-2.5-flash': 'gemini-2.5-flash',
    'gemini-2.0-flash': 'gemini-2.0-flash-exp',
    'gemini-1.5-pro': 'gemini-1.5-pro',
    'gemini-1.5-flash': 'gemini-1.5-flash',

    # Qwen models
    'qwen-max': 'qwen-max',
    'qwen-plus': 'qwen-plus',
    'qwen-turbo': 'qwen-turbo',

    # OpenAI models
    'gpt-4o': 'gpt-4o',
    'gpt-4o-mini': 'gpt-4o-mini',
}

def create_model(model_name: str, **kwargs):
    """Create a model instance by name.

    Args:
        model_name: Short name of the model (e.g., 'claude-sonnet-4-5')
        **kwargs: Additional arguments passed to the model constructor

    Returns:
        Model instance

    Raises:
        ValueError: If model_name is not recognized
    """
    if model_name not in MODELS:
        available = list(MODELS.keys())
        raise ValueError(f"Unknown model '{model_name}'. Available: {available}")

    model_class = MODELS[model_name]
    model_id = MODEL_IDS[model_name]

    return model_class(model_id=model_id, **kwargs)


def list_models():
    """List all available models."""
    return list(MODELS.keys())
