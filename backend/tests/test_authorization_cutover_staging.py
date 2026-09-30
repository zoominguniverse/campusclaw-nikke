"""Optional isolated-stack verification, enabled with CUTOVER_TEST_URL."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests


BASE_URL = os.getenv("CUTOVER_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="set CUTOVER_TEST_URL for an isolated Compose cutover test")


def _request(method, path, **kwargs):
    if os.getenv("CUTOVER_INSECURE_TLS") == "1":
        kwargs.setdefault("verify", False)
    return requests.request(method, f"{BASE_URL}{path}", timeout=10, **kwargs)


def _login():
    response = _request(
        "POST",
        "/api/auth/login",
        json={"username": "linzimo", "password": "authorization-cutover-password"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers
    return payload


def test_isolated_authorization_cutover_over_proxy():
    shell = _request("GET", "/materials")
    assert shell.status_code == 200
    assert "linzimo" not in shell.text

    legacy = _request("GET", "/api/auth/me", headers={"Cookie": "session=legacy"})
    assert legacy.status_code == 401
    assert legacy.headers["WWW-Authenticate"] == "Bearer"

    initial = _login()
    access_header = {"Authorization": f"Bearer {initial['access_token']}"}
    materials = _request("GET", "/api/classes/1/materials", headers=access_header)
    assert materials.status_code == 200
    material_id = materials.json()["items"][0]["id"]
    download = _request("GET", f"/api/classes/1/materials/{material_id}/download", headers=access_header)
    assert download.status_code == 200
    assert download.content

    if os.getenv("CUTOVER_VERIFY_EXPIRY") == "1":
        time.sleep(float(os.getenv("CUTOVER_EXPIRY_WAIT_SECONDS", "2")))
        assert _request("GET", "/api/auth/me", headers=access_header).status_code == 401

    refresh_header = {"Authorization": f"Bearer {initial['refresh_token']}"}
    gate = threading.Barrier(2)

    def rotate_once():
        gate.wait(timeout=5)
        return _request("POST", "/api/auth/token/refresh", headers=refresh_header)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result() for future in (pool.submit(rotate_once), pool.submit(rotate_once))]
    assert sorted(response.status_code for response in outcomes) == [200, 401]
    replacement = next(response.json() for response in outcomes if response.status_code == 200)
    assert _request("GET", "/api/auth/me", headers={"Authorization": f"Bearer {replacement['access_token']}"}).status_code == 401

    fresh = _login()
    fresh_access = {"Authorization": f"Bearer {fresh['access_token']}"}
    assert _request("GET", "/api/auth/me", headers=fresh_access).status_code == 200
    assert _request("POST", "/api/auth/logout", headers=fresh_access).status_code == 204
    assert _request("GET", "/api/auth/me", headers=fresh_access).status_code == 401
    assert _request("POST", "/api/auth/token/refresh", headers={"Authorization": f"Bearer {fresh['refresh_token']}"}).status_code == 401
