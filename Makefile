# Running Dinner Django App - Makefile
# Vereinfacht die Verwaltung der Docker-Umgebung

.PHONY: help build up down logs shell test clean dev-up dev-down prod-up prod-down

# Standard Target
help: ## Zeige verfügbare Befehle
	@echo "Running Dinner - Verfügbare Make-Befehle:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Development Umgebung
dev-build: ## Build Development Images
	docker-compose -f docker-compose.dev.yml build

dev-up: ## Starte Development Umgebung
	docker-compose -f docker-compose.dev.yml up -d
	@echo "🚀 Development Umgebung gestartet!"
	@echo "📱 Django App: http://localhost:8001"
	@echo "📧 MailHog: http://localhost:8025"
	@echo "🗄️  pgAdmin: http://localhost:8080"
	@echo "   └─ Login: admin@runningdinner.dev / admin"

dev-down: ## Stoppe Development Umgebung
	docker-compose -f docker-compose.dev.yml down

dev-logs: ## Zeige Development Logs
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell: ## Django Shell in Development Container
	docker-compose -f docker-compose.dev.yml exec web python manage.py shell

dev-reset: ## Reset Development Database
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose -f docker-compose.dev.yml up -d

# Production Umgebung
prod-build: ## Build Production Images
	docker-compose build

prod-up: ## Starte Production Umgebung
	docker-compose up -d
	@echo "🚀 Production Umgebung gestartet!"
	@echo "🌐 App verfügbar auf: http://localhost"

prod-down: ## Stoppe Production Umgebung
	docker-compose down

prod-logs: ## Zeige Production Logs
	docker-compose logs -f

# Allgemeine Befehle
build: dev-build ## Build Development Images (Standard)

up: dev-up ## Starte Development Umgebung (Standard)

down: dev-down ## Stoppe Development Umgebung (Standard)

logs: dev-logs ## Zeige Development Logs (Standard)

shell: dev-shell ## Django Shell (Standard)

# Database Management
migrate: ## Führe Django Migrations aus
	docker-compose -f docker-compose.dev.yml exec web python manage.py migrate

makemigrations: ## Erstelle Django Migrations
	docker-compose -f docker-compose.dev.yml exec web python manage.py makemigrations

createsuperuser: ## Erstelle Django Superuser
	docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser

dbshell: ## PostgreSQL Shell
	docker-compose -f docker-compose.dev.yml exec db psql -U dev_user -d running_dinner_dev

# Testing
test: ## Führe Tests aus
	docker-compose -f docker-compose.dev.yml exec web python manage.py test

test-coverage: ## Führe Tests mit Coverage aus
	docker-compose -f docker-compose.dev.yml exec web coverage run --source='.' manage.py test
	docker-compose -f docker-compose.dev.yml exec web coverage report

# Static Files & Collectstatic
collectstatic: ## Sammle statische Dateien
	docker-compose -f docker-compose.dev.yml exec web python manage.py collectstatic --noinput

# Code Quality
lint: ## Führe Linting aus
	docker-compose -f docker-compose.dev.yml exec web flake8 .
	docker-compose -f docker-compose.dev.yml exec web black --check .

format: ## Formatiere Code
	docker-compose -f docker-compose.dev.yml exec web black .
	docker-compose -f docker-compose.dev.yml exec web isort .

# Backup & Restore
backup-db: ## Backup der Datenbank
	@mkdir -p backups
	docker-compose -f docker-compose.dev.yml exec db pg_dump -U dev_user running_dinner_dev > backups/db_backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "📦 Database Backup erstellt in backups/"

restore-db: ## Restore Database (make restore-db FILE=backup.sql)
	@if [ -z "$(FILE)" ]; then echo "❌ Bitte FILE=backup.sql angeben"; exit 1; fi
	docker-compose -f docker-compose.dev.yml exec -T db psql -U dev_user running_dinner_dev < $(FILE)
	@echo "✅ Database wiederhergestellt"

# Cleanup
clean: ## Bereinige Docker Resources
	docker-compose -f docker-compose.dev.yml down -v --rmi all --remove-orphans
	docker-compose down -v --rmi all --remove-orphans
	docker system prune -f

clean-volumes: ## Lösche alle Volumes
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose down -v

# Monitoring
status: ## Zeige Container Status
	@echo "Development Container:"
	@docker-compose -f docker-compose.dev.yml ps
	@echo ""
	@echo "Production Container:"
	@docker-compose ps

health: ## Prüfe Container Gesundheit
	@echo "🏥 Checking container health..."
	@docker-compose -f docker-compose.dev.yml exec web curl -f http://localhost:8000/health/ || echo "❌ Web unhealthy"
	@docker-compose -f docker-compose.dev.yml exec db pg_isready -U dev_user || echo "❌ DB unhealthy"
	@docker-compose -f docker-compose.dev.yml exec redis redis-cli ping || echo "❌ Redis unhealthy"

# Security
security-check: ## Führe Security Checks aus
	docker-compose -f docker-compose.dev.yml exec web python manage.py check --deploy

# Initial Setup
dev-setup: ## Setup Development Environment (PostgreSQL + Redis)
	@echo "🛠️  Setting up Running Dinner Development Environment with PostgreSQL + Redis..."
	@echo "📋 Copying environment configuration..."
	cp env_example.txt .env
	@echo "🐳 Building and starting containers..."
	make dev-build
	make dev-up
	@echo "⏳ Waiting for services to be ready..."
	sleep 15
	@echo "🗄️  Running database migrations..."
	make migrate
	@echo "📦 Collecting static files..."
	make collectstatic
	@echo ""
	@echo "✅ PostgreSQL + Redis Setup completed!"
	@echo "🎉 Du kannst jetzt mit der Entwicklung beginnen:"
	@echo "   - Django: http://localhost:8001"
	@echo "   - Admin: http://localhost:8001/admin"
	@echo "   - MailHog: http://localhost:8025"
	@echo "   - pgAdmin: http://localhost:8080 (admin@runningdinner.dev / admin)"
	@echo "   - PostgreSQL: localhost:5433"
	@echo "   - Redis: localhost:6380"

setup: ## Initiales Setup für neue Entwickler (alias für dev-setup)
	make dev-setup

reset-db: ## Reset PostgreSQL database (Development)
	@echo "🗑️  Resetting PostgreSQL database..."
	docker-compose -f docker-compose.dev.yml exec db psql -U dev_user -d postgres -c "DROP DATABASE IF EXISTS running_dinner_dev;"
	docker-compose -f docker-compose.dev.yml exec db psql -U dev_user -d postgres -c "CREATE DATABASE running_dinner_dev;"
	@echo "🔄 Running migrations..."
	make migrate
	@echo "✅ Database reset completed!"

# Hilfsfunktionen
update-deps: ## Update Python Dependencies
	docker-compose -f docker-compose.dev.yml exec web pip install -r requirements.txt

enter-web: ## Betrete Web Container
	docker-compose -f docker-compose.dev.yml exec web bash

enter-db: ## Betrete DB Container
	docker-compose -f docker-compose.dev.yml exec db bash





