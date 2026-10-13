"""Hybrid invoice extraction pipeline orchestrator."""

import time
from typing import Optional

from ..config import settings
from .models import InvoiceRecord, ExtractionResult, ExtractedData
from .regex_engine import RegexParser
from .ai_engine import LocalAIEngine


class InvoiceExtractor:
    """Master orchestrator combining local AI and deterministic parsing."""

    def __init__(self):
        self.regex_parser = RegexParser()
        self.ai_engine = LocalAIEngine()

    def extract_from_text(self, text: str, source_filename: Optional[str] = None) -> ExtractionResult:
        """Process raw invoice text and return a validated ExtractionResult."""
        start_time = time.perf_counter()
        backend = settings.local_ai_backend.lower()

        extracted: Optional[ExtractedData] = None
        method_used = "regex_fallback"

        # 1. User forced 'regex'
        if backend == "regex":
            extracted = self.regex_parser.extract(text)
            method_used = "heuristic_regex"

        # 2. User forced 'ollama'
        elif backend == "ollama":
            if self.ai_engine.is_ollama_available():
                extracted = self.ai_engine.parse_with_ollama(text)
                if extracted:
                    method_used = f"ollama_{settings.ollama_model}"

            if not extracted:
                extracted = self.regex_parser.extract(text)
                method_used = "regex_fallback (ollama_unavailable)"

        # 3. User forced 'openai_compatible'
        elif backend == "openai_compatible":
            if self.ai_engine.is_openai_compatible_available():
                extracted = self.ai_engine.parse_with_openai_compatible(text)
                if extracted:
                    method_used = f"openai_compatible_{settings.openai_compatible_model}"

            if not extracted:
                extracted = self.regex_parser.extract(text)
                method_used = "regex_fallback (openai_endpoint_unavailable)"

        # 4. 'auto' mode: smart detection
        else:
            if self.ai_engine.is_ollama_available():
                extracted = self.ai_engine.parse_with_ollama(text)
                if extracted:
                    method_used = f"ollama_{settings.ollama_model}"

            if not extracted and self.ai_engine.is_openai_compatible_available():
                extracted = self.ai_engine.parse_with_openai_compatible(text)
                if extracted:
                    method_used = f"openai_compatible_{settings.openai_compatible_model}"

            if not extracted:
                extracted = self.regex_parser.extract(text)
                method_used = "heuristic_regex (auto)"

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if not extracted:
            return ExtractionResult(
                success=False,
                extraction_method=method_used,
                error_message="Failed to extract invoice data",
                execution_time_ms=round(elapsed_ms, 2)
            )

        # Build canonical InvoiceRecord
        notes = extracted.notes
        if source_filename:
            notes = f"Source: {source_filename} | {notes}" if notes else f"Source: {source_filename}"

        record = InvoiceRecord(
            vendor=extracted.vendor,
            transaction_date=extracted.transaction_date,
            total_amount=extracted.total_amount,
            currency=extracted.currency,
            tax_amount=extracted.tax_amount,
            category=extracted.category,
            raw_text=text,
            confidence_score=extracted.confidence_score,
            extraction_method=method_used,
            line_items=extracted.line_items,
            notes=notes
        )

        return ExtractionResult(
            success=True,
            record=record,
            extracted_data=extracted,
            extraction_method=method_used,
            execution_time_ms=round(elapsed_ms, 2)
        )
