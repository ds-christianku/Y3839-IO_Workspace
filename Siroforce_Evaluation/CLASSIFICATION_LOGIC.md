# Klassifizierungslogik – IO-Sensor Ticket-Analyse

## Überblick Pipeline-Architektur

```
CSV-Dateien (EXPORT_RH_*.csv)    Excel-Lookup (.xlsx)
          │                              │
          └──────────┬───────────────────┘
                     ▼
          ┌─────────────────────┐
          │  Stage 1: Ingest    │  pipeline_01_ingest.py
          │  CSV + Excel → JSON │
          └────────┬────────────┘
                   │  output/tickets_raw.json
                   ▼
          ┌─────────────────────────────────────┐
          │  Stage 2: Classify                  │  pipeline_02_classify.py
          │  Description + Notes → Kategorien   │
          │  Konfiguration: categories.json      │
          └────────┬────────────────────────────┘
                   │  output/tickets_classified.json
                   ▼
          ┌─────────────────────┐
          │  Stage 3: Render    │  pipeline_03_render.py
          │  JSON → HTML-Report │
          └─────────────────────┘
```

---

## Stage 1: Ingest

**Eingabe:** `EXPORT_RH_*.csv` + `20260731_IO_Imaging_SFTickets.xlsx`  
**Ausgabe:** `output/tickets_raw.json`

Jedes Ticket enthält:

| Feld | Quelle |
|------|--------|
| `ticket_id` | CSV: `SAPId__c` |
| `created_at` | CSV: `SAPCreatedDate__c` |
| `description_text` | CSV: `Subject` (normalisiert) |
| `notes_text` | CSV: `Description` (Ticket-Notes) |
| `record_type` | Excel (bevorzugt) / CSV: `Origin` |
| `region` | Excel (bevorzugt) / E-Mail-Domain-Fallback |
| `cat2/3/4` | Excel: Category Level 2/3/4 |
| `firmware` | Excel / Extraktion aus Notes |

---

## Stage 2: Klassifizierung

**Eingabe:** `output/tickets_raw.json` + `categories.json`  
**Ausgabe:** `output/tickets_classified.json`

Die Klassifizierung erfolgt in **zwei Schritten**:

### Schritt 2a: Description-Klassifizierung

Anhand des **Ticket-Betreffs** (Subject-Feld) wird eine erste Kategorie und Subkategorie vergeben.
Die Prüfung erfolgt in Prioritätsreihenfolge (erste Regel die greift, gewinnt):

#### Primärkategorien und ihre Regeln

| Primärkategorie | Typische Description-Muster |
|-----------------|----------------------------|
| `Spare Parts/RMA/Logistics` | `spare part`, `rma`, `return`, `sensor replacement`, `pn request` |
| `Connectivity/Recognition` | Interface/Sensor + Verbindungsproblem; nicht erkannte Geräte |
| `Hardware Defect/Physical Damage` | Defektes Interface/Sensor; Kabel-/Connector-Defekte |
| `Software/Firmware/Driver` | `sidexis`, `ioss`, `driver`, `firmware`, `update` |
| `Installation/Setup/Upgrade` | `install`, `setup`, `upgrade`, `new workstation` |
| `Imaging/Acquisition/Exposure` | Bildaufnahme-Probleme, Bildqualität |
| `Warranty/Part Number/Commercial` | `warranty`, `part number`, `guarantee` |
| `Info/Inquiry/How-to` | Rückrufe, Anfragen, allgemeine Fragen |
| `Unknown/Other` | Kein Muster trifft zu |

#### Connectivity-Subkategorien (Description-basiert)

Wenn die Beschreibung auf Connectivity hindeutet, wird zwischen 6 Subkategorien unterschieden:

| Subkategorie | Kriterium |
|--------------|-----------|
| `Sensor Detection Failure (Persistent)` | Sensor explizit + nicht erkannt / nicht verbindbar |
| `Sensor Detection Failure (Intermittent)` | Sensor + Abbrüche / intermittierend |
| `Remote Detection Failure (Persistent)` | Interface/Remote/Hub + nicht erkannt |
| `Remote Detection Failure (Intermittent)` | Interface/Remote/Hub + Abbrüche |
| `Ambiguous Detection Failure (Sensor/Remote)` | Beide Gerätetypen oder unklar |
| `Unknown/Other` | Kein Gerätebezug erkennbar |

---

### Schritt 2b: Notes-Refinement

Die Ticket-Notes werden in **4 Stufen** geprüft. Jede Stufe kann die Kategorie überschreiben:

```
Notes
  │
  ├─ 1. Kabeldefekt?          → Hardware Defect/Physical Damage → Cable Issue
  │      (sensor cable confirmed as point of failure)
  │
  ├─ 2. Defekter Sensor?      → Hardware Defect/Physical Damage → Sensor Failure
  │      (dead sensor, sensor is dead, defective sensor)
  │
  ├─ 3. Software-Lösung?      → Software/Firmware/Driver → Driver/Update/Software
  │      (reinstall/update + driver/firmware, ohne Hardware-Signal)
  │
  └─ 4. Connectivity-Subkat.  → Verfeinerung der Connectivity-Subkategorie
         (sensor vs. remote, persistent vs. intermittent)
```

#### Stufe 1: Kabeldefekt (Hardware Defect → Cable Issue)

Wird aktiviert wenn Notes eines der folgenden enthalten **UND** kein Negativ-Signal (Kabel war's nicht):

| Signal | Beispiel |
|--------|---------|
| `sensor cable ... point of failure` | "sensor cable was the point of failure" |
| `replace sensor cable` | "Replace sensor cable" |
| `cable is/was the point of failure` | "confirmed that the cable is the point of failure" |
| `confirmed ... cable ... defect/fail/broken` | "confirmed cable defective" |
| `kabel defekt` / `sensorkabel.*defekt` | Deutsch |

**Kabel ist NICHT die Ursache** (Ausschluss) wenn Notes enthalten:
- "even if the cable was changed" → Kabeltausch ohne Erfolg
- "cable replaced but sensor still..." → Kabel ok, Problem bleibt
- "replaced sensor cable suggest replacing sensor" → Sensor ist das eigentliche Problem

#### Stufe 2: Defekter Sensor (Hardware Defect → Sensor Failure)

| Signal | Stärke |
|--------|--------|
| `dead sensor` / `we have a dead sensor` / `sensor is dead` | Stark – überstimmt auch Boilerplate |
| `defective sensor` / `sensor failure` | Schwach – nur wenn kein Generic-Boilerplate |

Generic-Boilerplate-Text (wie "a part of the system must be replaced") verhindert Reklassifizierung bei schwachen Signalen.

#### Stufe 3: Software-Lösung (Software/Firmware/Driver)

Wird aktiviert wenn:
1. Ticket ist `Connectivity/Recognition` (Ausgangsbasis)
2. Notes zeigen eine Software-Aktion: `install/reinstall/update/upgrade + driver/ioss/sidexis/plugin/twain/software/firmware`
3. **Kein** Hardware-Signal: kein toter Sensor, keine Sensor-Austausch-Empfehlung
4. **Kein** Ausschluss-Boilerplate: nicht "related to software or connectivity within the office"

Dann wird nach folgendem klassifiziert:
- `Driver` wenn: `driver`, `ioss`, `twain`, `plugin` in Notes
- `Update/Version` wenn: `update`, `upgrade`, `version`, `sidexis`, `firmware` in Notes
- `Software` wenn: Lösung dokumentiert (`resolved`, `tested and functional`, etc.)

#### Stufe 4: Connectivity-Subkategorie verfeinern

Für Connectivity-Tickets werden die Notes auf Sensor vs. Interface und Persistent vs. Intermittent analysiert:

**Prioritätsreihenfolge:**

```
1. Direkter Proximity-Treffer (stärkster Beweis):
   - "sensor ... not detected" in der Nähe → Sensor Detection Failure
   - "interface/hub/remote ... not detected" in der Nähe → Remote Detection Failure

2. Generic-Template erkannt → Rückfall auf Description-Inferenz

3. Allgemeine Signale:
   - "not detected/recognized" + Sensor → Sensor Detection Failure (Persistent)
   - "not detected/recognized" + Interface → Remote Detection Failure (Persistent)
   - "disconnect/drops" + Sensor → Sensor Detection Failure (Intermittent)
   - WiFi → Ambiguous

4. Direkter Sensor-Disconnect-Treffer:
   - "reseat sensor", "loose screws on sensor", "sensor disconnecting" → Sensor
   - "interface disconnecting", "hub drops" → Remote

5. Fallback auf Description oder Unknown/Other
```

**Intermittent-Signale:** `intermittent`, `disconnect`, `drops`, `off and on`, `sporadic`, `occasionally`

---

## Stage 3: Clarity-Klassifizierung

Die **Clarity** bewertet ob ein Ticket eine klare Root Cause UND Lösung dokumentiert.

### Voraussetzungen (ansonsten sofort `unclear`)

1. Notes enthalten sowohl "Problem Description" als auch "Solution Description"
2. Solution-Text nach `Solution Description:` ist mindestens 25 Zeichen lang
3. Kein Generic-Ausschluss-Text im Solution-Bereich (z.B. "please refer to customer communication")

### Klassifizierung für Hardware-Tickets (involves_device = True)

Hardware-Tickets (`sensor`, `interface`, `hub`, `module`) benötigen explizite Evidenz:

| Bedingung | Ergebnis |
|-----------|---------|
| Negative im Solution-Text | `unclear` |
| Root-Cause-Keyword gefunden | `clear` |
| Spezifische Korrekturmaßnahme + Erfolgssignal oder Ursachenbeobachtung | `clear` |
| Nur generischer Austausch ohne Root Cause | `unclear` |
| Sonst | `unclear` |

### Klassifizierung für Software/Info-Tickets

| Bedingung | Ergebnis |
|-----------|---------|
| (Action ODER starkes Erfolgssignal) UND kein Negatives | `clear` |
| Sonst | `unclear` |

### Hinweis: "remote" als IT-Begriff vs. Hardware-Gerät

Das Wort "remote" kann entweder das Schick-Remote-Interface (Hardware) oder Remote-Access (IT) bedeuten. Als Hardware-Gerät wird es nur gewertet wenn es im Kontext von Hardware-Fehlern steht (`not detected`, `disconnect`, `issue`, `failure`, `replaced`, etc.). "PDATA Remote Location" oder "remoted into the PC" gilt nicht als Hardware-Gerät.

---

## categories.json – Konfigurierbare Keywords

Alle Keyword-Listen können in `categories.json` angepasst werden, ohne Python-Code zu ändern:

```json
{
  "clarity": {
    "root_cause_keywords": [...],       // Ursachen-Begriffe → clear
    "negative_indicators": [...],        // Misserfolgs-Signale → unclear
    "strong_resolution_keywords": [...], // Erfolgs-Signale → clear
    "action_keywords": [...],            // Handlungs-Begriffe (Software-Tickets)
    "specific_corrective_action_keywords": [...], // Technische Maßnahmen
    "concrete_cause_observation_keywords": [...], // Konkrete Ursachen-Beobachtungen
    "generic_replacement_only_terms": [...],       // Generischer Austausch ohne Ursache
    "generic_exclusions": [...],                   // Boilerplate-Ausschlüsse
    "hardware_device_terms": [...]                 // Welche Wörter = Hardware-Gerät
  }
}
```

**Wichtig:** Änderungen in `categories.json` werden beim nächsten `run_pipeline.py`-Aufruf (oder `--skip-ingest`) sofort wirksam.

---

## Verwendung

```powershell
# Vollständiger Durchlauf
python run_pipeline.py

# Nur neu klassifizieren (CSV bereits eingelesen)
python run_pipeline.py --skip-ingest

# Nur HTML neu rendern
python run_pipeline.py --skip-classify

# Einzelne Stages direkt aufrufen
python pipeline_01_ingest.py
python pipeline_02_classify.py
python pipeline_03_render.py
```
