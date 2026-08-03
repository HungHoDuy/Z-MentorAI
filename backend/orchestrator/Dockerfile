# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the FastAPI backend and package the frontend static assets
FROM python:3.11-slim
WORKDIR /app

# Install backend dependencies
COPY backend/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip check && python -c "from langchain_mcp_adapters.client import MultiServerMCPClient"

# Copy backend orchestrator code
COPY backend/orchestrator/ .

# Copy compiled frontend static assets from Stage 1 into uvicorn's path
COPY --from=frontend-builder /frontend/dist ./static

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
