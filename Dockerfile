FROM python:3.11-slim

WORKDIR /app

# Cài system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài Python dependencies trước (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY .env.example .env.example

# Tạo thư mục data cho SQLite
RUN mkdir -p /app/data /app/keys /app/certs

# Non-root user (security best practice)
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
