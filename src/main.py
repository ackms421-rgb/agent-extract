"""
ToolFarm Agent Extract — FastAPI + MCP-shaped tool surface.

REST:  POST /v1/url_to_markdown   (Ozma OpenAPI later)
MCP:   POST /mcp                  (JSON-RPC tools/list + tools/call)
       GET  /health
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .extract import ExtractResult, url_to_markdown

logger = logging.getLogger("agent_extract")

app = FastAPI(
    title="ToolFarm Agent Extract",
    description=(
        "URL → clean markdown/text for AI agents. "
        "v1 is extract-only; search is a later add-on. "
        "MCPize: meter via x402 (~$0.01–0.02/call). Ozma: Stripe Connect + OpenAPI."
    ),
    version="0.1.0",
    contact={"name": "ToolFarm"},
)


class UrlToMarkdownRequest(BaseModel):
    url: str = Field(..., description="Public http(s) URL to extract", min_length=8)


def require_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_key:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-extract", "version": "0.1.0"}


@app.post(
    "/v1/url_to_markdown",
    response_model=ExtractResult,
    summary="Extract clean markdown from a public URL",
    tags=["extract"],
)
async def api_url_to_markdown(
    body: UrlToMarkdownRequest,
    _: None = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
) -> ExtractResult:
    result = await url_to_markdown(body.url, settings.extract_config())
    if not result.success and result.error and result.error.startswith("ssrf_blocked"):
        raise HTTPException(status_code=400, detail=result.error)
    return result


# --- Minimal MCP JSON-RPC (tools/list + tools/call) for MCPize-style hosts ---

TOOL_DEF = {
    "name": "url_to_markdown",
    "description": (
        "Fetch a public web page and return its main content as clean markdown/text. "
        "Blocks private IPs and non-http(s) URLs. Use for agent research / RAG ingest."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Public http or https URL",
            }
        },
        "required": ["url"],
    },
}


class McpJsonRpc(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


@app.post("/mcp")
async def mcp_endpoint(
    rpc: McpJsonRpc,
    _: None = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Lightweight MCP tools surface (list + call). Not a full transport stack."""
    req_id = rpc.id

    if rpc.method in ("initialize", "notifications/initialized"):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "toolfarm-agent-extract", "version": "0.1.0"},
                },
            }
        )

    if rpc.method == "tools/list":
        return JSONResponse(
            {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [TOOL_DEF]}}
        )

    if rpc.method == "tools/call":
        params = rpc.params or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name != "url_to_markdown":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }
            )
        url = arguments.get("url")
        if not url or not isinstance(url, str):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "url (string) required"},
                }
            )
        result = await url_to_markdown(url, settings.extract_config())
        payload = result.model_dump()
        is_error = not result.success
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": payload["markdown"]
                            if result.success
                            else (result.error or "error"),
                        }
                    ],
                    "structuredContent": payload,
                    "isError": is_error,
                },
            }
        )

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {rpc.method}"},
        }
    )


def run() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    run()
