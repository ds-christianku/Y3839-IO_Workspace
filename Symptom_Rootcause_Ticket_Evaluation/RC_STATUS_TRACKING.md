# Status Tracking System

## 📋 Overview

Dieses System trackt die Root Cause (RC) Status-Änderungen wochenweise und ermöglicht es, die Progression über die Zeit zu verfolgen.

## 📁 Dateien

### 1. `rc_status.json`
- **Zweck**: Aktuelle Status der Root Causes (für diese Woche)
- **Format**: `{ "rc_status": { "RC_NAME": "Status", ... } }`
- **Status-Werte**: `OnHold`, `InAnalysis`, `InProgress`, `Completed`

### 2. `rc_status_history.json`
- **Zweck**: Wöchentliche Snapshots der RC-Status über die Zeit
- **Format**: Array von Weekly-Entries mit Status-Snapshots
- **Beispiel**:
  ```json
  {
    "tracking_history": [
      {
        "week": "2026-W35",
        "date": "2026-09-02",
        "rc_status": { ... }
      },
      ...
    ]
  }
  ```

## 🔧 Scripts

### `save_rc_status_snapshot.py`
Speichert den aktuellen Status aus `rc_status.json` als wöchentlichen Snapshot.

```bash
python save_rc_status_snapshot.py
```

**Output**: 
- Erstellt/aktualisiert den Eintrag für die aktuelle Woche (ISO-Week)
- Zeigt Zusammenfassung der Status-Verteilung

### `view_rc_status_history.py`
Zeigt die komplette Status-Historie mit Änderungen über die Zeit.

```bash
python view_rc_status_history.py
```

**Output**:
- Alle wöchentlichen Snapshots mit Status-Verteilung
- Vergleiche zwischen aufeinanderfolgenden Wochen
- Zusammenfassung des aktuellen Status

## 📅 Workflow

### Wöchentliche Aktualisierung:
1. **Montag/Freitag**: Alle notwendigen Status-Updates in `rc_status.json` durchführen
2. **Snapshot speichern**: `python save_rc_status_snapshot.py`
3. **Report generieren**: `python run_pipeline.py`

### Status überwachen:
```bash
python view_rc_status_history.py
```

## 📊 Status-Definitionen

| Status | Farbe | Bedeutung |
|--------|-------|-----------|
| **OnHold** | Grau (#9ca3af) | Nicht geplant / Warten auf Ressourcen |
| **InAnalysis** | Orange (#f59e0b) | Wird analysiert / Evaluiert |
| **InProgress** | Blau (#3b82f6) | Aktiv in Bearbeitung |
| **Completed** | Grün (#10b981) | Abgeschlossen |

## 🎯 Beispiel: Status ändern

1. **Datei öffnen**: `output/rc_status.json`
2. **RC suchen und Status ändern**:
   ```json
   "Loose sensor cable screws [CM]": "Completed" → "InProgress"
   ```
3. **Speichern**
4. **Snapshot**: `python save_rc_status_snapshot.py`
5. **Report**: `python run_pipeline.py`

## 📈 Tracking-Features

✅ **Automatische Wochenerkennung** - ISO-Week Format  
✅ **Historische Snapshots** - Alle Wochen-Einträge gespeichert  
✅ **Status-Vergleich** - Änderungen zwischen Wochen sichtbar  
✅ **Trend-Analyse** - Sichtbar in `view_rc_status_history.py`  

## 🔔 Pro-Tipp

Die Snapshots können auch manuell für ältere Wochen hinzugefügt werden, um historische Daten zu simulieren. Einfach `rc_status_history.json` editieren und neue Einträge im korrekten Format hinzufügen.

---

**Letzte Aktualisierung**: 2026-09-02  
**System**: Symptom Root Cause Ticket Evaluation
