"""Extract a concise problem and solution summary from ticket notes without LLMs.

This script mirrors the logic used in pipeline_02_classify.py but keeps it in a
standalone, reusable form. It supports rule-based extraction and a few
non-LLM alternatives that can be used instead of an LLM:

1. Section-based extraction (default): detect labels like "Problem Description"
   and "Solution Description" in ticket notes.
2. Keyword-based extraction: match problem/solution trigger phrases and keep the
   closest relevant sentence.
3. Sentence-ranking / TF-IDF scoring: rank sentences by relevance to problem or
   solution context.
4. Embedding-based similarity (optional): use sentence-transformers or
   scikit-learn vectorizer + cosine similarity.

The script can process a single ticket or a JSON file with a list of tickets.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


SECTION_ALIASES = {
    "problem": [
        "Problem Description",
        "Issue Description",
        "Troubleshooting Description",
        "Customer Problem",
        "Issue Reported",
    ],
    "solution": [
        "Solution Description",
        "Resolution",
        "Customer Communication",
        "Follow Up",
        "Further Action",
    ],
}

STOP_LABELS = [
    "Problem Description",
    "Issue Description",
    "Troubleshooting Description",
    "Solution Description",
    "Resolution",
    "Customer Communication",
    "Further Action",
    "Log",
    "Note",
    "Internal Note",
    "Customer Note",
    "Issue Reported",
]


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text == "#":
        return ""
    return re.sub(r"\s+", " ", text)


def _clean_section_text(raw: str) -> str:
    cleaned: list[str] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("____") or line.startswith("-----"):
            continue
        if re.match(r"\d{2}[./]\d{2}[./]\d{4}\s+\d{2}:\d{2}:\d{2}", line):
            continue
        cleaned.append(line)
    return " ".join(cleaned).strip()


def extract_labeled_section(notes_text: str, section_names: Iterable[str], stop_labels: Iterable[str]) -> str:
    """Return the last matching labeled section before the next stop label."""
    src = notes_text or ""
    src_lc = src.lower()
    matches: list[tuple[int, str]] = []

    for section_name in section_names:
        pos = src_lc.rfind(section_name.lower())
        if pos >= 0:
            matches.append((pos, section_name))

    if not matches:
        return ""

    pos, section_name = max(matches, key=lambda item: item[0])
    start = pos + len(section_name)
    while start < len(src) and src[start] in (":", " ", "\t", "\n", "\r"):
        start += 1

    end = len(src)
    stop_labels_list = list(stop_labels)
    for stop in stop_labels_list:
        p = src_lc.find(stop.lower(), start)
        if 0 <= p < end:
            end = p

    raw = src[start:end]
    return _clean_section_text(raw)


def _summary_value(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return "n.a."
    lowered = text.lower().strip()
    if lowered in {"n.a.", "n/a", "na", "none", "null", "-"}:
        return "n.a."
    return text


def extract_problem_solution_by_sections(notes_text: str, description: str = "") -> dict[str, str]:
    notes = normalize_text(notes_text)
    problem = extract_labeled_section(notes, SECTION_ALIASES["problem"], STOP_LABELS)
    solution = extract_labeled_section(notes, SECTION_ALIASES["solution"], STOP_LABELS)

    if not problem and description:
        candidate = normalize_text(description)
        if candidate and candidate.lower() not in {"n.a.", "n/a", "na", "none"}:
            problem = candidate

    problem = _summary_value(problem)
    solution = _summary_value(solution)

    if problem == "n.a." and solution != "n.a.":
        problem = "n.a."
    if solution == "n.a." and problem != "n.a.":
        solution = "n.a."

    return {"problem": problem, "solution": solution}


def extract_problem_solution_by_keywords(notes_text: str, description: str = "") -> dict[str, str]:
    """Fallback approach: detect sentences matching problem/solution patterns."""
    text = normalize_text(notes_text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    problem_candidates: list[str] = []
    solution_candidates: list[str] = []

    problem_patterns = [
        r"not recognized|not working|no response|cannot.*(capture|take|connect|acquire)|sensor.*(not|no)|remote.*(not|no)|issue reported|problem description",
        r"unable to|fails? to|won't|cannot|keine|nicht erkannt|nicht erreichbar|problem",
    ]
    solution_patterns = [
        r"reinstalled|re-seated|replaced|updated|upgraded|restart|reboot|cleaned|reset|configured|installed|patched|firmware",
        r"funktioniert wieder|erneut|neu installiert|getauscht|gereinigt|konfiguriert|angepasst|gelöst",
    ]

    for sentence in sentences:
        lower = sentence.lower()
        if any(re.search(p, lower) for p in problem_patterns):
            problem_candidates.append(sentence)
        if any(re.search(p, lower) for p in solution_patterns):
            solution_candidates.append(sentence)

    problem = problem_candidates[0] if problem_candidates else (normalize_text(description) or "n.a.")
    solution = solution_candidates[0] if solution_candidates else "n.a."
    return {"problem": _summary_value(problem), "solution": _summary_value(solution)}


def sentence_rank_summary(notes_text: str, description: str = "") -> dict[str, str]:
    """Simple non-LLM summarizer using sentence scoring.

    It scores each sentence by occurrence of problem and fix keywords. The highest
    scoring sentences become problem and solution summary.
    """
    text = normalize_text(notes_text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return {"problem": _summary_value(description), "solution": "n.a."}

    problem_score = {
        "not recognized": 3, "not working": 3, "cannot": 3, "unable": 3, "issue": 2, "problem": 2,
        "sensor": 1, "remote": 1, "connection": 1, "interface": 1, "image": 1, "blurry": 2,
        "not detected": 4, "no response": 4, "no power": 4, "fails": 3, "keine": 3, "nicht": 3,
    }
    solution_score = {
        "reinstalled": 4, "updated": 4, "installed": 4, "replaced": 4, "re-seated": 4, "restart": 3,
        "reboot": 3, "configured": 3, "reset": 3, "cleaned": 3, "firmware": 3, "gelöst": 4, "getauscht": 4,
        "neu installiert": 4, "konfiguriert": 3, "funktioniert wieder": 4,
    }

    problem_ranks = []
    solution_ranks = []
    for sentence in sentences:
        lower = sentence.lower()
        problem_score_value = sum(weight for key, weight in problem_score.items() if key in lower)
        solution_score_value = sum(weight for key, weight in solution_score.items() if key in lower)
        if problem_score_value:
            problem_ranks.append((problem_score_value, sentence))
        if solution_score_value:
            solution_ranks.append((solution_score_value, sentence))

    problem = max(problem_ranks, key=lambda x: x[0])[1] if problem_ranks else (normalize_text(description) or "n.a.")
    solution = max(solution_ranks, key=lambda x: x[0])[1] if solution_ranks else "n.a."
    return {"problem": _summary_value(problem), "solution": _summary_value(solution)}


def extract_problem_solution(notes_text: str, description: str = "", method: str = "section") -> dict[str, str]:
    """Dispatcher. Supported methods: section, keyword, sentence_rank."""
    method = (method or "section").lower()
    if method == "section":
        return extract_problem_solution_by_sections(notes_text, description)
    if method == "keyword":
        return extract_problem_solution_by_keywords(notes_text, description)
    if method in {"sentence_rank", "sentence-rank", "rank"}:
        return sentence_rank_summary(notes_text, description)
    raise ValueError(f"Unsupported method '{method}'. Use: section, keyword, sentence_rank")


def process_json(input_path: str | Path, output_path: str | Path | None = None, method: str = "section") -> list[dict]:
    source = Path(input_path)
    payload = json.loads(source.read_text(encoding="utf-8"))

    if isinstance(payload, dict):
        tickets = payload.get("tickets", []) if "tickets" in payload else [payload]
    elif isinstance(payload, list):
        tickets = payload
    else:
        raise TypeError("JSON must be a ticket object, object with 'tickets', or a list of tickets.")

    cleaned: list[dict] = []
    for ticket in tickets:
        notes = ticket.get("notes_text", ticket.get("notes", ""))
        description = ticket.get("description_text", ticket.get("description", ""))
        summary = extract_problem_solution(notes, description, method=method)
        updated = dict(ticket)
        updated["problem_summary"] = summary["problem"]
        updated["solution_summary"] = summary["solution"]
        cleaned.append(updated)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        json.dumps(cleaned, ensure_ascii=False, indent=2)
        out.write_text(json.dumps({"tickets": cleaned}, ensure_ascii=False, indent=2), encoding="utf-8")

    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract problem and solution summaries from tickets without LLM.")
    parser.add_argument("--input", type=str, required=True, help="Path to a JSON file containing tickets.")
    parser.add_argument("--output", type=str, default="", help="Optional output JSON path.")
    parser.add_argument("--method", choices=["section", "keyword", "sentence_rank"], default="section", help="Extraction method to use.")
    args = parser.parse_args()

    result = process_json(args.input, args.output or None, method=args.method)
    print(f"Processed {len(result)} tickets using method '{args.method}'.")


if __name__ == "__main__":
    main()
