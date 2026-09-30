from __future__ import annotations

import os

import requests
from flask import Flask, Response, redirect, render_template, request

app = Flask(__name__)
API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", "http://localhost:8080").rstrip("/")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "").rstrip("/")
HOP_BY_HOP_HEADERS = {"connection", "content-encoding", "content-length", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"}


def proxy_api(path: str):
    headers = {name: value for name, value in request.headers.items() if name.lower() in {"content-type", "authorization"}}
    try:
        upstream = requests.request(request.method, f"{API_INTERNAL_URL}{path}", params=request.args, data=request.get_data(), headers=headers, timeout=15, allow_redirects=False)
    except requests.RequestException:
        return Response("API unavailable", status=503)
    response_headers = [(name, value) for name, value in upstream.headers.items() if name.lower() not in HOP_BY_HOP_HEADERS | {"set-cookie"}]
    return Response(upstream.content, status=upstream.status_code, headers=response_headers)


@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def api_proxy(path: str):
    return proxy_api(f"/api/{path}")


@app.get("/health")
def health_proxy():
    return proxy_api("/health")


@app.get("/")
def home():
    return redirect("/login")


@app.get("/login")
def login_page():
    return render_template("login.html", api_url=API_PUBLIC_URL)


@app.get("/materials")
def materials_page():
    return render_template("materials.html", api_url=API_PUBLIC_URL)


@app.after_request
def security_headers(response):
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response
