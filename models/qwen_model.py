"""
Qwen Model Implementation for Metadata Extraction

Uses Alibaba Cloud's Qwen models via OpenAI-compatible API.
Optimized for academic paper metadata extraction with JSON schema enforcement.

Recommended by qwen-api-specialist for 72-76% accuracy (vs 70.2% Gemini Flash baseline).
"""

import os
import json
import time
from typing import Dict, Any, Optional
from openai import OpenAI
from .base import BaseModel


class QwenModel(BaseModel):
    """
    Qwen model implementation using OpenAI-compatible API

    Configuration optimized for deterministic, high-accuracy extraction:
    - Temperature: 0.0 (fully deterministic)
    - Max tokens: 4096 (generous for JSON output)
    - JSON mode: Enforced via response_format
    - Uses Singapore region endpoint (international)
    """

    def __init__(self, model_id="qwen-plus", **kwargs):
        super().__init__(model_id, **kwargs)

        # Get API key from environment or kwargs
        self.api_key = kwargs.get('api_key') or os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY not found in environment or kwargs")

        # Initialize OpenAI client with Qwen endpoint
        self.client = OpenAI(
            api_key=self.api_key,
            # Singapore region endpoint (international)
            # For China (Beijing) region, use: https://dashscope.aliyuncs.com/compatible-mode/v1
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )

        # Model configuration (specialist-recommended settings)
        self.model_id = model_id  # qwen-max, qwen-plus, or qwen-turbo
        self.temperature = kwargs.get('temperature', 0.0)  # Deterministic
        self.max_tokens = kwargs.get('max_tokens', 4096)  # Generous for JSON
        self.max_retries = kwargs.get('max_retries', 3)

        print(f"✅ Qwen {model_id} initialized via OpenAI SDK (temp={self.temperature})")

    def setup(self) -> bool:
        """
        Setup method (required by BaseModel abstract class)
        Qwen doesn't require special setup - client is initialized in __init__
        """
        return True

    def cleanup(self):
        """
        Cleanup method (required by BaseModel abstract class)
        Qwen doesn't require special cleanup
        """
        pass

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response from Qwen model with automatic retry and error handling

        Args:
            prompt: User prompt with extraction instructions and paper text
            system_prompt: Optional system instructions

        Returns:
            str: Generated JSON response (guaranteed valid JSON due to JSON mode)
        """
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Retry logic for API calls
        for attempt in range(self.max_retries):
            try:
                response = self._call_api(messages)
                return response

            except Exception as e:
                error_msg = str(e)

                # Handle rate limits with exponential backoff
                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    if attempt < self.max_retries - 1:
                        wait_time = 60 * (2 ** attempt)  # 60s, 120s, 240s
                        print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 2}/{self.max_retries}...")
                        time.sleep(wait_time)
                        continue

                # Handle other errors
                if attempt < self.max_retries - 1:
                    wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    print(f"⚠️  API error: {error_msg}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Qwen API failed after {self.max_retries} attempts: {error_msg}")

        raise Exception("Failed to generate response")

    def _call_api(self, messages: list) -> str:
        """
        Make API call to Qwen via OpenAI-compatible endpoint

        Uses JSON mode to guarantee valid JSON output.
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},  # JSON mode enforcement
            )

            # Extract response content
            response_text = completion.choices[0].message.content

            # Validate JSON (JSON mode should guarantee this, but double-check)
            json.loads(response_text)  # Raises ValueError if invalid

            return response_text

        except Exception as e:
            error_msg = str(e)
            # Add more context to error
            if "401" in error_msg or "Unauthorized" in error_msg:
                raise Exception("Invalid DASHSCOPE_API_KEY. Please check your API key.")
            elif "403" in error_msg or "AccessDenied" in error_msg:
                raise Exception(f"Access denied to model {self.model_id}. Please check model access permissions.")
            elif "404" in error_msg:
                raise Exception(f"Model {self.model_id} not found. Check model name.")
            else:
                raise Exception(f"Qwen API error: {error_msg}")

    def extract_metadata_full_pdf(self, full_text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from full PDF using Qwen

        Optimized prompt engineering based on qwen-api-specialist recommendations.

        Args:
            full_text: Complete PDF text content
            schema: Expected JSON schema for metadata fields

        Returns:
            dict: Extracted metadata matching schema
        """
        # Build optimized extraction prompt
        prompt = self._build_extraction_prompt(full_text, schema)

        # Generate response (JSON mode ensures valid JSON)
        response_json = self.generate(prompt)

        # Parse and validate
        try:
            metadata = json.loads(response_json)
            metadata = self._validate_metadata(metadata, schema)
            return metadata
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Qwen JSON response: {e}")

    def _build_extraction_prompt(self, paper_text: str, schema: Dict[str, Any]) -> str:
        """
        Build optimized extraction prompt based on specialist recommendations

        Key features:
        - Explicit schema with types
        - Numbered rules for clarity
        - Null handling to prevent hallucination
        - Specific format requirements
        - No markdown/extra text instructions
        """
        # Truncate if too long (Qwen context limits)
        if len(paper_text) > 120000:
            paper_text = self._smart_truncate(paper_text, max_chars=120000)

        # Build schema description
        schema_desc = json.dumps(schema, indent=2)

        prompt = f"""You are an expert at extracting structured metadata from academic papers.

Extract metadata from the following academic paper and return ONLY a valid JSON object.

REQUIRED SCHEMA:
{schema_desc}

CRITICAL EXTRACTION RULES:
1. Return ONLY valid JSON - no markdown code blocks, no explanations, no extra text
2. Use null for any field where information is NOT explicitly found in the paper
3. NEVER fabricate or guess information - be accurate or use null
4. For "datePublished", extract publication date in ISO 8601 format (YYYY-MM-DD)
5. For URLs (url, citeAs), include full valid URLs starting with https://
6. For "creator", use schema.org Person format: {{"@type": "Person", "name": "Author Name", "url": "https://..."}}
7. For "license", identify SPDX license identifier (e.g., "MIT", "Apache-2.0") or license URL
8. For "dataCollection", extract detailed methodology description from methods/data sections
9. For "dataCollectionTimeframe", extract time period when data was collected
10. For "dataAnnotationPlatform", extract platform/tool used for annotation (e.g., "Amazon MTurk", "LabelStudio")
11. For "annotatorDemographics", extract demographics ONLY if explicitly mentioned in paper
12. For "dataUseCases", extract intended use cases described in paper
13. For "personalSensitiveInformation", extract whether dataset contains PII (true/false or description)
14. Keep "description" concise but informative (2-3 sentences capturing dataset essence)
15. Extract "inLanguage" as language codes (e.g., "en", "en, fr, de") or language names

ACADEMIC PAPER TEXT:
{paper_text}

JSON OUTPUT (no other text, no markdown):"""

        return prompt

    def _smart_truncate(self, text: str, max_chars: int = 120000) -> str:
        """
        Intelligently truncate long papers while preserving metadata-rich sections

        Strategy: Keep first 60% and last 20% (metadata typically in intro/conclusion)
        """
        if len(text) <= max_chars:
            return text

        keep_start = int(max_chars * 0.6)
        keep_end = int(max_chars * 0.2)

        truncated = (
            text[:keep_start] +
            "\n\n[... MIDDLE CONTENT TRUNCATED FOR LENGTH ...]\n\n" +
            text[-keep_end:]
        )

        return truncated

    def _validate_metadata(self, metadata: dict, schema: Dict[str, Any]) -> dict:
        """
        Validate and clean extracted metadata

        Ensures:
        - All schema fields exist (fill with null if missing)
        - No extra fields beyond schema
        - Basic format validation
        """
        # Ensure all schema fields exist
        for field in schema.keys():
            if field not in metadata:
                metadata[field] = None

        # Remove any extra fields not in schema
        metadata = {k: v for k, v in metadata.items() if k in schema}

        # Clean empty strings to null
        for key, value in metadata.items():
            if value == "" or value == "Not mentioned" or value == "unknown":
                metadata[key] = None

        return metadata

    def get_model_info(self) -> Dict[str, Any]:
        """Return model information for logging/debugging"""
        return {
            "provider": "Qwen (Alibaba Cloud)",
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "json_mode": True,
            "api_type": "OpenAI-compatible",
            "endpoint": "dashscope-intl.aliyuncs.com",
            "expected_accuracy": "72-76% (qwen-max), 68-73% (qwen-plus)",
            "recommended_by": "qwen-api-specialist"
        }
