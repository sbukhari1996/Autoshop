FROM python:3.12-slim

WORKDIR /app

# System deps for WeasyPrint (PDF) and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-info \
    libcairo2 libharfbuzz0b libfontconfig1 \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
