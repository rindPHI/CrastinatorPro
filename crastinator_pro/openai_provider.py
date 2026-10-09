"""KI-Provider auf Basis der OpenAI Responses API.

Implementiert dieselbe `AIProvider`-Schnittstelle wie der `KeywordAIProvider`.
Freitext-Fragen beantwortet das LLM auf Basis der übergebenen Tasks; für die
Task-Anlage liefert es per Structured Output die Felder, die anschließend wie
beim Keyword-Provider an `TaskService.create_task` gehen.

Konfiguration über Umgebungsvariablen: `OPENAI_API_KEY` (Pflicht) und
`OPENAI_MODEL` (optional, Default `DEFAULT_MODEL`).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

from .ai import AIProvider
from .exceptions import AIProviderError
from .models import USERS, Priority, Task

DEFAULT_MODEL = "gpt-5.4-mini"

_WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class _ParsedTask(BaseModel):
    title: str
    description: Optional[str]
    due_date: Optional[str]
    assignee_user_id: Optional[int]
    priority: Literal["low", "medium", "high"]


def _today_line(reference_time: datetime) -> str:
    today = reference_time.date()
    return f"Heute ist {_WEEKDAYS_DE[today.weekday()]}, der {today.isoformat()}."


def _users_line() -> str:
    return ", ".join(f"{user.name} (ID {user.id})" for user in USERS.values())


def _task_to_dict(task: Task) -> dict:
    assignee = USERS.get(task.assignee_user_id) if task.assignee_user_id is not None else None
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "dueDate": task.due_date.isoformat() if task.due_date else None,
        "completed": task.completed,
        "priority": task.priority.value,
        "assignee": assignee.name if assignee else None,
    }


_ANSWER_INSTRUCTIONS = """\
Du bist der KI-Assistent der Task-Management-App "Crastinator Pro".
Beantworte die Frage des Users knapp und auf Deutsch, ausschließlich auf Basis
der unten aufgeführten Tasks dieses Users. Erfinde keine Tasks. Eine Task ist
überfällig, wenn ihr dueDate vor dem heutigen Datum liegt und sie nicht erledigt ist.
{today}"""

_PARSE_INSTRUCTIONS = """\
Du extrahierst aus einem deutschen Freitext die Felder für eine neue Task in
der App "Crastinator Pro".
{today}
Verfügbare User: {users}.

Regeln:
- title: kurze Beschreibung der Tätigkeit, ohne Prioritätswörter, ohne den
  Namen des zugewiesenen Users und ohne Datumsangaben.
- description: nur, wenn der Text zusätzliche Details enthält, sonst null.
- due_date: Fälligkeitsdatum im Format YYYY-MM-DD; relative Angaben wie
  "heute", "morgen", "übermorgen", "in 3 Tagen" oder "nächsten Freitag" relativ
  zum heutigen Datum auflösen. Ohne Datumsangabe null.
- assignee_user_id: ID des genannten Users, sonst null.
- priority: "high" bei Wörtern wie dringend, wichtig, asap, hoch; "low" bei
  unwichtig, niedrig, irgendwann, keine Eile; sonst "medium"."""


class OpenAIProvider(AIProvider):
    def __init__(self, model: Optional[str] = None, client: Any = None):
        self._model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        if client is None:
            from openai import OpenAI

            client = OpenAI(timeout=30.0, max_retries=2)
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    def answer(self, question: str, tasks: list[Task], reference_time: datetime) -> str:
        tasks_json = json.dumps([_task_to_dict(t) for t in tasks], ensure_ascii=False, indent=2)
        user_input = (
            f"Tasks des Users (JSON):\n{tasks_json}\n\nFrage: {question}"
            if tasks
            else f"Der User hat aktuell keine Tasks.\n\nFrage: {question}"
        )
        response = self._call(
            "create",
            instructions=_ANSWER_INSTRUCTIONS.format(today=_today_line(reference_time)),
            input=user_input,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        if not text:
            raise AIProviderError("Das LLM hat eine leere Antwort geliefert.")
        return text

    def parse_task(self, text: str, reference_time: datetime) -> dict:
        response = self._call(
            "parse",
            instructions=_PARSE_INSTRUCTIONS.format(
                today=_today_line(reference_time), users=_users_line()
            ),
            input=text,
            text_format=_ParsedTask,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AIProviderError("Das LLM hat keine auswertbare Task geliefert.")

        try:
            due_date = date.fromisoformat(parsed.due_date) if parsed.due_date else None
        except ValueError as exc:
            raise AIProviderError(
                f"Das LLM hat ein ungültiges Datum geliefert: {parsed.due_date!r}"
            ) from exc

        assignee_user_id = parsed.assignee_user_id if parsed.assignee_user_id in USERS else None
        description = (parsed.description or "").strip() or None
        title = parsed.title.strip() or text.strip()

        return {
            "title": title,
            "description": description,
            "due_date": due_date,
            "assignee_user_id": assignee_user_id,
            "priority": Priority(parsed.priority),
        }

    def _call(self, method: str, **kwargs):
        from openai import OpenAIError

        try:
            return getattr(self._client.responses, method)(model=self._model, **kwargs)
        except OpenAIError as exc:
            raise AIProviderError(f"Anfrage an OpenAI fehlgeschlagen: {exc}") from exc
