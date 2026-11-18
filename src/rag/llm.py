"""The one place that calls the LLM.

    result = complete("Describe this table: ...")
    result.text, result.cached, result.cost_usd

Every call: temperature 0, retried on transient errors, cached on disk by a hash of everything that
shapes the answer (so a rerun costs nothing), logged (tokens, latency, cost), and refused once the
logged spend reaches the budget cap. Keys are read from .env (OPENAI_API_KEY for OpenAI).

Model agnostic: the model is a LangChain "provider:model" string, e.g. "openai:gpt-4o-mini". To use another
provider, install its langchain package, change config.LLM_MODEL and add its price to config.LLM_PRICES.
Nothing else in this file names a provider.
"""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, messages_from_dict, messages_to_dict
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from rag import config


class BudgetExceeded(RuntimeError):
    """The logged spend has reached config.LLM_BUDGET_USD."""


@dataclass
class LLMResult:
    text: str
    cached: bool
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float   # 0.0 for a cached answer: nothing was spent this time


_models: dict = {}


def get_model(name: str):
    """One LangChain chat model per "provider:model" name. max_retries=0 because retrying is done here, the same for every provider."""
    if name not in _models:
        load_dotenv()  # reads the provider key from .env; never printed or logged
        _models[name] = init_chat_model(name, max_retries=0, **model_params(name))
    return _models[name]


def model_params(model: str) -> dict:
    """Call parameters for one model. Most models get temperature 0; some (gpt-5-nano) refuse that and get their own set."""
    return config.LLM_MODEL_PARAMS.get(model, {"temperature": config.LLM_TEMPERATURE})


def cache_key(model: str, system: str, prompt: str) -> str:
    """Hash of everything that can change the answer. Change the model, its parameters or any word and it is a new call."""
    payload = json.dumps({"model": model, "params": model_params(model), "system": system, "prompt": prompt},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = config.LLM_PRICES[model]
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def spent_usd() -> float:
    """Total cost of the calls in the log. Cached answers were logged with cost 0."""
    if not config.LLM_LOG_PATH.exists():
        return 0.0
    lines = config.LLM_LOG_PATH.read_text(encoding="utf-8").splitlines()
    return sum(json.loads(line)["cost_usd"] for line in lines if line.strip())


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _log(record: dict) -> None:
    config.LLM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LLM_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def is_transient(error: BaseException) -> bool:
    """Can this error go away on its own? Judged from the HTTP status or the error's name, so it holds for any provider.

    Retried: 408/409/429 and 5xx, timeouts, dropped connections. Not retried: a wrong key (401), a bad request (400),
    anything unknown: retrying cannot fix those and would only repeat a charge or hide a bug.
    """
    status = getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)
    if isinstance(status, int):
        return status in (408, 409, 429) or status >= 500
    name = type(error).__name__.lower()
    return isinstance(error, (TimeoutError, ConnectionError)) or any(w in name for w in ("timeout", "connection"))


def _call_api(model, system: str, prompt: str):
    @retry(retry=retry_if_exception(is_transient), stop=stop_after_attempt(config.LLM_RETRY_ATTEMPTS),
           wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
    def go():
        messages = ([("system", system)] if system else []) + [("human", prompt)]
        return model.invoke(messages)

    return go()


def complete(prompt: str, system: str = "", model: str | None = None, purpose: str = "", chat_model=None) -> LLMResult:
    """Answer `prompt`. `purpose` is a free label written to the log (e.g. "table_summary") so spend can be split by use."""
    model = model or config.LLM_MODEL
    key = cache_key(model, system, prompt)
    cache_file = config.LLM_CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        hit = json.loads(cache_file.read_text(encoding="utf-8"))
        _log({"time_utc": datetime.now(UTC).isoformat(timespec="seconds"), "model": model, "purpose": purpose, "key": key[:12],
              "cached": True, "prompt_tokens": hit["prompt_tokens"], "completion_tokens": hit["completion_tokens"],
              "latency_s": 0.0, "cost_usd": 0.0})
        return LLMResult(hit["text"], True, hit["prompt_tokens"], hit["completion_tokens"], 0.0, 0.0)

    if model not in config.LLM_PRICES:
        # Checked before the call: failing after it would spend money and lose the answer.
        raise KeyError(f"no price for model {model!r} in config.LLM_PRICES; add it so the budget cap can work")
    spent = spent_usd()
    if spent >= config.LLM_BUDGET_USD:
        raise BudgetExceeded(f"spent ${spent:.4f} of the ${config.LLM_BUDGET_USD:.2f} cap; raise LLM_BUDGET_USD on purpose to go on")

    started = time.perf_counter()
    response = _call_api(chat_model or get_model(model), system, prompt)
    latency = time.perf_counter() - started
    text = response.content if isinstance(response.content, str) else "".join(
        part.get("text", "") if isinstance(part, dict) else str(part) for part in response.content)
    usage = response.usage_metadata or {}   # LangChain reports tokens the same way for every provider
    prompt_tokens, completion_tokens = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    cost = cost_of(model, prompt_tokens, completion_tokens)

    config.LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"text": text, "prompt_tokens": prompt_tokens,
                                      "completion_tokens": completion_tokens}, ensure_ascii=False), encoding="utf-8")
    _log({"time_utc": datetime.now(UTC).isoformat(timespec="seconds"), "model": model, "purpose": purpose, "key": key[:12],
          "cached": False, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
          "latency_s": round(latency, 3), "cost_usd": cost})
    return LLMResult(text, False, prompt_tokens, completion_tokens, latency, cost)


@dataclass
class ChatResult:
    message: AIMessage   # the model's reply; `.tool_calls` is non-empty when it wants to call a tool
    cached: bool
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float


def _message_key(m) -> dict:
    """The parts of a message that shape the next answer. Message ids are left out: they are random per call."""
    return {"type": m.type, "content": m.content, "tool_call_id": getattr(m, "tool_call_id", None),
            "tool_calls": [(c["name"], c["args"]) for c in getattr(m, "tool_calls", [])]}


def chat(messages: list, tools: list[dict] | None = None, model: str | None = None, purpose: str = "") -> ChatResult:
    """One turn of a conversation that may use tools. `messages` are LangChain messages (system, human, ai, tool);
    `tools` are OpenAI-style tool schemas. Same rules as complete(): cached by hash, retried, logged, budget-checked."""
    model = model or config.LLM_MODEL
    payload = json.dumps({"model": model, "params": model_params(model), "tools": tools or [],
                          "messages": [_message_key(m) for m in messages]}, sort_keys=True, ensure_ascii=False)
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    cache_file = config.LLM_CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        hit = json.loads(cache_file.read_text(encoding="utf-8"))
        _log({"time_utc": _now(), "model": model, "purpose": purpose, "key": key[:12], "cached": True,
              "prompt_tokens": hit["prompt_tokens"], "completion_tokens": hit["completion_tokens"],
              "latency_s": 0.0, "cost_usd": 0.0})
        return ChatResult(messages_from_dict([hit["message"]])[0], True, hit["prompt_tokens"], hit["completion_tokens"], 0.0, 0.0)

    if model not in config.LLM_PRICES:
        raise KeyError(f"no price for model {model!r} in config.LLM_PRICES; add it so the budget cap can work")
    spent = spent_usd()
    if spent >= config.LLM_BUDGET_USD:
        raise BudgetExceeded(f"spent ${spent:.4f} of the ${config.LLM_BUDGET_USD:.2f} cap; raise LLM_BUDGET_USD on purpose to go on")

    chat_model = get_model(model)
    if tools:
        chat_model = chat_model.bind_tools(tools)

    @retry(retry=retry_if_exception(is_transient), stop=stop_after_attempt(config.LLM_RETRY_ATTEMPTS),
           wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
    def go():
        return chat_model.invoke(messages)

    started = time.perf_counter()
    response = go()
    latency = time.perf_counter() - started
    usage = response.usage_metadata or {}
    prompt_tokens, completion_tokens = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    cost = cost_of(model, prompt_tokens, completion_tokens)

    config.LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"message": messages_to_dict([response])[0], "prompt_tokens": prompt_tokens,
                                      "completion_tokens": completion_tokens}, ensure_ascii=False), encoding="utf-8")
    _log({"time_utc": _now(), "model": model, "purpose": purpose, "key": key[:12], "cached": False,
          "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "latency_s": round(latency, 3),
          "cost_usd": cost})
    return ChatResult(response, False, prompt_tokens, completion_tokens, latency, cost)


def complete_many(prompts: list[str], system: str = "", model: str | None = None, purpose: str = "",
                  max_concurrency: int = 8, chat_model=None) -> list[LLMResult]:
    """Answer many prompts at once, in the same order. Each prompt goes through complete(), so every one is cached,
    retried, logged and budget-checked. Concurrency only saves waiting time; it does not change the answers.

    The budget is checked per call, so up to `max_concurrency` calls already in flight can overshoot the cap slightly.
    """
    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        futures = [pool.submit(complete, p, system, model, purpose, chat_model) for p in prompts]
        return [f.result() for f in futures]
