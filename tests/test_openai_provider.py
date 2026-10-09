import os
from datetime import date, datetime
from types import SimpleNamespace

import openai
import pytest
from fastapi.testclient import TestClient

from crastinator_pro.ai import KeywordAIProvider, provider_from_env
from crastinator_pro.api import create_app
from crastinator_pro.exceptions import AIProviderError
from crastinator_pro.models import Priority
from crastinator_pro.openai_provider import OpenAIProvider, _ParsedTask
from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)  # Samstag


class FakeResponses:
    def __init__(self, output_text="", output_parsed=None, error=None):
        self.output_text = output_text
        self.output_parsed = output_parsed
        self.error = error
        self.calls = []

    def _respond(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output_text, output_parsed=self.output_parsed)

    def create(self, **kwargs):
        return self._respond(**kwargs)

    def parse(self, **kwargs):
        return self._respond(**kwargs)


def make_provider(**kwargs) -> tuple[OpenAIProvider, FakeResponses]:
    responses = FakeResponses(**kwargs)
    provider = OpenAIProvider(model="test-model", client=SimpleNamespace(responses=responses))
    return provider, responses


def parsed(**overrides) -> _ParsedTask:
    fields = dict(
        title="Bericht schreiben",
        description=None,
        due_date="2026-01-16",
        assignee_user_id=2,
        priority="high",
    )
    fields.update(overrides)
    return _ParsedTask(**fields)


# ------------------------------------------------------------ parse_task
def test_parse_task_maps_fields():
    provider, responses = make_provider(output_parsed=parsed())

    result = provider.parse_task("Dringend: Bericht für Bob nächsten Freitag schreiben", NOW)

    assert result == {
        "title": "Bericht schreiben",
        "description": None,
        "due_date": date(2026, 1, 16),
        "assignee_user_id": 2,
        "priority": Priority.HIGH,
    }
    assert responses.calls[0]["model"] == "test-model"
    assert responses.calls[0]["text_format"] is _ParsedTask


def test_parse_task_prompt_contains_reference_date_and_users():
    provider, responses = make_provider(output_parsed=parsed())

    provider.parse_task("irgendwas", NOW)

    instructions = responses.calls[0]["instructions"]
    assert "Samstag, der 2026-01-10" in instructions
    for name in ("Alice", "Bob", "Carol"):
        assert name in instructions


def test_parse_task_drops_unknown_user_and_empty_title():
    provider, _ = make_provider(output_parsed=parsed(assignee_user_id=99, title="  "))

    result = provider.parse_task("Folien machen", NOW)

    assert result["assignee_user_id"] is None
    assert result["title"] == "Folien machen"


def test_parse_task_invalid_date_raises():
    provider, _ = make_provider(output_parsed=parsed(due_date="nächste Woche"))

    with pytest.raises(AIProviderError):
        provider.parse_task("x", NOW)


def test_parse_task_without_parsed_output_raises():
    provider, _ = make_provider(output_parsed=None)

    with pytest.raises(AIProviderError):
        provider.parse_task("x", NOW)


def test_ai_create_task_via_service_uses_provider():
    provider, _ = make_provider(output_parsed=parsed())
    service = TaskService(ai_provider=provider)

    task = service.ai_create_task("Dringend: Bericht für Bob nächsten Freitag schreiben", NOW)

    assert task.title == "Bericht schreiben"
    assert task.assignee_user_id == 2
    assert task.due_date == date(2026, 1, 16)
    assert task.priority == Priority.HIGH


# ------------------------------------------------------------ answer
def test_answer_passes_tasks_and_returns_text():
    provider, responses = make_provider(output_text="  Du hast eine offene Task.  ")
    service = TaskService(ai_provider=provider)
    service.create_task(title="Folien vorbereiten", assignee_user_id=1, due_date=date(2026, 1, 5))

    answer = service.ai_ask(1, "Was ist überfällig?", NOW)

    assert answer == "Du hast eine offene Task."
    call = responses.calls[0]
    assert "Folien vorbereiten" in call["input"]
    assert "2026-01-05" in call["input"]
    assert "Was ist überfällig?" in call["input"]
    assert "2026-01-10" in call["instructions"]


def test_answer_without_tasks_still_asks_llm():
    provider, responses = make_provider(output_text="Keine Tasks.")

    assert provider.answer("Was steht an?", [], NOW) == "Keine Tasks."
    assert "keine Tasks" in responses.calls[0]["input"]


def test_answer_empty_text_raises():
    provider, _ = make_provider(output_text="   ")

    with pytest.raises(AIProviderError):
        provider.answer("?", [], NOW)


def test_openai_error_is_translated():
    provider, _ = make_provider(error=openai.APIConnectionError(request=None))

    with pytest.raises(AIProviderError):
        provider.answer("?", [], NOW)
    with pytest.raises(AIProviderError):
        provider.parse_task("x", NOW)


# ------------------------------------------------------------ API: 502
def test_api_returns_502_on_provider_error():
    provider, _ = make_provider(error=openai.APIConnectionError(request=None))
    client = TestClient(create_app(TaskService(ai_provider=provider)))

    ask = client.post("/api/users/1/ask", json={"question": "Was steht an?"})
    create = client.post("/api/tasks/ai-create", json={"text": "Folien machen"})

    assert ask.status_code == 502
    assert create.status_code == 502
    assert "OpenAI" in ask.json()["detail"]


# ------------------------------------------------------------ provider_from_env
def test_provider_from_env_defaults_to_keyword(monkeypatch):
    monkeypatch.delenv("CRASTINATOR_AI_PROVIDER", raising=False)

    assert isinstance(provider_from_env(), KeywordAIProvider)


def test_provider_from_env_openai_requires_key(monkeypatch):
    monkeypatch.setenv("CRASTINATOR_AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider_from_env()


def test_provider_from_env_openai(monkeypatch):
    monkeypatch.setenv("CRASTINATOR_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "some-model")

    provider = provider_from_env()

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "some-model"


def test_provider_from_env_unknown(monkeypatch):
    monkeypatch.setenv("CRASTINATOR_AI_PROVIDER", "magic")

    with pytest.raises(RuntimeError):
        provider_from_env()


# ------------------------------------------------------------ live (optional)
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or not os.environ.get("CRASTINATOR_LIVE_TESTS"),
    reason="Live-Test nur mit OPENAI_API_KEY und CRASTINATOR_LIVE_TESTS=1",
)
def test_live_openai_roundtrip():
    service = TaskService(ai_provider=OpenAIProvider())

    task = service.ai_create_task("Dringend: Bericht für Bob morgen schreiben", NOW)
    answer = service.ai_ask(2, "Was ist als nächstes fällig?", NOW)

    assert task.assignee_user_id == 2
    assert task.due_date == date(2026, 1, 11)
    assert task.priority == Priority.HIGH
    assert answer
