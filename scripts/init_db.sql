-- Running Dinner Database Initialization Script

-- Erstelle Datenbanken für verschiedene Umgebungen
CREATE DATABASE running_dinner_dev;
CREATE DATABASE running_dinner_test;

-- Erstelle User für Development
CREATE USER dev_user WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE running_dinner_dev TO dev_user;
GRANT ALL PRIVILEGES ON DATABASE running_dinner_test TO dev_user;

-- Erstelle Extensions für geografische Funktionen (falls benötigt)
\c running_dinner_dev;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\c running_dinner_test;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Zurück zur Hauptdatenbank
\c running_dinner;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
