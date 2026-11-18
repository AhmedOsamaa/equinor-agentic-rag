"""LLM client tests with a fake chat model: no network, no cost."""

from types import SimpleNamespace

import pytest

from rag import config, llm


class HttpError(Exception):
    """Any provider's error that carries an HTTP status code."""

    def __init__(self, status_code):
        super().__init__(f"http {status_code}")
        self.status_code = status_code


class FakeModel:
    """Stands in for a LangChain chat model: counts calls, can fail first, reports tokens like LangChain does."""

    def __init__(self, text="answer", fail_times=0, error=None):
        self.calls, self.fail_times, self.text = 0, fail_times, text
        self.error = error or HttpError(429)

    def invoke(self, messages):
        self.calls += 1
        self.messages = messages
        if self.calls <= self.fail_times:
            raise self.error
        return SimpleNamespace(content=self.text, usage_metadata={"input_tokens": 1000, "output_tokens": 200})


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LLM_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "LLM_LOG_PATH", tmp_path / "calls.jsonl")
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)  # do not really wait between retries


def test_the_second_identical_call_is_answered_from_the_cache_and_costs_nothing():
    fake = FakeModel()
    first = llm.complete("hello", chat_model=fake)
    second = llm.complete("hello", chat_model=fake)
    assert fake.calls == 1                      # the model was called once
    assert not first.cached and second.cached and second.text == first.text
    assert second.cost_usd == 0.0 and second.latency_s == 0.0


def test_any_change_to_the_prompt_system_or_model_is_a_new_call(monkeypatch):
    monkeypatch.setitem(config.LLM_PRICES, "anthropic:some-model", (3.0, 15.0))
    fake = FakeModel()
    llm.complete("hello", chat_model=fake)
    llm.complete("hello!", chat_model=fake)
    llm.complete("hello", system="be brief", chat_model=fake)
    llm.complete("hello", model="anthropic:some-model", chat_model=fake)
    assert fake.calls == 4


def test_cost_is_tokens_times_price_per_million():
    # 1000 input tokens at 0.15 and 200 output tokens at 0.60 per million: 0.00015 + 0.00012
    assert llm.cost_of("openai:gpt-4o-mini", 1000, 200) == pytest.approx(0.00027)


def test_system_and_user_messages_are_sent_in_order():
    fake = FakeModel()
    llm.complete("the question", system="be brief", chat_model=fake)
    assert fake.messages == [("system", "be brief"), ("human", "the question")]
    llm.complete("another", chat_model=fake)
    assert fake.messages == [("human", "another")]


def test_the_model_is_built_with_temperature_zero_and_no_provider_retries(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "_models", {})
    monkeypatch.setattr(llm, "init_chat_model", lambda name, **kw: seen.update(name=name, **kw) or FakeModel())
    llm.get_model("openai:gpt-4o-mini")
    assert seen == {"name": "openai:gpt-4o-mini", "temperature": 0, "max_retries": 0}


def test_nano_is_built_without_temperature_and_with_minimal_reasoning(monkeypatch):
    # gpt-5-nano answers 400 to temperature 0, so it must not be passed.
    seen = {}
    monkeypatch.setattr(llm, "_models", {})
    monkeypatch.setattr(llm, "init_chat_model", lambda name, **kw: seen.update(name=name, **kw) or FakeModel())
    llm.get_model("openai:gpt-5-nano")
    assert seen == {"name": "openai:gpt-5-nano", "max_retries": 0, "reasoning_effort": "minimal"}


def test_the_cache_key_changes_with_the_model_parameters(monkeypatch):
    before = llm.cache_key("openai:gpt-5-nano", "", "q")
    monkeypatch.setitem(config.LLM_MODEL_PARAMS, "openai:gpt-5-nano", {"reasoning_effort": "low"})
    assert llm.cache_key("openai:gpt-5-nano", "", "q") != before


def test_a_transient_error_is_retried_and_then_succeeds():
    fake = FakeModel(fail_times=2)
    assert llm.complete("hello", chat_model=fake).text == "answer"
    assert fake.calls == 3


def test_retries_stop_after_the_configured_number_of_attempts():
    fake = FakeModel(fail_times=99)
    with pytest.raises(HttpError):
        llm.complete("hello", chat_model=fake)
    assert fake.calls == config.LLM_RETRY_ATTEMPTS


def test_a_wrong_key_or_bad_request_is_not_retried():
    fake = FakeModel(fail_times=99, error=HttpError(401))
    with pytest.raises(HttpError):
        llm.complete("hello", chat_model=fake)
    assert fake.calls == 1


def test_which_errors_count_as_transient_does_not_depend_on_the_provider():
    class ReadTimeout(Exception):
        pass

    class RemoteConnectionDropped(Exception):
        pass

    assert llm.is_transient(HttpError(429)) and llm.is_transient(HttpError(503)) and llm.is_transient(HttpError(408))
    assert not llm.is_transient(HttpError(400)) and not llm.is_transient(HttpError(401)) and not llm.is_transient(HttpError(404))
    assert llm.is_transient(ReadTimeout()) and llm.is_transient(RemoteConnectionDropped()) and llm.is_transient(TimeoutError())
    assert not llm.is_transient(ValueError("bad prompt"))


def test_the_status_is_also_found_on_the_response_object():
    err = Exception("boom")
    err.response = SimpleNamespace(status_code=500)
    assert llm.is_transient(err)


def test_every_call_is_logged_and_spend_adds_up_but_cached_answers_add_nothing():
    fake = FakeModel()
    llm.complete("a", purpose="t", chat_model=fake)
    llm.complete("a", purpose="t", chat_model=fake)     # cached
    llm.complete("b", purpose="t", chat_model=fake)
    assert llm.spent_usd() == pytest.approx(2 * 0.00027)
    lines = config.LLM_LOG_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and '"cached": true' in lines[1]


def test_a_call_is_refused_once_the_budget_is_reached_but_cached_answers_still_work(monkeypatch):
    fake = FakeModel()
    llm.complete("a", chat_model=fake)
    monkeypatch.setattr(config, "LLM_BUDGET_USD", 0.0001)   # already below what was spent
    with pytest.raises(llm.BudgetExceeded):
        llm.complete("new prompt", chat_model=fake)
    assert llm.complete("a", chat_model=fake).cached        # no new spend, so it is allowed


def test_a_model_without_a_price_is_refused_before_any_call_is_made():
    fake = FakeModel()
    with pytest.raises(KeyError, match="no price"):
        llm.complete("hello", model="some:unpriced-model", chat_model=fake)
    assert fake.calls == 0


def test_complete_many_keeps_the_order_and_logs_every_call():
    class Echo:
        def invoke(self, messages):
            return SimpleNamespace(content="re:" + messages[-1][1], usage_metadata={"input_tokens": 10, "output_tokens": 5})

    prompts = [f"q{i}" for i in range(20)]
    out = llm.complete_many(prompts, chat_model=Echo(), max_concurrency=4)
    assert [r.text for r in out] == [f"re:q{i}" for i in range(20)]
    assert len(config.LLM_LOG_PATH.read_text(encoding="utf-8").splitlines()) == 20   # no lost or torn lines
    assert all(r.cached for r in llm.complete_many(prompts, chat_model=Echo()))      # a second pass is free
