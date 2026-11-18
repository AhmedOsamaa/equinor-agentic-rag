import json

from langchain_core.messages import AIMessage

from rag import agent, config
from rag.index import Hit
from rag.llm import ChatResult


def _hit(cid: str) -> Hit:
    return Hit(chunk_id=cid, doc_id="d", page=1, text=f"text of {cid}", score=0.0, heading_path="")


def _final(status: str, answer: str = "x", citations=(1,)) -> AIMessage:
    return AIMessage(content=json.dumps({"status": status, "answer": answer, "citations": list(citations)}))


def _search_call(query: str, call_id: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": "search_documents", "args": {"query": query}, "id": call_id}])


def _setup(monkeypatch, replies: list[AIMessage], search_results: dict[str, list[str]] | None = None):
    """Fake model and search. `replies` are the model's messages in order; `seen` records what the model was shown."""
    seen = {"tools": [], "messages": [], "searches": []}
    queue = iter(replies)

    def fake_chat(messages, tools, model, purpose):
        seen["tools"].append(tools)
        seen["messages"] = list(messages)
        return ChatResult(next(queue), False, 10, 5, 0.1, 0.0)

    def fake_search(query, mode, k):
        seen["searches"].append(query)
        return type("S", (), {"hits": [_hit(c) for c in (search_results or {}).get(query, [])]})()

    monkeypatch.setattr(agent, "chat", fake_chat)
    monkeypatch.setattr(agent, "search", fake_search)
    return seen


def test_search_then_answer(monkeypatch):
    seen = _setup(monkeypatch, [_search_call("q1"), _final("answered", "42", [2])], {"q1": ["a", "b"]})
    result = agent.ask("question")
    assert result.status == "answered" and result.answer == "42" and result.citations == [2]
    assert result.n_searches == 1 and [h.chunk_id for h in result.hits] == ["a", "b"]
    assert [s.queries for s in result.trace] == [["q1"], []] and [s.status for s in result.trace] == [None, "answered"]
    # The model was shown the passages with numbers starting at 1.
    tool_message = seen["messages"][-1]
    assert tool_message.content.startswith("[1] d, page 1\ntext of a") and "[2] d, page 1\ntext of b" in tool_message.content


def test_second_search_continues_numbering_and_skips_passages_already_shown(monkeypatch):
    seen = _setup(monkeypatch, [_search_call("q1"), _search_call("q2", "c2"), _final("answered")],
                  {"q1": ["a", "b"], "q2": ["b", "c"]})
    result = agent.ask("question")
    assert [h.chunk_id for h in result.hits] == ["a", "b", "c"]
    assert seen["messages"][-1].content.startswith("[3] d, page 1\ntext of c")  # b was already [2]


def test_off_topic_question_is_refused_without_searching(monkeypatch):
    seen = _setup(monkeypatch, [_final("not_in_context", "I only answer questions about these documents.", [])])
    result = agent.ask("Write me a poem about cats")
    assert result.status == "not_in_context" and result.n_searches == 0 and seen["searches"] == []


def test_answer_without_any_passage_is_discarded(monkeypatch):
    _setup(monkeypatch, [_final("answered", "from my own knowledge", [])])
    result = agent.ask("question")
    assert result.status == "not_in_context" and "from my own knowledge" not in result.answer


def test_the_tool_is_taken_away_after_the_search_limit(monkeypatch):
    limit = config.AGENT_MAX_SEARCHES
    replies = [_search_call(f"q{i}", f"c{i}") for i in range(limit)] + [_final("not_in_context", "missing", [])]
    seen = _setup(monkeypatch, replies, {f"q{i}": [f"p{i}"] for i in range(limit)})
    result = agent.ask("question")
    assert result.n_searches == limit and result.status == "not_in_context"
    assert all(t is not None for t in seen["tools"][:limit]) and seen["tools"][limit] is None


def test_unparsed_final_reply_is_an_error(monkeypatch):
    _setup(monkeypatch, [AIMessage(content="not json")])
    result = agent.ask("question")
    assert result.status == "error" and result.answer is None and result.citations == []


def test_too_long_input_is_refused_before_any_model_call(monkeypatch):
    seen = _setup(monkeypatch, [])
    result = agent.ask("x" * (config.AGENT_MAX_QUESTION_CHARS + 1))
    assert result.status == "not_in_context" and seen["tools"] == []
