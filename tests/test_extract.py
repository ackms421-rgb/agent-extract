"""Happy-path extract with mocked HTTP; SSRF path through url_to_markdown."""

import httpx
import pytest
import respx

from src.extract import url_to_markdown


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>ToolFarm Test Page</title></head>
<body>
  <nav>Ignore this nav</nav>
  <article>
    <h1>Hello Agents</h1>
    <p>This is the main content agents should extract.</p>
    <p>Second paragraph with useful text.</p>
  </article>
  <footer>Copyright ignore</footer>
</body>
</html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_url_to_markdown_happy_path() -> None:
    route = respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )
    result = await url_to_markdown("https://example.com/article")
    assert route.called
    assert result.success is True
    assert result.error is None
    assert result.char_count > 0
    assert "Hello Agents" in result.markdown or "main content" in result.markdown.lower()
    assert result.url.startswith("https://example.com")


@pytest.mark.asyncio
async def test_url_to_markdown_ssrf_blocked() -> None:
    result = await url_to_markdown("http://127.0.0.1:9000/admin")
    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("ssrf_blocked")
    assert result.markdown == ""


@pytest.mark.asyncio
@respx.mock
async def test_redirect_to_private_ip_blocked() -> None:
    respx.get("https://example.com/go").mock(
        return_value=httpx.Response(
            302, headers={"Location": "http://127.0.0.1/secret"}
        )
    )
    result = await url_to_markdown("https://example.com/go")
    assert result.success is False
    assert result.error is not None
    assert "ssrf_blocked" in result.error
