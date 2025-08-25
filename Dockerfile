# Multi-stage build für optimierte Größe
FROM python:3.13-slim AS base

# System-Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    curl \
    gettext \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Python-Umgebung konfigurieren
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Dependency Stage
FROM base AS dependencies

# Requirements kopieren und installieren
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production Stage
FROM base AS production

# Non-root user erstellen
RUN groupadd -r runningdinner && \
    useradd -r -g runningdinner -d /app -s /bin/bash runningdinner

# Python-Pakete von der dependency stage kopieren
COPY --from=dependencies /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# App-Code kopieren
COPY . .

# Static und Media-Verzeichnisse erstellen
RUN mkdir -p /app/staticfiles /app/media

# Permissions setzen
RUN chown -R runningdinner:runningdinner /app

# Zu non-root user wechseln
USER runningdinner

# Port freigeben
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Start Script
COPY --chown=runningdinner:runningdinner scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Default Command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "running_dinner_app.wsgi:application"]


# Development Stage
FROM dependencies AS development

# Development-Abhängigkeiten
RUN pip install \
    django-debug-toolbar \
    ipython \
    django-extensions

# App-Code kopieren
COPY . .

# Port freigeben
EXPOSE 8000

# Development Server starten
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]





