"""Unit tests for invoice and receipt extraction."""

from pathlib import Path
from datetime import datetime
from src.local_invoice_sorter.parser.extractor import InvoiceExtractor
from src.local_invoice_sorter.parser.models import ExpenseCategory


def test_tiger_cloud_invoice_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "01_tiger_cloud_infrastructure.txt"
    assert sample_file.exists()

    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    assert result.record is not None

    rec = result.record
    assert "Tiger" in rec.vendor
    assert rec.total_amount == 49.00
    assert rec.currency == "USD"
    assert rec.category == ExpenseCategory.SOFTWARE_CLOUD
    assert rec.transaction_date.year == 2026
    assert rec.transaction_date.month == 10
    assert rec.confidence_score >= 0.8


def test_aws_invoice_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "02_aws_hosting.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "AWS" in rec.vendor or "Amazon" in rec.vendor
    assert rec.total_amount == 84.20
    assert rec.tax_amount == 7.05
    assert rec.category == ExpenseCategory.SOFTWARE_CLOUD


def test_starbucks_meeting_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "04_starbucks_client_coffee.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "Starbucks" in rec.vendor
    assert rec.total_amount == 16.13
    assert rec.tax_amount == 1.28
    assert rec.category == ExpenseCategory.MEALS_ENTERTAINMENT


def test_home_depot_office_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "05_home_depot_office_desk.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "Home Depot" in rec.vendor
    assert rec.total_amount == 309.77
    assert rec.category == ExpenseCategory.OFFICE_SUPPLIES


def test_stripe_fees_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "06_stripe_processing_fees.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "Stripe" in rec.vendor
    assert rec.total_amount == 32.40
    assert rec.category == ExpenseCategory.PAYMENT_BANKING_FEES


def test_uber_ride_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "08_uber_business_trip.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "Uber" in rec.vendor
    assert rec.total_amount == 38.75
    assert rec.category == ExpenseCategory.TRAVEL_TRANSPORT


def test_upwork_contractor_extraction(samples_dir: Path, extractor: InvoiceExtractor):
    sample_file = samples_dir / "09_upwork_contractor.txt"
    result = extractor.extract_from_text(sample_file.read_text(encoding="utf-8"))
    assert result.success is True
    rec = result.record

    assert "Upwork" in rec.vendor
    assert rec.total_amount == 250.00
    assert rec.category == ExpenseCategory.PROFESSIONAL_SERVICES


def test_all_sample_files_extract_successfully(samples_dir: Path, extractor: InvoiceExtractor):
    files = list(samples_dir.glob("*.txt"))
    assert len(files) == 10

    for f in files:
        result = extractor.extract_from_text(f.read_text(encoding="utf-8"), source_filename=f.name)
        assert result.success is True, f"Failed on {f.name}: {result.error_message}"
        assert result.record is not None
        assert result.record.total_amount > 0, f"Zero amount on {f.name}"
        assert result.record.vendor != "", f"Empty vendor on {f.name}"
