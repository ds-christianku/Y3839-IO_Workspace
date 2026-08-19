"""Stage 2: Klassifiziert Tickets aus tickets_raw.json anhand von Description-Text und Ticket-Notes.

Vollstaendig self-contained - importiert keine analyze_*.py Skripte.
Keyword-Listen werden aus categories.json geladen (ueberschreiben die Defaults).

Ausgabe: output/tickets_classified.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# ABSCHNITT 1: Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text == "#":
        return ""
    return re.sub(r"\s+", " ", text)


def classify_record_type_group(record_type: str) -> str:
    value = record_type.lower().strip()
    if "complaint" in value:
        return "COMPLAINT"
    if "inquiry" in value:
        return "INQUIRY"
    return "REST"


# ══════════════════════════════════════════════════════════════════════════════
# ABSCHNITT 2: Description-Klassifizierung (aus Ticket-Betreff)
# ══════════════════════════════════════════════════════════════════════════════

_DR_DEVICE = re.compile(r"\b(interface|remote|hub|dock|module|connector|sensorbox|wandbox)\b|usb.?box")
_DR_DEFECT = re.compile(
    r"no power|not power(?:ing)?|won['.\s]?t power|fails? to power|will not power|not lighting up"
    r"|invisible|unable to acquire|keine funktion"
)
_DR_HW_CATS = {"usb module issue", "connector issue"}


def classify_description(description: str, cat4: str = "") -> tuple[str, str]:
    text = normalize_text(description)
    value = text.lower()
    cat4_lc = cat4.lower().strip()
    if not value:
        return "Unknown/Other", "Unknown"

    if re.search(r"\bspare parts?\b|\bparts? request\b|\brma\b|\breturn\b|sensor replacement|pn request|replacement request", value):
        if re.search(r"ptc proc rma|\brma\b", value):
            return "Spare Parts/RMA/Logistics", "RMA Request"
        if "spare part" in value or "part request" in value or "pn request" in value:
            return "Spare Parts/RMA/Logistics", "Spare Part Request"
        if "sensor replacement" in value or "replacement request" in value:
            return "Spare Parts/RMA/Logistics", "Spare Part Request"
        return "Spare Parts/RMA/Logistics", "Logistics"

    _has_device = bool(_DR_DEVICE.search(value))
    _has_defect = bool(_DR_DEFECT.search(value))
    _has_conn = bool(re.search(
        r"not connect(?:ing)?|connection issue|won['\s]?t connect|will not connect"
        r"|not recogniz(?:ed|ing)?|not detect(?:ed)?|undetect(?:ed)?|not recognized|not recognizing"
        r"|intermittent connect|no connection",
        value,
    ))

    if _has_device and _has_conn and not _has_defect:
        _has_sensor_d = bool(re.search(r"\bsensor\b|\bsensors\b|sensoren|schick sensor|capteur|sensore", value))
        _has_iface_d = bool(re.search(r"\binterface\b|\bremote\b|\bhub\b|\bmodule\b|\bbox\b|usb\s*box", value))
        _has_interm_d = bool(re.search(r"intermittent|disconnect|drops?|off and on|unstable", value))
        if _has_sensor_d and _has_iface_d:
            return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"
        if _has_sensor_d:
            return "Connectivity/Recognition", "Sensor Detection Failure (Intermittent)" if _has_interm_d else "Sensor Detection Failure (Persistent)"
        if _has_iface_d:
            return "Connectivity/Recognition", "Remote Detection Failure (Intermittent)" if _has_interm_d else "Remote Detection Failure (Persistent)"
        return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"

    if _has_device and _has_defect:
        return "Hardware Defect/Physical Damage", "Remote Failure"
    if cat4_lc in _DR_HW_CATS and (_has_device or _has_defect):
        return "Hardware Defect/Physical Damage", "Remote Failure"

    if re.search(r"warranty|guarantee|part number|parts kit", value):
        if "warranty" in value:
            return "Warranty/Part Number/Commercial", "Warranty"
        if "part number" in value:
            return "Warranty/Part Number/Commercial", "Part Number"
        return "Warranty/Part Number/Commercial", "Commercial Inquiry"

    if re.search(r"install|installation|setup|upgrade|new workstation", value):
        if "driver" in value:
            return "Installation/Setup/Upgrade", "Driver Install"
        if "upgrade" in value:
            return "Installation/Setup/Upgrade", "Upgrade"
        return "Installation/Setup/Upgrade", "Install/Setup"
    if re.search(r"setting up (a )?new sensors?|new sensors?|new sensor", value):
        return "Installation/Setup/Upgrade", "Install/Setup"

    if re.search(r"documentation:|call back|callback|call dropped|on site: i/o user study", value):
        return "Info/Inquiry/How-to", "General Inquiry"
    if re.search(r"admin password|sensor supp+ort|frage zur anordung", value):
        return "Info/Inquiry/How-to", "General Inquiry"

    if re.search(r"sidexis 4|win(?:dows)? 11|24h2|25h2|device manager", value):
        return "Software/Firmware/Driver", "Update/Version"
    if re.search(r"sidexis|cdr dicom|cdrdicom|curve dental|curve capture|curve integration|patterson integration|ioss\s*3|s4sp", value):
        return "Software/Firmware/Driver", "Software"
    if re.search(r"server migration|other: extreme slowness after ioss insta|schick template issue|odbc error|schick integration|ioss.*curve", value):
        return "Software/Firmware/Driver", "Software"

    if re.search(r"xios xg kp nicht m[öo]glich|konstanzpr[üu]fung nicht m[öo]glich|abnahmepr[üu]fung nicht m[öo]glich|kein konstanz m[öo]gl|keine konstanzpr[üu]fung|keine abnahmepr[üu]fung", value):
        return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
    if re.search(r"no acquisizione|acquisizione non possibile|çekim alinamiyor|non [èe] possibile acquisire|gerg: sensore.*non acquisisce|mancato trasferimento immagine|plus d acquisition capteur|les clich[eé]s sont blancs|lastre bianche", value):
        return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
    if re.search(r"immagini non leggibili|sensor blurry|white screen", value):
        return "Imaging/Acquisition/Exposure", "Image Quality"
    if re.search(r"lignes? verticales?|gerg: qualit[aà] immagini|latence capteur|artefact issue", value):
        return "Imaging/Acquisition/Exposure", "Image Quality"
    if re.search(r"kp p[üu]rfk[öo]rper nicht richtig erkennbar|geht nicht in den bereit modus", value):
        return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
    if re.search(r"cannot capture|unable to capture|capture issue|not captured|no capture|can['\s]*t\s*take\s*imag(?:e|es|s)|can\s*not\s*take\s*imag(?:e|es|s)|unable to take\s*imag(?:e|es|s)|could not take\s*imag(?:e|es|s)|cannot take\s*imag(?:e|es|s)|cannot take\s*scans?|cant take\s*scans?|not able to capture|sensor not capturing|issues capturing", value):
        return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"

    if re.search(r"sensor registration|sensor not register|sensor not registering|sensor not seen|sensor not found|sensor not showing|not recongni|not recogniz|not reading|cannot be registered|not in system|not in devicemanger|not in device manager|sensor undetected|sensor not detected", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
    if re.search(r"unable to register sensor|sensor cannot be registered|registering sensors|sensor not in inventory|product not in dscrm|device currently in use|sensor in another session|sensor being used in another session|sensor not loading|sensor does not get ready|no sensor attached error|sensor nicht im devicemanger angezeigt|on site service: schick sensor not conne|sensor will not connect|sensor won[' \\s]*t connect|sensor cannot connect|sensor not connect(?:ing)?", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
    if re.search(r"nicht im device ?man(?:a)?ger|nicht in device ?man(?:a)?ger|nicht in devman|nicht in s4 angezeigt|gerät nicht angezeigt|nicht angezeigt|sensorbereitschaft nicht vorhanden|sensor nicht hinzuzuf[ü]gen|sensor lässt sich nicht einbinden|gerg: mancato riconoscimento|sensore non viene riconosciuto|sensore.*non si connet|sensor service dienst startet nicht|system blinkt im gerätemanager", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
    if re.search(r"sensor wird nicht erkannt|sensors? not detected by|sensor nicht erkannt", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"

    if re.search(r"pb communication entre capteur|pb deconnexion capteur|probleme de connexion capteur|d[eé]connexion capteur|plus de connexion|xios si scollega|il sensore non si connette|boîtier n allume pas|plus de connexion.alimentation", value):
        if re.search(r"boîtier|alimentation", value):
            return "Connectivity/Recognition", "Remote Detection Failure (Persistent)"
        return "Connectivity/Recognition", "Sensor Detection Failure (Intermittent)"

    if re.search(r"sensor in use(?:\s|$|\b)|device in use error|sensor not accessible|sensor not ready|sensor is not ready|sensor not going ready|sensor icon missing|ghosted devices", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"

    if re.search(r"dead interface|dead remote|dead hub|dead box|out of box failure", value):
        return "Hardware Defect/Physical Damage", "Physical Damage"
    if re.search(r"unit not accessible|interface issue|interface issues|interface module issue|hub issue|bad remote|no power|no lights|not powering|nicht erreichbar|no conecta", value):
        return "Connectivity/Recognition", "Remote Detection Failure (Persistent)"
    if re.search(r"interface not responding|interface power issue|interface not turning on|sensor remote problem|dead interface|dead remote|bad interface|power issue|box doesn\s*t work|issue with remote|remote stays red|remote stopped working|unable to use remote", value):
        return "Connectivity/Recognition", "Remote Detection Failure (Persistent)"
    if re.search(r"remote disconnect|remote disconenct|hub drops at times|off and on light", value):
        return "Connectivity/Recognition", "Remote Detection Failure (Intermittent)"
    if re.search(r"sensor communication issue|issue with ae interface", value):
        return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"

    if re.search(r"xios xg kabel|kabelgeb", value):
        return "Hardware Defect/Physical Damage", "Cable Issue"
    if re.search(r"kabel defekt|kabel l[öo]st sich|sensorkabel|xios kabel defekt|xios ae kabel", value):
        return "Hardware Defect/Physical Damage", "Cable Issue"

    if re.search(r"self.?trigger(?:ing)?|autofiring sensor|sensor auto.?fir(?:e|es|ing)|sensor autofiring", value):
        return "Hardware Defect/Physical Damage", "Sensor Failure"
    if re.search(r"hallo zusammen|call back request|escalation", value):
        return "Info/Inquiry/How-to", "General Inquiry"
    if _has_device and re.search(r"defective|dead|faulty|broken|loose|not working|no longer working", value):
        return "Hardware Defect/Physical Damage", "Physical Damage"

    if re.search(r"interface|remote|hub|module", value) and re.search(r"no power|not powering|not power|not accessible|not working|no lights", value):
        return "Connectivity/Recognition", "Remote Detection Failure (Persistent)"
    if re.search(r"interface|remote|hub|module", value) and re.search(r"intermittent", value):
        return "Connectivity/Recognition", "Remote Detection Failure (Intermittent)"

    if re.search(r"firmware|software|driver|version|update|app|crash|freeze|twain", value):
        if "firmware" in value:
            return "Software/Firmware/Driver", "Firmware"
        if "driver" in value or "twain" in value:
            return "Software/Firmware/Driver", "Driver"
        if "update" in value or "upgrade" in value:
            return "Software/Firmware/Driver", "Update/Version"
        return "Software/Firmware/Driver", "Software"

    if re.search(r"(?:bad|faulty|broken|damaged|defective|loose)\s+(?:sensor\s+)?cable|cable\s+(?:bad|faulty|broken|damaged|loose)", value):
        return "Hardware Defect/Physical Damage", "Cable Issue"
    if re.search(r"capteur hs|pb capteur|capteur d[eé]fectueux|panne capteur|bonjour le capteur ne fonctionne plus|capteur d[eé]faillant|sensore ko|sensore.*non funzionante|gerg: sensore difettoso|gerg: sensore ko|sensor defekt|sensor ohne funktion|selbstauslöser|selbstauslösung|defekter sensor|ausfall sensor|sensor aussetzer|gerät ohne funktion|sensor sin funci[oó]n|sensor averiado", value):
        return "Hardware Defect/Physical Damage", "Sensor Failure"
    if re.search(r"bad sensor|sensor not working|sensor is not working|sensor does not work|sensor doesn['\s]*t work|sensor won['\s]*t work|sensor will not work|sensor failure|sensor defect|sensor problem|sensor issue|sensor issues|issue with sensor|issues with sensor|issues with sensors|sensors not working|sensor troubleshooting|sensor stopped working|sensor stop working|sensor stops working|sensor not responding|sensor not functioning|sensor does not function|sensor not operational|sensor inoperative|sensor dead|dead sensor|sensor faulty|faulty sensor|sensor broken|sensor malfunction|sensor drops(?:\s|$)|sensor works intermittent|sensor works intermittently|sensor intermittent issues|sensor repair|xios xg sensor|xios xg not working|elite sensor|senor not working|hardware not working|unable to use sensor|not able to use the sensor|not able to use sensors|sensor was not functioning|xios xg supreme not working|schick issue|schick issues|schick troubleshooting|schick sensor issue|schick sensor issues|schick sensor troubleshooting|issues with schick sensor|schick sensor failed test|schick sensor not ready|sensors are not working|device not working|st[öo]rung xios|xios.*nicht mehr|sensor.*ohne funktion|keine funktion|unit has died|faulty out of the box|not working properly", value):
        return "Hardware Defect/Physical Damage", "Sensor Failure"

    if re.search(r"intermittent schick failure to fire|issues with scans", value):
        return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
    if re.search(r"intermittent operation|intermittent issues?|intermittent schick function|intermittent$", value):
        return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"

    if re.search(r"cable|connector|plug|button|housing|broken|damage|damaged|defect|elastomer|dead|defective|faulty|loose|not working|no longer working", value):
        if "cable" in value:
            return "Hardware Defect/Physical Damage", "Cable Issue"
        if "connector" in value or "plug" in value:
            return "Hardware Defect/Physical Damage", "Connector Issue"
        if re.search(r"defective sensor|broken sensor|defective schick|faulty sensor|sensor defective|dead sensor", value):
            return "Hardware Defect/Physical Damage", "Sensor Failure"
        return "Hardware Defect/Physical Damage", "Physical Damage"

    if re.search(r"stripped screws", value):
        return "Hardware Defect/Physical Damage", "Physical Damage"
    if re.search(r"free good replacement|repair kit request|varify a part", value):
        return "Spare Parts/RMA/Logistics", "Spare Part Request"

    if re.search(r"wifi|wi-fi|usb|bluetooth|ethernet|network|connect|connection|verbind|erkannt|detect|recogniz|not seen|not found|not showing|registration", value):
        if "wifi" in value or "wi-fi" in value:
            return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"
        if re.search(r"not detected|not recognized|nicht erkannt|nicht mehr erkannt|not seen|not found|not showing|registration", value):
            if re.search(r"interface|remote|hub|module", value):
                return "Connectivity/Recognition", "Remote Detection Failure (Persistent)"
            return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
        if "no sensor info" in value:
            return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
        return "Connectivity/Recognition", "Ambiguous Detection Failure (Sensor/Remote)"

    if re.search(r"x-?ray|xray|image|imaging|exposure|acquire|aufnahme|bild|artifact", value):
        if "quality" in value:
            return "Imaging/Acquisition/Exposure", "Image Quality"
        if re.search(r"blurry|grainy|grain|white image|light image|dark image|lines in image|scrambled|washed out|artifact|ligne|vertical lines|horizontale", value):
            return "Imaging/Acquisition/Exposure", "Image Quality"
        if re.search(r"cannot take|cant take|can['\s]*t take|can\s*not take|unable to take|could not take|unable to acquire|keine aufnahme|unable to capture|cannot capture|capture issue|take\s*imag(?:e|es|s)", value):
            return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
        if re.search(r"konstanzpr[üu]fung nicht m[öo]glich|abnahmepr[üu]fung nicht m[öo]glich|xios xg kp nicht m[öo]glich", value):
            return "Imaging/Acquisition/Exposure", "Cannot Acquire Image"
        if "exposure" in value:
            return "Imaging/Acquisition/Exposure", "Exposure Issue"
        return "Imaging/Acquisition/Exposure", "Imaging Issue"

    if re.search(r"no sensor info|sensor no info|sensor info not available", value):
        return "Connectivity/Recognition", "Sensor Detection Failure (Persistent)"
    if re.search(r"inquiry|question|support|help|info", value):
        return "Info/Inquiry/How-to", "General Inquiry"

    return "Unknown/Other", "Other"


# ══════════════════════════════════════════════════════════════════════════════
# ABSCHNITT 3: Connectivity Notes-Refinement Regex
# ══════════════════════════════════════════════════════════════════════════════

_CONN_SENSOR_PERSISTENT   = "Sensor Detection Failure (Persistent)"
_CONN_SENSOR_INTERMITTENT = "Sensor Detection Failure (Intermittent)"
_CONN_INTERFACE_PERSISTENT   = "Remote Detection Failure (Persistent)"
_CONN_INTERFACE_INTERMITTENT = "Remote Detection Failure (Intermittent)"
_CONN_AMBIGUOUS = "Ambiguous Detection Failure (Sensor/Remote)"
_CONN_UNKNOWN   = "Unknown/Other"

_CONNECTIVITY_SIX_CATEGORY_MAP = {
    _CONN_SENSOR_PERSISTENT.lower(): _CONN_SENSOR_PERSISTENT,
    _CONN_SENSOR_INTERMITTENT.lower(): _CONN_SENSOR_INTERMITTENT,
    _CONN_INTERFACE_PERSISTENT.lower(): _CONN_INTERFACE_PERSISTENT,
    _CONN_INTERFACE_INTERMITTENT.lower(): _CONN_INTERFACE_INTERMITTENT,
    _CONN_AMBIGUOUS.lower(): _CONN_AMBIGUOUS,
    _CONN_UNKNOWN.lower(): _CONN_UNKNOWN,
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

_C_SENSOR_TERMS = re.compile(r"\bsensor\b|\bcapteur\b|\bsensore\b|xios xg|xios ae|schick sensor")
_C_IFACE_TERMS  = re.compile(r"\binterface\b|\bremote\b|\bhub\b|\bmodule\b|usb\s*module|usb[-\s]*box|sensorbox|wandbox")
_C_NOT_DET      = re.compile(r"not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|not in (?:device ?manager|devicemanager)|nicht erkannt|nicht erkennbar|nicht im (?:device ?manager|ger[aä]temanager)|mancato riconoscimento|non viene riconosciuto")
_C_SENSOR_ND_DIR = re.compile(r"(?:sensor|capteur|sensore).{0,45}(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento)|(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento).{0,45}(?:sensor|capteur|sensore)")
_C_IFACE_ND_DIR  = re.compile(r"(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox).{0,45}(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento)|(?:not detect(?:ed)?|not recogniz(?:ed|ing)?|cannot be registered|nicht erkannt|nicht erkennbar|non viene riconosciuto|mancato riconoscimento).{0,45}(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox)")
_C_CONN_TERMS   = re.compile(r"disconnect(?:ed|ing|ion)?|deconnexion|d[eé]connexion|intermittent|drops?|loose connection|no connection|cannot connect|can['\s]*t connect|cant connect|will not connect|won['\s]*t connect|not connecting|not reachable|not ready|device in use|si scollega|nicht anbind(?:bar|en)?")
_C_USB_TERMS    = re.compile(r"usb port|different usb|another usb|swap usb|changed usb|usb communication|usb disconnect|port issue|port problem|port not working|communication port|replug|unplug|plug back|plugged back|reseat|cable connection|bad cable|replace cable")
_C_USB_PROD_CTX = re.compile(r"usb interface|schick\s*\d+(?:\.\d+)?\s*usb\s*interface|\brma\b")
_C_WEAK_CONN    = re.compile(r"not working|does not work|doesn't work|will not work|won't work|unable to use")
_C_INTERMIT     = re.compile(r"intermittent|disconnect(?:ed|ing|ion)?|drops?|off and on|sporadic|sometimes works|occasionally")
_C_GENERIC_TPL  = re.compile(r"cannot be determined from the information provided|related to software or connectivity related within the office|part of the system must be replaced|replacement part has been recommended|require further troubleshooting at the dealer|please refer to customer communication|diagnosed and determined to be related to computer software, system compatibility or system connectivity|non-serious determination by chu eds")
_C_SENSOR_DISC  = re.compile(r"(?:sensor|capteur|sensore).{0,60}(?:disconnect(?:ed|ing|ion)?|loose|reseat|not connect(?:ing)?|not pick(?:ed)?\s*up)|(?:disconnect(?:ed|ing|ion)?|loose|reseat|not connect(?:ing)?).{0,60}(?:sensor|capteur|sensore)")
_C_IFACE_DISC   = re.compile(r"(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox).{0,60}(?:disconnect(?:ed|ing|ion)?|not connect(?:ing)?|drops?|lose connection)|(?:disconnect(?:ed|ing|ion)?|not connect(?:ing)?|drops?|lose connection).{0,60}(?:interface|remote|hub|module|usb[-\s]*box|sensorbox|wandbox)")

_D_SENSOR_TERMS  = re.compile(r"\bsensor\b|\bsensors\b|sensoren|schick sensor|capteur|sensore")
_D_IFACE_TERMS   = re.compile(r"\binterface\b|\bremote\b|\bhub\b|\bmodule\b|\bbox\b|boitier|bo[iî]tier|usb\s*box")
_D_INTERMIT      = re.compile(r"intermittent|disconnect(?:ing)?|off and on|drops?|fallen aus|unstable|wackelkontakt|won['\s]*t stay connected")
_D_CONN_TERMS    = re.compile(r"connect(?:ion|ing)?|not detected|not recognized|not seen|not found|no sensor attached|unit not accessible|wifi|usb|no lights|nicht erkannt|nicht erreichbar|keine verbindung|wird nicht erkannt|verbindungsprobleme|deconnexion|d[eé]connexion")
_D_SENSOR_ND     = re.compile(r"sensor(?:en)?\s+.*(?:not detected|not recognized|not seen|not found|nicht erkannt|nicht erreichbar|not reading|not registering)|sensor\s*(?:wird\s*)?nicht\s*(?:erkannt|angezeigt)|sensor\s+not\s+registering")
_D_IFACE_ND      = re.compile(r"interface\s+.*(?:not detected|not recognized|not connecting|not accessible|keine verbindung)|remote\s+.*(?:not connecting|stays red|not staying connected)|box\s+.*(?:nicht erkannt|keine verbindung|not connecting)")
_D_SENSOR_REG    = re.compile(r"registering sensors?|sensor registration|sensor not registering|no sensor info|sensor no info|sensor info")


def _refine_connectivity(secondary: str, notes: str, description: str = "") -> str:
    secondary_mapped = _CONNECTIVITY_SIX_CATEGORY_MAP.get(secondary.lower().strip())
    notes_lc = (notes or "").lower().strip()
    desc_lc = (description or "").lower().strip()

    def _classify(sensor: bool, interface: bool, intermittent: bool) -> str:
        if sensor and interface:
            return _CONN_AMBIGUOUS
        if sensor:
            return _CONN_SENSOR_INTERMITTENT if intermittent else _CONN_SENSOR_PERSISTENT
        if interface:
            return _CONN_INTERFACE_INTERMITTENT if intermittent else _CONN_INTERFACE_PERSISTENT
        return _CONN_AMBIGUOUS

    def _infer_desc() -> str | None:
        if not desc_lc:
            return None
        hs = bool(_D_SENSOR_TERMS.search(desc_lc))
        hi = bool(_D_IFACE_TERMS.search(desc_lc))
        hc = bool(_D_CONN_TERMS.search(desc_lc))
        snd = bool(_D_SENSOR_ND.search(desc_lc))
        ind = bool(_D_IFACE_ND.search(desc_lc))
        reg = bool(_D_SENSOR_REG.search(desc_lc))
        intr = bool(_D_INTERMIT.search(desc_lc))
        if reg:
            return _CONN_INTERFACE_PERSISTENT if (hi and not hs) else _CONN_SENSOR_PERSISTENT
        if snd and ind:
            return _CONN_AMBIGUOUS
        if snd:
            return _CONN_SENSOR_INTERMITTENT if intr else _CONN_SENSOR_PERSISTENT
        if ind:
            return _CONN_INTERFACE_INTERMITTENT if intr else _CONN_INTERFACE_PERSISTENT
        if not hc:
            return None
        return _classify(hs, hi, intr)

    if len(notes_lc) < 20:
        return _infer_desc() or secondary_mapped or _CONN_UNKNOWN

    hs   = bool(_C_SENSOR_TERMS.search(notes_lc))
    hi   = bool(_C_IFACE_TERMS.search(notes_lc))
    hnd  = bool(_C_NOT_DET.search(notes_lc))
    hcon = bool(_C_CONN_TERMS.search(notes_lc))
    hint = bool(_C_INTERMIT.search(notes_lc))
    hwk  = bool(_C_WEAK_CONN.search(notes_lc))
    snd  = bool(_C_SENSOR_ND_DIR.search(notes_lc))
    ind  = bool(_C_IFACE_ND_DIR.search(notes_lc))
    htpl = bool(_C_GENERIC_TPL.search(notes_lc))
    hwifi = bool(re.search(r"\bwifi\b|wi-?fi", notes_lc))

    if snd and ind:
        return _CONN_AMBIGUOUS
    if snd:
        return _CONN_SENSOR_INTERMITTENT if hint else _CONN_SENSOR_PERSISTENT
    if ind:
        return _CONN_INTERFACE_INTERMITTENT if hint else _CONN_INTERFACE_PERSISTENT

    if htpl:
        inferred = _infer_desc()
        if inferred:
            return inferred

    usb = bool(_C_USB_TERMS.search(notes_lc)) and not bool(_C_USB_PROD_CTX.search(notes_lc))

    if hwifi:
        return _CONN_AMBIGUOUS
    if hnd:
        return _classify(hs, hi, hint)
    if hcon or usb or hwk:
        sd = bool(_C_SENSOR_DISC.search(notes_lc))
        id_ = bool(_C_IFACE_DISC.search(notes_lc))
        if sd and not id_:
            return _CONN_SENSOR_INTERMITTENT if hint else _CONN_SENSOR_PERSISTENT
        if id_ and not sd:
            return _CONN_INTERFACE_INTERMITTENT if hint else _CONN_INTERFACE_PERSISTENT
        return _classify(hs, hi, hint)

    return _infer_desc() or secondary_mapped or _CONN_UNKNOWN


# ══════════════════════════════════════════════════════════════════════════════
# ABSCHNITT 4: Hardware Cable / Sensor Erkennung
# ══════════════════════════════════════════════════════════════════════════════

_HW_SENSOR_DEAD   = re.compile(r"\bdead sensor\b|we have a dead sensor|sensor is dead|defective sensor|sensor failure")
_HW_CABLE_OK      = re.compile(r"sensor cable.*(?:point of failure|not functioning|defective|broken|damaged|didn[' \\s]*t work|didnt? work)|(?:point of failure|not functioning|defective|broken|damaged).*sensor cable|replace(?:d|ment)?\s+sensor cable|sensor cable.*replac(?:ed|ement)?|cable.*(?:was|is).*(?:the\s+)?point of failure|confirmed.*cable.*(?:defect|fail|broken|damaged)|sensor cable didn[' \\s]*t work|kabel defekt|sensorkabel.*defekt|defektes sensorkabel")
_HW_CABLE_NOT     = re.compile(r"even if.*cable.*(?:was\s+)?(?:changed|replaced|swapped)|even after.*cable.*(?:changed|replaced|swapped)|cable.*(?:changed|replaced|swapped).*still\s+(?:undetected|not detect|not recogniz|not work|not connect)|still\s+(?:undetected|not detect|not recogniz).*cable.*(?:changed|replaced|swapped)|replaced?\s+sensor\s+cable.*suggest\s+replac.*sensor|after.*(?:replac|swap|chang).*cable.*sensor.*still\s+(?:not|un)")
_HW_SENSOR_REPL   = re.compile(r"suggest replacing(?: the)? sensors?|recommend replacing(?: the)? sensors?|replace sensors? out of warranty|new sensor rma|sensor rma")
_HW_SENSOR_TRBL   = re.compile(r"replaced? cables? and elastomers?|replaced? (?:sensor\s+)?cable and elastomer|cleaned contacts?|still having issue with connection|still no function|no help|other sensors? in the same setup.*worked|took multiple shots.*not get triggered")
_SW_ACTION        = re.compile(r"(?:install(?:ed|ing)?|reinstall(?:ed|ing)?|update(?:d|ing)?|upgrade(?:d|ing)?|rollback|removed?|uninstall(?:ed|ing)?).{0,24}(?:driver|ioss|sidexis|plugin|twain|software|firmware)|(?:driver|ioss|sidexis|plugin|twain|software|firmware).{0,24}(?:install(?:ed|ing)?|reinstall(?:ed|ing)?|update(?:d|ing)?|upgrade(?:d|ing)?|rollback|removed?|uninstall(?:ed|ing)?)")
_SW_EXCLUDE       = re.compile(r"related to software or connectivity related within the office|part of the system must be replaced|replacement part has been recommended")
_SW_DRIVER        = re.compile(r"driver|ioss|twain|plugin")
_SW_UPDATE        = re.compile(r"update|upgrade|version|sidexis|firmware")
_SW_RESOLVED      = re.compile(r"now able to acquire|can now acquire|test shot.*good|functional \(yes/no\): yes|issue resolved|resolved|tested and functional")


def refine_subcategory_with_notes(primary: str, secondary: str, notes: str, description: str = "") -> tuple[str, str]:
    notes_lc = (notes or "").lower().strip()

    # 1) Kabeldefekt aus Notes
    if primary in ("Connectivity/Recognition", "Hardware Defect/Physical Damage") and len(notes_lc) >= 20:
        if _HW_CABLE_OK.search(notes_lc) and not _HW_CABLE_NOT.search(notes_lc):
            return "Hardware Defect/Physical Damage", "Cable Issue"

    if primary == "Hardware Defect/Physical Damage":
        return primary, secondary

    # 2) Defekter Sensor aus Notes
    if primary == "Connectivity/Recognition" and len(notes_lc) >= 10:
        if _HW_SENSOR_DEAD.search(notes_lc):
            if not re.search(r"\bdead sensor\b|sensor is dead|we have a dead sensor", notes_lc):
                if _C_GENERIC_TPL.search(notes_lc):
                    pass
                else:
                    return "Hardware Defect/Physical Damage", "Sensor Failure"
            else:
                return "Hardware Defect/Physical Damage", "Sensor Failure"

    if primary == "Hardware Defect/Physical Damage":
        return primary, secondary

    # 3) Software aus Notes
    if primary == "Connectivity/Recognition" and len(notes_lc) >= 30:
        if not _SW_EXCLUDE.search(notes_lc) and _SW_ACTION.search(notes_lc):
            hw_sig = _HW_SENSOR_DEAD.search(notes_lc) or _HW_SENSOR_REPL.search(notes_lc) or _HW_SENSOR_TRBL.search(notes_lc)
            if not hw_sig:
                if _SW_DRIVER.search(notes_lc):
                    return "Software/Firmware/Driver", "Driver"
                if _SW_UPDATE.search(notes_lc):
                    return "Software/Firmware/Driver", "Update/Version"
                if _SW_RESOLVED.search(notes_lc):
                    return "Software/Firmware/Driver", "Software"

    if primary != "Connectivity/Recognition":
        return primary, secondary

    # 4) Connectivity-Subkategorie aus Notes verfeinern
    return primary, _refine_connectivity(secondary, notes, description=description)


# ══════════════════════════════════════════════════════════════════════════════
# ABSCHNITT 5: Clarity-Klassifizierung (Keyword-Listen aus categories.json)
# ══════════════════════════════════════════════════════════════════════════════

_ACTION_KEYWORDS: list[str] = ["replace","swap","repair","update","install","rma","exchange","tauschen","austausch","erneuert","resolved","fixed","upgraded","shipped","sent","new sensor","new cable","new remote","new interface","reseat","reseated","reconnect","reconnected","cleaned","clean"]
_STRONG_RESOLUTION_KEYWORDS: list[str] = ["now stable","now works","works again","issue resolved after","resolved by","now interface is stable","now the sensor is recognized","sensor is recognized","functional (yes/no): yes","functional test successful","tests shot successful","test shot successful","problem solved","wieder erkannt","funktioniert","behoben"]
_SPECIFIC_CORRECTIVE_ACTION_KEYWORDS: list[str] = ["reseat","reseated","reconnect","reconnected","replug","unplug","cleaned","clean contact","cleaned contact","tighten","tightened","retighten"]
_CONCRETE_CAUSE_OBSERVATION_KEYWORDS: list[str] = ["loose","wackelkontakt","dirty contact","contamination","oxid","oxidation","corrosion","cable was loose","connector loose","contacts were dirty"]
_GENERIC_REPLACEMENT_ONLY_TERMS: list[str] = ["part of the system must be replaced","replacement part has been recommended","please close complaint","closing ticket"]
_ROOT_CAUSE_KEYWORDS: list[str] = ["caused by","because of","result of","identified as","confirmed as","root cause","failure was","issue was","problem was","found to be","determined to be","turned out","confirmed that","point of failure","worn elastomer","damaged elastomer","defective elastomer","physical damage","liquid damage","water damage","bodily fluid","broken cable","bent pin","cracked","damaged cable","cable damage","driver conflict","software conflict","incompatib","firmware issue","firmware problem","firmware conflict","firmware update resolved","configuration error","settings issue","loose connector","loose connection","out of box failure","defective from factory","ursache","verursacht","aufgrund","defekt durch","beschaedigt durch"]
_NEGATIVE_INDICATORS: list[str] = ["no help","didn't fix","did not fix","didn't resolve","did not resolve","still not working","still not connecting","still not detecting","no improvement","without resolution","unresolved","suggest replacing","recommend replacing","recommended to replace","recommend to replace","advising to replace","suggest sensor replacement","unknown cause","tried replacing","tried swapping","tried changing","completely dead","functional (yes/no): no"]
_GENERIC_EXCLUSIONS: list[str] = ["please refer to customer communication","please refer to customer notes","refer to customer notes","see customer notes"]
_DEVICE_TERMS: list[str] = ["sensor","remote","interface","hub","module","sensorbox"]


def classify_clarity(notes: str) -> str:
    if not notes or len(notes) < 50:
        return "unclear"
    low = notes.lower()
    if "problem description" not in low or "solution description" not in low:
        return "unclear"
    sol_idx = low.rfind("solution description")
    sol_text = notes[sol_idx + len("solution description"):].strip()
    sol_text_clean = re.sub(r"\d{2}[./]\d{2}[./]\d{4}.*?\n", "", sol_text).strip()
    sol_low = sol_text_clean.lower()
    if any(excl in sol_low for excl in _GENERIC_EXCLUSIONS):
        return "unclear"
    if len(sol_text_clean) < 25:
        return "unclear"
    involves_device = bool(re.search(r"\b(?:" + "|".join(re.escape(t) for t in _DEVICE_TERMS) + r")\b", low))
    if involves_device and not re.search(r"\bsensor\b|\binterface\b|\bhub\b|\bmodule\b|\bsensorbox\b", low):
        if not re.search(r"\bremote\b.{0,60}(?:not detect|not connect|not recogniz|disconnect|drops?|issue|problem|failure|defect|replaced|repaired|rma|swap)", low):
            involves_device = False
    has_root_cause = any(kw in low for kw in _ROOT_CAUSE_KEYWORDS)
    has_negative   = any(kw in sol_low for kw in _NEGATIVE_INDICATORS)
    has_action     = any(kw in low for kw in _ACTION_KEYWORDS)
    has_strong_res = any(kw in sol_low for kw in _STRONG_RESOLUTION_KEYWORDS)
    has_spec_corr  = any(kw in low for kw in _SPECIFIC_CORRECTIVE_ACTION_KEYWORDS)
    has_concrete   = any(kw in low for kw in _CONCRETE_CAUSE_OBSERVATION_KEYWORDS)
    has_gen_repl   = any(kw in low for kw in _GENERIC_REPLACEMENT_ONLY_TERMS)
    if involves_device:
        if has_negative:
            return "unclear"
        if has_root_cause:
            return "clear"
        if has_spec_corr and (has_strong_res or has_concrete):
            return "clear"
        if has_concrete and has_strong_res:
            return "clear"
        if has_gen_repl and not has_root_cause:
            return "unclear"
        return "unclear"
    return "clear" if ((has_action or has_strong_res) and not has_negative) else "unclear"


def load_and_apply_categories(categories_path: Path) -> dict:
    with categories_path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    clarity = cfg.get("clarity", {})
    _map = {
        "root_cause_keywords": _ROOT_CAUSE_KEYWORDS,
        "negative_indicators": _NEGATIVE_INDICATORS,
        "strong_resolution_keywords": _STRONG_RESOLUTION_KEYWORDS,
        "action_keywords": _ACTION_KEYWORDS,
        "specific_corrective_action_keywords": _SPECIFIC_CORRECTIVE_ACTION_KEYWORDS,
        "concrete_cause_observation_keywords": _CONCRETE_CAUSE_OBSERVATION_KEYWORDS,
        "generic_replacement_only_terms": _GENERIC_REPLACEMENT_ONLY_TERMS,
        "generic_exclusions": _GENERIC_EXCLUSIONS,
        "hardware_device_terms": _DEVICE_TERMS,
    }
    for key, lst in _map.items():
        if key in clarity:
            lst[:] = clarity[key]
    return cfg


def classify_tickets(raw_tickets: list[dict]) -> tuple[list[dict], dict]:
    classified: list[dict] = []
    refined_total = 0
    refined_by_primary: Counter[str] = Counter()
    refined_transitions: Counter[str] = Counter()
    for t in raw_tickets:
        desc  = t["description_text"]
        notes = t["notes_text"]
        cat4  = t.get("cat4", "")
        p0, s0 = classify_description(desc, cat4=cat4)
        bp, bs = p0, s0
        p0, s0 = refine_subcategory_with_notes(p0, s0, notes, description=desc)
        if p0 != bp or s0 != bs:
            refined_total += 1
            refined_by_primary[bp] += 1
            refined_transitions[f"{bs} -> {s0}"] += 1
        classified.append({**t, "desc_primary_raw": bp, "desc_secondary_raw": bs, "primary": p0, "secondary": s0, "clarity": classify_clarity(notes), "tickets": 1})
    stats = {"total": len(classified), "notes_refined_total": refined_total, "refined_by_primary": dict(refined_by_primary.most_common()), "top_transitions": dict(refined_transitions.most_common(10))}
    return classified, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: tickets_raw.json + categories.json → tickets_classified.json")
    parser.add_argument("--input",      default="output/tickets_raw.json")
    parser.add_argument("--categories", default="categories.json")
    parser.add_argument("--output",     default="output/tickets_classified.json")
    args = parser.parse_args()
    raw_path = Path(args.input)
    if not raw_path.exists():
        raise FileNotFoundError(f"Rohdaten nicht gefunden: {raw_path}")
    print(f"Lese Rohdaten: {raw_path}")
    raw_tickets = json.loads(raw_path.read_text(encoding="utf-8"))
    print(f"  {len(raw_tickets)} Tickets geladen")
    cat_path = Path(args.categories)
    if cat_path.exists():
        load_and_apply_categories(cat_path)
        print(f"Kategorie-Konfiguration geladen: {cat_path}")
    print("Klassifiziere Tickets ...")
    classified, stats = classify_tickets(raw_tickets)
    print(f"\nNotes-Refinement: {stats['notes_refined_total']} / {stats['total']} Tickets geaendert")
    for tr, cnt in list(stats["top_transitions"].items())[:8]:
        pct = cnt / max(stats["notes_refined_total"], 1) * 100
        print(f"  {tr}: {cnt} ({pct:.1f}%)")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tickets": classified, "stats": stats}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()