"""Unit tests for database repository and financial analytics."""

from datetime import datetime, timezone
from pathlib import Path
from src.local_invoice_sorter.parser.models import InvoiceRecord, ExpenseCategory
from src.local_invoice_sorter.db.repository import InvoiceRepository


def test_schema_sql_file_exists():
    schema_file = Path(__file__).parent.parent / "src" / "local_invoice_sorter" / "db" / "schema.sql"
    assert schema_file.exists()
    content = schema_file.read_text(encoding="utf-8")
    assert "timescaledb" in content
    assert "create_hypertable" in content
    assert "monthly_category_summary" in content
    assert "timescaledb.compress" in content


def test_db_init_and_single_insert(temp_db):
    repo, _ = temp_db

    record = InvoiceRecord(
        vendor="Tiger Cloud (TimescaleDB)",
        transaction_date=datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc),
        total_amount=49.00,
        currency="USD",
        tax_amount=0.00,
        category=ExpenseCategory.SOFTWARE_CLOUD,
        notes="Invoice INV-TIGER-1049"
    )

    saved = repo.save_invoice(record)
    assert saved.id == record.id

    rows = repo.list_invoices(vendor="Tiger")
    assert len(rows) == 1
    assert rows[0]["vendor"] == "Tiger Cloud (TimescaleDB)"
    assert float(rows[0]["total_amount"]) == 49.00


def test_batch_insert_and_filtering(temp_db):
    repo, _ = temp_db

    records = [
        InvoiceRecord(
            vendor="AWS",
            transaction_date=datetime(2026, 9, 10, tzinfo=timezone.utc),
            total_amount=84.20,
            category=ExpenseCategory.SOFTWARE_CLOUD
        ),
        InvoiceRecord(
            vendor="Starbucks",
            transaction_date=datetime(2026, 9, 15, tzinfo=timezone.utc),
            total_amount=16.13,
            category=ExpenseCategory.MEALS_ENTERTAINMENT
        ),
        InvoiceRecord(
            vendor="Upwork",
            transaction_date=datetime(2026, 8, 20, tzinfo=timezone.utc),
            total_amount=250.00,
            category=ExpenseCategory.PROFESSIONAL_SERVICES
        )
    ]

    count = repo.save_many(records)
    assert count == 3

    # Filter by category
    softwares = repo.list_invoices(category=ExpenseCategory.SOFTWARE_CLOUD.value)
    assert len(softwares) == 1
    assert softwares[0]["vendor"] == "AWS"

    # Filter by min amount
    big_spends = repo.list_invoices(min_amount=80.00)
    assert len(big_spends) == 2


def test_analytics_and_burn_rate(temp_db):
    repo, _ = temp_db

    records = [
        InvoiceRecord(
            vendor="AWS",
            transaction_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
            total_amount=100.00,
            category=ExpenseCategory.SOFTWARE_CLOUD
        ),
        InvoiceRecord(
            vendor="GitHub",
            transaction_date=datetime(2026, 9, 15, tzinfo=timezone.utc),
            total_amount=50.00,
            category=ExpenseCategory.SOFTWARE_CLOUD
        ),
        InvoiceRecord(
            vendor="Home Depot",
            transaction_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
            total_amount=200.00,
            category=ExpenseCategory.OFFICE_SUPPLIES
        )
    ]
    repo.save_many(records)

    # Monthly burn rate
    burn = repo.get_monthly_burn_rate()
    assert len(burn) == 2
    sept = next(b for b in burn if b["month"] == "2026-09")
    assert sept["count"] == 2
    assert float(sept["total_spent"]) == 150.00

    # Category breakdown
    cats = repo.get_category_breakdown()
    assert len(cats) == 2


def test_tax_deduction_summary(temp_db):
    repo, _ = temp_db

    records = [
        InvoiceRecord(
            vendor="Client Lunch",
            transaction_date=datetime(2026, 5, 10, tzinfo=timezone.utc),
            total_amount=40.00,
            tax_amount=3.50,
            category=ExpenseCategory.MEALS_ENTERTAINMENT
        ),
        InvoiceRecord(
            vendor="Contractor Dev",
            transaction_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            total_amount=300.00,
            tax_amount=0.00,
            category=ExpenseCategory.PROFESSIONAL_SERVICES
        )
    ]
    repo.save_many(records)

    tax_sum = repo.get_tax_deduction_summary(year=2026)
    assert tax_sum["tax_year"] == 2026
    assert tax_sum["total_deductible_expenses"] == 340.00
    assert tax_sum["total_tax_paid"] == 3.50
    assert len(tax_sum["categories"]) == 2
