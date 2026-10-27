#!/bin/sh
set -eu

python init_db.py
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --worker-class gthread --threads 8 --timeout 180 wsgi:app

