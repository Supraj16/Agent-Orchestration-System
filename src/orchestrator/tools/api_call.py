"""Generic outbound HTTP API call tool, with basic SSRF guards: blocks requests to loopback,
link-local, and private-network hosts so an agent can't be tricked into hitting internal
services (the docker-compose network, cloud metadata endpoints, etc.)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

MAX_RESPONSE_BYTES = 20_000
TIMEOUT_SECONDS = 10
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _is_blocked_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # can't resolve -> refuse rather than risk it

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def call_api(url: str, method: str = "GET", json_body: dict | None = None, headers: dict | None = None) -> str:
    """Call an external HTTP API and return the response status and body (truncated)."""
    method = method.upper()
    if method not in ALLOWED_METHODS:
        return f"Error: unsupported method '{method}'."

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "Error: url must be an absolute http(s) URL."
    if _is_blocked_host(parsed.hostname):
        return "Error: requests to private/internal/loopback hosts are not permitted."

    try:
        response = httpx.request(
            method, url, json=json_body, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=False
        )
    except httpx.HTTPError as exc:
        return f"Error: request failed: {exc}"

    body = response.text[:MAX_RESPONSE_BYTES]
    return f"HTTP {response.status_code}\n{body}"
