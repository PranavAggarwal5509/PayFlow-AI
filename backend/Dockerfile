FROM python:3.12-slim

# Tesseract powers the OCR fallback for scanned invoices.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY scripts/ /app/scripts/
COPY sample_data/ /app/sample_data/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
# Migrations are idempotent, so applying them on every start is safe.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

