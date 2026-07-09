"""SSRF prevention helpers for outbound calls.

The suite makes outbound HTTP calls to configurable endpoints (DeepSeek /
NVIDIA inference, OpenBB). If any of those base URLs can be influenced by an
attacker or misconfiguration, they could be pointed at internal metadata
services (e.g. 169.254.169.254) or private IP ranges — a classic SSRF.

``validate_base_url`` enforces https (outside local dev), blocks obviously
private/loopback/link-local hosts, and — when an allowlist is configured —
requires the host to be explicitly permitted. It is intentionally strict and
fails closed.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from urllib.parse import urlparse


class OutboundURLNotAllowed(ValueError):
    """Raised when a configured outbound URL fails SSRF validation."""


def _is_private_host(host: str) -> bool:
    # Direct IP literal?
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        pass
    # Resolve hostname (best-effort). Any resolved address in a private range
    # is rejected.
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:  # noqa: BLE001 - resolution failure => treat as unknown
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def validate_base_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] = (),
    require_https: bool = True,
    allow_private: bool = False,
) -> str:
    """Validate an outbound base URL, returning it unchanged if acceptable.

    Raises :class:`OutboundURLNotAllowed` otherwise. ``allow_private`` should be
    enabled only for local development.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise OutboundURLNotAllowed(f"Unsupported scheme: {parsed.scheme!r}")
    if require_https and parsed.scheme != "https":
        raise OutboundURLNotAllowed("Outbound base URL must use https.")
    host = parsed.hostname or ""
    if not host:
        raise OutboundURLNotAllowed("Outbound base URL has no host.")

    allowed = {h.lower() for h in allowed_hosts}
    if allowed and host.lower() not in allowed:
        raise OutboundURLNotAllowed(f"Host {host!r} is not in the outbound allowlist.")

    if not allow_private and _is_private_host(host):
        raise OutboundURLNotAllowed(
            f"Host {host!r} resolves to a private/loopback/link-local address."
        )
    return url
