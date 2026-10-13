"""Unit tests for FastMCP tools and resources."""

from pathlib import Path
from src.local_invoice_sorter.mcp.server import (
    parse_and_store_invoice,
    query_invoices,
    get_monthly_burn_rate,
    get_category_breakdown,
    get_tax_deductions,
    get_timescale_stats,
    recent_invoices_resource,
    valid_categories_resource
)


def test_mcp_parse_and_store(temp_db, samples_dir: Path):
    sample_text = (samples_dir / "01_tiger_cloud_infrastructure.txt").read_text(encoding="utf-8")
    result = parse_and_store_invoice(sample_text, filename="01_tiger_cloud_infrastructure.txt")

    assert "Successfully ingested" in result
    assert "Tiger Cloud" in result
    assert "49.00" in result


def test_mcp_query_and_summaries(temp_db, samples_dir: Path):
    sample_text = (samples_dir / "01_tiger_cloud_infrastructure.txt").read_text(encoding="utf-8")
    parse_and_store_invoice(sample_text)

    # Test query
    query_res = query_invoices(vendor="Tiger")
    assert "Found 1 invoice" in query_res
    assert "Tiger" in query_res

    # Test monthly burn rate
    burn_res = get_monthly_burn_rate()
    assert "Monthly Financial Burn Rate" in burn_res

    # Test category breakdown
    cat_res = get_category_breakdown()
    assert "Expense Breakdown by Category" in cat_res
    assert "Software & Cloud Services" in cat_res

    # Test tax deductions
    tax_res = get_tax_deductions(year=2026)
    assert "Side Hustle Tax Deduction Report" in tax_res
    assert "Total Deductible Expenses: $49.00" in tax_res

    # Test timescale stats
    stats_res = get_timescale_stats()
    assert isinstance(stats_res, str)

    # Test resources
    recent = recent_invoices_resource()
    assert "Tiger" in recent

    cats = valid_categories_resource()
    assert "Software & Cloud Services" in cats
