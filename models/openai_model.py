import os
from openai import OpenAI
from .base import BaseModel
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, try without it

class OpenAIModel(BaseModel):
    def __init__(self, model_id="gpt-4o-mini", **kwargs):
        super().__init__(model_id, **kwargs)
        self.client = None
        self.temperature = kwargs.get('temperature', 0.3)
        self.max_tokens = kwargs.get('max_tokens', 1024)

    def setup(self) -> bool:
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("❌ OPENAI_API_KEY not set")
                print("   Please set OPENAI_API_KEY in .env file or environment")
                return False
            
            self.client = OpenAI(api_key=api_key)
            print(f"✅ OpenAI {self.model_id} ready")
            return True
        except Exception as e:
            print(f"❌ OpenAI setup failed: {e}")
            return False
    
    def generate(self, prompt: str) -> str:
        # GPT-5 models use max_completion_tokens instead of max_tokens
        # and only support temperature=1.0 (default)
        token_param = {}
        temp_param = {}

        if self.model_id.startswith('gpt-5'):
            token_param = {"max_completion_tokens": self.max_tokens}
            # GPT-5 only supports default temperature (1.0), so don't pass it
        else:
            token_param = {"max_tokens": self.max_tokens}
            temp_param = {"temperature": self.temperature}

        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            **temp_param,
            **token_param
        )
        return response.choices[0].message.content
    
    def cleanup(self):
        self.client = None