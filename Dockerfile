# Stage 1: Build frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-slim AS runtime
WORKDIR /app

# Install system deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    libpng-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir greenlet && \
    pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy aiosqlite chromadb \
    httpx websockets pillow python-dotenv pydantic pydantic-settings

# Copy backend
COPY backend/ ./backend/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy ComfyUI workflows
COPY comfyui/ ./comfyui/

# Create data directories
RUN mkdir -p /app/data /app/output

# Brands are mounted as a volume, not baked in
VOLUME ["/app/brands", "/app/output", "/app/data"]

EXPOSE 3000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "3000"]
