#!/usr/bin/env bash
# Render build step: install, collect static files, migrate (also creates the SQL views).
set -o errexit

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Optional demo data: set SEED_DEMO=true. Safe on every deploy (skips when data exists).
if [ "$SEED_DEMO" = "true" ]; then
  python manage.py seed_demo_data --if-empty
fi
