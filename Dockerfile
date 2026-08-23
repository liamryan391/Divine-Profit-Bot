FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DIVINE_DATA_DIR=/data
ENV DIVINE_HOST=0.0.0.0
ENV DIVINE_PORT=8765
ENV DIVINE_DAEMON_INTERVAL=300
ENV DIVINE_DEPLOYMENT_MODE=production

WORKDIR /app

COPY pyproject.toml README.md ROADMAP.md ./
COPY divine_tool ./divine_tool

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -m divine_tool deploy healthcheck --url http://127.0.0.1:8765/api/health

CMD ["python", "-m", "divine_tool", "web"]
