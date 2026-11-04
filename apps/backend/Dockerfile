# syntax=docker/dockerfile:1

# ---- build stage: install dependencies into an isolated virtualenv ----
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- runtime stage: only the venv and the app code, running as non-root ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" PORT=8000
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app.py .
USER 10001
EXPOSE 8000
# exec form + sh -c so $PORT / $GUNICORN_WORKERS are configurable at runtime
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-2} --access-logfile - app:app"]
