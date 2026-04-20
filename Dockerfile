FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps trafilatura/chromadb may need
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Persisted artifacts: data (raw/clean/cards), memory (rounds/candidates/results),
# SQLite db, and the Chroma store. Mount a host volume at /app/var for persistence.
RUN mkdir -p /app/var && \
    ln -s /app/var/data data || true && \
    ln -s /app/var/memory memory || true

ENV STRATENGINE_DB_PATH=/app/var/stratengine.db \
    STRATENGINE_CHROMA_PATH=/app/var/chroma

ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
