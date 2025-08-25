# 🏃‍♂️ Running Dinner Django App

Eine moderne Django-basierte Webapp zur Organisation von Running Dinner Events mit Docker-Support und VS Code DevContainer.

## 🚀 Quick Start

### Option 1: VS Code DevContainer (Empfohlen)

1. **Voraussetzungen:**
   - [VS Code](https://code.visualstudio.com/)
   - [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - [Dev Containers Extension](vscode:extension/ms-vscode-remote.remote-containers)

2. **Projekt starten:**
   ```bash
   git clone <repository>
   cd RunningDinner
   code .
   ```

3. **In VS Code:**
   - `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
   - Warten bis Container aufgebaut ist
   - Automatisch werden alle Dependencies installiert

4. **Services verfügbar:**
   - **Django App**: http://localhost:8000
   - **Admin**: http://localhost:8000/admin (admin@runningdinner.de)
   - **MailHog**: http://localhost:8025
   - **pgAdmin**: http://localhost:8080

### Option 2: Docker Compose

```bash
# Development Environment
make setup              # Einmaliges Setup
make dev-up            # Starte Services
make logs              # Logs anzeigen
make shell             # Django Shell

# Production Environment  
make prod-up           # Starte Production Setup
```

## 🏗️ Projekt-Struktur

```
RunningDinner/
├── .devcontainer/          # VS Code DevContainer Konfiguration
├── .vscode/               # VS Code Einstellungen
├── accounts/              # Benutzer- und Team-Management
├── events/                # Event-Management
├── optimization/          # Algorithmus für Optimierung
├── navigation/            # Navigationshilfen
├── nginx/                 # Nginx Konfiguration
├── scripts/               # Deployment Scripts
├── static/                # Statische Dateien
├── media/                 # Upload-Verzeichnis
└── running_dinner_app/    # Django Hauptprojekt
```

## 🎯 Features

### ✅ Bereits implementiert:
- **Benutzer-Management** mit erweiterten Profilen
- **Team-Management** mit Einladungssystem
- **Event-Management** mit Status-Tracking
- **Admin-Interface** mit umfassenden Features
- **Docker & DevContainer** Setup
- **PostgreSQL & Redis** Integration
- **Nginx** Reverse Proxy mit Security Features

### 🚧 In Entwicklung:
- Optimierungsalgorithmus für Running Dinner Routen
- REST API Endpoints
- Frontend UI (React/Vue.js)
- Navigationshilfen und Live-Event Features
- GDPR-konforme Datenschutzfeatures

## 💻 Development

### VS Code DevContainer Commands:

```bash
# Django Management
python manage.py runserver     # Server starten
python manage.py migrate       # Migrations ausführen
python manage.py test          # Tests ausführen
python manage.py shell         # Django Shell

# Code Quality
black .                        # Code formatieren
flake8 .                      # Linting
isort .                       # Imports sortieren
```

### Verfügbare Make Commands:

```bash
make help                 # Alle verfügbaren Commands
make dev-up              # Development Environment starten
make prod-up             # Production Environment starten
make test                # Tests ausführen
make migrate             # Migrations ausführen
make shell               # Django Shell
make clean               # Alles zurücksetzen
```

## 🔧 Konfiguration

### Environment Variables:

Kopieren Sie `env_example.txt` zu `.env` und passen Sie die Werte an:

```bash
cp env_example.txt .env
```

### Database Setup:

```bash
# In DevContainer oder Docker
python manage.py migrate
python manage.py createsuperuser
```

## 🔍 Testing

```bash
# Alle Tests
python manage.py test

# Mit Coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

## 📦 Deployment

### Production mit Docker:

```bash
# Production Build
docker-compose build

# Production Start
docker-compose up -d

# Logs
docker-compose logs -f
```

### Environment-spezifische Konfiguration:

- **Development**: `docker-compose.dev.yml`
- **Production**: `docker-compose.yml`
- **DevContainer**: `.devcontainer/docker-compose.devcontainer.yml`

## 🛠️ Troubleshooting

### DevContainer Issues:
```bash
# Container rebuilden
Ctrl+Shift+P → "Dev Containers: Rebuild Container"

# Volume reset
docker volume prune
```

### Database Issues:
```bash
# Reset Development Database
make dev-reset
```

### Permission Issues:
```bash
# Fix permissions
sudo chown -R $USER:$USER .
```

## 📚 Dokumentation

- **Django**: https://docs.djangoproject.com/
- **Docker**: https://docs.docker.com/
- **VS Code DevContainers**: https://code.visualstudio.com/docs/remote/containers

## 🤝 Contributing

1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/amazing-feature`)
3. Changes committen (`git commit -m 'feat: add amazing feature'`)
4. Branch pushen (`git push origin feature/amazing-feature`)
5. Pull Request erstellen

## 📄 License

Dieses Projekt steht unter der MIT License. Siehe `LICENSE` für Details.

---

**🎉 Happy Coding!** Entwickelt mit ❤️ für die Running Dinner Community.





