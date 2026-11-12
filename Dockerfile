# Multi-stage production container for Google Cloud Run
# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend and execution runtime
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source tree
COPY . .

# Copy compiled frontend from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Prevent gRPC fork issues when running multi-threaded Python processes
ENV GRPC_ENABLE_FORK_SUPPORT=0
ENV GRPC_POLL_STRATEGY=poll

# Mandatory GCP Pre-Flight Testing: Assert deterministic trading cycle, backend API, and AI agent suites pass
RUN pytest tests/test_deterministic_cycle.py tests/test_backend_api.py tests/test_agent_copilot.py tests/test_earnings_lab.py -v

# Expose standard Cloud Run port
ENV PORT=8080
EXPOSE 8080

# Launch uvicorn
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
