from __future__ import annotations

import os

import requests
from flask import Flask, redirect, render_template, request

app = Flask(__name__)
API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", "http://localhost:8080").rstrip("/")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "http://localhost:8080").rstrip("/")


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

