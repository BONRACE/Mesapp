FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# GeoDjango : GDAL (tire GEOS et PROJ)
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
RUN useradd -r -u 10001 app && mkdir -p media staticfiles && chown -R app /app
USER app

EXPOSE 8000
# Migrations + données de référence (catégories, points d'apport) puis serveur applicatif.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo --reference-only && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
