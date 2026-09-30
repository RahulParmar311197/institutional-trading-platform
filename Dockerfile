FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install . \
    && python -c "import trading_platform.app; import trading_platform.provider_historical"

USER app
EXPOSE 8000

CMD ["uvicorn", "trading_platform.app:app", "--host", "0.0.0.0", "--port", "8000"]
