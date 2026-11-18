"""Write ready-to-paste round-2 question-generation prompts, one file per call.

Reads the template between BEGIN/END in eval/question_gen_prompt_v2.md, fills the doc id,
title, counts and the list of questions already written (round 1), and writes:

  eval/prompts/<call>.txt            the prompt to paste
  eval/prompts/attach/<call>.md      the text to attach (cleaned pages with PAGE markers)

Equinor is split into three page ranges so that each call stays small enough for exact quotes.
Run: uv run python eval/build_prompts.py [candidates_dir]
"""

import json
import sys
from pathlib import Path

import yaml

from rag import config

TEMPLATE_PATH = Path("eval/question_gen_prompt_v2.md")
OUT = Path("eval/prompts")
START, END = "---- BEGIN PROMPT ----", "---- END PROMPT ----"

HAVTIL = "numerical 1, temporal 1, comparative 1, spanning 2, relationship 1, holistic 0, unanswerable_near 1"
EQUINOR_1 = "numerical 1, temporal 1, comparative 1, spanning 1, relationship 1, holistic 0, unanswerable_near 1"
EQUINOR_2 = "numerical 1, temporal 1, comparative 1, spanning 1, relationship 0, holistic 1, unanswerable_near 1"
EQUINOR_3 = "numerical 1, temporal 0, comparative 1, spanning 1, relationship 1, holistic 0, unanswerable_near 0"
IRENA = "numerical 2, temporal 1, comparative 2, spanning 2, relationship 2, holistic 1, unanswerable_near 1"
CROSS_A = "comparative 2, spanning 2, relationship 1 (all answerable)"
CROSS_B = "comparative 1, spanning 2, relationship 2 (all answerable)"

# call name -> (doc_ids, page range or None, counts text)
CALLS = {
    "equinor_ar2025_part1": (["equinor_ar2025"], (1, 110), EQUINOR_1),
    "equinor_ar2025_part2": (["equinor_ar2025"], (111, 220), EQUINOR_2),
    "equinor_ar2025_part3": (["equinor_ar2025"], (221, 400), EQUINOR_3),
    "irena_rpgc2024": (["irena_rpgc2024"], None, IRENA),
    "havtil_framework": (["havtil_framework"], None, HAVTIL),
    "havtil_management": (["havtil_management"], None, HAVTIL),
    "havtil_activities": (["havtil_activities"], None, HAVTIL),
    "havtil_co2": (["havtil_co2"], None, HAVTIL),
    "cross_havtil_a": (["havtil_framework", "havtil_management", "havtil_activities"], None, CROSS_A),
    "cross_havtil_b": (["havtil_co2", "havtil_framework", "havtil_management"], None, CROSS_B),
}


def template() -> str:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def existing_questions(folder: Path, doc_ids: list[str]) -> str:
    lines = []
    for doc_id in doc_ids:
        path = folder / f"{doc_id}_eval.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append("- " + json.loads(line)["question"])
    return "\n".join(lines) or "(none)"


def attachment(doc_ids: list[str], pages: tuple[int, int] | None) -> str:
    parts = []
    for doc_id in doc_ids:
        with open(config.CLEANED_PAGES_DIR / f"{doc_id}.jsonl", encoding="utf-8") as f:
            for rec in map(json.loads, f):
                if pages and not pages[0] <= rec["page"] <= pages[1]:
                    continue
                parts.append(f"\n\n##### PAGE {rec['page']} ({rec['doc_id']}) #####\n\n{rec['markdown']}")
    return "".join(parts).lstrip()


def main() -> None:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/candidates")
    titles = {d["doc_id"]: d["title"] for d in
              yaml.safe_load(config.CORPUS_YAML.read_text(encoding="utf-8"))["documents"]}
    (OUT / "attach").mkdir(parents=True, exist_ok=True)
    tmpl = template()
    for name, (doc_ids, pages, counts) in CALLS.items():
        cross = len(doc_ids) > 1
        prompt = tmpl.replace("{{EXISTING_QUESTIONS}}", existing_questions(folder, doc_ids))
        prompt = prompt.replace("{{COUNTS}}", counts)
        if cross:
            docs = "; ".join(f"{d} = {titles[d]}" for d in doc_ids)
            prompt = prompt.replace("- doc_id: {{DOC_ID}}\n- title: {{TITLE}}", f"- documents: {docs}")
            first_id = f"cross-{'1' if name.endswith('_a') else '2'}01"  # a and b must not collide
            prompt = prompt.replace("{{DOC_ID}}-101", first_id)
            prompt = prompt.replace("{{DOC_ID}}", doc_ids[0])
            prompt += ("\n\nThis is a cross-document call: write only the types listed in the counts, "
                       "every question answerable, every gold list with items from at least two of "
                       f"the documents above, ids {first_id} and up.")
        else:
            prompt = prompt.replace("{{DOC_ID}}", doc_ids[0]).replace("{{TITLE}}", titles[doc_ids[0]])
        if pages:
            prompt += (f"\n\nThe attached text covers PAGES {pages[0]} to {pages[1]} only. Use only "
                       f"those pages, and give `page` as the N of the PAGE marker.")
            prompt = prompt.replace(f"{doc_ids[0]}-101", f"{doc_ids[0]}-{name[-1]}01")
        assert "{{" not in prompt, f"unfilled placeholder in {name}"
        (OUT / f"{name}.txt").write_text(prompt, encoding="utf-8")
        body = attachment(doc_ids, pages)
        (OUT / "attach" / f"{name}.md").write_text(body, encoding="utf-8")
        print(f"{name:<24} prompt {len(prompt):>6} chars  attachment {len(body):>8} chars")


if __name__ == "__main__":
    main()
