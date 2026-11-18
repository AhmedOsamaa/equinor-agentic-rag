"""Answer one question from retrieved chunks, with a status the eval can count.

    prompt = build_prompt(question, hits)
    answer = parse_answer(complete(prompt, system=SYSTEM_PROMPT, model=config.GENERATION_MODEL).text)

The model must reply with a small JSON object: a status (answered / not_in_context / ambiguous), the answer, and the numbers
of the chunks it used. The status lets us count refusals on unanswerable questions without reading every answer; the chunk
numbers let us check mechanically whether a cited chunk really holds the gold quote. JSON is asked for in the prompt and parsed
here (not the API's structured-output mode), so a malformed reply is a measurable failure instead of a hidden retry.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from rag.index import Hit

SYSTEM_PROMPT = """You answer questions about six public energy documents: the Equinor Annual Report 2025, four Havtil regulations (Framework, Management, Activities, CO2 Safety) and the IRENA report "Renewable Power Generation Costs in 2024".

You are given numbered context passages. Each starts with its document and page. Follow these rules:
1. Use only the context passages. Do not use anything you know from elsewhere, even if you are sure of it.
2. Every claim in your answer must be supported by a passage. Give the numbers of the passages you used in "citations".
3. If the passages do not contain the answer, set "status" to "not_in_context" and say in "answer" what is missing. Do not guess and do not give a nearby number instead.
4. If the passages contain relevant information but the question has more than one reasonable reading (for example it does not say which year, which technology or which measure), set "status" to "ambiguous" and say in "answer" which readings are possible and what you would need to know.
5. Otherwise set "status" to "answered". Keep the answer short and keep numbers and units exactly as they appear in the passage.

Reply with one JSON object and nothing else:
{"status": "answered" | "not_in_context" | "ambiguous", "answer": "<text>", "citations": [<passage numbers>]}
For "not_in_context" and "ambiguous", "citations" lists the passages that were relevant, or is empty."""


# Closed-book baseline: same reply format, same models, but no passages. It measures how much of the question set a model
# can answer from what it already knows (the leakage limitation), so the RAG numbers can be read against it.
CLOSED_BOOK_SYSTEM_PROMPT = """You answer questions about six public energy documents: the Equinor Annual Report 2025, four Havtil regulations (Framework, Management, Activities, CO2 Safety) and the IRENA report "Renewable Power Generation Costs in 2024".

No passages are provided. Answer from your own knowledge of these documents. Follow these rules:
1. If you do not know the answer, set "status" to "not_in_context" and say what you do not know. Do not guess and do not give a nearby number instead.
2. If the question has more than one reasonable reading (for example it does not say which year, which technology or which measure), set "status" to "ambiguous" and say which readings are possible.
3. Otherwise set "status" to "answered". Keep the answer short and keep numbers and units exact.

Reply with one JSON object and nothing else:
{"status": "answered" | "not_in_context" | "ambiguous", "answer": "<text>", "citations": []}"""


class Answer(BaseModel):
    status: Literal["answered", "not_in_context", "ambiguous"]
    answer: str
    citations: list[int]


def build_prompt(question: str, hits: list[Hit]) -> str:
    """Numbered passages (1-based, in retrieval order) with document and page, then the question."""
    passages = [f"[{i}] {h.doc_id}, page {h.page}\n{h.text}" for i, h in enumerate(hits, start=1)]
    return "Context passages:\n\n" + "\n\n".join(passages) + f"\n\nQuestion: {question}"


def parse_answer(raw: str) -> Answer | None:
    """The reply as an Answer, or None if it is not valid JSON of the right shape. None is counted as a failure, never repaired
    by guessing. A reply wrapped in a ```json fence is accepted: that is formatting, not a wrong answer."""
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return Answer.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError):
        return None
