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
