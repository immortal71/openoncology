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

# 1000, matching `runAsUser` in infra/helm/templates/api.yaml. The image had no
# non-root user at all, so it ran as root under docker-compose while Kubernetes
# forced it to a uid that owned nothing in the filesystem — two different
# identities for the same image, neither of them checked anywhere.
#
# /app is chowned because `local_storage_dir` defaults to ./local_storage: with
# object storage unconfigured the app writes there, and a read-only /app turns
# that into a 500 on upload rather than a startup failure.
RUN groupadd -g 1000 openoncology \
    && useradd -u 1000 -g 1000 -m -s /usr/sbin/nologin openoncology \
    && chown -R 1000:1000 /app

USER 1000

EXPOSE 8000

# /health is the liveness question — the process is up. Readiness is /ready,
# which round-trips Postgres and Redis; that one belongs to the orchestrator,
# which can take a pod out of rotation without killing it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
