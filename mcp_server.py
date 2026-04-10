#!/usr/bin/env python3
"""Backward-compatible entrypoint for the tools MCP server."""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    server_path = Path(__file__).parent / "mcp" / "tools_server.py"
    runpy.run_path(str(server_path), run_name="__main__")
