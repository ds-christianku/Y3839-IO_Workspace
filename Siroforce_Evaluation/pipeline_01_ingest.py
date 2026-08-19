"""Stage 1: Liest CSV-Exporte + Excel-Lookup und speichert gemergte Rohdaten als JSON.

Ausgabe: output/tickets_raw.json
  Jedes Ticket enthaelt alle Felder aus CSV und Excel, aber noch keine Klassifizierung.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    from langdetect import detect as _ld_detect
    from langdetect import DetectorFactory as _LDF
    _LDF.seed = 0  # deterministic results
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


def detect_language(text: str) -> str:
    if not HAS_LANGDETECT or len(text) < 30:
        return ""
    try:
        return _ld_detect(text)
    except Exception:
        return ""


def normalize_text(text: str) -> str:
    """Normalisiert Text: whitespace bereinigen, strip."""
    if not text:
        return ""
    return " ".join(str(text).split()).lower()


# mutable so categories.json can override at runtime
_EU_HUB_CODES: set[str] = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}


def apply_region_config(cfg: dict) -> None:
    eu = cfg.get("region", {}).get("eu_hub_codes")
    if eu:
        _EU_HUB_CODES.clear()
        _EU_HUB_CODES.update(eu)


def classify_region(hub: str) -> str:
    code = hub.upper().strip()
    if code == "US":
        return "US"
    if code in _EU_HUB_CODES:
        return "EU"
    return "REST"


_EU_EMAIL_TLDS = {
    ".de", ".fr", ".it", ".es", ".nl", ".be", ".at", ".ch", ".pl", ".pt",
    ".se", ".dk", ".fi", ".no", ".cz", ".hu", ".ro", ".gr", ".sk", ".hr",
    ".bg", ".lt", ".lv", ".ee", ".si", ".lu", ".ie", ".uk", ".co.uk",
}


def region_from_email(email: str) -> str:
    e = email.lower().strip()
    return "EU" if any(e.endswith(tld) for tld in _EU_EMAIL_TLDS) else "REST"


_FW_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")
_FW_TO_RE = re.compile(r"\bto\b", re.IGNORECASE)
_FW_NOTES_PATTERNS = [
    re.compile(r"remote\s+fw(?:/fpga)?\s+version\s*:?\s*[_\s]*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"firmware\s*:\s*usb\s+v\.?\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"firmware\s*:\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
]


def normalize_firmware(raw: str) -> str:
    """Extrahiert die erste gueltige Major.Minor[.Patch]-Version aus einem Rohstring."""
    text = str(raw).strip()
    if not text:
        return ""
    if _FW_TO_RE.search(text):
        parts = _FW_TO_RE.split(text)
        text = parts[-1]
    m = _FW_VERSION_RE.search(text)
    return m.group(1) if m else ""


def extract_firmware_from_notes(notes: str) -> str:
    """Sucht Remote-Firmware in den Ticket-Notes (Fallback)."""
    for pattern in _FW_NOTES_PATTERNS:
        m = pattern.search(notes)
        if m:
            return m.group(1)
    return ""


def parse_created_at(value: str) -> str:
    """Parst created_at in ISO 8601 Format (YYYY-MM-DD)."""
    text = value.strip()
    if not text:
        return ""
    if "T" in text:
        text = text.split("T")[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def classify_record_type_group(record_type: str) -> str:
    """Klassifiziert Record Type in: COMPLAINT / INQUIRY / REST."""
    value = record_type.lower().strip()
    if "complaint" in value:
        return "COMPLAINT"
    if "inquiry" in value:
        return "INQUIRY"
    return "REST"


def load_rows_from_sheet(excel_path: Path, sheet_name: str) -> list[dict]:
    """Liest Excel-Sheet als Liste von Dicts."""
    if not HAS_OPENPYXL:
        print(f"openpyxl nicht verfuegbar – kann {excel_path} nicht lesen")
        return []

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    try:
        ws = wb[sheet_name]
    except KeyError:
        print(f"Sheet '{sheet_name}' nicht gefunden in {excel_path}")
        return []

    rows = []
    header = None
    for row in ws.iter_rows(values_only=True):
        if header is None:
            header = [str(cell or "").strip() for cell in row]
            continue
        rows.append({header[i]: row[i] for i in range(len(header))})
    return rows


def build_excel_lookup(excel_path: Path, sheet_name: str) -> dict[str, dict]:
    """Erstellt Lookup-Dict aus Excel."""
    excel_rows = load_rows_from_sheet(excel_path, sheet_name)
    lookup = {}
    for r in excel_rows:
        tx_num = r.get("Transaction Number", "")
        if tx_num:
            lookup[str(tx_num).strip()] = {
                "Record Type": r.get("Record Type", ""),
                "Region": r.get("Region", ""),
                "Support Hub (old)": r.get("Support Hub (old)", ""),
                "Category Level 2": r.get("Category Level 2", ""),
                "Category Level 3": r.get("Category Level 3", ""),
                "Category Level 4": r.get("Category Level 4", ""),
                "Firmware Version": normalize_firmware(str(r.get("Firmware Version", ""))),
            }
    return lookup


def ingest(
    csv_paths: list[Path],
    excel_path: Path | None,
    sheet_name: str = "IO 24Month",
) -> list[dict]:
    """Liest und mergt CSV + Excel. Gibt eine Liste von Roh-Ticket-Dicts zurueck."""
    excel_lookup: dict = {}
    if excel_path and excel_path.exists():
        print(f"Lese Excel-Lookup: {excel_path.name} (Sheet: {sheet_name})")
        excel_lookup = build_excel_lookup(excel_path, sheet_name)
        print(f"  Excel-Eintraege: {len(excel_lookup)}")
    else:
        print("Kein Excel-Lookup gefunden – Fallback auf CSV-Felder.")

    tickets: list[dict] = []
    seen: set[str] = set()
    excel_matched = 0

    for path in sorted(csv_paths):
        with open(path, encoding="latin-1", newline="") as f:
            for raw in csv.DictReader(f, delimiter=";"):
                ticket_id = normalize_text(raw.get("SAPId__c", ""))
                if not ticket_id or ticket_id in seen:
                    continue
                seen.add(ticket_id)

                description_text = normalize_text(raw.get("Subject", ""))
                notes_text = raw.get("Description", "").strip()
                email = raw.get("SiroforceEMailAddress__c", "")
                created_raw = raw.get("SAPCreatedDate__c", "")

                xl = excel_lookup.get(ticket_id)
                if xl:
                    record_type = xl["Record Type"]
                    region = xl["Region"] or classify_region(xl["Support Hub (old)"])
                    support_hub = xl["Support Hub (old)"]
                    cat2 = xl.get("Category Level 2", "")
                    cat3 = xl.get("Category Level 3", "")
                    cat4 = xl.get("Category Level 4", "")
                    firmware = xl.get("Firmware Version", "") or extract_firmware_from_notes(notes_text)
                    excel_matched += 1
                else:
                    record_type = normalize_text(raw.get("Origin", ""))
                    region = region_from_email(email)
                    support_hub = ""
                    cat2 = cat3 = cat4 = ""
                    firmware = extract_firmware_from_notes(notes_text)

                lang_src = notes_text if len(notes_text) > len(description_text) else description_text
                tickets.append({
                    "ticket_id": ticket_id,
                    "created_at": parse_created_at(created_raw),
                    "record_type_group": classify_record_type_group(record_type),
                    "region": region,
                    "language": detect_language(lang_src),
                    "category_level_2": cat2,
                    "category_level_3": cat3,
                    "category_level_4": cat4,
                    "firmware": firmware,
                    "support_hub": support_hub,
                    "description_text": description_text,
                    "notes_text": notes_text,
                    "excel_matched": xl is not None,
                })

    print(f"CSV-Dateien gelesen: {len(csv_paths)}")
    print(f"  Tickets gelesen: {len(tickets):,}")
    print(f"  Excel-Matches: {excel_matched:,}")

    return tickets


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Ingest CSV + Excel")
    parser.add_argument("--input-dir", type=Path, default=Path("input"),
                        help="Input directory mit CSV exports")
    parser.add_argument("--pattern", type=str, default="EXPORT_RH_*.csv",
                        help="CSV pattern zum Filtern (Glob)")
    parser.add_argument("--excel", type=Path,
                        help="Excel lookup file (optional)")
    parser.add_argument("--sheet", type=str, default="IO 24Month",
                        help="Sheet name in Excel")
    parser.add_argument("--output", type=Path, default=Path("output/tickets_raw.json"),
                        help="Output JSON file")

    args = parser.parse_args()

    input_dir = args.input_dir
    csv_paths = sorted(input_dir.glob(args.pattern))
    if not csv_paths:
        print(f"Keine CSV-Dateien gefunden in {input_dir} mit Pattern {args.pattern}")
        return

    print(f"CSV-Dateien gefunden: {len(csv_paths)}")
    for p in csv_paths:
        print(f"  {p.name}")

    tickets = ingest(csv_paths, args.excel, args.sheet)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2, ensure_ascii=False)

    print(f"Gespeichert: {args.output}")
    print(f"  Tickets: {len(tickets):,}")


if __name__ == "__main__":
    main()
