FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create build directory for temporary files
RUN mkdir -p /app/build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/backend

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.server:app --host 0.0.0.0 --port 8000"]