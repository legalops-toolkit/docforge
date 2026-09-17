# ── Stage 1: builder — собираем зависимости в изолированный venv ──────────
FROM python:3.14-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime — только venv + код, без компиляторов и кэша pip ─────
FROM python:3.14-slim AS runtime

# Непривилегированный пользователь — контейнер не должен работать под root.
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --chown=app:app src ./src
COPY --chown=app:app templates ./templates
COPY --chown=app:app main.py pyproject.toml ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
