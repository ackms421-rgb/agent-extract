"""SSRF protection: only public http/https URLs; block private/link-local/metadata IPs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that must never be fetched (cloud metadata, localhost aliases)
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
        "metadata.aws",
    }
)


class SSRFError(ValueError):
    """Raised when a URL fails SSRF checks."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network("169.254.0.0/16"))
        or (ip.version == 6 and ip in ipaddress.ip_network("fd00::/8"))
    )


def _resolve_and_check_host(hostname: str) -> list[str]:
    """Resolve hostname and ensure all addresses are public."""
    if not hostname:
        raise SSRFError("URL missing hostname")

    host_lower = hostname.lower().rstrip(".")
    if host_lower in BLOCKED_HOSTNAMES or host_lower.endswith(".localhost"):
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Literal IP in hostname
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_blocked_ip(ip):
            raise SSRFError(f"Blocked IP address: {hostname}")
        return [str(ip)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}: {exc}") from exc

    if not infos:
        raise SSRFError(f"No addresses for hostname: {hostname}")

    resolved: list[str] = []
    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if _is_blocked_ip(ip):
            raise SSRFError(f"Hostname resolves to blocked IP: {hostname} -> {addr}")
        resolved.append(addr)
    return resolved


def validate_url(url: str) -> str:
    """
    Validate URL for outbound fetch. Returns the normalized URL string.
    Raises SSRFError on failure.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFError("Only http and https URLs are allowed")

    if parsed.username or parsed.password:
        raise SSRFError("URLs with credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL missing hostname")

    _resolve_and_check_host(hostname)
    return url
