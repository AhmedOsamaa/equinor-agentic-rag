"""Terminal review loop for the generated question candidates.

Run: uv run python eval/review.py [--split dev|test|all] [--flagged-only]
                                  [--log eval/review_log.jsonl] [--out eval/questions.jsonl]

For each undecided question it shows the question, the reference answer, the gold quotes, the
verifier flags and any known defect from the defect list, then asks:
  a accept   e edit   r reject (a reason is required)   p print the cited page(s)
  s skip for now (it comes back next run)   q quit
Every decision is appended to the log, and --out (eval/questions.jsonl) is rebuilt from the log
after each one, so quitting loses nothing and the next run resumes. Rejected ids are dropped,
never re-split: eval/splits.json is not touched. The rejection rate per tier is printed at the end.

Reject reasons are free text; short codes help the summary, e.g. false-premise, wording,
two-answers, single-doc, weak-spanning, wrong-answer, unreadable.
"""

import json
import sys
from pathlib import Path

from verify_candidates import check_item, load_pages, review_flags, warnings_for

from rag.review import (
    append_log,
    apply_edit,
    build_questions,
    drop_gold,
    latest_decisions,
    read_log,
    review_order,
    summary,
)
from rag.splits import round_of

CANDIDATES = Path("eval/candidates")
SPLITS = Path("eval/splits.json")
DEFECTS = Path("eval/known_defects.json")
DOCS = ["equinor_ar2025", "havtil_framework", "havtil_management", "havtil_activities", "havtil_co2", "irena_rpgc2024"]
LABELS = {
    "t": ("type", {"direct_fact", "numerical", "temporal", "comparative", "spanning", "relationship", "holistic"}),
    "f": ("format", {"text", "table"}),
    "b": ("behaviour", {"answerable", "unanswerable_out", "unanswerable_near", "ambiguous"}),
}


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load_items() -> list[dict]:
    items = []
    for path in sorted(CANDIDATES.glob("*.jsonl")):
        items += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items


def show(item: dict, split: str, notes: list[str], position: str) -> None:
    print("\n" + "=" * 100)
    print(f"{position}  {item['id']}   round {round_of(item)}   split {split}")
    print(f"type {item['type']} | format {item['format']} | behaviour {item['behaviour']}")
    print(f"\nQUESTION: {item['question']}")
    print(f"ANSWER:   {item.get('reference_answer', '')}")
    for n, g in enumerate(item.get("gold", [])):
        print(f"  gold[{n}] {g['doc_id']} p{g['page']}: {g['evidence_quote']}")
    if item.get("notes"):
        print(f"notes: {item['notes']}")
    for note in notes:
        print(f"  ! {note}")


def edit_item(item: dict, pages_by_doc: dict) -> dict | None:
    """Let the reviewer change fields; returns the edited item, or None if nothing changed."""
    current = item
    print("edit: q question | a answer | t type | f format | b behaviour | n notes | g drop a gold entry | d done | x cancel")
    while True:
        choice = input("edit> ").strip().lower()
        if choice == "x":
            return None
        if choice == "d":
            return None if current == item else current
        try:
            if choice == "q":
                candidate = apply_edit(current, "question", input("new question: ").strip())
            elif choice == "a":
                candidate = apply_edit(current, "reference_answer", input("new reference answer: ").strip())
            elif choice == "n":
                candidate = apply_edit(current, "notes", input("notes: ").strip())
            elif choice in LABELS:
                field, allowed = LABELS[choice]
                value = input(f"{field} {sorted(allowed)}: ").strip()
                if value not in allowed:
                    print(f"  not one of {sorted(allowed)}")
                    continue
                candidate = apply_edit(current, field, value)
            elif choice == "g":
                candidate = drop_gold(current, int(input("gold index to drop: ")))
            else:
                print("  unknown choice")
                continue
        except (ValueError, IndexError) as e:
            print(f"  {e}")
            continue
        problems = check_item(candidate, pages_by_doc)
        if problems:
            print("  rejected edit, the verifier says: " + "; ".join(problems))
            continue
        current = candidate
        print("  ok")


def print_pages(item: dict, pages_by_doc: dict) -> None:
    for doc, page in dict.fromkeys((g["doc_id"], g["page"]) for g in item.get("gold", [])):
        print(f"\n----- {doc} page {page} (cleaned text) -----")
        print(pages_by_doc[doc].get(page, "(page not in cleaned pages)"))


def print_summary(items: list[dict], decisions: dict) -> None:
    s = summary(items, decisions)
    print("\nreviewed so far (rejection rate is the measured quality number for the README):")
    for key, c in s["tiers"].items():
        print(f"  {key:<8} reviewed {c['reviewed']:>3}  accepted {c['accept']:>3}  edited {c['edit']:>3}  "
              f"rejected {c['reject']:>3}  rate {c['rejection_rate']:.0%}")
    for reason, n in sorted(s["reject_reasons"].items(), key=lambda kv: -kv[1]):
        print(f"    {n}x {reason}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # the documents contain characters a Windows console chokes on
    which = option("--split", "dev")
    log_path, out_path = Path(option("--log", "eval/review_log.jsonl")), Path(option("--out", "eval/questions.jsonl"))
    items = load_items()
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["split"]
    defects = {k: v for k, v in json.loads(DEFECTS.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    pages_by_doc = {d: load_pages(d) for d in DOCS}

    flags = {i["id"]: [f"{kind}: {detail}" for kind, detail in review_flags(i, pages_by_doc)] + warnings_for(i)
             for i in items}
    flagged = {k for k, v in flags.items() if v}
    decisions = latest_decisions(read_log(log_path))
    queue = review_order(items, splits, which, flagged, set(defects))
    if "--flagged-only" in sys.argv:
        queue = [i for i in queue if i["id"] in flagged or i["id"] in defects]
    todo = [i for i in queue if i["id"] not in decisions]
    print(f"{len(queue)} questions in scope ({which}), {len(queue) - len(todo)} already decided, {len(todo)} to go")

    for n, item in enumerate(todo, start=1):
        notes = ([f"KNOWN DEFECT: {defects[item['id']]}"] if item["id"] in defects else []) + flags[item["id"]]
        show(item, splits[item["id"]], notes, f"[{n}/{len(todo)}]")
        while True:
            choice = input("\n[a]ccept  [e]dit  [r]eject  [p]age  [s]kip  [q]uit > ").strip().lower()
            if choice == "p":
                print_pages(item, pages_by_doc)
            elif choice in ("a", "e", "r", "s", "q"):
                break
        if choice == "q":
            break
        if choice == "s":
            continue
        if choice == "a":
            append_log(log_path, {"id": item["id"], "decision": "accept"})
        elif choice == "r":
            reason = ""
            while not reason:
                reason = input("reason (required): ").strip()
            append_log(log_path, {"id": item["id"], "decision": "reject", "reason": reason})
        elif choice == "e":
            edited = edit_item(item, pages_by_doc)
            if edited is None:
                print("  no change made; question left undecided")
                continue
            reason = input("what you changed and why: ").strip()
            append_log(log_path, {"id": item["id"], "decision": "edit", "reason": reason, "item": edited})
        decisions = latest_decisions(read_log(log_path))
        out_path.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in build_questions(items, decisions, splits)) + "\n",
                            encoding="utf-8")

    print_summary(items, decisions)
    print(f"\nlog: {log_path}   reviewed questions: {out_path}")


if __name__ == "__main__":
    main()
