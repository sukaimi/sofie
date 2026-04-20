FROM python:3.12-slim

# System dependencies for Cairo + Pango + GObject Introspection
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libgirepository-2.0-dev \
    gir1.2-pango-1.0 \
    pkg-config \
    libglib2.0-dev \
    fonts-noto-core \
    fonts-roboto \
    fonts-open-sans \
    fonts-lato \
    fonts-montserrat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
