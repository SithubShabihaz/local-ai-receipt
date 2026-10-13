"""Streamlit Web UI for Local AI Receipt & Invoice Sorter.
Hacktoberfest 2026 Open-Source AI Challenge Entry (Side Hustle Theme).
Run:
    streamlit run ui.py
or:
    python app.py ui
"""

import streamlit as st
from pathlib import Path
from datetime import datetime
import pandas as pd
import json

from src.local_invoice_sorter.config import settings
from src.local_invoice_sorter.db.connection import db_manager
from src.local_invoice_sorter.db.repository import InvoiceRepository
from src.local_invoice_sorter.parser.extractor import InvoiceExtractor
from src.local_invoice_sorter.parser.models import ExpenseCategory

# Configure Streamlit page
st.set_page_config(
    page_title="Local AI Receipt Sorter",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

PROJECT_ROOT = Path(__file__).parent.resolve()
samples_dir = PROJECT_ROOT / "samples"

# Initialize DAO and Extractor
@st.cache_resource
def get_services():
    repo = InvoiceRepository(db_manager)
    extractor = InvoiceExtractor()
    return repo, extractor

repo, extractor = get_services()

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧾 Invoice Sorter")
    st.caption("Hacktoberfest 2026 AI Challenge | Side Hustle Theme")
    st.divider()

    # Database Status
    status = db_manager.check_connection()
    backend = status.get("backend", "sqlite").upper()
    is_ts = status.get("is_timescale", False)

    if is_ts:
        st.success(f"🐯 **Tiger Cloud** (TimescaleDB)")
        st.caption("Hypertables & Columnar Compression Active")
    elif backend == "POSTGRESQL":
        st.info(f"🐘 **Tiger Cloud** (PostgreSQL)")
        st.caption("Cloud PostgreSQL Partition Table Active")
    else:
        st.warning(f"💾 **Local Storage** (SQLite)")
        st.caption("Offline Fallback Mode")

    st.divider()

    # Quick Ingest Sample Button
    st.subheader("⚡ Quick Sample Actions")
    if st.button("📥 Ingest All 10 Sample Receipts", use_container_width=True, type="primary"):
        with st.spinner("Ingesting sample receipts..."):
            count = 0
            if samples_dir.exists():
                for f in sorted(samples_dir.glob("*.txt")):
                    res = extractor.extract_from_text(f.read_text(encoding="utf-8"), source_filename=f.name)
                    if res.success and res.record:
                        repo.save_invoice(res.record)
                        count += 1
            st.success(f"Successfully processed {count} invoices!")
            st.rerun()

    st.divider()
    st.markdown("### 🔌 AI Assistant Integration")
    st.markdown("Use **Model Context Protocol (MCP)** with Claude Desktop or Cursor to ask questions in plain English.")


# --- MAIN HEADER ---
st.title("Local AI Receipt & Invoice Sorter")
st.markdown(
    "Automated expense categorization and time-series financial analytics for side hustlers, "
    "powered by **Tiger Cloud (TimescaleDB)**, **Local AI / Heuristics**, and **MCP**."
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Financial Dashboard",
    "📥 Ingest New Receipt",
    "📋 All Invoices",
    "📑 Tax Deductions (Schedule C)",
    "🔌 AI Assistant (MCP) Setup"
])

# ------------------------------------------------------------------------------
# TAB 1: FINANCIAL DASHBOARD
# ------------------------------------------------------------------------------
with tab1:
    invoices = repo.list_invoices(limit=500)
    burn_rates = repo.get_monthly_burn_rate()
    categories = repo.get_category_breakdown()
    tax_summary = repo.get_tax_deduction_summary()

    # Metric Cards
    total_volume = sum(float(r["total_amount"]) for r in invoices)
    total_tax = sum(float(r["tax_amount"]) for r in invoices)
    invoice_count = len(invoices)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Expenses", f"${total_volume:,.2f}")
    with col2:
        st.metric("Invoices Processed", invoice_count)
    with col3:
        st.metric("Schedule C Deductible", f"${tax_summary['total_deductible_expenses']:,.2f}")
    with col4:
        st.metric("Sales Tax / VAT Paid", f"${total_tax:,.2f}")

    st.divider()

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("📈 Monthly Burn Rate (Time-Series)")
        if burn_rates:
            burn_df = pd.DataFrame(burn_rates)
            burn_df["total_spent"] = burn_df["total_spent"].astype(float)
            burn_df = burn_df.sort_values("month", ascending=True)
            st.bar_chart(burn_df.set_index("month")["total_spent"], color="#2E86C1")
        else:
            st.info("No records yet. Ingest sample receipts from the sidebar.")

    with col_chart2:
        st.subheader("🏷️ Categorical Spending Breakdown")
        if categories:
            cat_df = pd.DataFrame(categories)
            cat_df["total_amount"] = cat_df["total_amount"].astype(float)
            st.bar_chart(cat_df.set_index("category")["total_amount"], color="#27AE60")
        else:
            st.info("No categorical data available.")


# ------------------------------------------------------------------------------
# TAB 2: INGEST NEW RECEIPT
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("Process a Receipt or Invoice")
    st.markdown("Paste raw receipt text, invoice email content, or pick one of the sample receipts.")

    # Preset selector
    sample_files = sorted(list(samples_dir.glob("*.txt"))) if samples_dir.exists() else []
    sample_options = ["-- Select a Sample Receipt --"] + [f.name for f in sample_files]
    selected_sample = st.selectbox("Load Sample Template:", sample_options)

    default_text = ""
    if selected_sample != "-- Select a Sample Receipt --":
        sample_path = samples_dir / selected_sample
        if sample_path.exists():
            default_text = sample_path.read_text(encoding="utf-8")

    receipt_input = st.text_area(
        "Receipt / Invoice Text:",
        value=default_text,
        height=220,
        placeholder="Paste your invoice, receipt, or email confirmation here..."
    )

    if st.button("🚀 Extract & Store in Database", type="primary"):
        if not receipt_input.strip():
            st.error("Please enter or paste invoice text first.")
        else:
            with st.spinner("Extracting details using Local AI & Heuristics..."):
                result = extractor.extract_from_text(receipt_input, source_filename=selected_sample if selected_sample != "-- Select a Sample Receipt --" else "manual_entry.txt")

                if result.success and result.record:
                    rec = repo.save_invoice(result.record)
                    st.success("✔ Successfully parsed and saved to Database!")

                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.markdown(f"**Vendor:** `{rec.vendor}`")
                        st.markdown(f"**Date:** `{rec.transaction_date.strftime('%Y-%m-%d')}`")
                        st.markdown(f"**Total Amount:** `{rec.currency} {rec.total_amount:.2f}`")
                        st.markdown(f"**Tax:** `{rec.currency} {rec.tax_amount:.2f}`")

                    with res_col2:
                        cat_str = rec.category.value if hasattr(rec.category, "value") else str(rec.category)
                        st.markdown(f"**Category:** `{cat_str}`")
                        st.markdown(f"**Confidence Score:** `{rec.confidence_score * 100:.1f}%`")
                        st.markdown(f"**Extraction Engine:** `{result.extraction_method}`")
                        if rec.notes:
                            st.markdown(f"**Notes:** `{rec.notes}`")

                    if rec.line_items:
                        st.markdown("**Line Items Detected:**")
                        for item in rec.line_items:
                            st.markdown(f"- {item}")
                else:
                    st.error(f"Extraction failed: {result.error_message}")


# ------------------------------------------------------------------------------
# TAB 3: ALL INVOICES
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("Stored Financial Records")
    records = repo.list_invoices(limit=200)

    if records:
        df = pd.DataFrame(records)
        df["total_amount"] = df["total_amount"].astype(float)
        df["tax_amount"] = df["tax_amount"].astype(float)
        df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.strftime("%Y-%m-%d")

        # Filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            categories_list = ["All Categories"] + sorted(list(df["category"].unique()))
            selected_cat = st.selectbox("Filter Category:", categories_list)
        with filter_col2:
            search_query = st.text_input("Search Vendor:", "")

        filtered_df = df.copy()
        if selected_cat != "All Categories":
            filtered_df = filtered_df[filtered_df["category"] == selected_cat]
        if search_query:
            filtered_df = filtered_df[filtered_df["vendor"].str.contains(search_query, case=False, na=False)]

        display_cols = ["transaction_date", "vendor", "total_amount", "currency", "tax_amount", "category", "extraction_method"]
        st.dataframe(
            filtered_df[display_cols].rename(columns={
                "transaction_date": "Date",
                "vendor": "Vendor",
                "total_amount": "Total",
                "currency": "Cur",
                "tax_amount": "Tax",
                "category": "Category",
                "extraction_method": "Engine"
            }),
            use_container_width=True,
            hide_index=True
        )

        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Invoices as CSV",
            data=csv,
            file_name="invoices_export.csv",
            mime="text/csv"
        )
    else:
        st.info("No records stored yet. Click 'Ingest All 10 Sample Receipts' in the sidebar to populate data.")


# ------------------------------------------------------------------------------
# TAB 4: TAX DEDUCTIONS (SCHEDULE C)
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("IRS Schedule C Business Tax Deductions")
    st.markdown("Categorized write-offs for sole proprietors, freelancers, and side hustlers.")

    tax = repo.get_tax_deduction_summary()
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        st.metric("Total Deductible Write-Offs", f"${tax['total_deductible_expenses']:,.2f}")
    with t_col2:
        st.metric("Total Tax / VAT Paid", f"${tax['total_tax_paid']:,.2f}")

    if tax.get("categories"):
        tax_df = pd.DataFrame(tax["categories"])
        tax_df["category_total"] = tax_df["category_total"].astype(float)
        tax_df["tax_paid"] = tax_df["tax_paid"].astype(float)

        st.dataframe(
            tax_df.rename(columns={
                "category": "IRS Schedule C Category",
                "count": "Receipts Count",
                "category_total": "Total Deductible ($)",
                "tax_paid": "Tax/VAT Included ($)"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No deductions recorded yet.")


# ------------------------------------------------------------------------------
# TAB 5: AI ASSISTANT (MCP) SETUP
# ------------------------------------------------------------------------------
with tab5:
    st.subheader("Query Your Records with AI (Model Context Protocol)")
    st.markdown(
        "Tiger Cloud and this project integrate with Claude Desktop, Cursor, and Antigravity using **MCP**. "
        "You can ask natural language questions about your finances without writing SQL."
    )

    st.markdown("#### Sample Prompts for Your AI Assistant:")
    st.code("""
• "What was my highest expense last quarter?"
• "Show my total cloud and hosting spend grouped by month."
• "Calculate my IRS Schedule C tax write-offs for 2026."
• "Here is a client meeting receipt text, please parse and store it in my hypertable."
    """)

    st.markdown("#### Claude Desktop Configuration (`claude_desktop_config.json`):")
    st.code(json.dumps({
        "mcpServers": {
            "tiger-cloud": {
                "command": "tiger",
                "args": ["mcp", "start"]
            },
            "local-invoice-sorter": {
                "command": "python",
                "args": ["-m", "src.local_invoice_sorter.mcp.server"]
            }
        }
    }, indent=2), language="json")
