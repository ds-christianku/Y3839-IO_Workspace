# Kalibrierungs-Pipeline

Diese Pipeline verarbeitet den HyperRAM-Dump und extrahiert daraus die Kalibrierungsdaten, entpackt sie und interpretiert die Struktur.

## Ablauf

### 1. 01_extract_calibration_blob.py
Extrahiert den relevanten Kalibrierungsbereich aus dem Rohdump.

- Pflichtparameter 1: Pfad zur HyperRAM-Bin-Datei
- Pflichtparameter 2: Size-Preset, derzeit nur size1 erlaubt
- Offset: 16.777.216 Bytes
- Beispielgröße für size1: 1.867.728 Bytes = 1336 x 699 x 2
- Ausgabe: CalibrationBlob_from_HyperRAM.bin

Beispiel:

```bash
python 01_extract_calibration_blob.py HyperRam_60kV_IT70ms_ET50ms.bin size1
```

Wenn size0 oder size2 verwendet wird, wird ein Fehler ausgelöst, da nur size1 für den aktuellen Kalibrierungsblock gültig ist.

```bash
Usage: python 01_extract_calibration_blob.py <hyperram_dump.bin> <size1>
```

### 2. 02_unpack_calibration_blob.py
Entpackt den extrahierten Blob und schreibt den gepackten sowie den entpackten Datenstrom als Textdateien. Aus dem 16-Bit-Datenstrom wird zusaetzlich eine Binaerdatei erzeugt.

- Eingabe: CalibrationBlob_from_HyperRAM.bin
- Ausgabe: CalibrationBlob_from_HyperRAM_12bits.txt
- Ausgabe: CalibrationBlob_from_HyperRAM_16bit.txt
- Ausgabe: CalibrationBlob_from_HyperRAM_16bit.bin

Beispiel:

```bash
python 02_unpack_calibration_blob.py
```

### 3. 03_interpret_calibration_blob.py
Parst die 16-Bit-Daten, dekodiert den Header und erzeugt eine verständliche Interpretation der Kalibrierungsdaten.

- Eingabe: CalibrationBlob_from_HyperRAM_16bit.txt
- Ausgabe: CalibrationBlob_from_HyperRAM_interpretation.md

Beispiel:

```bash
python 03_interpret_calibration_blob.py
```

## Lauf der kompletten Pipeline

Der HyperRAM-Dump-Pfad und der Size-Preset sind Pflichtparameter. Für den aktuellen Datensatz ist nur size1 zulässig.

```bash
python run_pipeline.py HyperRam_60kV_IT70ms_ET50ms.bin size1
```

Wenn size0 oder size2 verwendet wird, wird ein Fehler ausgelöst.

```bash
Usage: python run_pipeline.py <hyperram_dump.bin> <size1>
```

## Ergebnis

Die Pipeline liefert folgende Dateien:

- CalibrationBlob_from_HyperRAM.bin
- CalibrationBlob_from_HyperRAM_12bits.txt
- CalibrationBlob_from_HyperRAM_16bit.txt
- CalibrationBlob_from_HyperRAM_16bit.bin
- CalibrationBlob_from_HyperRAM_interpretation.md

## Zweck der Pipeline

Die Pipeline trennt den Prozess in logische Schritte auf:

1. Kalibrierungsdaten aus dem großen HyperRAM-Dump extrahieren
2. Die komprimierte Speicherstruktur wiederherstellen
3. Die Daten als echte Kalibrierungsstruktur interpretieren

Damit bleibt der Ablauf nachvollziehbar und jede Phase kann einzeln geprüft und debuggt werden.
