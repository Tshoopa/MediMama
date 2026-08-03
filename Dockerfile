# ---------- Base image ----------
FROM python:3.11-slim

# ---------- System dependencies ----------
# llama-cpp-python needs a compiler and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- Working directory ----------
WORKDIR /app

# ---------- Python dependencies ----------
# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Application code ----------
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# ---------- Runtime configuration ----------
EXPOSE 8000

# The model is mounted as a volume at runtime, not copied into the image.
# See docker-compose.yml

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]