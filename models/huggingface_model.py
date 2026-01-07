import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from .base import BaseModel

class HuggingFaceModel(BaseModel):
    def __init__(self, model_id="TheBloke/Mistral-7B-Instruct-v0.1-GPTQ", **kwargs):
        super().__init__(model_id, **kwargs)
        self.pipeline = None
        self.temperature = kwargs.get('temperature', 0.3)
        self.max_tokens = kwargs.get('max_tokens', 1024)
    
    def setup(self) -> bool:
        try:
            print(f"Loading {self.model_id}...")
            tokenizer = AutoTokenizer.from_pretrained(self.model_id, use_fast=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                device_map="auto",
                trust_remote_code=True
            )
            
            self.pipeline = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                do_sample=True
            )
            print(f"✅ {self.model_id} ready")
            return True
        except Exception as e:
            print(f"❌ HuggingFace setup failed: {e}")
            return False
    
    def generate(self, prompt: str) -> str:
        output = self.pipeline(prompt)[0]['generated_text']
        # Remove the prompt from output
        if output.startswith(prompt):
            output = output[len(prompt):].strip()
        return output
    
    def cleanup(self):
        if self.pipeline:
            del self.pipeline
        if torch.cuda.is_available():
            torch.cuda.empty_cache()