"""
OpenAI o1 reasoning model implementation
"""

from .base import BaseModel
from openai import OpenAI


class O1Model(BaseModel):
    """OpenAI o1 series reasoning models (o1-preview, o1-mini)"""

    def __init__(self, model_id="o1-mini", **kwargs):
        super().__init__(model_id, **kwargs)
        self.client = None

        # o1 models use max_completion_tokens instead of max_tokens
        # Default to 25,000 tokens as recommended by OpenAI
        self.max_completion_tokens = kwargs.get('max_tokens', 25000)

        # o1 models have temperature fixed at 1, don't pass it
        # No top_p, presence_penalty, frequency_penalty support

    def setup(self):
        """Setup the o1 model client"""
        try:
            self.client = OpenAI()
            print(f"✅ OpenAI {self.model_id} ready")
            return True
        except Exception as e:
            print(f"❌ Error loading OpenAI {self.model_id}: {e}")
            raise

    def cleanup(self):
        """Cleanup resources (no-op for OpenAI API)"""
        pass

    def generate(self, prompt: str) -> str:
        """
        Generate response using o1 reasoning model

        Note: o1 models don't support system messages, only user/assistant
        """
        if not self.client:
            raise ValueError("Model not loaded. Call load() first.")

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=self.max_completion_tokens
                # No temperature, top_p, or other sampling parameters
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            raise
