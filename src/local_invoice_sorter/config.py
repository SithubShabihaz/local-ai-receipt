"""Configuration module for local-invoice-sorter using Pydantic Settings."""

from typing import Optional, Literal
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --------------------------------------------------------------------------
    # Tiger Cloud / TimescaleDB Settings
    # --------------------------------------------------------------------------
    database_url: Optional[str] = Field(
        default=None,
        description="Full PostgreSQL connection string to Tiger Cloud TimescaleDB"
    )
    tiger_db_host: Optional[str] = Field(default=None, description="Tiger Cloud Host")
    tiger_db_port: int = Field(default=5432, description="Tiger Cloud Port")
    tiger_db_user: Optional[str] = Field(default="tsdbuser", description="Tiger Cloud User")
    tiger_db_password: Optional[str] = Field(default=None, description="Tiger Cloud Password")
    tiger_db_name: str = Field(default="tsdb", description="Tiger Cloud Database Name")
    tiger_db_sslmode: str = Field(default="require", description="SSL mode for Tiger Cloud")

    # Local fallback
    use_sqlite_fallback: bool = Field(
        default=True,
        description="Allow automatic fallback to SQLite when Tiger Cloud credentials are missing"
    )
    local_sqlite_path: str = Field(
        default="invoices_local.db",
        description="Local SQLite database file path"
    )

    # --------------------------------------------------------------------------
    # Local AI & Open-Weight Parser Settings
    # --------------------------------------------------------------------------
    local_ai_backend: Literal["auto", "ollama", "openai_compatible", "regex"] = Field(
        default="auto",
        description="AI parser backend engine to use"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama instance"
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Local model name in Ollama (e.g. llama3.2, mistral, qwen2.5)"
    )
    openai_compatible_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="Base URL for local LM Studio or vLLM endpoint"
    )
    openai_compatible_api_key: str = Field(
        default="local-dev-key",
        description="API key for local OpenAI-compatible endpoint"
    )
    openai_compatible_model: str = Field(
        default="mistral-7b-instruct",
        description="Model name for OpenAI-compatible endpoint"
    )

    # --------------------------------------------------------------------------
    # Model Context Protocol (MCP) Server Settings
    # --------------------------------------------------------------------------
    mcp_server_host: str = Field(default="0.0.0.0", description="MCP Server Host")
    mcp_server_port: int = Field(default=8000, description="MCP Server Port")
    mcp_log_level: str = Field(default="INFO", description="Log level for MCP server")

    def get_timescale_dsn(self) -> Optional[str]:
        """Construct or return the PostgreSQL / Tiger Cloud connection DSN."""
        if self.database_url and self.database_url.strip():
            return self.database_url.strip()

        if self.tiger_db_host and self.tiger_db_user and self.tiger_db_password:
            return (
                f"postgresql://{self.tiger_db_user}:{self.tiger_db_password}@"
                f"{self.tiger_db_host}:{self.tiger_db_port}/{self.tiger_db_name}"
                f"?sslmode={self.tiger_db_sslmode}"
            )
        return None

    @property
    def has_tiger_credentials(self) -> bool:
        """Check whether valid Tiger Cloud credentials are provided."""
        return bool(self.get_timescale_dsn())


# Global settings singleton
settings = Settings()
