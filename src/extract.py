"""Fetch a public URL and return clean text/markdown via trafilatura."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx
import trafilatura
from pydantic import BaseModel, Field

from .ssrf import SSRFError, validate_url

logger = logging.getLogger(__name__)


class ExtractResult(BaseModel):
    url: str
    title: str | None = None
    markdown: str = Field(description="Clean main-content text (markdown-ish)")
    char_count: int = 0
    success: bool = True
    error: str | None = None


class ExtractConfig(BaseModel):
    timeout_seconds: float = 15.0
    max_response_bytes: int = 2_097_152  # 2 MiB
    user_agent: str = "ToolFarm-AgentExtract/0.1"
    max_redirects: int = 5


async def fetch_html(url: str, config: ExtractConfig) -> tuple[str, str]:
    """
    Fetch HTML with SSRF checks on the initial URL and every redirect target.
    Returns (final_url, html_text).
    """
    headers = {
        "User-Agent": config.user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    current = validate_url(url)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=config.timeout_seconds,
        limits=limits,
    ) as client:
        for _ in range(config.max_redirects + 1):
            response = await client.get(current, headers=headers)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect without Location header")
                next_url = urljoin(str(response.url), location)
                current = validate_url(next_url)
                continue

            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
            content = response.content
            if len(content) > config.max_response_bytes:
                raise ValueError(
                    f"Response too large ({len(content)} bytes; "
                    f"max {config.max_response_bytes})"
                )
            text = content.decode(response.encoding or "utf-8", errors="replace")
            return str(response.url), text

    raise ValueError(f"Too many redirects (max {config.max_redirects})")


def html_to_markdown(html: str, source_url: str) -> tuple[str | None, str | None]:
    """Return (markdown_text, title)."""
    text = trafilatura.extract(
        html,
        url=source_url,
        include_comments=False,
        include_tables=True,
        output_format="markdown",
        favor_precision=True,
    )
    if not text:
        text = trafilatura.extract(
            html,
            url=source_url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta else None
    return text, title


async def url_to_markdown(url: str, config: ExtractConfig | None = None) -> ExtractResult:
    """SSRF-safe fetch + readability-style main content extraction."""
    config = config or ExtractConfig()
    try:
        validate_url(url)
    except SSRFError as exc:
        return ExtractResult(
            url=url,
            markdown="",
            success=False,
            error=f"ssrf_blocked: {exc}",
        )

    try:
        final_url, html = await fetch_html(url, config)
        text, title = html_to_markdown(html, final_url)
        if not text:
            return ExtractResult(
                url=final_url,
                title=title,
                markdown="",
                success=False,
                error="extraction_empty: no main content found",
            )
        return ExtractResult(
            url=final_url,
            title=title,
            markdown=text,
            char_count=len(text),
            success=True,
        )
    except SSRFError as exc:
        return ExtractResult(
            url=url,
            markdown="",
            success=False,
            error=f"ssrf_blocked: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — surface as tool error payload
        logger.exception("url_to_markdown failed for %s", url)
        return ExtractResult(
            url=url,
            markdown="",
            success=False,
            error=f"fetch_or_extract_failed: {type(exc).__name__}: {exc}",
        )


def url_to_markdown_sync(url: str, config: ExtractConfig | None = None) -> dict[str, Any]:
    """Sync wrapper for MCP tool handlers that are not async."""
    import asyncio

    return asyncio.run(url_to_markdown(url, config)).model_dump()
