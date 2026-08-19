from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from collections import Counter
from pathlib import Path

from analyze_srq_qr_tickets_only_description import (
    build_report_data,
    classify_description,
    classify_record_type_group,
    load_rows_from_sheet,
    normalize_text,
    render_html,
)

# EU-Länderdomains als Fallback wenn Ticket nicht in Excel gefunden
_EU_EMAIL_TLDS = {
    ".de", ".fr", ".it", ".es", ".nl", ".be", ".at", ".ch", ".pl", ".pt",
    ".se", ".dk", ".fi", ".no", ".cz", ".hu", ".ro", ".gr", ".sk", ".hr",
    ".bg", ".lt", ".lv", ".ee", ".si", ".lu", ".ie", ".uk", ".co.uk",
}


def region_from_email(email: str) -> str:
    e = email.lower().strip()
    for tld in _EU_EMAIL_TLDS:
        if e.endswith(tld):
            return "EU"
    return "REST"


_FW_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")

# "1.4 TO 1.5.1" → nimm die letzte Version im String
_FW_TO_RE = re.compile(r"\bto\b", re.IGNORECASE)

# Reihenfolge: Remote FW/FPGA, dann USB-Anteil in "Firmware: USB v. X", dann generisch Firmware:
_FW_NOTES_PATTERNS = [
    re.compile(r"remote\s+fw(?:/fpga)?\s+version\s*:?\s*[_\s]*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"firmware\s*:\s*usb\s+v\.?\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"firmware\s*:\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
]


def normalize_firmware(raw: str) -> str:
    """Extrahiert die erste gültige Major.Minor[.Patch]-Version aus einem Rohstring."""
    text = str(raw).strip()
    if not text:
        return ""
    # "X TO Y" → letzten Wert nehmen
    if _FW_TO_RE.search(text):
        parts = _FW_TO_RE.split(text)
        text = parts[-1]
    m = _FW_VERSION_RE.search(text)
    return m.group(1) if m else ""


def extract_firmware_from_notes(notes: str) -> str:
    """Sucht Remote-Firmware in den Ticket-Notes (Fallback wenn Excel keinen Wert hat)."""
    for pattern in _FW_NOTES_PATTERNS:
        m = pattern.search(notes)
        if m:
            return m.group(1)
    return ""


def parse_created_at(value: str) -> str:
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


_ACTION_KEYWORDS = [
    "replace", "swap", "repair", "update", "install", "rma", "exchange",
    "tauschen", "austausch", "erneuert", "resolved", "fixed", "upgraded",
    "shipped", "sent", "new sensor", "new cable", "new remote", "new interface",
    "reseat", "reseated", "reconnect", "reconnected", "cleaned", "clean",
]

_STRONG_RESOLUTION_KEYWORDS = [
    "now stable", "now works", "works again", "issue resolved after", "resolved by",
    "now interface is stable", "now the sensor is recognized", "sensor is recognized",
    "functional (yes/no): yes", "functional test successful", "tests shot successful", "test shot successful",
    "problem solved", "wieder erkannt", "funktioniert", "behoben",
]

_SPECIFIC_CORRECTIVE_ACTION_KEYWORDS = [
    "reseat", "reseated", "reconnect", "reconnected", "replug", "unplug",
    "cleaned", "clean contact", "cleaned contact", "tighten", "tightened", "retighten",
]

_CONCRETE_CAUSE_OBSERVATION_KEYWORDS = [
    "loose", "wackelkontakt", "dirty contact", "contamination", "oxid", "oxidation",
    "corrosion", "cable was loose", "connector loose", "contacts were dirty",
]

_GENERIC_REPLACEMENT_ONLY_TERMS = [
    "part of the system must be replaced",
    "replacement part has been recommended",
    "please close complaint",
    "closing ticket",
]

# Explizite Ursachen-Indikatoren – Austausch allein reicht für Sensor/Remote nicht
_ROOT_CAUSE_KEYWORDS = [
    "caused by", "because of", "result of", "identified as",
    "confirmed as", "root cause", "failure was", "issue was", "problem was",
    "found to be", "determined to be", "turned out",
    "confirmed that", "point of failure",
    "worn elastomer", "damaged elastomer", "defective elastomer",
    "physical damage", "liquid damage", "water damage", "bodily fluid",
    "broken cable", "bent pin", "cracked", "damaged cable", "cable damage",
    "driver conflict", "software conflict", "incompatib",
    "firmware issue", "firmware problem", "firmware conflict", "firmware update resolved",
    "configuration error", "settings issue", "loose connector", "loose connection",
    "out of box failure", "defective from factory",
    "ursache", "verursacht", "aufgrund", "defekt durch", "beschädigt durch",
]

# Negative Indikatoren: Maßnahme hat nicht geholfen oder Ursache unbekannt
_NEGATIVE_INDICATORS = [
    "no help", "didn't fix", "did not fix", "didn't resolve", "did not resolve",
    "still not working", "still not connecting", "still not detecting",
    "no improvement", "without resolution", "unresolved",
    "suggest replacing", "recommend replacing", "recommended to replace", "recommend to replace",
    "advising to replace", "suggest sensor replacement", "unknown cause",
    "tried replacing", "tried swapping", "tried changing",
    "completely dead", "functional (yes/no): no",
]

# Generischer Platzhaltertext ohne echten Lösungsinhalt
_GENERIC_EXCLUSIONS = [
    "please refer to customer communication",
    "please refer to customer notes",
    "refer to customer notes",
    "see customer notes",
]

# Geräte die eine explizite Ursache erfordern (Austausch ohne Ursache = unklar)
_DEVICE_TERMS = ["sensor", "remote", "interface", "hub", "module", "sensorbox"]


_CONNECTIVITY_SENSOR_TERMS = re.compile(
    r"\bsensor\b|\bcapteur\b|\bsensore\b|xios xg|xios ae|schick sensor"
)
_CONNECTIVITY_INTERFACE_TERMS = re.compile(
    r"\binterface\b|\bremote\b|\bhub\b|\bmodule\b|usb\s*module|usb[-\s]*box|sensorbox|wandbox"
)
_CONNECTIVITY_NOT_DETECTED_TERMS = re.compile(
    r"not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|not in (?:device ?manager|devicemanager)"
    r"|nicht erkannt|nicht erkennbar|nicht im (?:device ?manager|ger[aä]temanager)|mancato riconoscimento|non viene riconosciuto"
)
_CONNECTIVITY_SENSOR_NOT_DETECTED_DIRECT = re.compile(
    r"(?:sensor|capteur|sensore).{0,45}(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|non viene riconosciuto|mancato riconoscimento)"
    r"|(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|non viene riconosciuto|mancato riconoscimento).{0,45}(?:sensor|capteur|sensore)"
)
_CONNECTIVITY_SENSOR_SUBJECT_NOT_DETECTED = re.compile(
    r"(?:sensor|capteur|sensore).{0,45}(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|non viene riconosciuto|mancato riconoscimento)"
)
_CONNECTIVITY_INTERFACE_NOT_DETECTED_DIRECT = re.compile(
    r"(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox).{0,45}(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento)"
    r"|(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento).{0,45}(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox)"
)
_CONNECTIVITY_CONNECTION_TERMS = re.compile(
    r"disconnect(?:ed|ing|ion)?|deconnexion|d[eé]connexion|intermittent|drops?|loose connection|no connection"
    r"|cannot connect|can['\s]*t connect|cant connect|will not connect|won['\s]*t connect|not connecting"
    r"|not reachable|not ready|device in use|si scollega|nicht anbind(?:bar|en)?"
)
_CONNECTIVITY_POWER_TERMS = re.compile(
    r"no power|not power(?:ing)?|no lights?|not turning on|dead (?:interface|remote|hub|module)|stays red"
)
_CONNECTIVITY_USB_TERMS = re.compile(
    r"usb port|different usb|another usb|swap usb|changed usb|usb communication|usb disconnect"
    r"|port issue|port problem|port not working|communication port"
    r"|replug|unplug|plug back|plugged back|reseat"
    r"|cable connection|bad cable|replace cable"
)
_CONNECTIVITY_USB_PRODUCT_CONTEXT = re.compile(
    r"usb interface|schick\s*\d+(?:\.\d+)?\s*usb\s*interface|\brma\b"
)

_CONN_SENSOR_PERSISTENT = "Sensor Detection Failure (Persistent)"
_CONN_SENSOR_INTERMITTENT = "Sensor Detection Failure (Intermittent)"
_CONN_INTERFACE_PERSISTENT = "Remote Detection Failure (Persistent)"
_CONN_INTERFACE_INTERMITTENT = "Remote Detection Failure (Intermittent)"
_CONN_AMBIGUOUS = "Ambiguous Detection Failure (Sensor/Remote)"
_CONN_UNKNOWN = "Unknown/Other"

_CONNECTIVITY_SIX_CATEGORY_MAP = {
    _CONN_SENSOR_PERSISTENT.lower(): _CONN_SENSOR_PERSISTENT,
    _CONN_SENSOR_INTERMITTENT.lower(): _CONN_SENSOR_INTERMITTENT,
    _CONN_INTERFACE_PERSISTENT.lower(): _CONN_INTERFACE_PERSISTENT,
    _CONN_INTERFACE_INTERMITTENT.lower(): _CONN_INTERFACE_INTERMITTENT,
    _CONN_AMBIGUOUS.lower(): _CONN_AMBIGUOUS,
    _CONN_UNKNOWN.lower(): _CONN_UNKNOWN,
    # Legacy labels
    "sensor not detected": _CONN_SENSOR_PERSISTENT,
    "interface/remote not detected": _CONN_INTERFACE_PERSISTENT,
    "connection unstable (intermittent)": _CONN_AMBIGUOUS,
    "connection failed (persistent)": _CONN_AMBIGUOUS,
    "usb/port communication issue": _CONN_AMBIGUOUS,
    "no sensor info / missing device data": _CONN_UNKNOWN,
    "not detected": _CONN_AMBIGUOUS,
    "connection issue": _CONN_UNKNOWN,
    "wifi issue": _CONN_AMBIGUOUS,
    "no sensor info": _CONN_UNKNOWN,
    "device not detected": _CONN_AMBIGUOUS,
    "device connection issue": _CONN_AMBIGUOUS,
    "sensor/interface not detected": _CONN_AMBIGUOUS,
    "sensor/interface connection issue": _CONN_AMBIGUOUS,
}
_CONNECTIVITY_INTERMITTENT_TERMS = re.compile(
    r"intermittent|disconnect(?:ed|ing|ion)?|drops?|off and on|sporadic|sometimes works|occasionally"
)
_CONNECTIVITY_IN_USE_TERMS = re.compile(
    r"device in use|sensor in use|another session|currently in use|locked by session"
)
_CONNECTIVITY_READY_TERMS = re.compile(
    r"not ready|does not get ready|sensor not ready|not going ready|ready mode"
)
_CONNECTIVITY_WEAK_CONNECTION_TERMS = re.compile(
    r"not working|does not work|doesn't work|will not work|won't work|unable to use"
)
_CONNECTIVITY_SENSOR_REPAIR_TERMS = re.compile(
    r"replace(?:d|ment)?\s+(?:the\s+)?sensor|sensor cable|sensorkabel|sensor sn|capteur"
)
_CONNECTIVITY_INTERFACE_REPAIR_TERMS = re.compile(
    r"replace(?:d|ment)?\s+(?:the\s+)?(?:interface|remote|hub|module)|"
    r"usb interface|interface\s*,?\s*rma|remote\s*,?\s*rma|module\s*,?\s*rma"
)
_CONNECTIVITY_SENSOR_DISCONNECT_TERMS = re.compile(
    r"(?:sensor|capteur|sensore).{0,60}(?:disconnect(?:ed|ing|ion)?|loose|reseat|not connect(?:ing)?|not pick(?:ed)?\s*up)"
    r"|(?:disconnect(?:ed|ing|ion)?|loose|reseat|not connect(?:ing)?).{0,60}(?:sensor|capteur|sensore)"
)
_CONNECTIVITY_INTERFACE_DISCONNECT_TERMS = re.compile(
    r"(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox).{0,60}(?:disconnect(?:ed|ing|ion)?|not connect(?:ing)?|drops?|lose connection)"
    r"|(?:disconnect(?:ed|ing|ion)?|not connect(?:ing)?|drops?|lose connection).{0,60}(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox)"
)
_HARDWARE_SENSOR_DEAD_TERMS = re.compile(
    r"\bdead sensor\b|we have a dead sensor|sensor is dead|defective sensor|sensor failure"
)
_HARDWARE_SENSOR_REPLACE_RECOMMEND_TERMS = re.compile(
    r"suggest replacing(?: the)? sensors?|recommend replacing(?: the)? sensors?|"
    r"replace sensors? out of warranty|new sensor rma|sensor rma"
)
_HARDWARE_SENSOR_TROUBLESHOOTED_TERMS = re.compile(
    r"replaced? cables? and elastomers?|replaced? (?:sensor\s+)?cable and elastomer|"
    r"cleaned contacts?|still having issue with connection|still no function|no help|"
    r"other sensors? in the same setup.*worked|took multiple shots.*not get triggered"
)
_HARDWARE_CABLE_CONFIRMED_TERMS = re.compile(
    r"sensor cable.*(?:point of failure|not functioning|defective|broken|damaged|didn['\ s]*t work|didnt? work)"
    r"|(?:point of failure|not functioning|defective|broken|damaged).*sensor cable"
    r"|replace(?:d|ment)?\s+sensor cable|sensor cable.*replac(?:ed|ement)?"
    r"|cable.*(?:was|is).*(?:the\s+)?point of failure"
    r"|confirmed.*cable.*(?:defect|fail|broken|damaged)"
    r"|sensor cable didn['\ s]*t work|kabel defekt|sensorkabel.*defekt|defektes sensorkabel"
)
# Cable was replaced/swapped but did NOT fix the issue → cable is not the root cause
_HARDWARE_CABLE_NOT_CAUSE_TERMS = re.compile(
    r"even if.*cable.*(?:was\s+)?(?:changed|replaced|swapped)"
    r"|even after.*cable.*(?:changed|replaced|swapped)"
    r"|cable.*(?:changed|replaced|swapped).*still\s+(?:undetected|not detect|not recogniz|not work|not connect)"
    r"|still\s+(?:undetected|not detect|not recogniz).*cable.*(?:changed|replaced|swapped)"
    r"|replaced?\s+sensor\s+cable.*suggest\s+replac.*sensor"
    r"|after.*(?:replac|swap|chang).*cable.*sensor.*still\s+(?:not|un)"
)
_SOFTWARE_CONNECTIVITY_ACTION_TERMS = re.compile(
    r"(?:install(?:ed|ing)?|reinstall(?:ed|ing)?|update(?:d|ing)?|upgrade(?:d|ing)?|rollback|"
    r"removed?|uninstall(?:ed|ing)?).{0,24}(?:driver|ioss|sidexis|plugin|twain|software|firmware)"
    r"|(?:driver|ioss|sidexis|plugin|twain|software|firmware).{0,24}(?:install(?:ed|ing)?|reinstall(?:ed|ing)?|update(?:d|ing)?|upgrade(?:d|ing)?|rollback|removed?|uninstall(?:ed|ing)?)"
)
_SOFTWARE_CONNECTIVITY_RESOLUTION_TERMS = re.compile(
    r"now able to acquire|can now acquire|test shot.*good|functional \(yes/no\): yes|issue resolved|resolved|"
    r"tested and functional"
)
_SOFTWARE_CONNECTIVITY_EXCLUDE_TERMS = re.compile(
    r"related to software or connectivity related within the office|"
    r"part of the system must be replaced|replacement part has been recommended"
)
_SOFTWARE_DRIVER_TERMS = re.compile(r"driver|ioss|twain|plugin")
_SOFTWARE_UPDATE_TERMS = re.compile(r"update|upgrade|version|sidexis|firmware")
_CONNECTIVITY_GENERIC_NOTE_TEMPLATES = re.compile(
    r"cannot be determined from the information provided|related to software or connectivity related within the office"
    r"|part of the system must be replaced|replacement part has been recommended"
    r"|require further troubleshooting at the dealer|please refer to customer communication"
    r"|diagnosed and determined to be related to computer software, system compatibility or system connectivity"
    r"|non-serious determination by chu eds"
)
_DESC_SENSOR_TERMS = re.compile(r"\bsensor\b|\bsensors\b|sensoren|schick sensor|capteur|sensore")
_DESC_INTERFACE_TERMS = re.compile(
    r"\binterface\b|\bremote\b|\bhub\b|\bmodule\b|\bbox\b|boitier|bo[iî]tier|usb\s*box"
)
_DESC_INTERMITTENT_TERMS = re.compile(
    r"intermittent|disconnect(?:ing)?|off and on|drops?|fallen aus|unstable|wackelkontakt|won['\s]*t stay connected"
)
_DESC_CONNECTIVITY_TERMS = re.compile(
    r"connect(?:ion|ing)?|not detected|not recognized|not seen|not found|no sensor attached|unit not accessible|wifi|usb|no lights"
    r"|nicht erkannt|nicht erreichbar|keine verbindung|wird nicht erkannt|verbindungsprobleme|deconnexion|d[eé]connexion"
)
_DESC_SENSOR_NOT_DETECTED = re.compile(
    r"sensor(?:en)?\s+.*(?:not detected|not recognized|not seen|not found|nicht erkannt|nicht erreichbar|not reading|not registering)"
    r"|sensor\s*(?:wird\s*)?nicht\s*(?:erkannt|angezeigt)|sensor\s+not\s+registering"
)
_DESC_INTERFACE_NOT_DETECTED = re.compile(
    r"interface\s+.*(?:not detected|not recognized|not connecting|not accessible|keine verbindung)"
    r"|remote\s+.*(?:not connecting|stays red|not staying connected)|box\s+.*(?:nicht erkannt|keine verbindung|not connecting)"
)
_DESC_SENSOR_REG_INFO_TERMS = re.compile(
    r"registering sensors?|sensor registration|sensor not registering|no sensor info|sensor no info|sensor info"
)
_DESC_INTERFACE_FAILURE_TERMS = re.compile(
    r"remote stays red|no lights|usb\s*3\.0|usb interface|usb package|usb kabel|replace (?:the )?(?:interface|remote|box|hub|module)"
)


def refine_connectivity_subcategory_with_notes(secondary: str, notes: str, description: str = "") -> str:
    secondary_norm = secondary.lower().strip()
    secondary_mapped = _CONNECTIVITY_SIX_CATEGORY_MAP.get(secondary_norm)
    notes_lc = (notes or "").lower().strip()
    desc_lc = (description or "").lower().strip()

    def _classify_device(sensor: bool, interface: bool, intermittent: bool) -> str:
        if sensor and interface:
            return _CONN_AMBIGUOUS
        if sensor:
            return _CONN_SENSOR_INTERMITTENT if intermittent else _CONN_SENSOR_PERSISTENT
        if interface:
            return _CONN_INTERFACE_INTERMITTENT if intermittent else _CONN_INTERFACE_PERSISTENT
        return _CONN_AMBIGUOUS

    def _infer_from_description() -> str | None:
        if not desc_lc:
            return None
        has_sensor_desc = bool(_DESC_SENSOR_TERMS.search(desc_lc))
        has_interface_desc = bool(_DESC_INTERFACE_TERMS.search(desc_lc))
        has_connectivity_desc = bool(_DESC_CONNECTIVITY_TERMS.search(desc_lc))
        has_sensor_not_detected_desc = bool(_DESC_SENSOR_NOT_DETECTED.search(desc_lc))
        has_interface_not_detected_desc = bool(_DESC_INTERFACE_NOT_DETECTED.search(desc_lc))
        has_sensor_reg_info_desc = bool(_DESC_SENSOR_REG_INFO_TERMS.search(desc_lc))
        has_intermittent_desc = bool(_DESC_INTERMITTENT_TERMS.search(desc_lc))

        if has_sensor_reg_info_desc:
            if has_interface_desc and not has_sensor_desc:
                return _CONN_INTERFACE_PERSISTENT
            return _CONN_SENSOR_PERSISTENT

        if has_sensor_not_detected_desc and has_interface_not_detected_desc:
            return _CONN_AMBIGUOUS
        if has_sensor_not_detected_desc:
            return _CONN_SENSOR_INTERMITTENT if has_intermittent_desc else _CONN_SENSOR_PERSISTENT
        if has_interface_not_detected_desc:
            return _CONN_INTERFACE_INTERMITTENT if has_intermittent_desc else _CONN_INTERFACE_PERSISTENT

        if not has_connectivity_desc:
            return None
        return _classify_device(has_sensor_desc, has_interface_desc, has_intermittent_desc)

    if len(notes_lc) < 20:
        inferred = _infer_from_description()
        return inferred or secondary_mapped or _CONN_UNKNOWN

    has_sensor = bool(_CONNECTIVITY_SENSOR_TERMS.search(notes_lc))
    has_interface = bool(_CONNECTIVITY_INTERFACE_TERMS.search(notes_lc))
    has_not_detected = bool(_CONNECTIVITY_NOT_DETECTED_TERMS.search(notes_lc))
    has_connection = bool(_CONNECTIVITY_CONNECTION_TERMS.search(notes_lc))
    has_intermittent = bool(_CONNECTIVITY_INTERMITTENT_TERMS.search(notes_lc))
    has_weak_connection = bool(_CONNECTIVITY_WEAK_CONNECTION_TERMS.search(notes_lc))
    has_sensor_not_detected_direct = bool(_CONNECTIVITY_SENSOR_NOT_DETECTED_DIRECT.search(notes_lc))
    has_interface_not_detected_direct = bool(_CONNECTIVITY_INTERFACE_NOT_DETECTED_DIRECT.search(notes_lc))
    has_generic_template = bool(_CONNECTIVITY_GENERIC_NOTE_TEMPLATES.search(notes_lc))
    has_wifi = bool(re.search(r"\bwifi\b|wi-?fi", notes_lc))

    # Direct proximity signals override generic template short-circuit
    if has_sensor_not_detected_direct and has_interface_not_detected_direct:
        return _CONN_AMBIGUOUS
    if has_sensor_not_detected_direct:
        return _CONN_SENSOR_INTERMITTENT if has_intermittent else _CONN_SENSOR_PERSISTENT
    if has_interface_not_detected_direct:
        return _CONN_INTERFACE_INTERMITTENT if has_intermittent else _CONN_INTERFACE_PERSISTENT

    if has_generic_template:
        inferred = _infer_from_description()
        if inferred:
            return inferred

    usb_signal = bool(_CONNECTIVITY_USB_TERMS.search(notes_lc))
    usb_product_context = bool(_CONNECTIVITY_USB_PRODUCT_CONTEXT.search(notes_lc))
    has_usb_issue = usb_signal and not usb_product_context

    if has_wifi:
        return _CONN_AMBIGUOUS

    if has_not_detected:
        return _classify_device(has_sensor, has_interface, has_intermittent)

    if has_connection or has_usb_issue or has_weak_connection:
        sensor_direct = bool(_CONNECTIVITY_SENSOR_DISCONNECT_TERMS.search(notes_lc))
        iface_direct = bool(_CONNECTIVITY_INTERFACE_DISCONNECT_TERMS.search(notes_lc))
        if sensor_direct and not iface_direct:
            return _CONN_SENSOR_INTERMITTENT if has_intermittent else _CONN_SENSOR_PERSISTENT
        if iface_direct and not sensor_direct:
            return _CONN_INTERFACE_INTERMITTENT if has_intermittent else _CONN_INTERFACE_PERSISTENT
        return _classify_device(has_sensor, has_interface, has_intermittent)

    inferred = _infer_from_description()
    return inferred or secondary_mapped or _CONN_UNKNOWN


def refine_hardware_cable_with_notes(primary: str, secondary: str, notes: str) -> tuple[str, str]:
    if primary not in ("Connectivity/Recognition", "Hardware Defect/Physical Damage"):
        return primary, secondary
    notes_lc = (notes or "").lower().strip()
    if len(notes_lc) < 20:
        return primary, secondary
    if _HARDWARE_CABLE_CONFIRMED_TERMS.search(notes_lc):
        if not _HARDWARE_CABLE_NOT_CAUSE_TERMS.search(notes_lc):
            return "Hardware Defect/Physical Damage", "Cable Issue"
    return primary, secondary


def refine_hardware_sensor_with_notes(primary: str, secondary: str, notes: str) -> tuple[str, str]:
    if primary != "Connectivity/Recognition":
        return primary, secondary
    notes_lc = (notes or "").lower().strip()
    if len(notes_lc) < 10:
        return primary, secondary
    if not _HARDWARE_SENSOR_DEAD_TERMS.search(notes_lc):
        return primary, secondary
    # Weak signals ("sensor failure", "defective sensor") require absence of generic boilerplate
    if not re.search(r"\bdead sensor\b|sensor is dead|we have a dead sensor", notes_lc):
        if _CONNECTIVITY_GENERIC_NOTE_TEMPLATES.search(notes_lc):
            return primary, secondary
    return "Hardware Defect/Physical Damage", "Sensor Failure"


def refine_software_with_notes(primary: str, secondary: str, notes: str) -> tuple[str, str]:
    if primary != "Connectivity/Recognition":
        return primary, secondary
    notes_lc = (notes or "").lower().strip()
    if len(notes_lc) < 30:
        return primary, secondary
    if _SOFTWARE_CONNECTIVITY_EXCLUDE_TERMS.search(notes_lc):
        return primary, secondary
    has_software_action = bool(_SOFTWARE_CONNECTIVITY_ACTION_TERMS.search(notes_lc))
    if not has_software_action:
        return primary, secondary
    has_hardware_signal = bool(
        _HARDWARE_SENSOR_DEAD_TERMS.search(notes_lc)
        or _HARDWARE_SENSOR_REPLACE_RECOMMEND_TERMS.search(notes_lc)
        or _HARDWARE_SENSOR_TROUBLESHOOTED_TERMS.search(notes_lc)
    )
    if has_hardware_signal:
        return primary, secondary
    if _SOFTWARE_DRIVER_TERMS.search(notes_lc):
        return "Software/Firmware/Driver", "Driver"
    if _SOFTWARE_UPDATE_TERMS.search(notes_lc):
        return "Software/Firmware/Driver", "Update/Version"
    has_resolution = bool(_SOFTWARE_CONNECTIVITY_RESOLUTION_TERMS.search(notes_lc))
    if has_resolution:
        return "Software/Firmware/Driver", "Software"
    return primary, secondary


def refine_subcategory_with_notes(primary: str, secondary: str, notes: str, description: str = "") -> tuple[str, str]:
    primary, secondary = refine_hardware_cable_with_notes(primary, secondary, notes)
    if primary == "Hardware Defect/Physical Damage":
        return primary, secondary
    primary, secondary = refine_hardware_sensor_with_notes(primary, secondary, notes)
    if primary == "Hardware Defect/Physical Damage":
        return primary, secondary
    primary, secondary = refine_software_with_notes(primary, secondary, notes)
    if primary != "Connectivity/Recognition":
        return primary, secondary
    return primary, refine_connectivity_subcategory_with_notes(secondary, notes, description=description)


def classify_clarity(notes: str) -> str:
    """Bewertet ob ein Ticket eine klare Problemursache und Lösung dokumentiert."""
    if not notes or len(notes) < 50:
        return "unclear"
    low = notes.lower()
    has_problem = "problem description" in low
    has_solution = "solution description" in low
    if not has_problem or not has_solution:
        return "unclear"
    import re as _re
    sol_idx = low.rfind("solution description")
    sol_text = notes[sol_idx + len("solution description"):].strip()
    sol_text_clean = _re.sub(r"\d{2}[./]\d{2}[./]\d{4}.*?\n", "", sol_text).strip()
    sol_low = sol_text_clean.lower()
    if any(excl in sol_low for excl in _GENERIC_EXCLUSIONS):
        return "unclear"
    if len(sol_text_clean) < 25:
        return "unclear"
    involves_device = bool(re.search(
        r"\b(?:" + "|".join(re.escape(t) for t in _DEVICE_TERMS) + r")\b", low
    ))
    # "remote" in IT/form context (PDATA Remote, remote access) is not a hardware device
    if involves_device and not re.search(r"\bsensor\b|\binterface\b|\bhub\b|\bmodule\b|\bsensorbox\b", low):
        if not re.search(
            r"\bremote\b.{0,60}(?:not detect|not connect|not recogniz|disconnect|drops?|issue|problem|failure|defect|replaced|repaired|rma|swap)",
            low,
        ):
            involves_device = False
    has_root_cause = any(kw in low for kw in _ROOT_CAUSE_KEYWORDS)
    has_negative = any(kw in sol_low for kw in _NEGATIVE_INDICATORS)
    has_action = any(kw in low for kw in _ACTION_KEYWORDS)
    has_strong_resolution = any(kw in sol_low for kw in _STRONG_RESOLUTION_KEYWORDS)
    has_specific_corrective_action = any(kw in low for kw in _SPECIFIC_CORRECTIVE_ACTION_KEYWORDS)
    has_concrete_cause_observation = any(kw in low for kw in _CONCRETE_CAUSE_OBSERVATION_KEYWORDS)
    has_generic_replacement_only = any(kw in low for kw in _GENERIC_REPLACEMENT_ONLY_TERMS)
    if involves_device:
        # Negative Indikatoren überschreiben Root-Cause-Treffer
        if has_negative:
            return "unclear"
        # Für Sensor/Remote: dokumentierte Ursache ODER konkrete technische Maßnahme + klares Erfolgssignal.
        if has_root_cause:
            return "clear"
        if has_specific_corrective_action and (has_strong_resolution or has_concrete_cause_observation):
            return "clear"
        if has_concrete_cause_observation and has_strong_resolution:
            return "clear"
        if has_generic_replacement_only and not has_root_cause:
            return "unclear"
        return "unclear"
    # Für andere Tickets (Software, Installation, Info) genügt eine konkrete Maßnahme
    return "clear" if ((has_action or has_strong_resolution) and not has_negative) else "unclear"


def build_excel_lookup(excel_path: Path, sheet_name: str) -> dict[str, dict]:
    """Erstellt ein Lookup-Dict {transaction_number: {record_type, region, support_hub, cat3, cat4}} aus Excel."""
    excel_rows = load_rows_from_sheet(excel_path, sheet_name)
    return {
        r["Transaction Number"]: {
            "Record Type": r["Record Type"],
            "Region": r["Region"],
            "Support Hub (old)": r["Support Hub (old)"],
            "Category Level 2": r.get("Category Level 2", ""),
            "Category Level 3": r.get("Category Level 3", ""),
            "Category Level 4": r.get("Category Level 4", ""),
            "Firmware Version": normalize_firmware(str(r.get("Firmware Version", ""))),
        }
        for r in excel_rows
        if r.get("Transaction Number")
    }


def write_notes_refinement_stats_csv(stats: dict[str, object], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    total_rows = int(stats["total_rows"])
    refined_total = int(stats["refined_total"])
    by_primary: Counter[str] = stats["by_primary"]  # type: ignore[assignment]
    transitions: Counter[str] = stats["transitions"]  # type: ignore[assignment]

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["section", "name", "count", "share_percent"])
        writer.writerow([
            "summary",
            "notes_refinement_total",
            refined_total,
            f"{((refined_total / total_rows) * 100) if total_rows else 0.0:.2f}",
        ])
        writer.writerow(["summary", "total_rows", total_rows, "100.00"])

        for primary, count in by_primary.most_common():
            writer.writerow([
                "primary_category",
                primary,
                count,
                f"{((count / refined_total) * 100) if refined_total else 0.0:.2f}",
            ])

        for transition, count in transitions.most_common():
            writer.writerow([
                "subcategory_transition",
                transition,
                count,
                f"{((count / refined_total) * 100) if refined_total else 0.0:.2f}",
            ])


def load_rows_from_csv_files(csv_paths: list[Path], excel_lookup: dict) -> tuple[list[dict], dict[str, object]]:
    rows: list[dict] = []
    seen: set[str] = set()
    matched = 0
    notes_refined_total = 0
    notes_refined_by_primary: Counter[str] = Counter()
    notes_refined_transitions: Counter[str] = Counter()

    for path in sorted(csv_paths):
        with open(path, encoding="latin-1", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for raw in reader:
                tn = normalize_text(raw.get("SAPId__c", ""))
                if not tn or tn in seen:
                    continue
                seen.add(tn)

                description = normalize_text(raw.get("Subject", ""))
                notes = raw.get("Description", "").strip()
                email = raw.get("SiroforceEMailAddress__c", "")

                # Aus Excel anreichern falls vorhanden
                xl = excel_lookup.get(tn)
                if xl:
                    record_type = xl["Record Type"]
                    region = xl["Region"]
                    support_hub = xl["Support Hub (old)"]
                    cat2 = xl.get("Category Level 2", "")
                    cat3 = xl.get("Category Level 3", "")
                    cat4 = xl.get("Category Level 4", "")
                    firmware = xl.get("Firmware Version", "") or extract_firmware_from_notes(notes)
                    matched += 1
                else:
                    record_type = normalize_text(raw.get("Origin", ""))
                    region = region_from_email(email)
                    support_hub = ""
                    cat2 = ""
                    cat3 = ""
                    cat4 = ""
                    firmware = extract_firmware_from_notes(notes)

                desc_primary, desc_secondary = classify_description(description, cat4=cat4)
                base_primary, base_secondary = desc_primary, desc_secondary
                desc_primary, desc_secondary = refine_subcategory_with_notes(
                    desc_primary,
                    desc_secondary,
                    notes,
                    description=description,
                )
                if desc_secondary != base_secondary or desc_primary != base_primary:
                    notes_refined_total += 1
                    notes_refined_by_primary[base_primary] += 1
                    notes_refined_transitions[f"{base_secondary} -> {desc_secondary}"] += 1
                clarity = classify_clarity(notes)

                rows.append({
                    "Transaction Number": tn,
                    "CreatedAt": parse_created_at(raw.get("SAPCreatedDate__c", "")),
                    "Record Type": record_type,
                    "RecordTypeGroup": classify_record_type_group(record_type),
                    "Category Level 2": cat2,
                    "Category Level 3": cat3,
                    "Category Level 4": cat4,
                    "Firmware Version": firmware,
                    "Description": description,
                    "Description Primary": desc_primary,
                    "Description Secondary": desc_secondary,
                    "Support Hub (old)": support_hub,
                    "Tickets": 1,
                    "Region": region,
                    "Notes": notes,
                    "Clarity": clarity,
                })

    print(f"Tickets mit Excel-Anreicherung: {matched} / {len(rows)}")
    print(f"Notes-Refinement: {notes_refined_total} / {len(rows)} Tickets mit Subkategorie-Änderung")
    if notes_refined_total:
        print("Top Refined Primary-Kategorien:")
        for primary, count in notes_refined_by_primary.most_common(5):
            share = (count / notes_refined_total) * 100
            print(f"  - {primary}: {count} ({share:.1f}%)")

        print("Top Subkategorie-Übergänge:")
        for transition, count in notes_refined_transitions.most_common(8):
            share = (count / notes_refined_total) * 100
            print(f"  - {transition}: {count} ({share:.1f}%)")

    stats = {
        "total_rows": len(rows),
        "refined_total": notes_refined_total,
        "by_primary": notes_refined_by_primary,
        "transitions": notes_refined_transitions,
    }
    return rows, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auswertung aus EXPORT_RH_*.csv Dateien erstellen und als HTML speichern.",
    )
    parser.add_argument(
        "--input-dir",
        default="../02_Input_Data_To_AI",
        help="Ordner mit den EXPORT_RH_*.csv Dateien.",
    )
    parser.add_argument(
        "--pattern",
        default="EXPORT_RH_*.csv",
        help="Glob-Muster für die CSV-Dateien.",
    )
    parser.add_argument(
        "--excel",
        default="../02_Input_Data_To_AI/20260731_IO_Imaging_SFTickets.xlsx",
        help="Excel-Datei für Record Type und Region Anreicherung.",
    )
    parser.add_argument(
        "--sheet",
        default="IO 24Month",
        help="Worksheet-Name in der Excel-Datei.",
    )
    parser.add_argument(
        "--output",
        default="Ticket_Report_CSV.html",
        help="Pfad zur Ausgabe-HTML.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    csv_files = sorted(input_dir.glob(args.pattern))
    if not csv_files:
        raise FileNotFoundError(f"Keine CSV-Dateien gefunden in: {input_dir / args.pattern}")

    print(f"Gefundene CSV-Dateien: {len(csv_files)}")
    for f in csv_files:
        print(f"  {f.name}")

    excel_path = Path(args.excel)
    if excel_path.exists():
        print(f"\nLade Excel-Lookup: {excel_path.name} (Sheet: {args.sheet})")
        excel_lookup = build_excel_lookup(excel_path, args.sheet)
        print(f"Excel-Einträge geladen: {len(excel_lookup)}")
    else:
        print(f"\nExcel-Datei nicht gefunden, nutze Fallback: {excel_path}")
        excel_lookup = {}

    print()
    rows, stats = load_rows_from_csv_files(csv_files, excel_lookup)

    source_label = f"{csv_files[0].name} … {csv_files[-1].name} ({len(csv_files)} Dateien)"
    report_data = build_report_data(
        rows,
        file_name=source_label,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    report_html = render_html(report_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_html, encoding="utf-8")

    print(f"\nReport erstellt: {output_path.resolve()}")
    print(f"Datensätze verarbeitet: {report_data['summaries']['ALL']['rows']}")
    print(f"Ticket Summe: {report_data['summaries']['ALL']['tickets']}")


if __name__ == "__main__":
    main()
