"""Unit tests for the CLI interface."""

from typer.testing import CliRunner
from pathlib import Path
from src.local_invoice_sorter.cli import app

runner = CliRunner()


def test_cli_check_connection():
    result = runner.invoke(app, ["check-connection"])
    assert result.exit_code == 0
    assert "Database Environment Status" in result.stdout


def test_cli_init_db(temp_db):
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Initialization Complete" in result.stdout


def test_cli_parse(samples_dir: Path):
    sample_file = str(samples_dir / "01_tiger_cloud_infrastructure.txt")
    result = runner.invoke(app, ["parse", sample_file])
    assert result.exit_code == 0
    assert "Extracted Invoice" in result.stdout
    assert "Tiger" in result.stdout
    assert "49.00" in result.stdout


def test_cli_parse_json(samples_dir: Path):
    sample_file = str(samples_dir / "01_tiger_cloud_infrastructure.txt")
    result = runner.invoke(app, ["parse", sample_file, "--json"])
    assert '"vendor": "Tiger Data Inc."' in result.stdout


def test_cli_ingest(temp_db, samples_dir: Path):
    sample_file = str(samples_dir / "03_github_copilot.txt")
    result = runner.invoke(app, ["ingest", sample_file])
    assert result.exit_code == 0
    assert "Successfully Ingested" in result.stdout
    assert "19.00" in result.stdout


def test_cli_batch_ingest_and_list(temp_db, samples_dir: Path):
    result = runner.invoke(app, ["batch-ingest", str(samples_dir)])
    assert result.exit_code == 0
    assert "Batch Ingestion" in result.stdout
    assert "Ingested 10 records" in result.stdout

    # Test list command
    list_res = runner.invoke(app, ["list"])
    assert list_res.exit_code == 0
    assert "Financial Records" in list_res.stdout

    # Test stats command
    stats_res = runner.invoke(app, ["stats"])
    assert stats_res.exit_code == 0
    assert "Monthly Burn Rate" in stats_res.stdout

    # Test tax report
    tax_res = runner.invoke(app, ["tax-report"])
    assert tax_res.exit_code == 0
    assert "Schedule C" in tax_res.stdout

    # Test hypertable info
    info_res = runner.invoke(app, ["hypertable-info"])
    assert info_res.exit_code == 0
