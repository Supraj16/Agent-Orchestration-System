FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000
# Migrations run once here (not in the worker/ui images) so docker-compose up is a clean,
# single-step start -- the API container is always present and starts first via depends_on.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
