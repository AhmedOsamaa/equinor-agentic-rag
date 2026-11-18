"""Logic behind the review loop (eval/review.py): decision log, review order, assembling the
reviewed question file, and the rejection-rate summary.

The log is append-only: every decision is one JSON line, and the latest line per question id
wins. `eval/questions.jsonl` is rebuilt from the log, so it never holds an unreviewed question.
Rejected ids are dropped, never re-split: `eval/splits.json` is not touched here.
"""

import copy
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from rag.splits import round_of

EDITABLE = ("question", "reference_answer", "type", "format", "behaviour", "notes")


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_log(path: Path, record: dict) -> None:
    record = {**record, "time": datetime.now(UTC).isoformat(timespec="seconds")}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + chr(10))


def latest_decisions(log: list[dict]) -> dict[str, dict]:
    """The last logged decision per question id; a later line overrides an earlier one."""
    return {r["id"]: r for r in log}


def review_order(items: list[dict], splits: dict[str, str], which: str,
                 flagged: set[str], defects: set[str], sample: set[str] | frozenset = frozenset()) -> list[dict]:
    """Items of one split (or "all"): known defects first, then flagged ones, then the audit
    sample, then the rest by id."""
    chosen = [i for i in items if which == "all" or splits[i["id"]] == which]
    rank = lambda i: 0 if i["id"] in defects else 1 if i["id"] in flagged else 2 if i["id"] in sample else 3
    return sorted(chosen, key=lambda i: (rank(i), i["id"]))


def draw_sample(ids: list[str], n: int, seed: int) -> list[str]:
    """A reproducible random sample of n ids (sorted, so the same ids and seed always give the same list)."""
    if n > len(ids):
        raise ValueError(f"cannot draw {n} from {len(ids)}")
    return sorted(random.Random(seed).sample(sorted(ids), n))


def apply_edit(item: dict, field: str, value: str) -> dict:
    """A copy of the item with one text or label field changed."""
    if field not in EDITABLE:
        raise ValueError(f"cannot edit {field!r}; editable: {EDITABLE}")
    out = copy.deepcopy(item)
    out[field] = value
    return out


def drop_gold(item: dict, index: int) -> dict:
    """A copy of the item without the gold entry at `index` (0-based)."""
    if not 0 <= index < len(item.get("gold", [])):
        raise ValueError(f"no gold entry {index}")
    out = copy.deepcopy(item)
    del out["gold"][index]
    return out


def build_questions(items: list[dict], decisions: dict[str, dict], splits: dict[str, str]) -> list[dict]:
    """Accepted and edited questions, with their split and review status; rejected and undecided
    questions are left out."""
    out = []
    for item in sorted(items, key=lambda i: i["id"]):
        d = decisions.get(item["id"])
        if not d or d["decision"] == "reject":
            continue
        final = d["item"] if d["decision"] == "edit" else item
        out.append({**final, "split": splits[item["id"]],
                    "review": {"status": "edited" if d["decision"] == "edit" else "accepted"}})
    return out


def summary(items: list[dict], decisions: dict[str, dict]) -> dict:
    """Counts per tier and overall: reviewed, accepted, edited, rejected, rejection rate, reasons."""
    tiers: dict[str, Counter] = defaultdict(Counter)
    reasons = Counter()
    for item in items:
        d = decisions.get(item["id"])
        if not d:
            continue
        for key in (f"round_{round_of(item)}", "all"):
            tiers[key]["reviewed"] += 1
            tiers[key][d["decision"]] += 1
        if d["decision"] == "reject":
            reasons[d.get("reason", "")] += 1
    out = {}
    for key, c in sorted(tiers.items()):
        out[key] = {"reviewed": c["reviewed"], "accept": c["accept"], "edit": c["edit"], "reject": c["reject"],
                    "rejection_rate": c["reject"] / c["reviewed"]}
    return {"tiers": out, "reject_reasons": dict(reasons)}


# ---------------------------------------------------------------------- spreadsheet round trip

SHEET_INFO = ["id", "tier", "split", "known_defect", "flags", "prescreen", "prescreen_reason", "sample", "type", "format", "behaviour",
              "question", "reference_answer", "gold_1", "gold_2", "gold_3"]
SHEET_INPUT = ["decision", "reason", "new_question", "new_answer", "new_type", "new_format", "new_behaviour",
               "drop_gold"]
SHEET_COLUMNS = SHEET_INFO + SHEET_INPUT
_DECISION_WORDS = {"a": "accept", "accept": "accept", "e": "edit", "edit": "edit", "r": "reject", "reject": "reject"}
_NEW_FIELDS = {"new_question": "question", "new_answer": "reference_answer", "new_type": "type",
               "new_format": "format", "new_behaviour": "behaviour"}


def sheet_rows(items: list[dict], splits: dict[str, str], defects: dict[str, str],
               flags: dict[str, list[str]], decisions: dict[str, dict],
               prescreen: dict[str, dict] | None = None, sample: set[str] | frozenset = frozenset()) -> list[dict]:
    """One row per item: read-only information first, then the empty (or already decided) input
    columns. The gold entries sit in their own columns so they stay readable in a spreadsheet.

    `prescreen` (id -> {suggestion, category, reason}) is an advisory model opinion shown in two
    read-only columns; it never fills the decision column."""
    prescreen = prescreen or {}
    rows = []
    for item in items:
        p = prescreen.get(item["id"])
        gold = [f"{g['doc_id']} p{g['page']}: {g['evidence_quote']}" for g in item.get("gold", [])]
        d = decisions.get(item["id"], {})
        row = {"id": item["id"], "tier": round_of(item), "split": splits[item["id"]],
               "known_defect": defects.get(item["id"], ""), "flags": " | ".join(flags.get(item["id"], [])),
               "prescreen": f"{p['suggestion']}: {p['category']}" if p else "",
               "prescreen_reason": p["reason"] if p else "",
               "sample": "READ THIS ONE (audit sample of pre-screen accepts)" if item["id"] in sample else "",
               "type": item["type"], "format": item["format"], "behaviour": item["behaviour"],
               "question": item["question"], "reference_answer": item.get("reference_answer", ""),
               **{f"gold_{n + 1}": (gold[n] if n < len(gold) else "") for n in range(3)},
               **{c: "" for c in SHEET_INPUT}}
        if d:
            row["decision"], row["reason"] = d["decision"], d.get("reason", "")
        rows.append(row)
    return rows


def decision_from_row(row: dict, item: dict) -> dict | None:
    """The log record for a filled-in sheet row, or None if the decision cell is empty.

    Raises ValueError with a message the reviewer can act on (unknown word, reject without a
    reason, an edit that changes nothing, a gold number that does not exist)."""
    word = (row.get("decision") or "").strip().lower()
    if not word:
        return None
    if word not in _DECISION_WORDS:
        raise ValueError(f"decision {word!r} is not accept, edit or reject")
    decision, reason = _DECISION_WORDS[word], (row.get("reason") or "").strip()
    if decision == "accept":
        return {"id": item["id"], "decision": "accept"}
    if decision == "reject":
        if not reason:
            raise ValueError("a rejection needs a reason")
        return {"id": item["id"], "decision": "reject", "reason": reason}
    edited = item
    for column, field in _NEW_FIELDS.items():
        value = (row.get(column) or "").strip()
        if value:
            edited = apply_edit(edited, field, value)
    drop = sorted({int(x) for x in (row.get("drop_gold") or "").replace(",", " ").split()}, reverse=True)
    for number in drop:  # the sheet counts gold from 1; highest first so the numbers stay valid
        if not 1 <= number <= len(item.get("gold", [])):
            raise ValueError(f"drop_gold {number}: this question has {len(item.get('gold', []))} gold entries")
        edited = drop_gold(edited, number - 1)
    if edited == item:
        raise ValueError("decision is edit but no new_* or drop_gold cell is filled")
    return {"id": item["id"], "decision": "edit", "reason": reason or "edited in the sheet", "item": edited}


def unsaved_input(existing: list[dict], new: list[dict]) -> list[str]:
    """Ids whose input cells in an existing sheet hold something the new export would not write.

    Re-exporting over such a sheet would silently destroy the reviewer's work, so the export script
    refuses unless forced. A cell the new export reproduces (a decision already in the log) is fine."""
    new_by_id = {r["id"]: r for r in new}
    lost = []
    for row in existing:
        fresh = new_by_id.get(row.get("id"), {})
        if any((row.get(c) or "").strip() and (row.get(c) or "").strip() != (fresh.get(c) or "").strip()
               for c in SHEET_INPUT):
            lost.append(row.get("id"))
    return lost
