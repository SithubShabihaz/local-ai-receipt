"""Data models and schemas for invoices and expenses."""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, field_validator


class ExpenseCategory(str, Enum):
    """Side hustle tax deduction expense categories (aligned with IRS Schedule C)."""
    SOFTWARE_CLOUD = "Software & Cloud Services"
    OFFICE_SUPPLIES = "Office Supplies & Equipment"
    MEALS_ENTERTAINMENT = "Meals & Client Meetings"
    TRAVEL_TRANSPORT = "Travel & Transportation"
    PROFESSIONAL_SERVICES = "Professional & Legal Services"
    ADVERTISING_MARKETING = "Advertising & Marketing"
    UTILITIES_INTERNET = "Utilities & Internet"
    PAYMENT_BANKING_FEES = "Payment & Banking Fees"
    EDUCATION_TRAINING = "Education & Training"
    OTHER_MISC = "Other / Miscellaneous"


class ExtractedData(BaseModel):
    """Raw structured data extracted from invoice or receipt text."""
    vendor: str = Field(description="Name of the merchant, vendor, or billing entity")
    transaction_date: datetime = Field(description="Date and time the invoice/receipt was issued")
    total_amount: float = Field(description="Total monetary amount paid or due")
    currency: str = Field(default="USD", description="Currency ISO code or symbol (e.g. USD, EUR, GBP)")
    tax_amount: float = Field(default=0.0, description="Tax, VAT, or GST amount included")
    category: ExpenseCategory = Field(
        default=ExpenseCategory.OTHER_MISC,
        description="Categorized business expense bucket"
    )
    line_items: List[str] = Field(default_factory=list, description="List of purchased items or service lines")
    notes: Optional[str] = Field(default=None, description="Any invoice notes, PO number, or invoice ID")
    confidence_score: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score of the extraction (0.0 to 1.0)"
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        v = v.strip().upper()
        mapping = {
            "$": "USD",
            "US$": "USD",
            "USD": "USD",
            "€": "EUR",
            "EUR": "EUR",
            "£": "GBP",
            "GBP": "GBP",
            "C$": "CAD",
            "CAD": "CAD",
            "A$": "AUD",
            "AUD": "AUD",
        }
        return mapping.get(v, v)

    @field_validator("total_amount", "tax_amount")
    @classmethod
    def round_amounts(cls, v: float) -> float:
        return round(float(v), 2)


class InvoiceRecord(BaseModel):
    """Canonical database record for an invoice stored in Tiger Cloud hypertable."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier (UUID)")
    vendor: str = Field(description="Vendor or merchant name")
    transaction_date: datetime = Field(description="Transaction date (TimescaleDB partition key)")
    total_amount: float = Field(description="Total amount paid")
    currency: str = Field(default="USD", description="Currency code")
    tax_amount: float = Field(default=0.0, description="Tax or VAT amount")
    category: ExpenseCategory = Field(description="Categorized expense bucket")
    raw_text: Optional[str] = Field(default=None, description="Original source receipt text")
    confidence_score: float = Field(default=1.0, description="Extraction confidence score")
    extraction_method: str = Field(default="unknown", description="Engine used for extraction")
    line_items: List[str] = Field(default_factory=list, description="Extracted line items")
    notes: Optional[str] = Field(default=None, description="Additional context or invoice number")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when record was saved"
    )

    @field_validator("transaction_date", mode="before")
    @classmethod
    def ensure_tz(cls, v: Any) -> datetime:
        if isinstance(v, str):
            from dateutil.parser import parse
            dt = parse(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(f"Invalid datetime format: {v}")

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class ExtractionResult(BaseModel):
    """Container for the output of the invoice extraction pipeline."""
    success: bool
    record: Optional[InvoiceRecord] = None
    extracted_data: Optional[ExtractedData] = None
    extraction_method: str
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
