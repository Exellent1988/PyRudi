# DevContainer Setup Guide

## 🎯 Übersicht

DevContainer-Konfiguration für Running Dinner mit Docker-in-Docker Support für PostgreSQL und Redis Services.

## 🔧 Setup

### 1. DevContainer Rebuild
```bash
# In VS Code Command Palette (Ctrl+Shift+P):
Dev Containers: Rebuild Container
```

### 2. After Container Rebuild
```bash
# Start services
make dev-setup

# Or manually:
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Verfügbare Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Django App | http://localhost:8000 | - |
| pgAdmin | http://localhost:8080 | admin@runningdinner.dev / admin |
| MailHog | http://localhost:8025 | - |
| PostgreSQL | localhost:5433 | dev_user / dev_password |
| Redis | localhost:6380 | - |

## 🐳 DevContainer Features

- **Python 3.11** mit allen Dependencies
- **Docker-in-Docker** für Services
- **Port Forwarding** für alle Services
- **VS Code Extensions** vorkonfiguriert
- **Django Templates** Syntax Highlighting

## 🔄 Development Workflow

```bash
# 1. Start services
make dev-setup

# 2. Development server
python manage.py runserver 0.0.0.0:8000

# 3. Database operations
make migrate
make dbshell
make reset-db

# 4. Code quality
make lint
make format
make test
```

## 🐛 Troubleshooting

### Docker Issues
```bash
# Check Docker daemon
docker ps

# Restart Docker if needed
sudo service docker restart
```

### Service Issues
```bash
# Check service logs
make dev-logs

# Reset all services
make clean && make dev-setup
```

### Port Conflicts
```bash
# Check running services
docker ps
netstat -tulpn | grep :8000
```

## 🔗 Files

- `.devcontainer/devcontainer.json` - DevContainer configuration
- `.devcontainer/Dockerfile` - DevContainer image
- `.devcontainer/docker-compose.yml` - DevContainer services
- `docker-compose.dev.yml` - Development services (PostgreSQL, Redis, etc.)
