# Hardware Analysis Datenbank

## Voraussetzungen
- Node.js LTS (enthaelt npm)

## Start
1. Abhaengigkeiten installieren:
   npm install
2. Server starten:
   npm start
3. Browser oeffnen:
   http://localhost:3000

## Funktionen
- Umschalten zwischen Bereich Sensor und Remote
- Eingabebereich Anlieferzustand fuer beide Bereiche
- Sensor-spezifische Felder: Sensorgeneration und Brand
- Remote-spezifische Auswahl: USB2Remote oder USB3Remote
- Speicherung in SQLite Datenbankdatei `hardware_analysis.db`
- Beim Speichern werden Zeitstempel und Windows-Benutzername abgelegt

## Datenbank
Tabelle: intake_entries
- area
- serial_number
- firmware_on_delivery
- delivery_date
- ticket_number
- ticket_error_description
- sensor_generation
- sensor_brand
- remote_type
- created_at
- windows_username
