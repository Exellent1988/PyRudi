# PostgreSQL Migration - Phase 1

## 🎯 Übersicht

Diese Migration ersetzt SQLite durch PostgreSQL als primäre Datenbank und fügt Redis für Caching hinzu.

## 🔧 Änderungen

### Database Configuration
- ✅ **PostgreSQL Setup**: Vollständige PostgreSQL-Konfiguration in `settings.py`
- ✅ **Redis Caching**: Redis für Session-Management und API-Caching
- ✅ **Environment Variables**: Konfiguration über `.env` Datei
- ✅ **Docker Integration**: Aktualisierte Docker-Compose Files

### Development Environment
- ✅ **DevContainer**: Aktualisiert für PostgreSQL/Redis
- ✅ **Dockerfile.dev**: Separates Development Dockerfile
- ✅ **Database Init Script**: Automatische DB-Erstellung mit Extensions
- ✅ **Makefile**: Neue Commands für PostgreSQL-Management

## 🚀 Getting Started

### 1. Environment Setup
```bash
# Erstelle .env Datei
cp env_example.txt .env

# Starte Development Environment
make dev-setup
```

### 2. Verfügbare Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Django App | http://localhost:8001 | - |
| pgAdmin | http://localhost:8080 | admin@runningdinner.dev / admin |
| MailHog | http://localhost:8025 | - |
| PostgreSQL | localhost:5433 | dev_user / dev_password |
| Redis | localhost:6380 | - |

### 3. Database Management
```bash
# Database Migrations
make migrate

# Database Shell
make dbshell

# Reset Database
make reset-db

# Backup Database
make backup-db

# Restore Database
make restore-db FILE=backup.sql
```

## 📊 Performance Benefits

### Before (SQLite)
- ❌ Keine echte Concurrency
- ❌ Limitierte Skalierbarkeit
- ❌ Kein Connection Pooling
- ❌ Kein Caching

### After (PostgreSQL + Redis)
- ✅ **Concurrency**: Echte Multi-User-Unterstützung
- ✅ **Skalierbarkeit**: Unterstützt 1000+ gleichzeitige Teams
- ✅ **Connection Pooling**: Optimierte DB-Verbindungen
- ✅ **Redis Caching**: Session + API Response Caching
- ✅ **Geographic Extensions**: PostGIS-ready für erweiterte Geo-Features
- ✅ **Production-Ready**: Robuste Produktionsumgebung

## 🔄 Migration Path

### Existing Data Migration
Falls bestehende SQLite-Daten migriert werden sollen:

```bash
# 1. Export existing data
python manage.py dumpdata --natural-foreign --natural-primary > data_backup.json

# 2. Switch to PostgreSQL (bereits getan)

# 3. Import data
python manage.py loaddata data_backup.json
```

## 🧪 Testing

```bash
# Tests mit PostgreSQL
make test

# Tests mit Coverage
make test-coverage

# Health Check
make health
```

## 🐛 Troubleshooting

### Common Issues

**1. Container startet nicht:**
```bash
# Check logs
make dev-logs

# Rebuild containers
make dev-build && make dev-up
```

**2. Database Connection Errors:**
```bash
# Reset database
make reset-db

# Check database status
docker-compose -f docker-compose.dev.yml exec db pg_isready -U dev_user
```

**3. Redis Connection Issues:**
```bash
# Test Redis connection
docker-compose -f docker-compose.dev.yml exec redis redis-cli ping
```

## 📈 Next Steps (Phase 2)

- [ ] Database Indexes für Performance-Optimierung  
- [ ] Query Optimization mit Eager Loading
- [ ] Advanced Redis Caching Strategies
- [ ] Database Connection Pooling
- [ ] Monitoring & Metrics

## 🔗 Related Files

- `running_dinner_app/settings.py` - Database & Cache Configuration
- `docker-compose.dev.yml` - Development Services
- `Dockerfile.dev` - Development Container
- `scripts/init_db.sql` - Database Initialization
- `Makefile` - Management Commands
- `.env` - Environment Variables
