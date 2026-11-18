#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py ensure_library_seed
exec gunicorn library_project.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads 2 \
  --timeout 120
