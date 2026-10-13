"""Command Line Interface for local-invoice-sorter using Typer and Rich."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint
from pathlib import Path
from typing import Optional
from datetime import datetime
import json

from .config import settings
from .db.connection import db_manager
from .db.repository import InvoiceRepository
from .parser.extractor import InvoiceExtractor
from .parser.models import ExpenseCategory

app = typer.Typer(
    name="local-invoice-sorter",
    help="Local AI Receipt & Invoice Sorter for Side Hustlers | Tiger Cloud (TimescaleDB) & MCP",
    add_completion=False
)
console = Console()
repo = InvoiceRepository(db_manager)
extractor = InvoiceExtractor()


@app.command()
def check_connection():
    """Verify connection health to Tiger Cloud (TimescaleDB) or local fallback."""
    console.rule("[bold cyan]Tiger Cloud Database Connection Check[/bold cyan]")
    status = db_manager.check_connection()

    table = Table(title="Database Environment Status", border_style="cyan")
    table.add_column("Property", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Connected", str(status.get("connected")))
    table.add_row("Backend Engine", status.get("backend", "unknown"))
    table.add_row("Is TimescaleDB Hypertable Active", str(status.get("is_timescale")))

    if "postgres_version" in status:
        table.add_row("PostgreSQL Version", status["postgres_version"].split("\n")[0])
    if "timescaledb_version" in status:
        table.add_row("TimescaleDB Extension Version", str(status["timescaledb_version"]))
    if "warning" in status:
        table.add_row("Warning / Notice", f"[yellow]{status['warning']}[/yellow]")
    if "message" in status:
        table.add_row("Status Message", status["message"])

    console.print(table)


@app.command()
def init_db():
    """Initialize database schema, hypertables, and continuous aggregates on Tiger Cloud."""
    console.rule("[bold cyan]Initializing Database Schema[/bold cyan]")
    result = repo.init_db()

    if result.get("status") == "success":
        console.print(Panel(
            f"[bold green][OK] Schema Initialization Complete![/bold green]\n\n"
            f"[bold white]Backend:[/bold white] {result['backend'].upper()}\n"
            f"[bold white]Details:[/bold white] {result['message']}",
            title="Success",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]Initialization Failed:[/bold red] {result.get('error')}",
            title="Error",
            border_style="red"
        ))


@app.command()
def parse(
    file_path: Path = typer.Argument(..., help="Path to raw invoice/receipt text file"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of table")
):
    """Extract structured details from receipt text using Local AI / deterministic engine."""
    if not file_path.exists():
        console.print(f"[bold red]Error: File {file_path} not found![/bold red]")
        raise typer.Exit(code=1)

    text = file_path.read_text(encoding="utf-8")
    result = extractor.extract_from_text(text, source_filename=file_path.name)

    if not result.success or not result.record:
        console.print(f"[bold red]Extraction failed: {result.error_message}[/bold red]")
        raise typer.Exit(code=1)

    rec = result.record
    if json_output:
        rprint(json.dumps(rec.model_dump(mode="json"), indent=2))
        return

    table = Table(title=f"Extracted Invoice: {file_path.name}", border_style="green")
    table.add_column("Field", style="bold yellow")
    table.add_column("Extracted Value", style="white")

    table.add_row("Vendor", rec.vendor)
    table.add_row("Transaction Date", rec.transaction_date.strftime("%Y-%m-%d %H:%M:%S UTC"))
    table.add_row("Total Amount", f"{rec.currency} {rec.total_amount:.2f}")
    table.add_row("Tax Amount", f"{rec.currency} {rec.tax_amount:.2f}")
    table.add_row("Expense Category", rec.category.value if isinstance(rec.category, ExpenseCategory) else rec.category)
    table.add_row("Extraction Method", result.extraction_method)
    table.add_row("Confidence Score", f"{rec.confidence_score * 100:.1f}%")
    table.add_row("Execution Time", f"{result.execution_time_ms:.1f} ms")
    if rec.notes:
        table.add_row("Notes", rec.notes)
    if rec.line_items:
        table.add_row("Line Items", "\n".join(rec.line_items[:5]))

    console.print(table)


@app.command()
def ingest(
    file_path: Path = typer.Argument(..., help="Path to invoice text file to parse and store")
):
    """Parse invoice and insert it into Tiger Cloud (TimescaleDB) hypertable."""
    if not file_path.exists():
        console.print(f"[bold red]Error: File {file_path} not found![/bold red]")
        raise typer.Exit(code=1)

    text = file_path.read_text(encoding="utf-8")
    result = extractor.extract_from_text(text, source_filename=file_path.name)

    if not result.success or not result.record:
        console.print(f"[bold red]Extraction failed: {result.error_message}[/bold red]")
        raise typer.Exit(code=1)

    rec = repo.save_invoice(result.record)
    console.print(Panel(
        f"[bold green][OK] Successfully Ingested Invoice into Hypertable![/bold green]\n\n"
        f"- [bold]ID:[/bold] {rec.id}\n"
        f"- [bold]Vendor:[/bold] {rec.vendor}\n"
        f"- [bold]Date:[/bold] {rec.transaction_date.strftime('%Y-%m-%d')}\n"
        f"- [bold]Total:[/bold] {rec.currency} {rec.total_amount:.2f}\n"
        f"- [bold]Category:[/bold] {rec.category.value if isinstance(rec.category, ExpenseCategory) else rec.category}\n"
        f"- [bold]Engine:[/bold] {result.extraction_method}",
        title="Ingestion Succeeded",
        border_style="green"
    ))


@app.command()
def batch_ingest(
    folder_path: Path = typer.Argument(..., help="Directory containing receipt/invoice .txt files")
):
    """Scan directory and batch ingest all invoices into Tiger Cloud hypertable."""
    if not folder_path.is_dir():
        console.print(f"[bold red]Error: {folder_path} is not a valid directory![/bold red]")
        raise typer.Exit(code=1)

    files = list(folder_path.glob("*.txt"))
    if not files:
        console.print(f"[bold yellow]No .txt receipt files found in {folder_path}[/bold yellow]")
        return

    console.rule(f"[bold cyan]Batch Ingestion: {len(files)} Invoices[/bold cyan]")

    records = []
    summary_table = Table(title="Batch Processing Results", border_style="cyan")
    summary_table.add_column("File", style="yellow")
    summary_table.add_column("Vendor", style="white")
    summary_table.add_column("Date", style="blue")
    summary_table.add_column("Total", style="green")
    summary_table.add_column("Category", style="magenta")
    summary_table.add_column("Status", style="bold green")

    for file in sorted(files):
        text = file.read_text(encoding="utf-8")
        result = extractor.extract_from_text(text, source_filename=file.name)
        if result.success and result.record:
            rec = repo.save_invoice(result.record)
            records.append(rec)
            summary_table.add_row(
                file.name,
                rec.vendor,
                rec.transaction_date.strftime("%Y-%m-%d"),
                f"{rec.currency} {rec.total_amount:.2f}",
                rec.category.value if isinstance(rec.category, ExpenseCategory) else rec.category,
                "[OK] Saved"
            )
        else:
            summary_table.add_row(file.name, "-", "-", "-", "-", "[red]Failed[/red]")

    console.print(summary_table)
    total_spent = sum(r.total_amount for r in records)
    console.print(f"\n[bold green]Ingested {len(records)} records. Total Volume: ${total_spent:,.2f}[/bold green]")


@app.command(name="list")
def list_records(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    vendor: Optional[str] = typer.Option(None, "--vendor", "-v", help="Filter by vendor name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max records to display")
):
    """List financial records stored in the TimescaleDB hypertable."""
    rows = repo.list_invoices(category=category, vendor=vendor, limit=limit)

    if not rows:
        console.print("[yellow]No invoice records found matching criteria.[/yellow]")
        return

    table = Table(title="TimescaleDB Financial Records", border_style="cyan")
    table.add_column("Date", style="blue")
    table.add_column("Vendor", style="white")
    table.add_column("Category", style="magenta")
    table.add_column("Total", style="green", justify="right")
    table.add_column("Tax", style="yellow", justify="right")
    table.add_column("Engine", style="dim")

    for r in rows:
        dt = r["transaction_date"]
        date_str = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
        table.add_row(
            date_str,
            r["vendor"],
            r["category"],
            f"{r['currency']} {float(r['total_amount']):.2f}",
            f"{r['currency']} {float(r['tax_amount']):.2f}",
            r["extraction_method"]
        )

    console.print(table)


@app.command()
def stats():
    """Display time-series monthly burn rate and categorical spending analysis."""
    console.rule("[bold cyan]Side Hustle Financial Analytics[/bold cyan]")

    burn_rates = repo.get_monthly_burn_rate()
    if burn_rates:
        b_table = Table(title="Monthly Burn Rate (Time-Series Bucket)", border_style="green")
        b_table.add_column("Month", style="cyan")
        b_table.add_column("Invoices", justify="right")
        b_table.add_column("Total Spent", style="bold green", justify="right")
        b_table.add_column("Avg Ticket", justify="right")

        for b in burn_rates:
            b_table.add_row(
                b["month"],
                str(b["count"]),
                f"{b['currency']} {float(b['total_spent']):,.2f}",
                f"{b['currency']} {float(b['avg_ticket']):,.2f}"
            )
        console.print(b_table)

    breakdown = repo.get_category_breakdown()
    if breakdown:
        c_table = Table(title="Categorical Spending Breakdown", border_style="magenta")
        c_table.add_column("Category", style="yellow")
        c_table.add_column("Count", justify="right")
        c_table.add_column("Total Volume", style="bold green", justify="right")

        for c in breakdown:
            c_table.add_row(
                c["category"],
                str(c["invoice_count"]),
                f"{c['currency']} {float(c['total_amount']):,.2f}"
            )
        console.print(c_table)


@app.command()
def tax_report(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Tax year (e.g. 2026)")
):
    """Generate Side Hustle Tax Deduction Report (IRS Schedule C Expense Buckets)."""
    console.rule(f"[bold cyan]Side Hustle Tax Deduction Summary ({year or 'All Time'})[/bold cyan]")
    report = repo.get_tax_deduction_summary(year=year)

    table = Table(title="Schedule C Eligible Business Deductions", border_style="yellow")
    table.add_column("Deduction Category", style="bold white")
    table.add_column("Invoices", justify="right")
    table.add_column("Tax / VAT Included", justify="right", style="cyan")
    table.add_column("Deductible Total", justify="right", style="bold green")

    for cat in report["categories"]:
        table.add_row(
            cat["category"],
            str(cat["count"]),
            f"${float(cat['tax_paid']):,.2f}",
            f"${float(cat['category_total']):,.2f}"
        )

    console.print(table)
    console.print(Panel(
        f"[bold yellow]Total Deductible Expenses:[/bold yellow] [bold green]${report['total_deductible_expenses']:,.2f}[/bold green]\n"
        f"[bold yellow]Total Tax/VAT Paid:[/bold yellow] [bold cyan]${report['total_tax_paid']:,.2f}[/bold cyan]",
        title="Audit Summary",
        border_style="green"
    ))


@app.command()
def hypertable_info():
    """Inspect TimescaleDB Hypertable chunks and compression performance on Tiger Cloud."""
    console.rule("[bold cyan]Tiger Cloud Hypertable Diagnostics[/bold cyan]")
    info = repo.get_hypertable_stats()

    if not info.get("is_hypertable"):
        console.print(f"[yellow]{info.get('note', 'Hypertable info unavailable')}[/yellow]")
        return

    table = Table(title="TimescaleDB Hypertable Partitioning & Compression", border_style="cyan")
    table.add_column("Metric", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Hypertable Name", info.get("hypertable_name", "invoices"))
    table.add_row("Active Chunks Partitioned", str(info.get("num_chunks", 0)))
    table.add_row("Compression Enabled", str(info.get("compression_enabled", True)))

    comp_stats = info.get("compression_stats", {})
    if comp_stats:
        table.add_row("Total Chunks", str(comp_stats.get("total_chunks", 0)))
        table.add_row("Compressed Chunks", str(comp_stats.get("compressed_chunks", 0)))
        table.add_row("Uncompressed Size", str(comp_stats.get("uncompressed_size", "N/A")))
        table.add_row("Compressed Size", str(comp_stats.get("compressed_size", "N/A")))

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
