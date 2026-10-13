# 🧾 Local AI Receipt & Invoice Sorter (`local-invoice-sorter`)

[![Hacktoberfest 2026](https://img.shields.io/badge/Hacktoberfest-2026%20AI%20Challenge-orange.svg)](https://hacktoberfest.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tiger Cloud](https://img.shields.io/badge/Database-Tiger%20Cloud%20%2F%20TimescaleDB-green.svg)](https://tigerdata.cloud)
[![Model Context Protocol](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-purple.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Side Hustle Theme Entry for the Hacktoberfest Open-Source AI Challenge.**  
> A production-ready financial tracking engine built for freelancers, creators, and side hustlers to ingest, categorize, and query chaotic receipts using **Open-Weight AI Models**, **Tiger Cloud (TimescaleDB Hypertables)**, and the **Model Context Protocol (MCP)**.

---

## 💡 The Problem & The Solution

Side hustlers and solopreneurs wear every hat: developer, marketer, accountant, and tax preparer. At the end of every quarter or tax season:
1. **Receipt Chaos**: Invoices and receipts sit trapped in email confirmations, raw text snippets, and scanned paper tickets.
2. **Missing Tax Deductions**: Legitimate IRS Schedule C write-offs (cloud hosting, client coffees, contractor fees, home office gear) are overlooked, leading to overpaid taxes.
3. **Sluggish Analytics**: Standard relational databases struggle with high-frequency time-series expense aggregation and long-term historical storage.

**`local-invoice-sorter`** solves this with a modern, open-source stack:
* **Local & Open-Weight AI Intelligence**: Parses receipts using local LLMs (Ollama `llama3.2`/`mistral`/`qwen2.5`, LM Studio) with a deterministic regex/heuristic fallback that works 100% offline with zero external dependencies.
* **Tiger Cloud (TimescaleDB Hypertables)**: Automatically partitions financial records by monthly time chunks (`by_range('transaction_date', INTERVAL '1 month')`), applies **native columnar compression** for 90%+ storage savings on data older than 30 days, and maintains **Continuous Aggregates** for real-time monthly burn rate analytics.
* **Dual MCP Support**:
  1. **Tiger MCP** (`tiger mcp start`): Direct database management, zero-copy forking, and SQL query capabilities via the official Tiger Data CLI.
  2. **Application MCP Server**: Exposes domain-specific financial tools (`parse_and_store_invoice`, `query_invoices`, `get_tax_deductions`, `get_monthly_burn_rate`) to Claude Desktop, Cursor, and Antigravity.

---

## 🏗️ Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Input["📥 Document Ingestion"]
        R1["Raw Receipt Text / OCR"]
        R2["Email Invoices"]
        R3["Batch Directory of .txt"]
    end

    subgraph AI["🤖 Hybrid Extraction Engine"]
        Router{"AI Backend Router"}
        Ollama["Local LLM (Ollama / Llama 3.2)"]
        OpenAIComp["LM Studio / vLLM"]
        RegexFall["Deterministic Heuristic & Regex Fallback"]
        Pydantic["Pydantic Validation & Normalization"]

        Router -->|Auto / Ollama| Ollama
        Router -->|LM Studio| OpenAIComp
        Router -->|Offline / Fallback| RegexFall
        Ollama --> Pydantic
        OpenAIComp --> Pydantic
        RegexFall --> Pydantic
    end

    subgraph DB["🐯 Tiger Cloud (TimescaleDB)"]
        Hypertable[("invoices Hypertable<br/>Partitioned by 1-Month Range")]
        Compression["TimescaleDB Columnar Compression<br/>Segmented by Category & Currency"]
        ContinuousAgg["Continuous Aggregate View<br/>monthly_category_summary"]

        Hypertable --> Compression
        Hypertable --> ContinuousAgg
    end

    subgraph Interfaces["⚡ User & Agent Interfaces"]
        CLI["Rich Terminal CLI<br/>(parse, ingest, stats, tax-report)"]
        FastMCP["Local Invoice Sorter FastMCP Server"]
        TigerMCP["Tiger MCP (Tiger CLI)"]
        Agents["AI Assistants<br/>(Claude Desktop, Cursor, Antigravity)"]

        FastMCP <--> Agents
        TigerMCP <--> Agents
    end

    Input --> Router
    Pydantic --> Hypertable
    Hypertable <--> CLI
    Hypertable <--> FastMCP
```

---

## ⚡ Instant 5-Second Demo (Zero Configuration Required)

Want to see the project in action immediately with zero setup? Simply run:

```bash
python app.py
```

This single zero-friction command will:
1. Auto-initialize the database (Tiger Cloud or instant local storage).
2. Parse and categorize all 10 real-world sample side-hustle invoices in `samples/`.
3. Calculate the time-series monthly burn rate (TimescaleDB time-bucketing).
4. Generate the IRS Schedule C business tax deduction audit report.

```bash
# Parse any custom invoice or receipt:
python app.py parse samples/01_tiger_cloud_infrastructure.txt

# View your monthly burn rate & category breakdown:
python app.py stats

# View Schedule C tax deductions:
python app.py tax

# Run all 21 automated tests:
python app.py test
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
* Python 3.10 or higher
* [Tiger Cloud Account](https://console.tigerdata.cloud) (free tier available) or local Docker
* *(Optional)* [Ollama](https://ollama.com/) running locally for open-weight model extraction

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/local-invoice-sorter.git
cd local-invoice-sorter

# Create and activate a virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 3. Configure Environment Variables

Copy the example environment template:
```bash
cp .env.example .env
```

Edit `.env` with your Tiger Cloud credentials:
```env
# Full connection string from Tiger Cloud Console:
DATABASE_URL=postgres://tsdbuser:your_password@your-service.tigerdata.cloud:5432/tsdb?sslmode=require

# Local AI backend (options: 'auto', 'ollama', 'openai_compatible', 'regex')
LOCAL_AI_BACKEND=auto
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Automatic local SQLite fallback when testing offline:
USE_SQLITE_FALLBACK=true
```

> [!TIP]
> If you don't have Tiger Cloud credentials immediately available, leave `USE_SQLITE_FALLBACK=true`. The system will automatically use an offline SQLite database so you can test all CLI and MCP commands without blockers!

---

## 🐯 Tiger Cloud & TimescaleDB Integration

### Step 1: Getting Your Tiger Cloud Connection
1. Sign up / Log in to [Tiger Data Cloud Console](https://console.tigerdata.cloud).
2. Create a new service (PostgreSQL with TimescaleDB enabled).
3. Copy your connection URI (`postgres://tsdbuser:***@host:5432/tsdb?sslmode=require`).
4. Paste it into your `.env` file under `DATABASE_URL`.

### Step 2: Initialize Hypertables & Continuous Aggregates

Run the initialization command to execute the optimized schema:
```bash
local-invoice-sorter init-db
```

This sets up:
* **Hypertable Partitioning**:
  ```sql
  SELECT create_hypertable('invoices', by_range('transaction_date', INTERVAL '1 month'), if_not_exists => TRUE);
  ```
* **Columnar Compression Policy**:
  ```sql
  ALTER TABLE invoices SET (
      timescaledb.compress,
      timescaledb.compress_segmentby = 'category, currency',
      timescaledb.compress_orderby = 'transaction_date DESC'
  );
  SELECT add_compression_policy('invoices', INTERVAL '30 days', if_not_exists => TRUE);
  ```
* **Continuous Aggregate View**:
  ```sql
  CREATE MATERIALIZED VIEW monthly_category_summary
  WITH (timescaledb.continuous) AS
  SELECT
      time_bucket('1 month', transaction_date) AS month,
      category,
      currency,
      COUNT(*) AS invoice_count,
      SUM(total_amount) AS total_spent
  FROM invoices
  GROUP BY month, category, currency;
  ```

### Step 3: Check Connection Health
```bash
local-invoice-sorter check-connection
```

---

## 🖥️ Command Line Interface (CLI) Usage

The project includes an interactive terminal interface built with **Typer** and **Rich**:

### 1. Extract Details from a Receipt (Dry Run)
Inspect extracted vendor, date, amount, tax, and category without modifying the database:
```bash
local-invoice-sorter parse samples/01_tiger_cloud_infrastructure.txt
```
To receive raw JSON output:
```bash
local-invoice-sorter parse samples/01_tiger_cloud_infrastructure.txt --json
```

### 2. Ingest a Single Receipt into Tiger Cloud
```bash
local-invoice-sorter ingest samples/01_tiger_cloud_infrastructure.txt
```

### 3. Batch Ingest an Entire Receipt Folder
Process all `.txt` receipts in the `samples/` directory in one command:
```bash
local-invoice-sorter batch-ingest samples/
```

### 4. Query Stored Records
```bash
# List recent invoices
local-invoice-sorter list

# Filter by category
local-invoice-sorter list --category "Software & Cloud Services"

# Filter by vendor
local-invoice-sorter list --vendor "Tiger"
```

### 5. View Time-Series Monthly Burn Rate & Categorical Breakdown
```bash
local-invoice-sorter stats
```

### 6. Generate Side Hustle Tax Deduction Report (IRS Schedule C)
```bash
local-invoice-sorter tax-report --year 2026
```

### 7. Inspect TimescaleDB Hypertable & Compression Metrics
```bash
local-invoice-sorter hypertable-info
```

---

## 🔌 Model Context Protocol (MCP) Integration

This project integrates with AI coding assistants (Claude Desktop, Cursor, Antigravity, Windsurf) through **two complementary MCP pathways**:

### Pathway A: Official Tiger MCP (`tiger mcp start`)
The official Tiger Data MCP server comes bundled inside the Tiger CLI. It gives your AI agent infrastructure-level superpowers:
* Spin up and inspect TimescaleDB instances
* Perform **zero-copy database forks** to test schema changes or data migrations in isolation
* Query TimescaleDB documentation directly

Install the Tiger CLI and start the MCP server:
```bash
# Install Tiger CLI (see official Tiger Data docs)
# Test MCP start:
tiger mcp start
```

### Pathway B: Application-Level MCP Server (`FastMCP`)
Our included Python MCP server (`src.local_invoice_sorter.mcp.server`) exposes specialized financial tools to AI assistants:
* `parse_and_store_invoice`: Send raw invoice text; agent parses and stores it in Tiger Cloud.
* `query_invoices`: Filter expenses by category, vendor, or dollar threshold.
* `get_monthly_burn_rate`: Query time-series spending trends.
* `get_tax_deductions`: Summarize deductible write-offs for Schedule C.
* `get_timescale_stats`: Inspect compression ratio and partitioned chunks.

### Configuration for Claude Desktop

Add both servers to your `claude_desktop_config.json`:
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tiger-cloud": {
      "command": "tiger",
      "args": ["mcp", "start"]
    },
    "local-invoice-sorter": {
      "command": "python",
      "args": ["-m", "src.local_invoice_sorter.mcp.server"],
      "env": {
        "PYTHONPATH": "d:\\Shabiha\\Hacktoberfest Challange"
      }
    }
  }
}
```

### Example Natural Language Prompts in Claude / Cursor:

* 💬 *"I had a client coffee today at Starbucks for $16.13 including $1.28 tax on Sept 22. Ingest this into my financial hypertable."*
* 💬 *"What is my monthly burn rate across all cloud and software infrastructure?"*
* 💬 *"Calculate my total tax-deductible expenses for the 2026 tax year grouped by IRS Schedule C categories."*
* 💬 *"Inspect the TimescaleDB hypertable compression statistics on my Tiger Cloud cluster."*

---

## 📂 Project Structure

```text
local-invoice-sorter/
├── src/
│   └── local_invoice_sorter/
│       ├── __init__.py           # Package version and metadata
│       ├── config.py             # Pydantic Settings & environment loader
│       ├── cli.py                # Rich Typer terminal commands
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.sql        # Hypertables, compression & continuous aggregates
│       │   ├── connection.py     # Tiger Cloud connection manager & SQLite fallback
│       │   └── repository.py     # Data Access Object & time-series analytics
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── models.py         # Pydantic schemas (InvoiceRecord, ExpenseCategory)
│       │   ├── regex_engine.py   # Deterministic offline heuristic fallback
│       │   ├── ai_engine.py      # Ollama / LM Studio open-weight model client
│       │   └── extractor.py      # Hybrid orchestrator with confidence scoring
│       └── mcp/
│           ├── __init__.py
│           └── server.py         # FastMCP Server exposing tools and resources
├── samples/                      # 10 realistic side hustle sample invoices
│   ├── 01_tiger_cloud_infrastructure.txt
│   ├── 02_aws_hosting.txt
│   ├── 03_github_copilot.txt
│   ├── 04_starbucks_client_coffee.txt
│   ├── 05_home_depot_office_desk.txt
│   ├── 06_stripe_processing_fees.txt
│   ├── 07_adobe_creative_cloud.txt
│   ├── 08_uber_business_trip.txt
│   ├── 09_upwork_contractor.txt
│   └── 10_figma_annual_plan.txt
├── mcp_configs/                  # Ready-to-use client configs
│   ├── claude_desktop_config.json
│   ├── cursor_mcp_config.json
│   └── antigravity_mcp_config.json
├── tests/                        # Comprehensive test suite (pytest)
│   ├── conftest.py               # Shared test fixtures & SQLite mock
│   ├── test_parser.py            # Extraction tests across all 10 sample files
│   ├── test_db.py                # Hypertable queries, burn rate & tax audits
│   ├── test_cli.py               # Typer CLI subcommands tests
│   └── test_mcp.py               # FastMCP tool execution tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Python and database ignores
├── Dockerfile                    # Container definition
├── docker-compose.yml            # Local TimescaleDB + application stack
├── pyproject.toml                # Build system and project metadata
├── requirements.txt              # Production dependencies
└── README.md                     # Project documentation
```

---

## 🧪 Running Tests

The test suite covers parser accuracy across all sample documents, database operations, time-series rollups, CLI execution, and MCP tools:

```bash
python -m pytest -v
```

---

## 🐳 Docker Setup

Run the application with a local TimescaleDB container:
```bash
docker compose up --build
```

---

## 🤝 Contributing for Hacktoberfest 2026

Contributions are welcome! Suggested ideas for pull requests:
1. **OCR Ingestion**: Add `pytesseract` or `easyocr` integration for scanned image files (PNG/JPEG/PDF).
2. **Additional Currencies**: Expand currency conversion logic using real-time foreign exchange APIs.
3. **Receipt Email Watcher**: Build an IMAP/Gmail API webhook to automatically ingest invoices arriving by email.
4. **Vector Search / Semantic Querying**: Use TimescaleDB `pgvector` / `DiskANN` to semantically search invoice line items.

### How to Contribute:
1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/awesome-feature`).
3. Commit your changes (`git commit -m 'feat: add awesome feature'`).
4. Push to the branch (`git push origin feature/awesome-feature`).
5. Open a Pull Request tagged with `hacktoberfest`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
