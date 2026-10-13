"""Local open-weight AI model parser for invoices and receipts.

Connects to local inference engines (Ollama or local OpenAI-compatible endpoints
such as LM Studio, vLLM, or llama.cpp) to extract structured financial data.
"""

import json
from typing import Optional
import httpx
from pydantic import ValidationError

from ..config import settings
from .models import ExtractedData, ExpenseCategory

EXTRACTION_SYSTEM_PROMPT = """You are a specialized financial document parser for side hustlers and freelancers.
Your task is to analyze receipt or invoice text and output a valid JSON object matching the following structure:
{
  "vendor": "Name of the merchant or billing company",
  "transaction_date": "YYYY-MM-DDTHH:MM:SSZ",
  "total_amount": 0.00,
  "currency": "USD",
  "tax_amount": 0.00,
  "category": "One of: Software & Cloud Services | Office Supplies & Equipment | Meals & Client Meetings | Travel & Transportation | Professional & Legal Services | Advertising & Marketing | Utilities & Internet | Payment & Banking Fees | Education & Training | Other / Miscellaneous",
  "line_items": ["Item 1 with price", "Item 2 with price"],
  "notes": "Invoice or order number if found",
  "confidence_score": 0.95
}

Return ONLY the raw JSON object. Do not enclose in markdown code fences or add explanations.
"""


class LocalAIEngine:
    """Client for local open-weight LLMs via Ollama or OpenAI-compatible endpoints."""

    def __init__(self):
        self.ollama_url = settings.ollama_base_url.rstrip("/")
        self.ollama_model = settings.ollama_model
        self.openai_url = settings.openai_compatible_base_url.rstrip("/")
        self.openai_key = settings.openai_compatible_api_key
        self.openai_model = settings.openai_compatible_model
        self._ollama_available: Optional[bool] = None
        self._openai_available: Optional[bool] = None

    def is_ollama_available(self) -> bool:
        """Check if local Ollama server is running and responding (cached)."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            with httpx.Client(timeout=0.2) as client:
                res = client.get(f"{self.ollama_url}/api/tags")
                self._ollama_available = (res.status_code == 200)
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def is_openai_compatible_available(self) -> bool:
        """Check if local OpenAI-compatible endpoint is responsive (cached)."""
        if self._openai_available is not None:
            return self._openai_available
        try:
            with httpx.Client(timeout=0.2) as client:
                headers = {"Authorization": f"Bearer {self.openai_key}"}
                res = client.get(f"{self.openai_url}/models", headers=headers)
                self._openai_available = (res.status_code == 200)
        except Exception:
            self._openai_available = False
        return self._openai_available

    def parse_with_ollama(self, text: str) -> Optional[ExtractedData]:
        """Send receipt text to local Ollama instance for structured extraction."""
        endpoint = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract financial details from this invoice:\n\n{text}"}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("message", {}).get("content", "")
                    return self._clean_and_parse_json(content)
        except Exception as e:
            return None
        return None

    def parse_with_openai_compatible(self, text: str) -> Optional[ExtractedData]:
        """Send receipt text to local OpenAI-compatible server (LM Studio, vLLM)."""
        endpoint = f"{self.openai_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract financial details from this invoice:\n\n{text}"}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._clean_and_parse_json(content)
        except Exception:
            return None
        return None

    def _clean_and_parse_json(self, raw_str: str) -> Optional[ExtractedData]:
        """Strip possible markdown formatting and validate through Pydantic."""
        cleaned = raw_str.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed_dict = json.loads(cleaned)
            # Normalize category if invalid
            cat_val = parsed_dict.get("category", "")
            valid_cats = {c.value for c in ExpenseCategory}
            if cat_val not in valid_cats:
                parsed_dict["category"] = ExpenseCategory.OTHER_MISC.value

            return ExtractedData.model_validate(parsed_dict)
        except (json.JSONDecodeError, ValidationError):
            return None
