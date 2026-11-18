"""LLM summaries of table chunks, used to make tables findable by words.

A table chunk is a grid of cells and numbers. A question such as "which segment had the larger net
impairment losses" shares few words with it. One short plain-language description per table gives the
index words to match: what the table shows, the entities, the years and units, and the measures.

The summary is only put in front of the text that is embedded and indexed (chunk.embed_text); the stored
chunk text, and so every gold-evidence match, is unchanged. Summaries are keyed by a hash of the chunk
text, so a changed chunk gets a new summary and an old file can never be applied to the wrong chunk.

Prompt version 2 (17 Nov): adds the questions the table answers. Version 1 (description only) is data/table_summaries_v1.json.

Run: uv run python -m rag.table_summary --sample 5     (print 5 answers, spend about a cent)
     uv run python -m rag.table_summary --all           (every table chunk, concurrent, cached)
"""

import argparse
import json

from rag import config, llm
from rag.chunk import table_context, text_hash

SYSTEM = (
    "You write short descriptions of tables taken from annual reports and technical or legal documents. "
    "The description is added to a search index, so that someone asking a question in different words "
    "can still find the table."
)

PROMPT = """Write a description of the table below for a search index, in two parts.

Part 1, "Description": 1 or 2 plain sentences saying what the table shows, which entities or categories it
covers, the years or periods, and the unit.

Part 2, "Questions this table answers": 4 questions that a reader could answer from this table alone. Word them
the way a person would ask, not the way the table is labelled: use everyday synonyms and short forms (for example
"capital investment" for "additions to property, plant and equipment", "UK" for "United Kingdom"), and include
at least one question that compares two rows or two years.

Rules: use only what is in the table. Do not calculate or interpret. Do not invent numbers; if you mention a
figure, copy it exactly. Output only the two parts.

Where it appears: {heading}

{text}"""


def build_prompt(heading_path: list[str], text: str) -> str:
    return PROMPT.format(heading=" > ".join(heading_path) or "(no heading)", text=text)


def load_chunks() -> list[dict]:
    return [json.loads(line) for line in config.CHUNKS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def table_chunks(chunks: list[dict]) -> list[dict]:
    return [c for c in chunks if table_context(c["text"])]


def summarise(chunks: list[dict]) -> dict[str, str]:
    prompts = [build_prompt(c["heading_path"], c["text"]) for c in chunks]
    results = llm.complete_many(prompts, system=SYSTEM, purpose="table_summary",
                                max_concurrency=config.TABLE_SUMMARY_CONCURRENCY)
    return {text_hash(c["text"]): r.text.strip() for c, r in zip(chunks, results)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, help="summarise this many chunks and print them; nothing is saved")
    parser.add_argument("--all", action="store_true", help="summarise every table chunk and save the file")
    args = parser.parse_args()
    tables = table_chunks(load_chunks())
    print(f"{len(tables)} table chunks")
    if args.sample:
        step = max(1, len(tables) // args.sample)   # spread over the documents, not the first five
        picked = tables[::step][: args.sample]
        for c, summary in zip(picked, summarise(picked).values()):
            print(f"\n=== {c['chunk_id']} p{c['page']} [{' > '.join(c['heading_path'])}]\n{c['text'][:260]!r}\n--> {summary}")
        return
    if args.all:
        summaries = summarise(tables)
        config.TABLE_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.TABLE_SUMMARY_PATH.write_text(json.dumps(summaries, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{len(summaries)} summaries -> {config.TABLE_SUMMARY_PATH}; spent so far ${llm.spent_usd():.4f}")
        return
    parser.error("give --sample N or --all")


if __name__ == "__main__":
    main()
