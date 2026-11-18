"""Review the candidate questions in a spreadsheet instead of the terminal loop.

  uv run python eval/review_sheet.py export [--split dev|test|all] [--out eval/review_sheet.csv]
  uv run python eval/review_sheet.py import [--in eval/review_sheet.csv]

export writes one row per question: the read-only information (tier, split, known defect, verifier
flags, the advisory pre-screen from eval/prescreen_suggestions.csv if present, the question, the reference answer, the gold quotes) and empty input columns. Open it in
Excel or Google Sheets and fill in:
  decision       accept | edit | reject   (a, e, r also work; leave empty to decide later)
  reason         required for reject; for edit say what you changed and why
  new_question, new_answer, new_type, new_format, new_behaviour   only for edit, only what changes
  drop_gold      for edit: the gold entries to drop, counted as in the sheet (1 = gold_1), e.g. 1 or 1,2
import reads the sheet back. Each filled row is checked (an edit goes through the verifier again), then
appended to the same decision log as the terminal loop (eval/review_log.jsonl) and eval/questions.jsonl
is rebuilt. A row that is wrong is reported and skipped; the others are still imported. Importing the
same sheet twice adds nothing, because unchanged decisions are not logged again. Close the file in Excel
before importing. Rejected ids are dropped, never re-split.

The pre-screen columns are a language model's opinion, not a decision, and import ignores them. A
re-export refuses to overwrite a sheet that holds input the decision log does not (use --force).
"""

import csv
import json
import sys
from pathlib import Path

from verify_candidates import check_item, load_pages, review_flags, warnings_for

from rag.review import (
    SHEET_COLUMNS,
    append_log,
    build_questions,
    decision_from_row,
    latest_decisions,
    read_log,
    review_order,
    sheet_rows,
    summary,
    unsaved_input,
)


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


CANDIDATES = Path("eval/candidates")
SPLITS = Path("eval/splits.json")
DEFECTS = Path("eval/known_defects.json")
SAMPLE = Path("eval/accept_sample.json")  # the audit sample, see eval/draw_sample.py
LOG = Path(option("--log", "eval/review_log.jsonl"))  # --log and --questions let a test run use throw-away files
QUESTIONS = Path(option("--questions", "eval/questions.jsonl"))
DOCS = ["equinor_ar2025", "havtil_framework", "havtil_management", "havtil_activities", "havtil_co2", "irena_rpgc2024"]


def load_items() -> list[dict]:
    items = []
    for path in sorted(CANDIDATES.glob("*.jsonl")):
        items += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items


def load_defects() -> dict[str, str]:
    return {k: v for k, v in json.loads(DEFECTS.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def load_prescreen(path: Path) -> dict[str, dict]:
    """The advisory pre-screen (a language model's suggestions), or {} if the file is absent."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def export() -> None:
    items, defects = load_items(), load_defects()
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["split"]
    pages_by_doc = {d: load_pages(d) for d in DOCS}
    flags = {i["id"]: [f"{kind}: {detail}" for kind, detail in review_flags(i, pages_by_doc)] + warnings_for(i)
             for i in items}
    flagged = {k for k, v in flags.items() if v}
    decisions = latest_decisions(read_log(LOG))
    prescreen = load_prescreen(Path(option("--prescreen", "eval/prescreen_suggestions.csv")))
    # Rows the pre-screen disagrees with join the flagged group, so the contested ones come first.
    flagged |= {i for i, p in prescreen.items() if p["suggestion"] != "accept"}
    sample = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["ids"]) if SAMPLE.exists() else set()
    ordered = review_order(items, splits, option("--split", "all"), flagged, set(defects), sample)
    out = Path(option("--out", "eval/review_sheet.csv"))
    rows = sheet_rows(ordered, splits, defects, flags, decisions, prescreen, sample)
    if out.exists() and "--force" not in sys.argv:
        with out.open(encoding="utf-8-sig", newline="") as f:
            lost = unsaved_input(list(csv.DictReader(f)), rows)
        if lost:
            raise SystemExit(f"{out} holds input for {len(lost)} rows that is not in the decision log "
                             f"(for example {lost[:3]}). Import it first, or pass --force to overwrite.")
    with out.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel reads the characters correctly
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(ordered)} rows to {out} (known defects first, then flagged, then the rest by id)")
    print(f"{sum(1 for i in ordered if i['id'] in decisions)} already carry a decision from the log")


def import_sheet() -> None:
    path = Path(option("--in", "eval/review_sheet.csv"))
    items = load_items()
    by_id = {i["id"]: i for i in items}
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["split"]
    pages_by_doc = {d: load_pages(d) for d in DOCS}
    decisions = latest_decisions(read_log(LOG))
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    new, same, empty, errors = 0, 0, 0, []
    for number, row in enumerate(rows, start=2):  # row 1 is the header, as in the spreadsheet
        qid = (row.get("id") or "").strip()
        if qid not in by_id:
            errors.append(f"row {number}: unknown id {qid!r}")
            continue
        try:
            record = decision_from_row(row, by_id[qid])
            if record is None:
                empty += 1
                continue
            if record["decision"] == "edit":
                problems = check_item(record["item"], pages_by_doc)
                if problems:
                    raise ValueError("the verifier rejects the edit: " + "; ".join(problems))
        except ValueError as e:
            errors.append(f"row {number} ({qid}): {e}")
            continue
        old = decisions.get(qid)
        if old and old["decision"] == record["decision"] and old.get("reason", "") == record.get("reason", "") \
                and old.get("item") == record.get("item"):
            same += 1
            continue
        append_log(LOG, record)
        new += 1

    decisions = latest_decisions(read_log(LOG))
    QUESTIONS.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in build_questions(items, decisions, splits))
                         + "\n", encoding="utf-8")
    print(f"{len(rows)} rows: {new} new decisions logged, {same} unchanged, {empty} left undecided, {len(errors)} with problems")
    for e in errors:
        print(f"  ! {e}")
    s = summary(items, decisions)
    print("\nreviewed so far (rejection rate is the measured quality number for the README):")
    for key, c in s["tiers"].items():
        print(f"  {key:<8} reviewed {c['reviewed']:>3}  accepted {c['accept']:>3}  edited {c['edit']:>3}  "
              f"rejected {c['reject']:>3}  rate {c['rejection_rate']:.0%}")
    print(f"\nlog: {LOG}   reviewed questions: {QUESTIONS}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "export":
        export()
    elif command == "import":
        import_sheet()
    else:
        raise SystemExit("usage: review_sheet.py export|import  (see the docstring for options)")


if __name__ == "__main__":
    main()
