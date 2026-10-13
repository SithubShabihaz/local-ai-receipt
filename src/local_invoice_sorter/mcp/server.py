"""Model Context Protocol (MCP) server for Local AI Receipt & Invoice Sorter.

Enables conversational AI assistants (Claude Desktop, Cursor, Antigravity, Windsurf)
to query, ingest, and analyze financial hypertable records using natural language.
"""

from typing import Optional, List
import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

from ..config import settings
from ..db.connection import db_manager
from ..db.repository import InvoiceRepository
from ..parser.extractor import InvoiceExtractor
from ..parser.models import ExpenseCategory

# Initialize FastMCP Server
mcp = FastMCP("local-invoice-sorter")

# DAO and Extractor instances
repo = InvoiceRepository(db_manager)
extractor = InvoiceExtractor()


@mcp.tool()
def parse_and_store_invoice(raw_text: str, filename: str = "receipt.txt") -> str:
    """Extract structured details from receipt text and save it to the Tiger Cloud TimescaleDB hypertable.

    Args:
        raw_text: The complete text content of the invoice, receipt, or billing email.
        filename: Optional filename or source descriptor for the document.
    """
    result = extractor.extract_from_text(raw_text, source_filename=filename)
    if not result.success or not result.record:
        return f"Error extracting invoice: {result.error_message}"

    rec = repo.save_invoice(result.record)
    cat_str = rec.category.value if isinstance(rec.category, ExpenseCategory) else rec.category
    return (
        f"Successfully ingested invoice into Tiger Cloud hypertable!\n"
        f"- ID: {rec.id}\n"
        f"- Vendor: {rec.vendor}\n"
        f"- Date: {rec.transaction_date.strftime('%Y-%m-%d')}\n"
        f"- Total: {rec.currency} {rec.total_amount:.2f}\n"
        f"- Tax: {rec.currency} {rec.tax_amount:.2f}\n"
        f"- Category: {cat_str}\n"
        f"- Extraction Engine: {result.extraction_method}\n"
        f"- Confidence: {rec.confidence_score * 100:.1f}%"
    )


@mcp.tool()
def query_invoices(
    category: Optional[str] = None,
    vendor: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    limit: int = 15
) -> str:
    """Query invoices stored in the Tiger Cloud hypertable with optional filters.

    Args:
        category: Filter by expense category (e.g., 'Software & Cloud Services', 'Meals & Client Meetings').
        vendor: Filter by vendor/merchant name (case-insensitive substring match).
        min_amount: Minimum total dollar amount.
        max_amount: Maximum total dollar amount.
        limit: Maximum number of records to return (default: 15).
    """
    records = repo.list_invoices(
        category=category,
        vendor=vendor,
        min_amount=min_amount,
        max_amount=max_amount,
        limit=limit
    )
    if not records:
        return "No invoices found matching the specified filters."

    lines = [f"Found {len(records)} invoice(s):"]
    for r in records:
        dt = r["transaction_date"]
        date_str = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
        lines.append(
            f"• [{date_str}] {r['vendor']}: {r['currency']} {float(r['total_amount']):.2f} "
            f"({r['category']}) - Method: {r['extraction_method']}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_monthly_burn_rate() -> str:
    """Calculate historical monthly expenditure trends using TimescaleDB time_bucket partitioning."""
    burn_rates = repo.get_monthly_burn_rate()
    if not burn_rates:
        return "No financial history recorded yet."

    lines = ["Monthly Financial Burn Rate:"]
    for b in burn_rates:
        lines.append(
            f"• {b['month']}: Total {b['currency']} {float(b['total_spent']):,.2f} "
            f"across {b['count']} transactions (Avg: {b['currency']} {float(b['avg_ticket']):,.2f})"
        )
    return "\n".join(lines)


@mcp.tool()
def get_category_breakdown() -> str:
    """Aggregate total side hustle spending by category."""
    breakdown = repo.get_category_breakdown()
    if not breakdown:
        return "No expense records available."

    lines = ["Expense Breakdown by Category:"]
    for c in breakdown:
        lines.append(
            f"• {c['category']}: {c['currency']} {float(c['total_amount']):,.2f} ({c['invoice_count']} transactions)"
        )
    return "\n".join(lines)


@mcp.tool()
def get_tax_deductions(year: Optional[int] = None) -> str:
    """Generate a side hustle business tax deduction audit aligned with IRS Schedule C expense categories.

    Args:
        year: The calendar tax year to filter by (e.g., 2026). If omitted, calculates all-time deductions.
    """
    summary = repo.get_tax_deduction_summary(year=year)
    lines = [
        f"Side Hustle Tax Deduction Report ({summary['tax_year']}):",
        f"Total Deductible Expenses: ${summary['total_deductible_expenses']:,.2f}",
        f"Total Tax/VAT Paid: ${summary['total_tax_paid']:,.2f}",
        "",
        "Breakdown by Schedule C Category:"
    ]
    for c in summary["categories"]:
        lines.append(
            f"• {c['category']}: ${float(c['category_total']):,.2f} ({c['count']} receipts) | Tax paid: ${float(c['tax_paid']):,.2f}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_timescale_stats() -> str:
    """Inspect TimescaleDB Hypertable chunks, compression ratio, and storage performance on Tiger Cloud."""
    stats = repo.get_hypertable_stats()
    if not stats.get("is_hypertable"):
        return stats.get("note", "Hypertable metrics are available when connected to Tiger Cloud TimescaleDB.")

    comp = stats.get("compression_stats", {})
    return (
        f"Tiger Cloud Hypertable Diagnostics:\n"
        f"- Hypertable: {stats.get('hypertable_name')}\n"
        f"- Partition Chunks: {stats.get('num_chunks')}\n"
        f"- Compression Active: {stats.get('compression_enabled')}\n"
        f"- Total Chunks: {comp.get('total_chunks', 'N/A')}\n"
        f"- Compressed Chunks: {comp.get('compressed_chunks', 'N/A')}\n"
        f"- Uncompressed Size: {comp.get('uncompressed_size', 'N/A')}\n"
        f"- Compressed Size: {comp.get('compressed_size', 'N/A')}"
    )


@mcp.resource("invoices://recent")
def recent_invoices_resource() -> str:
    """Resource returning the 10 most recent invoices as structured JSON."""
    records = repo.list_invoices(limit=10)
    # Convert dates to isoformat for json serialization
    clean = []
    for r in records:
        d = dict(r)
        if isinstance(d.get("transaction_date"), datetime):
            d["transaction_date"] = d["transaction_date"].isoformat()
        clean.append(d)
    return json.dumps(clean, indent=2)


@mcp.resource("invoices://categories")
def valid_categories_resource() -> str:
    """Resource returning all valid tax deduction expense categories."""
    return json.dumps([c.value for c in ExpenseCategory], indent=2)


@mcp.prompt()
def analyze_spending() -> str:
    """Analyze the user's spending trends and suggest tax-saving optimizations."""
    return (
        "Please query the current monthly burn rate and expense category breakdown. "
        "Identify high-cost recurring software or operational expenses, calculate potential "
        "tax write-offs for this side hustle, and suggest 3 concrete actions to optimize cash flow."
    )


def run_mcp_server():
    """Start the FastMCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
