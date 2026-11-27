FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 decisionos \
    && mkdir -p /app/forecast_runs /app/decision_reviews /app/simulated_inventory \
    && chown -R decisionos:decisionos /app
COPY --chown=decisionos:decisionos src ./src
COPY --chown=decisionos:decisionos backend ./backend
COPY --chown=decisionos:decisionos operational_migrations ./operational_migrations
COPY --chown=decisionos:decisionos operational_alembic.ini ./
USER decisionos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
