from rag.generation import build_prompt, parse_answer
from rag.index import Hit


def hit(doc, page, text):
    return Hit(chunk_id=f"{doc}-{page}", score=1.0, doc_id=doc, page=page, heading_path="", text=text)


def test_prompt_numbers_passages_from_one_with_document_and_page():
    prompt = build_prompt("Why?", [hit("irena_rpgc2024", 12, "Solar fell."), hit("havtil_co2", 3, "Section 1.")])
    assert "[1] irena_rpgc2024, page 12\nSolar fell." in prompt
    assert "[2] havtil_co2, page 3\nSection 1." in prompt
    assert prompt.endswith("Question: Why?")


def test_a_valid_reply_is_parsed():
    a = parse_answer('{"status": "answered", "answer": "42 TWh", "citations": [2, 5]}')
    assert (a.status, a.answer, a.citations) == ("answered", "42 TWh", [2, 5])


def test_a_json_fence_is_accepted():
    assert parse_answer('```json\n{"status": "not_in_context", "answer": "no year", "citations": []}\n```').status == "not_in_context"


def test_bad_replies_are_none_not_repaired():
    assert parse_answer("The answer is 42.") is None
    assert parse_answer('{"status": "maybe", "answer": "x", "citations": []}') is None   # unknown status
    assert parse_answer('{"status": "answered", "answer": "x"}') is None                  # citations missing
