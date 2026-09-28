#!/bin/sh
set -eu

python init_db.py
exec gunicorn --bind 0.0.0.0:8080 --workers 2 wsgi:app

