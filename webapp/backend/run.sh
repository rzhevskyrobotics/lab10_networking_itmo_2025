#!/usr/bin/env bash
set -e
source .venv/bin/activate
export PYTHONUNBUFFERED=1
exec uvicorn app.main:app --host 127.0.0.1 --port 8095
