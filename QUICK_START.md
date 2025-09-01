# 🚀 Quick Start Guide

## Option 1: Sofort starten (SQLite)

```bash
# Ein-Kommando-Setup:
python run_local.py
# ↳ Bei der Frage "Use SQLite fallback?" → 'y' eingeben

# Server ist verfügbar unter:
# http://localhost:8000
```

## Option 2: DevContainer (Einfach)

1. **DevContainer neu laden** (Ctrl+Shift+P):
   ```
   Dev Containers: Rebuild Container
   ```

2. **Development Server starten**:
   ```bash
   python run_local.py
   # ↳ 'y' für SQLite fallback
   ```

## Option 3: Manual Setup

```bash
# 1. Dependencies installieren
pip install -r requirements.txt

# 2. SQLite Database setup
export USE_SQLITE=True
python manage.py migrate

# 3. Superuser erstellen (optional)
python manage.py createsuperuser

# 4. Development server starten
python manage.py runserver 0.0.0.0:8000
```

## ✅ Verfügbare URLs

| Service | URL | Notes |
|---------|-----|-------|
| 🎯 **Main App** | http://localhost:8000 | Running Dinner App |
| 👑 **Admin** | http://localhost:8000/admin | Django Admin |
| 📊 **Dashboard** | http://localhost:8000/accounts/dashboard | User Dashboard |
| 📅 **Events** | http://localhost:8000/events | Event Management |

## 🔑 Test Login-Daten

**WICHTIG: Login erfolgt mit E-Mail-Adresse, nicht Username!**

| Rolle | E-Mail | Passwort | Berechtigung |
|-------|--------|----------|--------------|
| **Admin** | `admin@runningdinner.de` | `testpass123` | Superuser (alles) |
| **Organizer** | `organizer@test.com` | `organizer123` | Event-Verwaltung |
| **User** | `user@test.com` | `user123` | Team-Teilnahme |

## 🎉 Next Steps

1. **Login** mit Demo-Accounts (siehe README.md)
2. **Event erstellen** über Admin-Interface  
3. **Teams registrieren** und testen
4. **Optimierung starten** für Running Dinner Routen

## 📈 Upgrade zu PostgreSQL

Wenn du später PostgreSQL nutzen möchtest:

```bash
# 1. PostgreSQL installieren/starten
# 2. Environment Variable setzen
export USE_SQLITE=False

# 3. Database konfigurieren
python manage.py migrate

# 4. Development server starten
python run_local.py
```

## 🐛 Troubleshooting

**Server startet nicht:**
```bash
# Check dependencies
pip install -r requirements.txt

# Reset database
rm db.sqlite3
python manage.py migrate
```

**Port bereits belegt:**
```bash
# Use different port
python manage.py runserver 0.0.0.0:8001
```

**DevContainer Issues:**
```bash
# Rebuild container
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```
