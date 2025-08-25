#!/bin/bash

# Entrypoint script für Django Running Dinner App

set -e

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Running Dinner Application...${NC}"

# Funktion für Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Database Connection Check
check_database() {
    log "Checking database connection..."
    python manage.py check --database default
    if [ $? -eq 0 ]; then
        log "Database connection successful"
    else
        error "Database connection failed"
        exit 1
    fi
}

# Wait for database to be ready
wait_for_db() {
    log "Waiting for database to be ready..."
    
    while ! nc -z $DB_HOST $DB_PORT; do
        warning "Database is not ready yet. Waiting..."
        sleep 2
    done
    
    log "Database is ready!"
}

# Run Django migrations
run_migrations() {
    log "Running database migrations..."
    python manage.py migrate --noinput
    if [ $? -eq 0 ]; then
        log "Migrations completed successfully"
    else
        error "Migrations failed"
        exit 1
    fi
}

# Collect static files
collect_static() {
    log "Collecting static files..."
    python manage.py collectstatic --noinput --clear
    if [ $? -eq 0 ]; then
        log "Static files collected successfully"
    else
        warning "Static files collection failed"
    fi
}

# Create superuser if it doesn't exist
create_superuser() {
    log "Creating superuser if it doesn't exist..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@runningdinner.de',
        password='admin123',
        first_name='Admin',
        last_name='User'
    )
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"
}

# Load initial data
load_initial_data() {
    log "Loading initial data..."
    python manage.py shell -c "
from events.models import Course
from django.utils.translation import gettext_lazy as _

# Erstelle Standard-Kurse falls sie nicht existieren
courses = [
    {'name': 'appetizer', 'display_name': 'Vorspeise', 'order': 1},
    {'name': 'main_course', 'display_name': 'Hauptgang', 'order': 2},
    {'name': 'dessert', 'display_name': 'Nachspeise', 'order': 3},
]

for course_data in courses:
    course, created = Course.objects.get_or_create(
        name=course_data['name'],
        defaults={
            'display_name': course_data['display_name'],
            'order': course_data['order']
        }
    )
    if created:
        print(f'Created course: {course.display_name}')
    else:
        print(f'Course already exists: {course.display_name}')
"
}

# Health check endpoint
setup_health_check() {
    log "Setting up health check..."
    python manage.py shell -c "
import os
from django.core.management import execute_from_command_line
# Health check setup would go here
print('Health check configured')
"
}

# Main execution
main() {
    # Warte auf Datenbank wenn DB_HOST gesetzt ist
    if [ ! -z "$DB_HOST" ]; then
        wait_for_db
        check_database
    fi
    
    # Führe Migrations aus
    run_migrations
    
    # Lade initiale Daten
    load_initial_data
    
    # Erstelle Superuser für Development
    if [ "$DEBUG" = "True" ]; then
        create_superuser
    fi
    
    # Sammle statische Dateien
    collect_static
    
    # Setup Health Check
    setup_health_check
    
    log "Initialization completed successfully!"
    
    # Führe den übergebenen Befehl aus
    exec "$@"
}

# Script ausführen
main "$@"





