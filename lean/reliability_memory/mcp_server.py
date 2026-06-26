"""
Optional MCP server surface — 4 tools over stdio.

Requires the `mcp` package (not a core dependency; imported lazily so the
package works without it).  Install with: pip install mcp

Environment variable:
    RELIABILITY_MEMORY_PATH  — path to the session JSON.
                               Default: ~/.reliability_memory/session.json
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_SESSION = Path.home() / ".reliability_memory" / "session.json"


def _session_path() -> Path:
    return Path(os.environ.get("RELIABILITY_MEMORY_PATH", str(_DEFAULT_SESSION)))


def run_mcp_server() -> None:
    """Start the MCP stdio server.  Blocks until the client disconnects."""
    try:
        from mcp.server import Server  # type: ignore[import]
        from mcp.server.stdio import stdio_server  # type: ignore[import]
        import mcp.types as types  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "The `mcp` package is required.  Install with: pip install mcp"
        ) from exc

    import asyncio
    import json

    from .store import ReliabilityStore

    path = _session_path()
    store = ReliabilityStore.load(path)
    server = Server("reliability-memory")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="observe",
                description="Record a signal-level outcome (e.g. tool step).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "signal_id": {"type": "string"},
                        "outcome": {
                            "type": "string",
                            "enum": ["success", "failure", "partial"],
                        },
                    },
                    "required": ["signal_id", "outcome"],
                },
            ),
            types.Tool(
                name="observe_edge",
                description="Record a directed context→action outcome.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "outcome": {
                            "type": "string",
                            "enum": ["success", "failure", "partial"],
                        },
                    },
                    "required": ["source", "target", "outcome"],
                },
            ),
            types.Tool(
                name="recommend",
                description="Get the most reliable next action for a given context.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "candidates": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["state", "candidates"],
                },
            ),
            types.Tool(
                name="status",
                description="Return observations, graph size, and cold-start flag.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "observe":
            result = store.observe(arguments["signal_id"], arguments["outcome"])
            store.save(path)
            return [types.TextContent(type="text", text=json.dumps(result))]

        if name == "observe_edge":
            result = store.observe_edge(
                arguments["source"], arguments["target"], arguments["outcome"]
            )
            store.save(path)
            return [types.TextContent(type="text", text=json.dumps(result))]

        if name == "recommend":
            rec = store.recommend(arguments["state"], arguments["candidates"])
            return [types.TextContent(type="text", text=json.dumps({
                "recommended": rec.recommended,
                "reason": rec.reason,
                "reliability": rec.reliability,
                "observations": rec.observations,
            }))]

        if name == "status":
            return [types.TextContent(type="text", text=json.dumps(store.status()))]

        raise ValueError(f"Unknown tool: {name}")

    asyncio.run(stdio_server(server))
