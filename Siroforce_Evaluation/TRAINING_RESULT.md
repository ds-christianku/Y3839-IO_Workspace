# Training Result - Gesamt Report
**Generiert:** 2026-08-20 16:39:01  
**Pipeline:** pipeline_02_classify.py (Multi-level classification)

---

## Executive Summary

| Metrik | Wert |
|--------|------|
| **Gesamt Training-Tickets** | 93 |
| **Kategorien validiert** | 3 |
| **Kategorisierung bestanden** | 70/86 (81.4%) |
| **Clearness bestanden** | 75/86 (87.2%) |
| **Durchschnittliche Erfolgsquote** | 84.3% |
| **Fehlerhafte Fälle** | 24 |
| **Status** | ⚠️ FEHLER |

---

## Detaillierte Ergebnisse pro Kategorie

### Connectivity/Recognition

**Test-Datei:** training_connectivity_tickets.json  
**Tickets:** 33

#### Kategorisierung
- ✓ Bestanden: **27/30** (90.0%)
- ✗ Fehlgeschlagen: **3**
- ⏭️ Übersprungen: 3
- **Status:** 🟡 Gut

#### Clearness-Klassifikation
- ✓ Bestanden: **26/30** (86.7%)
- ✗ Fehlgeschlagen: **4**
- ⏭️ Übersprungen: 3
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 7

---

### Software/Firmware/Driver

**Test-Datei:** training_software_firmware_driver_tickets.json  
**Tickets:** 30

#### Kategorisierung
- ✓ Bestanden: **22/26** (84.6%)
- ✗ Fehlgeschlagen: **4**
- ⏭️ Übersprungen: 4
- **Status:** 🔴 Verbesserungsbedarf

#### Clearness-Klassifikation
- ✓ Bestanden: **25/26** (96.2%)
- ✗ Fehlgeschlagen: **1**
- ⏭️ Übersprungen: 4
- **Status:** 🟡 Gut

**Fehlerhafte Fälle:** 5

---

### Installation/Setup/Upgrade

**Test-Datei:** training_installation_setup_upgrade_tickets.json  
**Tickets:** 30

#### Kategorisierung
- ✓ Bestanden: **21/30** (70.0%)
- ✗ Fehlgeschlagen: **9**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

#### Clearness-Klassifikation
- ✓ Bestanden: **24/30** (80.0%)
- ✗ Fehlgeschlagen: **6**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 12

---

## Zusammenfassung

| Kategorie | Tickets | Kategorie Pass | Clearness Pass | Status |
|-----------|---------|----------------|-----------------|--------|
| Connectivity/Recognition | 33 | 27/30 | 26/30 | 🟡 |
| Software/Firmware/Driver | 30 | 22/26 | 25/26 | ⚠️ |
| Installation/Setup/Upgrade | 30 | 21/30 | 24/30 | ⚠️ |

---

## Test-Ausführung

**Python-Kommando:**
```bash
python training/run_all_training.py
```

**Test-Dateien:**
- training/training_connectivity_tickets.json
- training/training_software_firmware_driver_tickets.json
- training/training_installation_setup_upgrade_tickets.json

**Konfiguration:**
- Kategorien: categories.json
- UTF-8 Encoding aktiviert
- Multilevel Klassifizierung aktiv

---

## Empfehlungen

⚠️ **24 Fehler gefunden**

Betroffene Kategorien sollten überprüft werden:
1. Identifiziere Kategorien mit Fehlern
2. Überprüfe die spezifischen fehlerhaften Tickets
3. Passe Regex-Muster in pipeline_02_classify.py an
4. Wiederhole die Tests nach jeder Änderung

---

**Report generiert:** 2026-08-20 16:39:01
