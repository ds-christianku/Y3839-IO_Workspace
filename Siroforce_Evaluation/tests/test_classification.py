"""Automatisierter Klassifizierungstest.

Verwendung:
  python tests/test_classification.py                  # Standard-Testdatei
  python tests/test_classification.py --verbose        # Zeigt alle Ergebnisse
  python tests/test_classification.py --file mein.json # Eigene Testdatei

Jeder Testfall in labeled_tickets.json benoetigt:
  description, notes, expected_primary, expected_secondary

Testfall-Gruppen (getrennte Ausgabe):
  T001..T999  → Synthetische Testfaelle (handgepflegte Beispiele)
  REAL-...    → Echte Tickets aus tickets_classified.json

Rueckgabewert: Exit-Code 0 = alle Tests bestanden, 1 = mind. ein Fehler.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline_02_classify as classify


def _classify(case: dict) -> tuple[bool, dict]:
    p, s = classify.classify_description(case["description"])
    p, s = classify.refine_subcategory_with_notes(p, s, case["notes"], description=case["description"])
    exp_p = case["expected_primary"]
    exp_s = case["expected_secondary"]
    ok = (p == exp_p) and (s == exp_s)
    return ok, {
        "id":            case.get("_id", "?"),
        "desc":          case["description"][:60],
        "got_primary":   p,
        "got_secondary": s,
        "exp_primary":   exp_p,
        "exp_secondary": exp_s,
    }


def run_group(label: str, cases: list[dict], verbose: bool) -> tuple[int, int]:
    """Läuft eine Gruppe durch und gibt (passed, failed) zurück."""
    passed = failed = 0
    errors: list[dict] = []

    print(f"\n{'─'*60}")
    print(f"  {label}  ({len(cases)} Faelle)")
    print(f"{'─'*60}")

    for case in cases:
        ok, info = _classify(case)
        if ok:
            passed += 1
            if verbose:
                print(f"  ✓  {info['id']}: {info['got_primary']} / {info['got_secondary']}")
        else:
            failed += 1
            errors.append(info)
            if verbose:
                print(f"  ✗  {info['id']}: got  '{info['got_primary']}' / '{info['got_secondary']}'")
                print(f"               want '{info['exp_primary']}' / '{info['exp_secondary']}'")

    pct = f"{passed/(passed+failed)*100:.0f}%" if (passed + failed) else "–"
    print(f"\n  Ergebnis: {passed}/{passed+failed} bestanden  ({pct})")

    if errors:
        print(f"\n  Fehler ({len(errors)}):")
        for e in errors:
            p_ok = "✓" if e["got_primary"]   == e["exp_primary"]   else "✗"
            s_ok = "✓" if e["got_secondary"] == e["exp_secondary"] else "✗"
            print(f"    [{e['id']}]  {e['desc']!r}")
            print(f"      Primary:   {p_ok} got='{e['got_primary']}'  want='{e['exp_primary']}'")
            print(f"      Secondary: {s_ok} got='{e['got_secondary']}'  want='{e['exp_secondary']}'")

    return passed, failed


def run_tests(test_path: Path, verbose: bool = False) -> int:
    cases = json.loads(test_path.read_text(encoding="utf-8"))

    synthetic = [c for c in cases if str(c.get("_id", "")).startswith("T")]
    real      = [c for c in cases if str(c.get("_id", "")).startswith("REAL")]
    other     = [c for c in cases if c not in synthetic and c not in real]

    total_passed = total_failed = 0

    if synthetic:
        p, f = run_group("Synthetische Testfaelle", synthetic, verbose)
        total_passed += p; total_failed += f

    if real:
        p, f = run_group("Connectivity/Recognition Test", real, verbose)
        total_passed += p; total_failed += f

    if other:
        p, f = run_group("Sonstige Testfaelle", other, verbose)
        total_passed += p; total_failed += f

    total = total_passed + total_failed
    pct   = f"{total_passed/total*100:.0f}%" if total else "–"
    print(f"\n{'='*60}")
    print(f"GESAMT: {total_passed}/{total} bestanden  ({pct})")
    print(f"{'='*60}")

    return 0 if total_failed == 0 else 1


def test_llm_summary_fallback() -> None:
    notes = """
    Problem Description
    Sensor not recognized on workstation 3.

    Solution Description
    Re-seated sensor cable and reinstalled driver. Sensor works again.
    """
    summary = classify.build_problem_solution_summary(notes, "Sensor not recognized")
    assert summary["problem"] == "Sensor not recognized on workstation 3."
    assert summary["solution"] == "Re-seated sensor cable and reinstalled driver. Sensor works again."

    empty = classify.build_problem_solution_summary("No useful data here", "")
    assert empty["problem"] == "n.a."
    assert empty["solution"] == "n.a."


def test_summary_drives_clarity() -> None:
    summary = {
        "problem": "Sensor not recognized on workstation 3.",
        "solution": "Re-seated sensor cable and reinstalled driver. Sensor works again.",
    }
    assert classify.classify_clarity("Problem Description\nSensor issue", summary) == "clear"
    assert classify.classify_clarity("Problem Description\nSensor issue", {"problem": "Sensor issue", "solution": "n.a."}) == "unclear"


def test_select_unclassified_batch_skips_existing_and_limits_size() -> None:
    raw_tickets = [{"ticket_id": f"T{i}", "description_text": f"issue {i}", "notes_text": "some notes"} for i in range(1200)]
    existing = [{"ticket_id": f"T{i}", "primary": "Connectivity/Recognition", "secondary": "Other"} for i in range(75)]

    batch = classify.select_unclassified_batch(raw_tickets, existing_tickets=existing, batch_size=500)

    assert len(batch) == 500
    assert all(ticket["ticket_id"] not in {t["ticket_id"] for t in existing} for ticket in batch)
    assert batch[0]["ticket_id"] == "T75"
    assert batch[-1]["ticket_id"] == "T574"


def main() -> None:
    parser = argparse.ArgumentParser(description="Klassifizierungstest fuer Ticket-Pipeline")
    parser.add_argument("--file", type=Path,
                        default=Path(__file__).parent / "labeled_tickets.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--categories", type=Path,
                        default=Path(__file__).parent.parent / "categories.json")
    args = parser.parse_args()

    if args.categories.exists():
        classify.load_and_apply_categories(args.categories)
        print(f"Konfiguration geladen: {args.categories.name}")

    total = len(json.loads(args.file.read_text(encoding="utf-8")))
    print(f"Testdatei: {args.file.name}  ({total} Faelle)")

    test_llm_summary_fallback()
    print("LLM summary fallback checks: OK")
    sys.exit(run_tests(args.file, verbose=args.verbose))


if __name__ == "__main__":
    main()
