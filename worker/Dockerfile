FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libreoffice \
    poppler-utils \
    qpdf \
    curl \
    ca-certificates \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium

COPY main.py .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
