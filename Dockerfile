# Production Dockerfile for local-invoice-sorter
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source code and sample data
COPY pyproject.toml .
COPY src/ ./src/
COPY samples/ ./samples/
COPY mcp_configs/ ./mcp_configs/

# Install package in editable/standard mode
RUN pip install -e .

# Default command displays CLI help
ENTRYPOINT ["local-invoice-sorter"]
CMD ["--help"]
