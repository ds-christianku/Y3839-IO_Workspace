"""Automatisierter Klassifizierungstest.

Verwendung:
  python tests/test_classification.py                  # Standard-Testdatei
  python tests/test_classification.py --verbose        # Zeigt alle Ergebnisse
  python tests/test_classification.py --file mein.json # Eigene Testdatei

Jeder Testfall in labeled_tickets.json benoetigt:
  description, notes, expected_primary, expected_secondary

Rueckgabewert: Exit-Code 0 = alle Tests bestanden, 1 = mind. ein Fehler.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Sicherstellen dass pipeline_02_classify importierbar ist
sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline_02_classify as classify


def run_tests(test_path: Path, verbose: bool = False) -> int:
    cases = json.loads(test_path.read_text(encoding="utf-8"))

    passed = 0
    failed = 0
    errors: list[dict] = []

    for case in cases:
        tid       = case.get("_id", "?")
        desc      = case["description"]
        notes     = case["notes"]
        exp_p     = case["expected_primary"]
        exp_s     = case["expected_secondary"]

        # Description-Klassifizierung
        p, s = classify.classify_description(desc)
        # Notes-Refinement
        p, s = classify.refine_subcategory_with_notes(p, s, notes, description=desc)

        ok_p = (p == exp_p)
        ok_s = (s == exp_s)
        ok   = ok_p and ok_s

        if ok:
            passed += 1
            if verbose:
                print(f"  ✓  {tid}: {p} / {s}")
        else:
            failed += 1
            errors.append({
                "id": tid,
                "desc": desc[:60],
                "got_primary": p,
                "got_secondary": s,
                "exp_primary": exp_p,
                "exp_secondary": exp_s,
            })
            if verbose:
                print(f"  ✗  {tid}: got  '{p}' / '{s}'")
                print(f"           want '{exp_p}' / '{exp_s}'")

    total = passed + failed
    print(f"\n{'='*60}")
    print(f"Klassifizierungstest: {passed}/{total} bestanden", end="")
    if total:
        print(f"  ({passed/total*100:.0f}%)")
    else:
        print()

    if errors:
        print(f"\nFehlgeschlagene Tests ({len(errors)}):")
        for e in errors:
            p_mark = "✓" if e["got_primary"]   == e["exp_primary"]   else "✗"
            s_mark = "✓" if e["got_secondary"] == e["exp_secondary"] else "✗"
            print(f"  [{e['id']}] {e['desc']!r}")
            print(f"    Primary:   {p_mark} got='{e['got_primary']}'  want='{e['exp_primary']}'")
            print(f"    Secondary: {s_mark} got='{e['got_secondary']}'  want='{e['exp_secondary']}'")
    print("=" * 60)

    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Klassifizierungstest fuer Ticket-Pipeline")
    parser.add_argument(
        "--file", type=Path,
        default=Path(__file__).parent / "labeled_tickets.json",
        help="Pfad zur JSON-Testdatei",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Alle Testergebnisse ausgeben, nicht nur Fehler",
    )
    parser.add_argument(
        "--categories", type=Path,
        default=Path(__file__).parent.parent / "categories.json",
        help="categories.json laden (optional)",
    )
    args = parser.parse_args()

    if args.categories.exists():
        classify.load_and_apply_categories(args.categories)
        print(f"Konfiguration geladen: {args.categories}")

    print(f"Testdatei: {args.file}  ({sum(1 for _ in json.loads(args.file.read_text(encoding='utf-8')))} Faelle)\n")
    if args.verbose:
        print("Ergebnisse:")

    sys.exit(run_tests(args.file, verbose=args.verbose))


if __name__ == "__main__":
    main()
