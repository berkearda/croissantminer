import os
from openai import OpenAI
from .base import BaseModel
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

class GPT5Model(BaseModel):
    """GPT-5 model using Responses API"""
    
    def __init__(self, model_id="gpt-5", **kwargs):
        super().__init__(model_id, **kwargs)
        self.client = None
        # GPT-5 specific parameters
        self.reasoning_effort = kwargs.get('reasoning_effort', 'minimal')  # minimal, low, medium, high

        # For gpt-5-mini, use 'low' verbosity to avoid overly long JSON strings
        # For gpt-5, use 'medium' verbosity for balanced output
        if 'mini' in model_id.lower():
            self.text_verbosity = kwargs.get('text_verbosity', 'low')  # More concise for mini
        else:
            self.text_verbosity = kwargs.get('text_verbosity', 'medium')  # Balanced for full model

        # Increase max_output_tokens to allow complete JSON responses
        self.max_output_tokens = kwargs.get('max_tokens', 2048)  # Increased from 1024

    def setup(self) -> bool:
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("❌ OPENAI_API_KEY not set")
                print("   Please set OPENAI_API_KEY in .env file or environment")
                return False
            
            self.client = OpenAI(api_key=api_key)
            print(f"✅ OpenAI {self.model_id} ready (Responses API)")
            return True
        except Exception as e:
            print(f"❌ OpenAI setup failed: {e}")
            return False
    
    def generate(self, prompt: str) -> str:
        """Generate response using Responses API"""
        try:
            # Use Responses API for GPT-5
            response = self.client.responses.create(
                model=self.model_id,
                input=prompt,
                reasoning={
                    "effort": self.reasoning_effort
                },
                text={
                    "verbosity": self.text_verbosity
                },
                max_output_tokens=self.max_output_tokens
            )
            
            # Extract text from response
            return response.output_text
            
        except Exception as e:
            print(f"❌ GPT-5 generation error: {e}")
            raise
    
    def cleanup(self):
        self.client = None
