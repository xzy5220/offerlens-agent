FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system offerlens && adduser --system --ingroup offerlens offerlens
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

RUN mkdir -p /app/.offerlens && chown -R offerlens:offerlens /app
USER offerlens

EXPOSE 8000
CMD ["uvicorn", "offerlens_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
