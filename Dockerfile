FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY sample_data ./sample_data
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
