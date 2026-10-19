# Status Tracking System

## 📋 Overview

Dieses System trackt die Root Cause (RC) Status-Änderungen wochenweise und ermöglicht es, die Progression über die Zeit zu verfolgen.

## 📁 Dateien

### 1. `rc_status_history.json`
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
1. **Montag/Freitag**: Status-Eintrag der aktuellen Woche in `output/rc_status_history.json` aktualisieren oder über den HTML-Report bestätigen
2. **Report generieren**: `python run_pipeline.py`

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

1. **Datei öffnen**: `output/rc_status_history.json`
2. **Aktuelle Woche suchen und RC-Status ändern**:
   ```json
   "Loose sensor cable screws [CM]": "Completed" → "InProgress"
   ```
3. **Speichern**
4. **Report**: `python run_pipeline.py`

## 📈 Tracking-Features

✅ **Historische Snapshots** - Alle Wochen-Einträge gespeichert  
✅ **Status-Vergleich** - Änderungen zwischen Wochen sichtbar  
✅ **Trend-Analyse** - Sichtbar in `view_rc_status_history.py`  

## 🔔 Pro-Tipp

Die Snapshots können auch manuell für ältere Wochen hinzugefügt werden, um historische Daten zu simulieren. Einfach `rc_status_history.json` editieren und neue Einträge im korrekten Format hinzufügen.

---

**Letzte Aktualisierung**: 2026-09-02  
**System**: Symptom Root Cause Ticket Evaluation
