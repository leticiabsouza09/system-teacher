#!/usr/bin/env bash
# Script de build do Render — roda a cada deploy (push no GitHub).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Idempotente (get_or_create) — seguro rodar a cada deploy, inclusive
# quando o banco Postgres gratuito expira e é recriado do zero.
python manage.py seed_demo_data
