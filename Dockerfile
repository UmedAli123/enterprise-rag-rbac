FROM python:3.12-slim

WORKDIR /app

# Install minimal OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy repository contents
COPY . .

# Set runtime environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000 8501

# Default command: run backend API
CMD ["sh", "-c", "python scripts/seed_users.py && python -m app.ingestion && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
