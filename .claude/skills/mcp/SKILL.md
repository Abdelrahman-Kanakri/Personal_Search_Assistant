---
name: mcp
description: Use when building or consuming Model Context Protocol (MCP) servers or tools — exposing Python functions as MCP tools/resources/prompts, or connecting an agent to an MCP server. Triggers "MCP server", "expose a tool over MCP", "model context protocol", "connect to an MCP", "FastMCP". NOT for in-process LangChain/LangGraph tools that don't cross the MCP boundary (use agent-design).
---

# Skill: MCP (Model Context Protocol)

MCP standardizes how an LLM app discovers and calls external capabilities — write a
server once, any MCP client (Claude Desktop, Cursor, LangGraph, etc.) can use it. Build
servers with **FastMCP** (ships inside the official `mcp` SDK; FastMCP 3.x is current).

Three primitives:
- **Tools** — callable functions with side effects (POST-like). The model invokes them.
- **Resources** — read-only URI-addressable data (GET-like) loaded into context.
- **Prompts** — reusable templated messages the client can surface.

## Server skeleton
```python
from fastmcp import FastMCP

mcp = FastMCP(name="orders")

@mcp.tool()
def get_order(order_id: str) -> dict:
    """Return an order by ID. Use when the user references a specific order number."""
    # type hints become the input schema; the docstring is what the LLM reads to
    # decide whether to call this — write it precisely.
    return {"id": order_id, "status": "shipped"}

@mcp.resource("data://catalog")
def catalog() -> str:
    """Static product catalog the model can read at any time."""
    return "..."

if __name__ == "__main__":
    mcp.run()   # stdio transport by default (local clients)
```

## Rules that matter
- **Every parameter needs a type annotation.** FastMCP builds the JSON schema from them;
  `*args`/`**kwargs` are unsupported.
- The **docstring is the tool's prompt.** Vague docstring → wrong tool calls. Say what
  it does and *when* to use it.
- Make functions **async** for disk/network I/O so the server doesn't block.
- Return dicts/Pydantic models for structured output (auto-serialized); strings for
  plain text.

## Dev loop
```bash
uv add fastmcp            # or: uv add "mcp[cli]"
fastmcp dev server.py     # hot reload + MCP Inspector to test tools live
fastmcp install server.py --client claude   # register with Claude Desktop
```

For remote/HTTP servers add OAuth (stdio servers don't need it). After defining tools,
test each one in the Inspector before wiring it into an agent.
