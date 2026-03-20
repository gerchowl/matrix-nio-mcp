{
  description = "matrix-nio-mcp — MCP server for Matrix homeserver integration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # libolm is deprecated upstream (CVE-2024-45191/2/3) but still required
        # by matrix-nio for E2EE. Explicitly permitted here — we accept the risk
        # for a development tool. Track matrix-nio's vodozemac migration.
        pkgs = import nixpkgs {
          inherit system;
          config.permittedInsecurePackages = [ "olm-3.2.16" ];
        };

        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: with ps; [
          # Matrix client
          matrix-nio

          # MCP framework
          # Note: 'mcp' is the Anthropic Python SDK for building MCP servers
          # Install via pip in the venv (not yet in nixpkgs)

          # Async & networking
          aiohttp
          aiofiles

          # Config & serialization
          pydantic
          tomli
          python-dotenv

          # Dev & test
          pytest
          pytest-asyncio
          mypy
          ruff

          # Utilities
          structlog
          rich
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.uv           # fast Python package manager for any gaps
            pkgs.olm          # libolm — required for E2EE (matrix-nio[e2e])
            pkgs.sqlite       # nio uses SQLite for E2EE store
            pkgs.just         # task runner (justfile)
            pkgs.git
          ];

          shellHook = ''
            echo "matrix-nio-mcp dev environment"
            echo "Python: $(python --version)"

            # Bootstrap venv for packages not yet in nixpkgs (e.g. mcp SDK)
            if [ ! -d .venv ]; then
              echo "Creating .venv..."
              uv venv --python ${python}/bin/python3
            fi
            source .venv/bin/activate

            # Install MCP SDK and any other pip-only deps
            if [ ! -f .venv/.bootstrapped ]; then
              uv pip install "mcp[cli]>=1.0" && touch .venv/.bootstrapped
            fi

            export LD_LIBRARY_PATH="${pkgs.olm}/lib:$LD_LIBRARY_PATH"
            export MATRIX_NIO_MCP_ENV=development
          '';
        };
      });
}
