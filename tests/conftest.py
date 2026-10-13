"""Shared pytest fixtures."""

import pytest
from pathlib import Path
import tempfile
import os

from src.local_invoice_sorter.config import settings
from src.local_invoice_sorter.db.connection import DatabaseManager
from src.local_invoice_sorter.db.repository import InvoiceRepository
from src.local_invoice_sorter.parser.extractor import InvoiceExtractor


@pytest.fixture
def samples_dir() -> Path:
    """Path to sample invoices directory."""
    return Path(__file__).parent.parent / "samples"


@pytest.fixture
def temp_db():
    """Temporary SQLite database manager for isolated unit tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    original_db_url = settings.database_url
    original_fallback = settings.use_sqlite_fallback
    original_path = settings.local_sqlite_path

    settings.database_url = None
    settings.use_sqlite_fallback = True
    settings.local_sqlite_path = db_path

    from src.local_invoice_sorter.db.connection import db_manager
    from src.local_invoice_sorter.mcp import server as mcp_server
    from src.local_invoice_sorter import cli as cli_module

    old_mgr_dsn = db_manager.dsn
    db_manager.dsn = None
    db_manager._tested = False

    mgr = DatabaseManager(dsn="")
    repo = InvoiceRepository(mgr)
    repo.init_db()

    mcp_server.repo = repo
    cli_module.repo = repo

    yield repo, mgr

    # Cleanup
    db_manager.dsn = old_mgr_dsn
    db_manager._tested = False
    mcp_server.repo = InvoiceRepository(db_manager)
    cli_module.repo = InvoiceRepository(db_manager)
    settings.database_url = original_db_url
    settings.use_sqlite_fallback = original_fallback
    settings.local_sqlite_path = original_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def extractor() -> InvoiceExtractor:
    """Invoice extractor instance."""
    return InvoiceExtractor()
