FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# System deps for bcrypt, asyncpg, etc.
#
# The pango libraries belong to WeasyPrint. Without them `import weasyprint`
# raises OSError rather than ImportError, because the Python package installs
# and its shared libraries do not, so every report download quietly served
# HTML from a route named oncologist-report.pdf. WeasyPrint has not needed
# cairo or gdk-pixbuf since v53; pango brings glib, harfbuzz and fontconfig
# with it. fonts-dejavu-core is separate and still required: fontconfig with
# no font installed lays the text out correctly and draws every glyph as a box.
RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl \
    libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core \
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
