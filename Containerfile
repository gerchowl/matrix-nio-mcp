FROM python:3.12-slim

# Install system dependencies
# libolm-dev: E2EE support for matrix-nio
# sqlite3: E2EE key store (nio SqliteStore)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libolm-dev \
    libolm3 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying source for better layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir "matrix-nio[e2e]>=0.25" "mcp[cli]>=1.0" \
    "pydantic>=2.0" "structlog>=24.0" "aiofiles>=23.0" "python-dotenv>=1.0"

# Copy source
COPY src/ src/
RUN pip install --no-cache-dir -e . --no-deps

# E2EE store persists in a volume
VOLUME ["/data/store"]

ENV MATRIX_STORE_PATH=/data/store
ENV MCP_TRANSPORT=stdio
ENV LOG_LEVEL=INFO

# stdio transport: run as a subprocess from the MCP host
CMD ["python", "-m", "matrix_nio_mcp.server"]
