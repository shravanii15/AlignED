# Two images from one file:
#   docker build --target dashboard -t aligned-dashboard .   (the Streamlit app)
#   docker build --target pipeline  -t aligned-pipeline  .   (ingestion + rebuild jobs)
# docker compose builds and runs both; see docker-compose.yml.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 aligned

# ---------------- dashboard ----------------
FROM base AS dashboard
COPY dashboard/requirements.txt dashboard/requirements.txt
RUN pip install -r dashboard/requirements.txt
COPY dashboard/ dashboard/
COPY database/aligned.db database/aligned.db
USER aligned
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status == 200 else 1)"
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]

# ---------------- pipeline ----------------
# Light dependencies only: ingestion and the derived-table rebuild. The
# heavy extraction stack (torch, sentence-transformers, Ollama) is not needed
# to refresh data and is deliberately left out.
FROM base AS pipeline
COPY requirements-pipeline.txt requirements-pipeline.txt
RUN pip install -r requirements-pipeline.txt
COPY scripts/ scripts/
COPY database/schema.sql database/schema.sql
COPY data/raw/ data/raw/
COPY data/sample_adzuna_pull.json data/sample_adzuna_pull.json
# The pipeline writes report files under data/gap_analysis, so the unprivileged
# user needs to own the app folder (COPY leaves it owned by root).
RUN mkdir -p data/gap_analysis && chown -R aligned:aligned /app
USER aligned
CMD ["python", "scripts/rebuild_all.py", "--derived-only"]
