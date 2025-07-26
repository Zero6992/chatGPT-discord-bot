FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -r -u 1001 botuser && \
    mkdir -p /app/.cache && \
    chown -R botuser:botuser /app

# Copy requirements first for better caching
COPY --chown=botuser:botuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=botuser:botuser . .

# Create system prompt file if it doesn't exist
RUN touch system_prompt.txt && chown botuser:botuser system_prompt.txt

# Switch to non-root user
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import discord; print('Bot container healthy')" || exit 1

# Run the bot
CMD ["python", "main.py"]