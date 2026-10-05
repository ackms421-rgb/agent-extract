"""MCP discovery stays open; tools/call respects API_KEY."""

from fastapi.testclient import TestClient

from src.config import get_settings
from src.main import app


def _client_with_key(monkeypatch, key: str) -> TestClient:
    monkeypatch.setenv("API_KEY", key)
    get_settings.cache_clear()
    return TestClient(app)


def test_tools_list_open_when_api_key_set(monkeypatch) -> None:
    client = _client_with_key(monkeypatch, "secret-test-key")
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["tools"][0]["name"] == "url_to_markdown"


def test_initialize_open_when_api_key_set(monkeypatch) -> None:
    client = _client_with_key(monkeypatch, "secret-test-key")
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["serverInfo"]["name"] == "toolfarm-agent-extract"


def test_tools_call_requires_key(monkeypatch) -> None:
    client = _client_with_key(monkeypatch, "secret-test-key")
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "url_to_markdown",
                "arguments": {"url": "https://example.com"},
            },
        },
    )
    assert r.status_code == 401


def test_tools_call_accepts_x_mcp_api_key(monkeypatch) -> None:
    client = _client_with_key(monkeypatch, "secret-test-key")
    r = client.post(
        "/mcp",
        headers={"X-MCP-Api-Key": "secret-test-key"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "url_to_markdown",
                "arguments": {"url": "http://127.0.0.1/x"},
            },
        },
    )
    # Auth passed; SSRF should reject the URL with a JSON-RPC result (not 401)
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["isError"] is True
