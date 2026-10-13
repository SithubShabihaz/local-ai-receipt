"""Repository for financial invoices and time-series analytics on Tiger Cloud."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import json

from ..parser.models import InvoiceRecord, ExpenseCategory
from .connection import DatabaseManager, db_manager


class InvoiceRepository:
    """Data Access Object for Invoice Hypertables."""

    def __init__(self, manager: DatabaseManager = db_manager):
        self.manager = manager
        self._initialized = False

    def _ensure_initialized(self):
        if not self._initialized:
            try:
                self.init_db()
                self._initialized = True
            except Exception:
                pass

    def init_db(self) -> dict[str, Any]:
        """Initialize database schema, hypertables, and continuous aggregates."""
        status = self.manager.check_connection()
        backend = status.get("backend")

        if backend in ("timescaledb", "postgresql"):
            base_pg_schema = """
            CREATE TABLE IF NOT EXISTS invoices (
                id UUID NOT NULL,
                transaction_date TIMESTAMPTZ NOT NULL,
                vendor VARCHAR(255) NOT NULL,
                total_amount NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'USD',
                tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                category VARCHAR(100) NOT NULL,
                raw_text TEXT,
                confidence_score NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
                extraction_method VARCHAR(100) NOT NULL DEFAULT 'unknown',
                line_items JSONB NOT NULL DEFAULT '[]'::jsonb,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (id, transaction_date)
            );
            CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices (vendor);
            CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices (category);
            CREATE INDEX IF NOT EXISTS idx_invoices_currency ON invoices (currency);
            CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices (transaction_date);
            """
            with self.manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(base_pg_schema)

            # Attempt TimescaleDB hypertable features if available on this service
            is_ts = False
            try:
                with self.manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                        cur.execute("SELECT create_hypertable('invoices', by_range('transaction_date', INTERVAL '1 month'), if_not_exists => TRUE);")
                        cur.execute("""
                            ALTER TABLE invoices SET (
                                timescaledb.compress,
                                timescaledb.compress_segmentby = 'category, currency',
                                timescaledb.compress_orderby = 'transaction_date DESC'
                            );
                        """)
                        cur.execute("SELECT add_compression_policy('invoices', INTERVAL '30 days', if_not_exists => TRUE);")
                        is_ts = True
            except Exception:
                pass

            msg = "Initialized TimescaleDB Hypertables & Compression on Tiger Cloud." if is_ts else "Initialized PostgreSQL tables on Tiger Cloud (Standard PostgreSQL service)."
            return {
                "status": "success",
                "backend": "timescaledb" if is_ts else "postgresql",
                "message": msg
            }
        else:
            # SQLite fallback schema
            sqlite_schema = """
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                vendor TEXT NOT NULL,
                total_amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                tax_amount REAL NOT NULL DEFAULT 0.0,
                category TEXT NOT NULL,
                raw_text TEXT,
                confidence_score REAL NOT NULL DEFAULT 1.0,
                extraction_method TEXT NOT NULL DEFAULT 'unknown',
                line_items TEXT NOT NULL DEFAULT '[]',
                notes TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (id, transaction_date)
            );
            CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices(vendor);
            CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices(category);
            CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(transaction_date);
            """
            with self.manager.get_connection() as conn:
                conn.executescript(sqlite_schema)

            return {
                "status": "success",
                "backend": "sqlite",
                "message": "Initialized local SQLite database fallback."
            }

    def save_invoice(self, record: InvoiceRecord) -> InvoiceRecord:
        """Insert a single invoice into the hypertable."""
        self._ensure_initialized()
        status = self.manager.check_connection()
        backend = status.get("backend")

        if backend in ("timescaledb", "postgresql"):
            query = """
            INSERT INTO invoices (
                id, transaction_date, vendor, total_amount, currency,
                tax_amount, category, raw_text, confidence_score,
                extraction_method, line_items, notes, created_at
            ) VALUES (
                %(id)s, %(transaction_date)s, %(vendor)s, %(total_amount)s, %(currency)s,
                %(tax_amount)s, %(category)s, %(raw_text)s, %(confidence_score)s,
                %(extraction_method)s, %(line_items)s, %(notes)s, %(created_at)s
            ) ON CONFLICT (id, transaction_date) DO UPDATE SET
                vendor = EXCLUDED.vendor,
                total_amount = EXCLUDED.total_amount,
                category = EXCLUDED.category,
                notes = EXCLUDED.notes;
            """
            params = {
                "id": record.id,
                "transaction_date": record.transaction_date,
                "vendor": record.vendor,
                "total_amount": record.total_amount,
                "currency": record.currency,
                "tax_amount": record.tax_amount,
                "category": record.category.value if isinstance(record.category, ExpenseCategory) else record.category,
                "raw_text": record.raw_text,
                "confidence_score": record.confidence_score,
                "extraction_method": record.extraction_method,
                "line_items": json.dumps(record.line_items),
                "notes": record.notes,
                "created_at": record.created_at,
            }
            with self.manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
        else:
            # SQLite insertion
            query = """
            INSERT OR REPLACE INTO invoices (
                id, transaction_date, vendor, total_amount, currency,
                tax_amount, category, raw_text, confidence_score,
                extraction_method, line_items, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            params = (
                record.id,
                record.transaction_date.isoformat(),
                record.vendor,
                record.total_amount,
                record.currency,
                record.tax_amount,
                record.category.value if isinstance(record.category, ExpenseCategory) else record.category,
                record.raw_text,
                record.confidence_score,
                record.extraction_method,
                json.dumps(record.line_items),
                record.notes,
                record.created_at.isoformat(),
            )
            with self.manager.get_connection() as conn:
                conn.execute(query, params)

        return record

    def save_many(self, records: List[InvoiceRecord]) -> int:
        """Batch insert multiple invoices into the hypertable."""
        count = 0
        for rec in records:
            self.save_invoice(rec)
            count += 1
        return count

    def list_invoices(
        self,
        category: Optional[str] = None,
        vendor: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query invoices with multi-attribute filtering."""
        self._ensure_initialized()
        status = self.manager.check_connection()
        backend = status.get("backend")

        where_clauses = []
        params: dict[str, Any] = {}
        sqlite_params = []

        if category:
            where_clauses.append("category = %(category)s" if backend in ("timescaledb", "postgresql") else "category = ?")
            params["category"] = category
            sqlite_params.append(category)

        if vendor:
            where_clauses.append("vendor ILIKE %(vendor)s" if backend in ("timescaledb", "postgresql") else "vendor LIKE ?")
            params["vendor"] = f"%{vendor}%"
            sqlite_params.append(f"%{vendor}%")

        if start_date:
            where_clauses.append("transaction_date >= %(start_date)s" if backend in ("timescaledb", "postgresql") else "transaction_date >= ?")
            params["start_date"] = start_date
            sqlite_params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("transaction_date <= %(end_date)s" if backend in ("timescaledb", "postgresql") else "transaction_date <= ?")
            params["end_date"] = end_date
            sqlite_params.append(end_date.isoformat())

        if min_amount is not None:
            where_clauses.append("total_amount >= %(min_amount)s" if backend in ("timescaledb", "postgresql") else "total_amount >= ?")
            params["min_amount"] = min_amount
            sqlite_params.append(min_amount)

        if max_amount is not None:
            where_clauses.append("total_amount <= %(max_amount)s" if backend in ("timescaledb", "postgresql") else "total_amount <= ?")
            params["max_amount"] = max_amount
            sqlite_params.append(max_amount)

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        if backend in ("timescaledb", "postgresql"):
            query = f"""
            SELECT id, transaction_date, vendor, total_amount, currency,
                   tax_amount, category, notes, confidence_score, extraction_method
            FROM invoices
            {where_str}
            ORDER BY transaction_date DESC
            LIMIT %(limit)s OFFSET %(offset)s;
            """
            params["limit"] = limit
            params["offset"] = offset

            with self.manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
        else:
            query = f"""
            SELECT id, transaction_date, vendor, total_amount, currency,
                   tax_amount, category, notes, confidence_score, extraction_method
            FROM invoices
            {where_str}
            ORDER BY transaction_date DESC
            LIMIT ? OFFSET ?;
            """
            sqlite_params.extend([limit, offset])
            with self.manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, sqlite_params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

    def get_monthly_burn_rate(self) -> List[Dict[str, Any]]:
        """Calculate time-series monthly spend using TimescaleDB time_bucket or date grouping."""
        self._ensure_initialized()
        status = self.manager.check_connection()
        backend = status.get("backend")

        if backend in ("timescaledb", "postgresql"):
            query = """
            SELECT
                TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
                currency,
                COUNT(*) AS count,
                ROUND(SUM(total_amount)::numeric, 2) AS total_spent,
                ROUND(AVG(total_amount)::numeric, 2) AS avg_ticket
            FROM invoices
            GROUP BY 1, 2
            ORDER BY 1 DESC;
            """
            with self.manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [dict(row) for row in cur.fetchall()]
        else:
            query = """
            SELECT
                SUBSTR(transaction_date, 1, 7) AS month,
                currency,
                COUNT(*) AS count,
                ROUND(SUM(total_amount), 2) AS total_spent,
                ROUND(AVG(total_amount), 2) AS avg_ticket
            FROM invoices
            GROUP BY 1, 2
            ORDER BY 1 DESC;
            """
            with self.manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]

    def get_category_breakdown(self) -> List[Dict[str, Any]]:
        """Aggregate total spending by expense category."""
        self._ensure_initialized()
        status = self.manager.check_connection()
        backend = status.get("backend")

        query = """
        SELECT
            category,
            COUNT(*) AS invoice_count,
            ROUND(SUM(total_amount)::numeric, 2) AS total_amount,
            currency
        FROM invoices
        GROUP BY category, currency
        ORDER BY total_amount DESC;
        """ if backend in ("timescaledb", "postgresql") else """
        SELECT
            category,
            COUNT(*) AS invoice_count,
            ROUND(SUM(total_amount), 2) AS total_amount,
            currency
        FROM invoices
        GROUP BY category, currency
        ORDER BY total_amount DESC;
        """

        with self.manager.get_connection() as conn:
            if backend in ("timescaledb", "postgresql"):
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [dict(row) for row in cur.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]

    def get_tax_deduction_summary(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Compile a tax deduction audit for side hustle business expenses."""
        self._ensure_initialized()
        status = self.manager.check_connection()
        backend = status.get("backend")

        year_filter = ""
        params: dict[str, Any] = {}
        sqlite_params = []

        if year:
            if backend in ("timescaledb", "postgresql"):
                year_filter = "WHERE EXTRACT(YEAR FROM transaction_date) = %(year)s"
                params["year"] = year
            else:
                year_filter = "WHERE SUBSTR(transaction_date, 1, 4) = ?"
                sqlite_params.append(str(year))

        query = f"""
        SELECT
            category,
            COUNT(*) AS count,
            ROUND(SUM(total_amount)::numeric, 2) AS category_total,
            ROUND(SUM(tax_amount)::numeric, 2) AS tax_paid
        FROM invoices
        {year_filter}
        GROUP BY category
        ORDER BY category_total DESC;
        """ if backend in ("timescaledb", "postgresql") else f"""
        SELECT
            category,
            COUNT(*) AS count,
            ROUND(SUM(total_amount), 2) AS category_total,
            ROUND(SUM(tax_amount), 2) AS tax_paid
        FROM invoices
        {year_filter}
        GROUP BY category
        ORDER BY category_total DESC;
        """

        with self.manager.get_connection() as conn:
            if backend in ("timescaledb", "postgresql"):
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    breakdown = [dict(row) for row in cur.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute(query, sqlite_params)
                breakdown = [dict(row) for row in cursor.fetchall()]

        total_expenses = sum(item["category_total"] for item in breakdown)
        total_tax = sum(item["tax_paid"] for item in breakdown)

        return {
            "tax_year": year or "All Time",
            "total_deductible_expenses": round(total_expenses, 2),
            "total_tax_paid": round(total_tax, 2),
            "categories": breakdown
        }

    def get_hypertable_stats(self) -> Dict[str, Any]:
        """Fetch TimescaleDB hypertable compression ratio and partition chunks on Tiger Cloud."""
        status = self.manager.check_connection()
        backend = status.get("backend")

        if backend != "timescaledb":
            return {
                "backend": backend,
                "is_hypertable": False,
                "note": "Connect to Tiger Cloud to unlock hypertable partition metrics and columnar compression stats."
            }

        try:
            with self.manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Hypertable chunk summary
                    cur.execute("""
                        SELECT
                            hypertable_name,
                            num_chunks,
                            compression_enabled
                        FROM timescaledb_information.hypertables
                        WHERE hypertable_name = 'invoices';
                    """)
                    row = cur.fetchone()

                    # Compression stats
                    cur.execute("""
                        SELECT
                            total_chunks,
                            compressed_chunks,
                            pg_size_pretty(before_compression_total_bytes) as uncompressed_size,
                            pg_size_pretty(after_compression_total_bytes) as compressed_size
                        FROM hypertable_compression_stats('invoices');
                    """)
                    comp_row = cur.fetchone()

                    return {
                        "backend": "timescaledb",
                        "is_hypertable": True,
                        "hypertable_name": "invoices",
                        "num_chunks": row["num_chunks"] if row else 0,
                        "compression_enabled": row["compression_enabled"] if row else True,
                        "compression_stats": dict(comp_row) if comp_row else {}
                    }
        except Exception as e:
            return {
                "backend": "timescaledb",
                "is_hypertable": True,
                "error": str(e)
            }
