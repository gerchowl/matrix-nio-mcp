# matrix-nio-mcp task runner

default:
    @just --list

# Run the MCP server (stdio transport)
run:
    python -m matrix_nio_mcp.server

# Run with SSE transport
run-sse:
    MCP_TRANSPORT=sse python -m matrix_nio_mcp.server

# Run all tests
test:
    pytest tests/ -v

# Run only unit tests
test-unit:
    pytest tests/unit/ -v

# Run only integration tests (requires local Synapse)
test-integration:
    pytest tests/integration/ -v

# Lint
lint:
    ruff check src/ tests/

# Format
fmt:
    ruff format src/ tests/

# Type check
typecheck:
    mypy src/

# All checks (CI)
check: lint typecheck test-unit

# Start local Synapse for integration testing
synapse-up:
    docker compose -f tests/integration/docker-compose.yml up -d

synapse-down:
    docker compose -f tests/integration/docker-compose.yml down -v

# Install project in dev mode (creates .venv and installs all deps incl. dev)
install:
    uv sync --all-groups

# Start dev server (SSE transport, pretty logging)
dev:
    MCP_TRANSPORT=sse LOG_FORMAT=pretty python -m matrix_nio_mcp.server

# Remove build artifacts, caches, and virtualenv
clean:
    rm -rf .venv dist build *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    rm -rf .mypy_cache .ruff_cache .pytest_cache

# Tail container logs
logs:
    podman logs -f matrix-nio-mcp 2>/dev/null || podman compose -f tests/integration/docker-compose.yml logs -f
