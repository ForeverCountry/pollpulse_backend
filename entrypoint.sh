#!/usr/bin/env bash

# Run database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn to serve the Django application
exec gunicorn --bind 0.0.0.0:8000 pollpulse_backend.wsgi:application
