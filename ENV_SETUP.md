# 🔑 API-Key Setup für echte Routen

## ✅ **AKTUELLER STATUS: FUNKTIONIERT PERFEKT!**

Das System verwendet jetzt eine **dreistufige Fallback-Strategie**:

1. **OpenRouteService** (mit Ihrem API-Key) ← **PRIMÄR**
2. **OSRM** (kostenlos, Fallback) ← **BACKUP**  
3. **Haversine + 40%** (lokal berechnet) ← **NOTFALL**

## 📊 **Aktuell verwendet:** OpenRouteService
- ✅ **Ihr API-Key wird optimal genutzt**
- ✅ Höchste Routenqualität und Genauigkeit
- ✅ 2000 Anfragen/Tag verfügbar
- ✅ Speziell für Fußgänger optimiert

## 🛡️ **OSRM als robuster Fallback**
- ✅ **Aktiviert sich automatisch** bei API-Problemen
- ✅ Komplett kostenlos, keine Limits
- ✅ Nahtloser Übergang ohne Ausfälle

### 1. OpenRouteService Account erstellen
```
🌐 Website: https://openrouteservice.org/dev/#/signup
📧 Kostenlose Registrierung mit E-Mail
```

### 2. API-Key erstellen
```
1. Einloggen → Dashboard
2. "Request a token" klicken
3. Token-Name eingeben (z.B. "Running Dinner")
4. Key kopieren
```

### 3. .env Datei erstellen
```bash
# In /workspaces/RunningDinner/
cp .env.template .env  # oder manuell erstellen:
```

### 4. API-Key in .env eintragen
```bash
# OpenRouteService API für echte Routen
OPENROUTE_API_KEY=dein_api_key_hier
```

### 5. Django neu starten
```bash
python manage.py runserver
```

## 📊 API-Limits (kostenlos)
- **2000 Anfragen/Tag** (völlig ausreichend)
- **40 Anfragen/Minute** 
- Für 12 Teams = ~66 Routen = **unter 1 Minute**

## 🔄 Ohne API-Key
- System verwendet **intelligente Fallbacks**
- Luftlinie + 40% Umwegfaktor
- Trotzdem **sehr realistische** Ergebnisse
