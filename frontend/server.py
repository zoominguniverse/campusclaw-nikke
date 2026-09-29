from __future__ import annotations

import os

import requests
from flask import Flask, Response, redirect, render_template, request

app = Flask(__name__)
API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", "http://localhost:8080").rstrip("/")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "").rstrip("/")
HOP_BY_HOP_HEADERS = {"connection", "content-encoding", "content-length", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"}


def current_user():
    try:
        response = requests.get(
            f"{API_INTERNAL_URL}/api/auth/me",
            headers={"Cookie": request.headers.get("Cookie", "")},
            timeout=3,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.json()["user"]


def proxy_api(path: str):
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() in {"content-type", "cookie", "x-csrf-token"}
    }
    try:
        upstream = requests.request(
            request.method,
            f"{API_INTERNAL_URL}{path}",
            params=request.args,
            data=request.get_data(),
            headers=headers,
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException:
        return Response("API unavailable", status=503)
    response_headers = [
        (name, value)
        for name, value in upstream.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    ]
    return Response(upstream.content, status=upstream.status_code, headers=response_headers)


@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def api_proxy(path: str):
    return proxy_api(f"/api/{path}")


@app.get("/health")
def health_proxy():
    return proxy_api("/health")


@app.get("/")
def home():
    return redirect("/materials")


@app.get("/login")
def login_page():
    if current_user():
        return redirect("/materials")
    return render_template("login.html", api_url=API_PUBLIC_URL)


@app.get("/materials")
def materials_page():
    user = current_user()
    if not user:
        return redirect("/login?next=/materials")
    return render_template("materials.html", api_url=API_PUBLIC_URL, user=user)
