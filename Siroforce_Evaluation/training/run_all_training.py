"""Combined Training Report für alle Kategorien (Connectivity, Software, Installation).

Verwendung:
  python training/run_all_training.py
  python training/run_all_training.py --verbose
  
Output: Markdown-Report wird in TRAINING_RESULT.md gespeichert
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TRAINING_DIR.parent
DEFAULT_CATEGORIES = PROJECT_ROOT / "categories.json"

sys.path.insert(0, str(TRAINING_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

import pipeline_02_classify as classify


def _new_dimension_stats() -> dict[str, int]:
    return {
        "evaluated": 0,
        "skipped": 0,
        "passed": 0,
        "failed": 0,
    }


def _new_stats() -> dict[str, dict[str, int]]:
    return {
        "category": _new_dimension_stats(),
        "clearness": _new_dimension_stats(),
    }


def _classify(case: dict) -> tuple[bool, dict]:
    primary, secondary = classify.classify_description(case["description"])
    primary, secondary = classify.refine_subcategory_with_notes(
        primary,
        secondary,
        case["notes"],
        description=case["description"],
    )

    exp_primary = case["expected_primary"]
    exp_secondary = case["expected_secondary"]
    exp_clarity = case.get("expected_clarity", "-")

    skip_category = (exp_primary == "-") and (exp_secondary == "-")
    skip_clearness = exp_clarity == "-"

    category_ok = skip_category or ((primary == exp_primary) and (secondary == exp_secondary))
    got_clarity = classify.classify_clarity(case["notes"])
    clearness_ok = skip_clearness or (got_clarity == exp_clarity)
    ok = category_ok and clearness_ok

    return ok, {
        "id": case.get("_id", "?"),
        "desc": case.get("description", "")[:80],
        "got_primary": primary,
        "got_secondary": secondary,
        "exp_primary": exp_primary,
        "exp_secondary": exp_secondary,
        "got_clarity": got_clarity,
        "exp_clarity": exp_clarity,
        "category_skipped": skip_category,
        "clearness_skipped": skip_clearness,
        "category_ok": category_ok,
        "clearness_ok": clearness_ok,
    }


def _run_group(label: str, cases: list[dict], verbose: bool) -> tuple[int, dict[str, dict[str, int]], list[dict]]:
    failed_cases = 0
    stats = _new_stats()
    errors: list[dict] = []

    print(f"\n{'-' * 70}")
    print(f"  {label}  ({len(cases)} Fälle)")
    print(f"{'-' * 70}")

    for case in cases:
        ok, info = _classify(case)

        if info["category_skipped"]:
            stats["category"]["skipped"] += 1
        else:
            stats["category"]["evaluated"] += 1
            if info["category_ok"]:
                stats["category"]["passed"] += 1
            else:
                stats["category"]["failed"] += 1

        if info["clearness_skipped"]:
            stats["clearness"]["skipped"] += 1
        else:
            stats["clearness"]["evaluated"] += 1
            if info["clearness_ok"]:
                stats["clearness"]["passed"] += 1
            else:
                stats["clearness"]["failed"] += 1

        if ok:
            if verbose:
                print(
                    f"  ✓  {info['id']}: "
                    f"{info['got_primary']} / {info['got_secondary']} | clarity={info['got_clarity']}"
                )
        else:
            failed_cases += 1
            errors.append(info)
            if verbose:
                print(
                    f"  ✗  {info['id']}: "
                    f"cat got='{info['got_primary']}/{info['got_secondary']}' "
                    f"want='{info['exp_primary']}/{info['exp_secondary']}'"
                )
                print(
                    f"             clarity got='{info['got_clarity']}' "
                    f"want='{info['exp_clarity']}'"
                )

    return failed_cases, stats, errors


def _discover_training_files() -> dict[str, Path]:
    """Ermittelt alle trainingsrelevanten JSON-Dateien inklusive der neu hinzugefügten Kategorien."""
    mapping = {
        "Connectivity/Recognition": [
            TRAINING_DIR / "training_connectivity_tickets.json",
            TRAINING_DIR / "Training_connectivity_tickets.json",
        ],
        "Software/Firmware/Driver": [
            TRAINING_DIR / "training_software_firmware_driver_tickets.json",
            TRAINING_DIR / "Training_software_firmware_driver_tickets.json",
        ],
        "Installation/Setup/Upgrade": [
            TRAINING_DIR / "training_installation_setup_upgrade_tickets.json",
            TRAINING_DIR / "Training_installation_setup_upgrade_tickets.json",
        ],
        "Imaging/Acquisition/Exposure": [
            TRAINING_DIR / "Training_imaging_acquisition_exposure.json",
            TRAINING_DIR / "training_imaging_acquisition_exposure.json",
        ],
        "Spare Parts/RMA/Logistics": [
            TRAINING_DIR / "Training_spareparts_rma_logistics.json",
            TRAINING_DIR / "training_spareparts_rma_logistics.json",
        ],
        "Hardware Defect/Physical Damage": [
            TRAINING_DIR / "Training_hardwaredefect_physicaldamage.json",
            TRAINING_DIR / "training_hardwaredefect_physicaldamage.json",
        ],
    }

    training_files: dict[str, Path] = {}
    for category_name, file_candidates in mapping.items():
        for file_path in file_candidates:
            if file_path.exists():
                training_files[category_name] = file_path
                break
    return training_files


def _generate_markdown_report(
    results: dict,
) -> str:
    """Generiert einen kombinierten Markdown-Report für alle Training-Kategorien."""
    
    # Aggregierte Statistiken
    total_cat_passed = sum(r["stats"]["category"]["passed"] for r in results.values())
    total_cat_total = sum(r["stats"]["category"]["evaluated"] for r in results.values())
    total_clear_passed = sum(r["stats"]["clearness"]["passed"] for r in results.values())
    total_clear_total = sum(r["stats"]["clearness"]["evaluated"] for r in results.values())
    
    total_failed_cases = sum(r["failed_cases"] for r in results.values())
    total_tickets = sum(r["total_cases"] for r in results.values())
    
    cat_pct = (total_cat_passed / total_cat_total * 100) if total_cat_total > 0 else 0
    clear_pct = (total_clear_passed / total_clear_total * 100) if total_clear_total > 0 else 0
    
    status = "✅ BESTANDEN" if total_failed_cases == 0 else "⚠️ FEHLER"
    overall_pct = ((total_cat_passed + total_clear_passed) / (total_cat_total + total_clear_total) * 100) if (total_cat_total + total_clear_total) > 0 else 0
    
    markdown = f"""# Training Result - Gesamt Report
**Generiert:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Pipeline:** pipeline_02_classify.py (Multi-level classification)

---

## Executive Summary

| Metrik | Wert |
|--------|------|
| **Gesamt Training-Tickets** | {total_tickets} |
| **Kategorien validiert** | {len(results)} |
| **Kategorisierung bestanden** | {total_cat_passed}/{total_cat_total} ({cat_pct:.1f}%) |
| **Clearness bestanden** | {total_clear_passed}/{total_clear_total} ({clear_pct:.1f}%) |
| **Durchschnittliche Erfolgsquote** | {overall_pct:.1f}% |
| **Fehlerhafte Fälle** | {total_failed_cases} |
| **Status** | {status} |

---

## Detaillierte Ergebnisse pro Kategorie

"""
    
    # Detaillierte Ergebnisse für jede Kategorie
    for category_name, data in results.items():
        stats = data["stats"]
        failed_cases = data["failed_cases"]
        total_cases = data["total_cases"]
        
        cat_passed = stats["category"]["passed"]
        cat_total = stats["category"]["evaluated"]
        cat_pct = (cat_passed / cat_total * 100) if cat_total > 0 else 0
        
        clear_passed = stats["clearness"]["passed"]
        clear_total = stats["clearness"]["evaluated"]
        clear_pct = (clear_passed / clear_total * 100) if clear_total > 0 else 0
        
        cat_status = "🟢 Ausgezeichnet" if cat_pct == 100 else "🟡 Gut" if cat_pct >= 90 else "🔴 Verbesserungsbedarf"
        clear_status = "🟢 Ausgezeichnet" if clear_pct == 100 else "🟡 Gut" if clear_pct >= 90 else "🔴 Verbesserungsbedarf"
        
        markdown += f"""### {category_name}

**Test-Datei:** {data['file'].name}  
**Tickets:** {total_cases}

#### Kategorisierung
- ✓ Bestanden: **{cat_passed}/{cat_total}** ({cat_pct:.1f}%)
- ✗ Fehlgeschlagen: **{stats['category']['failed']}**
- ⏭️ Übersprungen: {stats['category']['skipped']}
- **Status:** {cat_status}

#### Clearness-Klassifikation
- ✓ Bestanden: **{clear_passed}/{clear_total}** ({clear_pct:.1f}%)
- ✗ Fehlgeschlagen: **{stats['clearness']['failed']}**
- ⏭️ Übersprungen: {stats['clearness']['skipped']}
- **Status:** {clear_status}

**Fehlerhafte Fälle:** {failed_cases}

---

"""
    
    markdown += """## Zusammenfassung

"""
    
    # Tabelle mit allen Kategorien
    markdown += "| Kategorie | Tickets | Kategorie Pass | Clearness Pass | Status |\n"
    markdown += "|-----------|---------|----------------|-----------------|--------|\n"
    
    for category_name, data in results.items():
        stats = data["stats"]
        total = data["total_cases"]
        cat_pass = f"{stats['category']['passed']}/{stats['category']['evaluated']}"
        clear_pass = f"{stats['clearness']['passed']}/{stats['clearness']['evaluated']}"
        
        cat_pct = (stats['category']['passed'] / stats['category']['evaluated'] * 100) if stats['category']['evaluated'] > 0 else 0
        clear_pct = (stats['clearness']['passed'] / stats['clearness']['evaluated'] * 100) if stats['clearness']['evaluated'] > 0 else 0
        
        if cat_pct == 100 and clear_pct == 100:
            status = "✅"
        elif cat_pct >= 85 and clear_pct >= 85:
            status = "🟡"
        else:
            status = "⚠️"
        
        markdown += f"| {category_name} | {total} | {cat_pass} | {clear_pass} | {status} |\n"
    
    markdown += f"""
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

"""
    
    if total_failed_cases == 0:
        markdown += """✅ **Alle Tests bestanden!** 

Alle Trainingskategorien funktionieren perfekt. Die Klassifikation ist produktionsreif.
"""
    else:
        markdown += f"""⚠️ **{total_failed_cases} Fehler gefunden**

Betroffene Kategorien sollten überprüft werden:
1. Identifiziere Kategorien mit Fehlern
2. Überprüfe die spezifischen fehlerhaften Tickets
3. Passe Regex-Muster in pipeline_02_classify.py an
4. Wiederhole die Tests nach jeder Änderung
"""
    
    markdown += f"""
---

**Report generiert:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Gesamt Training für alle Kategorien")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "TRAINING_RESULT.md")
    args = parser.parse_args()

    if args.categories.exists():
        classify.load_and_apply_categories(args.categories)
        print(f"✓ Konfiguration geladen: {args.categories.name}")

    # Definiere alle Training-Dateien (inkl. neuer Kategorien)
    training_files = _discover_training_files()
    if not training_files:
        print("⚠️  Keine Trainingsdateien gefunden.")
        sys.exit(1)

    results = {}

    # Verarbeite jede Kategorie
    for category_name, file_path in training_files.items():
        if not file_path.exists():
            print(f"⚠️  Testdatei nicht gefunden: {file_path.name}")
            continue

        cases = json.loads(file_path.read_text(encoding="utf-8"))
        total_cases = len(cases)
        print(f"\n📋 Kategorie: {category_name} ({total_cases} Fälle)")

        # Führe Tests durch
        failed_cases, stats, errors = _run_group(category_name, cases, args.verbose)

        results[category_name] = {
            "file": file_path,
            "total_cases": total_cases,
            "failed_cases": failed_cases,
            "stats": stats,
            "errors": errors,
        }

    # Zusammenfassung in Terminal
    print(f"\n{'=' * 70}")
    print("GESAMT AUSWERTUNG")
    print("  {:<30} {:>16} {:>16}".format("Kategorie", "Kategorisierung", "Clearness"))
    print(f"{'=' * 70}")
    
    for category_name, data in results.items():
        stats = data["stats"]
        cat_str = f"{stats['category']['passed']}/{stats['category']['evaluated']}"
        clear_str = f"{stats['clearness']['passed']}/{stats['clearness']['evaluated']}"
        print(f"  {category_name:<28} {cat_str:>16} {clear_str:>16}")
    
    print(f"{'=' * 70}\n")

    # Generiere Markdown-Report
    markdown_report = _generate_markdown_report(results)

    # Speichere Report
    args.output.write_text(markdown_report, encoding="utf-8")
    print(f"✓ Markdown-Report gespeichert: {args.output.name}\n")

    # Bestimme Exit-Code
    total_failed = sum(r["failed_cases"] for r in results.values())
    exit_code = 0 if total_failed == 0 else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
