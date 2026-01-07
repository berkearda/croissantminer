from .openai_model import OpenAIModel
from .gpt5_model import GPT5Model
from .o1_model import O1Model
from .gemini_model import GeminiModel
from .qwen_model import QwenModel
from .claude_model import ClaudeModel
from .huggingface_model import HuggingFaceModel

MODELS = {
    # Claude models (Anthropic)
    'claude-sonnet-4-5': ClaudeModel,
    'claude-4-sonnet': ClaudeModel,
    'claude-3-5-sonnet': ClaudeModel,
    'claude-3-opus': ClaudeModel,

    # Qwen models (Alibaba Cloud)
    'qwen-max': QwenModel,
    'qwen-plus': QwenModel,
    'qwen-turbo': QwenModel,

    # Gemini models
    'gemini-2.5-pro': GeminiModel,
    'gemini-2.5-flash': GeminiModel,
    'gemini-2.0-flash-exp': GeminiModel,
    'gemini-2.0-flash': GeminiModel,
    'gemini-1.5-pro': GeminiModel,
    'gemini-1.5-flash': GeminiModel,

    # GPT-5 models (use Responses API)
    'gpt-5': GPT5Model,
    'gpt-5-mini': GPT5Model,
    'gpt-5-nano': GPT5Model,

    # o1 reasoning models (use Chat Completions API with special parameters)
    'o1-preview': O1Model,
    'o1-mini': O1Model,

    # OpenAI models (use Chat Completions API)
    'gpt-4o': OpenAIModel,
    'gpt-4o-mini': OpenAIModel,
    'gpt-3.5-turbo': OpenAIModel,

    # HuggingFace models
    'mistral-7b': HuggingFaceModel,
}

MODEL_IDS = {
    # Claude models
    'claude-sonnet-4-5': 'claude-sonnet-4-5-20250929',
    'claude-4-sonnet': 'claude-4-sonnet-20250514',
    'claude-3-5-sonnet': 'claude-3-5-sonnet-20241022',
    'claude-3-opus': 'claude-3-opus-20240229',

    # Qwen models
    'qwen-max': 'qwen-max',
    'qwen-plus': 'qwen-plus',
    'qwen-turbo': 'qwen-turbo',

    # Gemini models
    'gemini-2.5-pro': 'gemini-2.5-pro',
    'gemini-2.5-flash': 'gemini-2.5-flash',
    'gemini-2.0-flash-exp': 'gemini-2.0-flash-exp',
    'gemini-2.0-flash': 'gemini-2.0-flash-exp',  # Experimental version for now
    'gemini-1.5-pro': 'gemini-1.5-pro',
    'gemini-1.5-flash': 'gemini-1.5-flash',

    # GPT models
    'gpt-5': 'gpt-5',
    'gpt-5-mini': 'gpt-5-mini',
    'gpt-5-nano': 'gpt-5-nano',
    'o1-preview': 'o1-preview',
    'o1-mini': 'o1-mini',
    'gpt-4o': 'gpt-4o',
    'gpt-4o-mini': 'gpt-4o-mini',
    'gpt-3.5-turbo': 'gpt-3.5-turbo',
    'mistral-7b': 'TheBloke/Mistral-7B-Instruct-v0.1-GPTQ',
}

def create_model(model_name: str, **kwargs):
    """Create a model instance"""
    if model_name not in MODELS:
        available = list(MODELS.keys())
        raise ValueError(f"Unknown model '{model_name}'. Available: {available}")
    
    model_class = MODELS[model_name]
    model_id = MODEL_IDS[model_name]
    
    return model_class(model_id=model_id, **kwargs)