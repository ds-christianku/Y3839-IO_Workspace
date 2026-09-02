# Training Result - Gesamt Report
**Generiert:** 2026-09-01 17:25:12  
**Pipeline:** pipeline_02_classify.py (Multi-level classification)

---

## Executive Summary

| Metrik | Wert |
|--------|------|
| **Gesamt Training-Tickets** | 173 |
| **Kategorien validiert** | 6 |
| **Kategorisierung bestanden** | 117/142 (82.4%) |
| **Clearness bestanden** | 141/166 (84.9%) |
| **Durchschnittliche Erfolgsquote** | 83.8% |
| **Fehlerhafte Fälle** | 45 |
| **Status** | ⚠️ FEHLER |

---

## Detaillierte Ergebnisse pro Kategorie

### Connectivity/Recognition

**Test-Datei:** training_connectivity_tickets.json  
**Tickets:** 33

#### Kategorisierung
- ✓ Bestanden: **25/30** (83.3%)
- ✗ Fehlgeschlagen: **5**
- ⏭️ Übersprungen: 3
- **Status:** 🔴 Verbesserungsbedarf

#### Clearness-Klassifikation
- ✓ Bestanden: **25/30** (83.3%)
- ✗ Fehlgeschlagen: **5**
- ⏭️ Übersprungen: 3
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 10

---

### Software/Firmware/Driver

**Test-Datei:** training_software_firmware_driver_tickets.json  
**Tickets:** 30

#### Kategorisierung
- ✓ Bestanden: **21/26** (80.8%)
- ✗ Fehlgeschlagen: **5**
- ⏭️ Übersprungen: 4
- **Status:** 🔴 Verbesserungsbedarf

#### Clearness-Klassifikation
- ✓ Bestanden: **19/26** (73.1%)
- ✗ Fehlgeschlagen: **7**
- ⏭️ Übersprungen: 4
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 11

---

### Installation/Setup/Upgrade

**Test-Datei:** training_installation_setup_upgrade_tickets.json  
**Tickets:** 30

#### Kategorisierung
- ✓ Bestanden: **15/30** (50.0%)
- ✗ Fehlgeschlagen: **15**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

#### Clearness-Klassifikation
- ✓ Bestanden: **26/30** (86.7%)
- ✗ Fehlgeschlagen: **4**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 15

---

### Imaging/Acquisition/Exposure

**Test-Datei:** Training_imaging_acquisition_exposure.json  
**Tickets:** 25

#### Kategorisierung
- ✓ Bestanden: **22/22** (100.0%)
- ✗ Fehlgeschlagen: **0**
- ⏭️ Übersprungen: 3
- **Status:** 🟢 Ausgezeichnet

#### Clearness-Klassifikation
- ✓ Bestanden: **19/25** (76.0%)
- ✗ Fehlgeschlagen: **6**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 6

---

### Spare Parts/RMA/Logistics

**Test-Datei:** Training_spareparts_rma_logistics.json  
**Tickets:** 15

#### Kategorisierung
- ✓ Bestanden: **14/14** (100.0%)
- ✗ Fehlgeschlagen: **0**
- ⏭️ Übersprungen: 1
- **Status:** 🟢 Ausgezeichnet

#### Clearness-Klassifikation
- ✓ Bestanden: **13/15** (86.7%)
- ✗ Fehlgeschlagen: **2**
- ⏭️ Übersprungen: 0
- **Status:** 🔴 Verbesserungsbedarf

**Fehlerhafte Fälle:** 2

---

### Hardware Defect/Physical Damage

**Test-Datei:** Training_hardwaredefect_physicaldamage.json  
**Tickets:** 40

#### Kategorisierung
- ✓ Bestanden: **20/20** (100.0%)
- ✗ Fehlgeschlagen: **0**
- ⏭️ Übersprungen: 20
- **Status:** 🟢 Ausgezeichnet

#### Clearness-Klassifikation
- ✓ Bestanden: **39/40** (97.5%)
- ✗ Fehlgeschlagen: **1**
- ⏭️ Übersprungen: 0
- **Status:** 🟡 Gut

**Fehlerhafte Fälle:** 1

---

## Zusammenfassung

| Kategorie | Tickets | Kategorie Pass | Clearness Pass | Status |
|-----------|---------|----------------|-----------------|--------|
| Connectivity/Recognition | 33 | 25/30 | 25/30 | ⚠️ |
| Software/Firmware/Driver | 30 | 21/26 | 19/26 | ⚠️ |
| Installation/Setup/Upgrade | 30 | 15/30 | 26/30 | ⚠️ |
| Imaging/Acquisition/Exposure | 25 | 22/22 | 19/25 | ⚠️ |
| Spare Parts/RMA/Logistics | 15 | 14/14 | 13/15 | 🟡 |
| Hardware Defect/Physical Damage | 40 | 20/20 | 39/40 | 🟡 |

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

⚠️ **45 Fehler gefunden**

Betroffene Kategorien sollten überprüft werden:
1. Identifiziere Kategorien mit Fehlern
2. Überprüfe die spezifischen fehlerhaften Tickets
3. Passe Regex-Muster in pipeline_02_classify.py an
4. Wiederhole die Tests nach jeder Änderung

---

**Report generiert:** 2026-09-01 17:25:12
