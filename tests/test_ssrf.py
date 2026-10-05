"""SSRF block tests — private IPs, localhost, non-http schemes."""

import pytest

from src.ssrf import SSRFError, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/secret",
        "http://localhost/",
        "http://localhost.localdomain/",
        "http://[::1]/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "https://user:pass@example.com/",
    ],
)
def test_ssrf_blocks_dangerous_urls(url: str) -> None:
    with pytest.raises(SSRFError):
        validate_url(url)


def test_ssrf_allows_public_https() -> None:
    # example.com resolves to public addresses
    out = validate_url("https://example.com/path?q=1")
    assert out.startswith("https://example.com")


def test_ssrf_allows_public_http() -> None:
    out = validate_url("http://example.com/")
    assert out.startswith("http://example.com")


def test_empty_url_rejected() -> None:
    with pytest.raises(SSRFError):
        validate_url("")


def test_missing_scheme_rejected() -> None:
    with pytest.raises(SSRFError):
        validate_url("example.com/foo")
