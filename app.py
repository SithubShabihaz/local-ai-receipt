#!/usr/bin/env python3
"""Local AI Receipt & Invoice Sorter (local-invoice-sorter)
Hacktoberfest 2026 Open-Source AI Challenge Entry (Side Hustle Theme).

A simple, robust, production-ready script that works out of the box with zero setup.
Run:
    python app.py                  # Full end-to-end demo & dashboard
    python app.py parse <file>     # Parse a specific invoice or receipt
    python app.py list             # View all stored invoices
    python app.py stats            # View monthly burn rate & category breakdown
    python app.py tax              # View IRS Schedule C tax deduction audit
    python app.py mcp              # Launch Model Context Protocol (MCP) server
    python app.py test             # Run automated test suite
"""

import sys
import os
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.local_invoice_sorter.config import settings
from src.local_invoice_sorter.db.connection import db_manager
from src.local_invoice_sorter.db.repository import InvoiceRepository
from src.local_invoice_sorter.parser.extractor import InvoiceExtractor
from src.local_invoice_sorter.parser.models import ExpenseCategory

repo = InvoiceRepository(db_manager)
extractor = InvoiceExtractor()


def print_banner():
    print("=" * 76)
    print("  LOCAL AI RECEIPT & INVOICE SORTER (local-invoice-sorter)")
    print("  Hacktoberfest 2026 AI Challenge | Side Hustle Theme")
    print("  Tech Stack: Python, Tiger Cloud (TimescaleDB), & Model Context Protocol")
    print("=" * 76)


def run_full_demo():
    """Run complete end-to-end pipeline: DB init, sample ingestion, and reporting."""
    print_banner()

    # Step 1: Database Status
    print("\n[1/4] Checking Database Connection...")
    status = db_manager.check_connection()
    if status.get("is_timescale"):
        print(f"  [OK] Connected to Tiger Cloud (TimescaleDB Hypertables Active)")
        print(f"       Engine: PostgreSQL | Partition Interval: 1 Month")
    else:
        print(f"  [OK] Database Ready: {status.get('backend').upper()} Storage")
        print(f"       Note: To connect to live Tiger Cloud, add DATABASE_URL in .env")

    # Step 2: Ingest Sample Invoices
    print("\n[2/4] Ingesting & Categorizing Sample Side-Hustle Receipts...")
    samples_dir = PROJECT_ROOT / "samples"
    if not samples_dir.exists():
        print(f"  [ERROR] Samples folder not found at {samples_dir}")
        return

    sample_files = sorted(list(samples_dir.glob("*.txt")))
    print(f"  Found {len(sample_files)} sample invoices in samples/")

    print("\n  " + "-" * 72)
    print(f"  {'VENDOR':<24} {'DATE':<12} {'AMOUNT':<12} {'TAX':<8} {'CATEGORY'}")
    print("  " + "-" * 72)

    total_spent = 0.0
    for f in sample_files:
        try:
            text = f.read_text(encoding="utf-8")
            result = extractor.extract_from_text(text, source_filename=f.name)
            if result.success and result.record:
                rec = repo.save_invoice(result.record)
                total_spent += rec.total_amount
                cat_name = rec.category.value if hasattr(rec.category, "value") else str(rec.category)
                date_str = rec.transaction_date.strftime("%Y-%m-%d")
                print(f"  {rec.vendor[:23]:<24} {date_str:<12} {rec.currency} {rec.total_amount:>6.2f}   ${rec.tax_amount:>5.2f}  {cat_name[:22]}")
        except Exception as e:
            print(f"  Failed processing {f.name}: {e}")

    print("  " + "-" * 72)
    print(f"  Processed {len(sample_files)} receipts. Total Invoiced Volume: ${total_spent:,.2f}")

    # Step 3: Time-Series Monthly Burn Rate
    print("\n[3/4] Time-Series Monthly Burn Rate (TimescaleDB Time-Bucketing):")
    burn_rates = repo.get_monthly_burn_rate()
    if burn_rates:
        print("  " + "-" * 56)
        print(f"  {'MONTH':<12} {'INVOICES':<10} {'TOTAL SPENT':<16} {'AVG TICKET'}")
        print("  " + "-" * 56)
        for b in burn_rates:
            print(f"  {b['month']:<12} {b['count']:<10} {b['currency']} {float(b['total_spent']):>8.2f}      {b['currency']} {float(b['avg_ticket']):>6.2f}")
        print("  " + "-" * 56)

    # Step 4: Tax Deduction Audit
    print("\n[4/4] Side Hustle Tax Deduction Summary (IRS Schedule C Categories):")
    tax_summary = repo.get_tax_deduction_summary()
    print("  " + "-" * 65)
    print(f"  {'SCHEDULE C CATEGORY':<32} {'COUNT':<8} {'TAX INCLUDED':<14} {'TOTAL'}")
    print("  " + "-" * 65)
    for c in tax_summary.get("categories", []):
        print(f"  {c['category'][:30]:<32} {c['count']:<8} ${float(c['tax_paid']):>7.2f}       ${float(c['category_total']):>8.2f}")
    print("  " + "-" * 65)
    print(f"  TOTAL DEDUCTIBLE WRITE-OFFS: ${tax_summary['total_deductible_expenses']:,.2f}")
    print(f"  TOTAL TAX/VAT PAID:          ${tax_summary['total_tax_paid']:,.2f}")
    print("  " + "-" * 65)

    # Quick Next Steps
    print("\n" + "=" * 76)
    print("  ALL SYSTEMS OPERATIONAL! WHAT WOULD YOU LIKE TO DO NEXT?")
    print("=" * 76)
    print("  * Parse an invoice:     python app.py parse <file_path>")
    print("  * View stored records:  python app.py list")
    print("  * View analytics:       python app.py stats")
    print("  * Run test suite:       python app.py test")
    print("  * Start Tiger MCP:      tiger mcp start  (from Tiger CLI)")
    print("  * Start Local MCP:      python app.py mcp")
    print("=" * 76 + "\n")


def parse_file(file_path: str):
    """Parse a single invoice file and print clean details."""
    p = Path(file_path)
    if not p.exists():
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)

    print(f"Parsing invoice: {p.name}...")
    text = p.read_text(encoding="utf-8")
    result = extractor.extract_from_text(text, source_filename=p.name)

    if not result.success or not result.record:
        print(f"[FAILED] Extraction error: {result.error_message}")
        sys.exit(1)

    rec = repo.save_invoice(result.record)
    cat_name = rec.category.value if hasattr(rec.category, "value") else str(rec.category)

    print("\n" + "=" * 50)
    print("  EXTRACTION & INGESTION SUCCEEDED")
    print("=" * 50)
    print(f"  Vendor:           {rec.vendor}")
    print(f"  Transaction Date: {rec.transaction_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Total Amount:     {rec.currency} {rec.total_amount:.2f}")
    print(f"  Tax Amount:       {rec.currency} {rec.tax_amount:.2f}")
    print(f"  Category:         {cat_name}")
    print(f"  Confidence Score: {rec.confidence_score * 100:.1f}%")
    print(f"  Engine Used:      {result.extraction_method}")
    if rec.notes:
        print(f"  Notes:            {rec.notes}")
    if rec.line_items:
        print("  Line Items:")
        for item in rec.line_items:
            print(f"    - {item}")
    print("=" * 50 + "\n")


def list_records():
    """List recent stored records."""
    records = repo.list_invoices(limit=25)
    if not records:
        print("No invoices stored yet. Run 'python app.py' to ingest sample data.")
        return

    print("\nStored Financial Records:")
    print("-" * 72)
    print(f"{'DATE':<12} {'VENDOR':<24} {'CATEGORY':<24} {'TOTAL'}")
    print("-" * 72)
    for r in records:
        dt = r["transaction_date"]
        date_str = str(dt)[:10]
        print(f"{date_str:<12} {r['vendor'][:23]:<24} {r['category'][:23]:<24} {r['currency']} {float(r['total_amount']):>7.2f}")
    print("-" * 72 + "\n")


def show_stats():
    """Show monthly burn rate and category totals."""
    burn = repo.get_monthly_burn_rate()
    cats = repo.get_category_breakdown()

    print("\nMonthly Burn Rate:")
    print("-" * 50)
    for b in burn:
        print(f"  {b['month']}: {b['currency']} {float(b['total_spent']):,.2f} ({b['count']} invoices)")

    print("\nCategory Spending:")
    print("-" * 50)
    for c in cats:
        print(f"  {c['category']:<30} {c['currency']} {float(c['total_amount']):>8.2f}")
    print()


def show_tax():
    """Show tax deduction summary."""
    tax = repo.get_tax_deduction_summary()
    print("\nIRS Schedule C Tax Deductions:")
    print("-" * 55)
    for c in tax["categories"]:
        print(f"  {c['category']:<30} ${float(c['category_total']):>8.2f} (Tax: ${float(c['tax_paid']):.2f})")
    print("-" * 55)
    print(f"  Total Deductible Expenses: ${tax['total_deductible_expenses']:,.2f}")
    print(f"  Total Tax/VAT Paid:        ${tax['total_tax_paid']:,.2f}\n")


def run_tests():
    """Run the pytest test suite."""
    import pytest
    print("\nRunning automated test suite with pytest...")
    ret = pytest.main(["-q", "tests"])
    sys.exit(ret)


def start_ui():
    """Launch the Streamlit web dashboard in the browser."""
    import subprocess
    print("\nLaunching Streamlit Web UI Dashboard...")
    print("Opening in your browser at http://localhost:8501\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "ui.py"])


def start_mcp():
    """Start the Model Context Protocol (MCP) server."""
    from src.local_invoice_sorter.mcp.server import run_mcp_server
    print("\nStarting FastMCP Server (stdio transport)...")
    print("Connect this server from Claude Desktop, Cursor, or Antigravity.\n")
    run_mcp_server()


def main():
    if len(sys.argv) == 1:
        run_full_demo()
        return

    cmd = sys.argv[1].lower()
    if cmd == "parse" and len(sys.argv) > 2:
        parse_file(sys.argv[2])
    elif cmd in ("list", "ls"):
        list_records()
    elif cmd in ("stats", "burn"):
        show_stats()
    elif cmd in ("tax", "tax-report"):
        show_tax()
    elif cmd == "test":
        run_tests()
    elif cmd == "mcp":
        start_mcp()
    elif cmd in ("ui", "web", "dashboard"):
        start_ui()
    elif cmd in ("help", "--help", "-h"):
        print_banner()
        print("\nCommands:")
        print("  python app.py                  Run end-to-end demo & dashboard")
        print("  python app.py parse <file>     Parse specific receipt or invoice")
        print("  python app.py list             List stored financial records")
        print("  python app.py stats            View monthly burn rate & category breakdown")
        print("  python app.py tax              View IRS Schedule C tax deduction audit")
        print("  python app.py mcp              Launch FastMCP server for AI assistants")
        print("  python app.py ui               Launch interactive Streamlit Web Dashboard")
        print("  python app.py test             Run the 21-test pytest verification suite")
    else:
        # If user passed a file directly: python app.py samples/01_tiger_cloud_infrastructure.txt
        if Path(sys.argv[1]).exists():
            parse_file(sys.argv[1])
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Run 'python app.py --help' for available commands.")


if __name__ == "__main__":
    main()
