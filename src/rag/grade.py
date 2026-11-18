"""Grade retrieved chunks: do they contain what is needed to answer the question? (the trigger for query rewriting)

    grade = grade_retrieval(question, hits)
    if not grade.sufficient: ... rewrite using grade.missing

The grader sees only the question and the numbered passages, never the gold labels. It does not answer the question; it says
whether the evidence is there and, if not, what is missing. Malformed reply: treated as sufficient (no rewrite), counted by the
caller, so a broken grader cannot make the pipeline worse than plain retrieval.
"""

import json
import re
from dataclasses import dataclass

from rag import config
from rag.generation import build_prompt
from rag.index import Hit
from rag.llm import complete

GRADER_SYSTEM_PROMPT = """You check search results for a question-answering system. You get a question and numbered passages.

Decide whether the passages together contain everything needed to answer the question fully.
- "sufficient": true only if every part of the question (every fact, number, condition or comparison it asks for) is supported by the passages.
- If something is missing, set "sufficient" to false and say in "missing" what information is not in the passages, in a short phrase (what to look for, not an answer).
- Do not answer the question and do not use knowledge from outside the passages.

Reply with one JSON object and nothing else: {"sufficient": true | false, "missing": "<what is missing, or empty>"}"""


@dataclass
class Grade:
    sufficient: bool
    missing: str
    parsed: bool   # False if the reply was malformed (then sufficient is True by rule)


def parse_grade(raw: str) -> Grade:
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
        sufficient, missing = data["sufficient"], data.get("missing", "")
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return Grade(True, "", False)
    if not isinstance(sufficient, bool) or not isinstance(missing, str):
        return Grade(True, "", False)
    return Grade(sufficient, missing.strip(), True)


def grade_retrieval(question: str, hits: list[Hit], model: str | None = None) -> Grade:
    reply = complete(build_prompt(question, hits), system=GRADER_SYSTEM_PROMPT, model=model or config.GENERATION_MODEL,
                     purpose="grade")
    return parse_grade(reply.text)
