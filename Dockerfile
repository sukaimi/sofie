FROM python:3.12-slim

# System dependencies for Cairo + Pango
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    pkg-config \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
