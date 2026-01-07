"""
Google Gemini model implementation using REST API
"""

from .base import BaseModel
import os
import requests
import json


class GeminiModel(BaseModel):
    """Google Gemini models via REST API"""

    def __init__(self, model_id="gemini-2.5-flash", **kwargs):
        super().__init__(model_id, **kwargs)
        self.api_key = None
        self.temperature = kwargs.get('temperature', 0.0)  # Set to 0 for deterministic extraction
        self.max_tokens = kwargs.get('max_tokens', 8192)  # Increased default for full JSON responses
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.use_json_schema = kwargs.get('use_json_schema', True)  # Enable JSON schema enforcement

    def setup(self):
        """Setup the Gemini API key"""
        try:
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")

            print(f"✅ Gemini {self.model_id} ready")
            return True
        except Exception as e:
            print(f"❌ Error loading Gemini {self.model_id}: {e}")
            raise

    def cleanup(self):
        """Cleanup resources"""
        pass

    def generate(self, prompt: str) -> str:
        """Generate response using Gemini REST API with JSON schema enforcement"""
        if not self.api_key:
            raise ValueError("Model not loaded. Call setup() first.")

        try:
            # Construct the API endpoint
            url = f"{self.base_url}/{self.model_id}:generateContent"

            # Prepare the request headers
            headers = {
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json"
            }

            # System instruction for metadata extraction
            system_instruction = """You are a precise metadata extraction system for academic papers.

Rules:
1. Extract ONLY information explicitly present in the document
2. Return "Not mentioned" for missing or unclear fields
3. Do NOT infer, guess, or hallucinate any information
4. For nested objects, preserve the exact structure
5. Be thorough but concise"""

            # Prepare generation config with JSON schema if enabled
            generation_config = {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "topP": 1.0,
                "topK": 1  # Greedy decoding for consistency
            }

            # Add JSON mode if schema enforcement is enabled
            if self.use_json_schema:
                generation_config["responseMimeType"] = "application/json"
                # Note: Full schema will be added by passing METADATA_SCHEMA from config
                # For now, we just enforce JSON output format

            # Prepare the request body
            data = {
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": generation_config
            }

            # Make the API request with retry logic for rate limits
            max_retries = 3
            retry_delay = 60  # Start with 60 seconds for Gemini 2.5 Pro rate limits

            for attempt in range(max_retries):
                try:
                    response = requests.post(url, headers=headers, json=data)
                    response.raise_for_status()
                    break  # Success, exit retry loop

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:  # Rate limit error
                        if attempt < max_retries - 1:
                            import time
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                            time.sleep(wait_time)
                        else:
                            print(f"❌ Rate limit exceeded after {max_retries} attempts")
                            raise
                    else:
                        raise  # Re-raise non-rate-limit errors

            # Parse the response
            result = response.json()

            # Extract the generated text
            # Response structure: result['candidates'][0]['content']['parts'][0]['text']
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]

                # Check if response was truncated due to max_tokens
                finish_reason = candidate.get('finishReason', '')
                if finish_reason == 'MAX_TOKENS':
                    raise ValueError(f"Response truncated - MAX_TOKENS limit reached. Increase max_tokens (currently {self.max_tokens})")

                if 'content' in candidate:
                    content = candidate['content']
                    if 'parts' in content and len(content['parts']) > 0:
                        return content['parts'][0].get('text', '')

            # If we couldn't extract text, raise an error
            raise ValueError(f"Unexpected response structure: {result}")

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            print(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            raise
