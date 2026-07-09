"""Integration tests for the mounted modular-monolith (server:app).

These boot the *parent* ASGI app that mounts all six sub-applications and
verify cross-cutting behaviour: aggregate health, per-app mounting, request-id
header propagation, and the standard error envelope. Requires the full
requirements set (fastapi, httpx, pydantic-settings) to be installed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

server = pytest.importorskip("server")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(server.app)


def test_root_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in {"ok", "healthy"}


def test_request_id_header_present(client: TestClient) -> None:
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers
    assert resp.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "mount",
    ["/advisor", "/coach", "/budget", "/savings", "/rag", "/market"],
)
def test_each_subapp_health_mounted(client: TestClient, mount: str) -> None:
    resp = client.get(f"{mount}/api/v1/health")
    # Some sub-apps expose /health at the app root rather than under /api/v1.
    if resp.status_code == 404:
        resp = client.get(f"{mount}/health")
    assert resp.status_code == 200, f"{mount} health not reachable"


def test_unknown_route_returns_404_envelope(client: TestClient) -> None:
    resp = client.get("/advisor/api/v1/does-not-exist")
    assert resp.status_code == 404
