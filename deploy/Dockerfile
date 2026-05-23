FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY backend/ /app/backend/
WORKDIR /app/backend
RUN pip install --no-cache-dir .

COPY schemas /app/schemas
WORKDIR /app/backend

ENV PGDCT_DATABASE_URL=sqlite+aiosqlite:///./data/pgdct.db
RUN mkdir -p /app/data

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
