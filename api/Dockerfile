FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# System deps for bcrypt, asyncpg, etc.
RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt .
# pip vendors its own internal copies of msgpack and setuptools (pip/_vendor/),
# independent of the top-level setuptools pinned above. Even the latest pip
# release still ships older vulnerable versions of those, so once packages are
# installed pip itself is removed, taking its vendored copies with it. The
# app runs via uvicorn and never needs pip at runtime.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

COPY api/. .
COPY ai/. ./ai/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
