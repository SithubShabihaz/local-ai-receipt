"""Database connection manager for Tiger Cloud (TimescaleDB) with SQLite fallback."""

import sqlite3
from typing import Optional, ContextManager, Generator, Any
from contextlib import contextmanager
import logging

try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

from ..config import settings

logger = logging.getLogger("local_invoice_sorter.db")


class DatabaseManager:
    """Manages connections to Tiger Cloud TimescaleDB or local SQLite fallback."""

    def __init__(self, dsn: Optional[str] = None):
        if dsn is not None:
            self.dsn = dsn.strip() if dsn.strip() else None
        else:
            self.dsn = settings.get_timescale_dsn()
        self._is_timescale = False
        self._tested = False

    def check_connection(self) -> dict[str, Any]:
        """Test and return connection health status and database backend details."""
        if not self.dsn or not HAS_PSYCOPG:
            return {
                "connected": True,
                "backend": "sqlite",
                "is_timescale": False,
                "target": settings.local_sqlite_path,
                "message": "Running on local SQLite fallback. Configure Tiger Cloud credentials in .env to use TimescaleDB Hypertables."
            }

        try:
            with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    pg_version = cur.fetchone()[0]

                    # Check timescaledb extension
                    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';")
                    row = cur.fetchone()
                    ts_version = row[0] if row else None

                    self._is_timescale = bool(ts_version)
                    self._tested = True

                    return {
                        "connected": True,
                        "backend": "timescaledb" if ts_version else "postgresql",
                        "is_timescale": bool(ts_version),
                        "postgres_version": pg_version,
                        "timescaledb_version": ts_version,
                        "message": "Connected to Tiger Cloud (TimescaleDB)" if ts_version else "Connected to PostgreSQL"
                    }
        except Exception as e:
            if settings.use_sqlite_fallback:
                return {
                    "connected": True,
                    "backend": "sqlite",
                    "is_timescale": False,
                    "target": settings.local_sqlite_path,
                    "warning": f"Could not connect to Tiger Cloud ({str(e)}). Falling back to SQLite."
                }
            return {
                "connected": False,
                "backend": "timescaledb",
                "is_timescale": False,
                "error": str(e)
            }

    @property
    def is_timescale_active(self) -> bool:
        """Return True if connected to an active TimescaleDB cluster."""
        if not self._tested:
            status = self.check_connection()
            return status.get("is_timescale", False)
        return self._is_timescale

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Context manager yielding a live database connection."""
        conn = None
        if self.dsn and HAS_PSYCOPG:
            try:
                conn = psycopg.connect(self.dsn, row_factory=dict_row)
            except Exception as e:
                conn = None
                if not settings.use_sqlite_fallback:
                    raise ConnectionError(f"Failed to connect to Tiger Cloud: {e}") from e
                logger.warning(f"Tiger Cloud connection failed ({e}), using local SQLite fallback.")

        if conn is not None:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return

        # SQLite Fallback
        conn = sqlite3.connect(settings.local_sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# Singleton database manager instance
db_manager = DatabaseManager()
