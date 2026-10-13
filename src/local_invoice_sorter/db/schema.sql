-- ==============================================================================
-- Tiger Cloud (TimescaleDB) Financial Hypertable & Continuous Aggregate Schema
-- Project: Local AI Receipt & Invoice Sorter (local-invoice-sorter)
-- ==============================================================================

-- 1. Ensure TimescaleDB extension is active
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 2. Financial Invoices Base Table
-- Note: In TimescaleDB hypertables, unique constraints and primary keys must include
-- the time-partitioning column (transaction_date).
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

-- 3. Convert table to TimescaleDB Hypertable partitioned by monthly time chunks
SELECT create_hypertable(
    'invoices',
    by_range('transaction_date', INTERVAL '1 month'),
    if_not_exists => TRUE
);

-- 4. Enable Native Columnar Compression for Historical Partitions (Older than 30 days)
-- Segments by category and currency to achieve 90%+ compression ratio on financial time-series.
ALTER TABLE invoices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'category, currency',
    timescaledb.compress_orderby = 'transaction_date DESC'
);

SELECT add_compression_policy('invoices', INTERVAL '30 days', if_not_exists => TRUE);

-- 5. Specialized Indexes for Sub-millisecond Analytical Filtering
CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices (vendor);
CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices (category);
CREATE INDEX IF NOT EXISTS idx_invoices_currency ON invoices (currency);
CREATE INDEX IF NOT EXISTS idx_invoices_line_items_gin ON invoices USING gin (line_items);

-- 6. TimescaleDB Continuous Aggregate: Real-time Monthly Burn Rate & Categorical Spending
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_category_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', transaction_date) AS month,
    category,
    currency,
    COUNT(*) AS invoice_count,
    SUM(total_amount) AS total_spent,
    AVG(total_amount) AS avg_invoice_amount,
    MIN(total_amount) AS min_invoice_amount,
    MAX(total_amount) AS max_invoice_amount
FROM invoices
GROUP BY month, category, currency
WITH NO DATA;

-- 7. Continuous Aggregate Automated Refresh Policy
SELECT add_continuous_aggregate_policy('monthly_category_summary',
    start_offset => INTERVAL '6 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
