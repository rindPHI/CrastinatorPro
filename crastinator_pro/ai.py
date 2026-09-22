"""KI-Assistent-Abstraktion für Freitext-Fragen und Freitext-Task-Anlage.

`AIProvider` ist bewusst als austauschbare Abstraktion gehalten: die mitgelieferte
`KeywordAIProvider` ist eine einfache, aber echte regel-/keywordbasierte
Implementierung. Eine Anbindung an ein echtes LLM könnte dieselbe Schnittstelle
implementieren, ohne dass der restliche Code angepasst werden müsste.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from .models import USERS, Priority, Task


class AIProvider(ABC):
    @abstractmethod
    def answer(self, question: str, tasks: list[Task], reference_time: datetime) -> str:
        """Beantwortet eine Freitext-Frage zu den übergebenen Tasks eines Users."""

    @abstractmethod
    def parse_task(self, text: str, reference_time: datetime) -> dict:
        """Extrahiert aus Freitext die Felder für eine Task-Neuanlage.

        Rückgabe-Keys: title, description, due_date, assignee_user_id, priority.
        """


_NAME_TO_USER_ID = {user.name.lower(): user.id for user in USERS.values()}

# Wortgrenzen-Patterns statt reiner Substrings, damit z. B. "wichtig" nicht
# faelschlich innerhalb von "unwichtig" matcht.
_HIGH_PRIORITY_PATTERNS = [
    r"\bdringend\w*\b",
    r"\bwichtig\b",
    r"\bhoh(e|en|em|er)?\b",
    r"\bhoch\b",
    r"\basap\b",
]
_LOW_PRIORITY_PATTERNS = [
    r"\bunwichtig\w*\b",
    r"\bniedrig\w*\b",
    r"\birgendwann\b",
    r"\bkeine eile\b",
]

_RELATIVE_DAY_PATTERN = re.compile(r"in (\d+) tagen")
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


class KeywordAIProvider(AIProvider):
    """Regelbasierter Assistent ohne externe Abhängigkeiten."""

    def answer(self, question: str, tasks: list[Task], reference_time: datetime) -> str:
        q = question.lower().strip()

        if not tasks:
            return "Du hast aktuell keine Tasks."

        if "überfällig" in q or "ueberfaellig" in q:
            today = reference_time.date()
            overdue = [t for t in tasks if t.due_date is not None and t.due_date < today and not t.completed]
            if not overdue:
                return "Du hast keine überfälligen Tasks."
            titles = ", ".join(t.title for t in overdue)
            return f"Du hast {len(overdue)} überfällige Task(s): {titles}."

        if "priorität" in q or "prioritaet" in q:
            if re.search(r"\bhoh(e|en|em|er)?\b", q) or re.search(r"\bhoch\b", q):
                matching = [t for t in tasks if t.priority == Priority.HIGH]
                label = "hoher Priorität"
            elif re.search(r"\bniedrig\w*\b", q):
                matching = [t for t in tasks if t.priority == Priority.LOW]
                label = "niedriger Priorität"
            else:
                matching = [t for t in tasks if t.priority == Priority.MEDIUM]
                label = "mittlerer Priorität"
            if not matching:
                return f"Du hast keine Tasks mit {label}."
            titles = ", ".join(t.title for t in matching)
            return f"Tasks mit {label}: {titles}."

        if "wie viele" in q:
            if "offen" in q or "nicht erledigt" in q:
                count = sum(1 for t in tasks if not t.completed)
                return f"Du hast {count} offene Task(s)."
            if "erledigt" in q or "abgeschlossen" in q:
                count = sum(1 for t in tasks if t.completed)
                return f"Du hast {count} erledigte Task(s)."
            return f"Du hast insgesamt {len(tasks)} Task(s)."

        if "nächste" in q or "naechste" in q or "als nächstes" in q or "als naechstes" in q:
            open_with_due = [t for t in tasks if not t.completed and t.due_date is not None]
            if not open_with_due:
                return "Es gibt keine offene Task mit dueDate."
            next_task = min(open_with_due, key=lambda t: t.due_date)
            return f"Als nächstes fällig ist: '{next_task.title}' am {next_task.due_date.isoformat()}."

        if "liste" in q or "welche tasks" in q or "zeig" in q:
            titles = ", ".join(t.title for t in tasks)
            return f"Deine Tasks: {titles}."

        open_count = sum(1 for t in tasks if not t.completed)
        done_count = len(tasks) - open_count
        return (
            f"Du hast {len(tasks)} Task(s) insgesamt, davon {open_count} offen und "
            f"{done_count} erledigt."
        )

    def parse_task(self, text: str, reference_time: datetime) -> dict:
        remaining = text.strip()

        priority = Priority.MEDIUM
        lowered = remaining.lower()
        if _matches_any(_LOW_PRIORITY_PATTERNS, lowered):
            priority = Priority.LOW
        elif _matches_any(_HIGH_PRIORITY_PATTERNS, lowered):
            priority = Priority.HIGH

        assignee_user_id: Optional[int] = None
        for name, user_id in _NAME_TO_USER_ID.items():
            if re.search(rf"\b{name}\b", lowered):
                assignee_user_id = user_id
                remaining = re.sub(rf"(?i)\bfür {name}\b", "", remaining)
                remaining = re.sub(rf"(?i)\b{name}\b", "", remaining)
                break

        due_date = None
        iso_match = _ISO_DATE_PATTERN.search(remaining)
        relative_match = _RELATIVE_DAY_PATTERN.search(lowered)
        if iso_match:
            due_date = datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
            remaining = remaining.replace(iso_match.group(1), "")
        elif "übermorgen" in lowered or "uebermorgen" in lowered:
            due_date = (reference_time + timedelta(days=2)).date()
            remaining = re.sub(r"(?i)übermorgen|uebermorgen", "", remaining)
        elif "morgen" in lowered:
            due_date = (reference_time + timedelta(days=1)).date()
            remaining = re.sub(r"(?i)morgen", "", remaining)
        elif "heute" in lowered:
            due_date = reference_time.date()
            remaining = re.sub(r"(?i)heute", "", remaining)
        elif relative_match:
            due_date = (reference_time + timedelta(days=int(relative_match.group(1)))).date()
            remaining = re.sub(r"(?i)in \d+ tagen", "", remaining)

        for pattern in (*_HIGH_PRIORITY_PATTERNS, *_LOW_PRIORITY_PATTERNS):
            remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE)

        title = re.sub(r"\s{2,}", " ", remaining).strip(" ,.:;-")
        if not title:
            title = text.strip()

        return {
            "title": title,
            "description": None,
            "due_date": due_date,
            "assignee_user_id": assignee_user_id,
            "priority": priority,
        }
