#!/usr/bin/env bash
source ./common.env
python3 manage.py collectstatic --no-input
gunicorn saleor.wsgi --bind 0.0.0.0:8000 --workers 3 --log-level=debug
