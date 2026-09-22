"""Zentrale Geschäftslogik von Crastinator Pro, nutzbar als reine Python-Bibliothek.

Der `TaskService` hält den gesamten Zustand ausschließlich im Arbeitsspeicher
(kein Persistieren über einen Neustart hinweg). Die FastAPI-Schicht in
`api.py` ist ein dünner Wrapper um genau diese Klasse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .ai import AIProvider, KeywordAIProvider
from .csv_io import ImportResult, export_tasks_to_csv, import_tasks_from_csv
from .exceptions import NoDueDateError, TaskNotFoundError, UserNotFoundError, ValidationError
from .models import USERS, Priority, Task, User
from .workdays import add_business_days

SORT_FIELDS = {"due_date", "title", "priority", "completed"}
_PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}


class TaskService:
    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._auto_plus10_enabled = False
        self._ai_provider: AIProvider = ai_provider or KeywordAIProvider()

    # ------------------------------------------------------------------ Users
    def list_users(self) -> list[User]:
        return list(USERS.values())

    def get_user(self, user_id: int) -> User:
        user = USERS.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    # ------------------------------------------------------------------ CRUD
    def create_task(
        self,
        *,
        title: str,
        description: Optional[str] = None,
        due_date=None,
        assignee_user_id: Optional[int] = None,
        priority: Priority = Priority.MEDIUM,
    ) -> Task:
        if not title or not title.strip():
            raise ValidationError("title ist Pflichtfeld und darf nicht leer sein.")
        if assignee_user_id is not None and assignee_user_id not in USERS:
            raise UserNotFoundError(assignee_user_id)

        task = Task(
            id=self._next_id,
            title=title.strip(),
            description=description,
            due_date=due_date,
            assignee_user_id=assignee_user_id,
            priority=Priority(priority),
        )
        self._tasks[task.id] = task
        self._next_id += 1
        return task

    def get_task(self, task_id: int) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list_tasks(
        self,
        *,
        reference_time: datetime,
        sort_by: Optional[str] = None,
        order: str = "asc",
        assignee_user_id: Optional[int] = None,
        completed: Optional[bool] = None,
    ) -> list[Task]:
        if self._auto_plus10_enabled:
            self._apply_auto_plus10(reference_time)

        tasks = list(self._tasks.values())

        if assignee_user_id is not None:
            tasks = [t for t in tasks if t.assignee_user_id == assignee_user_id]
        if completed is not None:
            tasks = [t for t in tasks if t.completed == completed]
        if sort_by is not None:
            tasks = self._sort_tasks(tasks, sort_by, order)

        return tasks

    def toggle_task(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        task.completed = not task.completed
        return task

    def delete_task(self, task_id: int) -> None:
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        del self._tasks[task_id]

    def assign_task(self, task_id: int, user_id: Optional[int]) -> Task:
        task = self.get_task(task_id)
        if user_id is not None and user_id not in USERS:
            raise UserNotFoundError(user_id)
        task.assignee_user_id = user_id
        return task

    # ------------------------------------------------------------------ +10
    def plus_10(self, task_id: int, reference_time: datetime) -> Task:
        # reference_time wird bewusst entgegengenommen (kein Zugriff auf die
        # Systemuhr), auch wenn die reine Werktagsverschiebung selbst nicht
        # von "jetzt" abhängt - für Konsistenz mit Auto-+10 und deterministisches
        # property-based Testen.
        del reference_time
        task = self.get_task(task_id)
        if task.due_date is None:
            raise NoDueDateError(task_id)
        task.due_date = add_business_days(task.due_date, 10)
        return task

    def _apply_auto_plus10(self, reference_time: datetime) -> None:
        today = reference_time.date()
        for task in self._tasks.values():
            if task.due_date is None:
                continue
            while task.due_date < today:
                task.due_date = add_business_days(task.due_date, 10)

    def set_auto_plus10(self, enabled: bool) -> None:
        self._auto_plus10_enabled = bool(enabled)

    def get_auto_plus10(self) -> bool:
        return self._auto_plus10_enabled

    # ------------------------------------------------------------------ Sort
    @staticmethod
    def _sort_tasks(tasks: list[Task], sort_by: str, order: str) -> list[Task]:
        if sort_by not in SORT_FIELDS:
            raise ValidationError(
                f"Ungültiges sort_by '{sort_by}'. Erlaubt: {sorted(SORT_FIELDS)}."
            )
        if order not in ("asc", "desc"):
            raise ValidationError("order muss 'asc' oder 'desc' sein.")

        reverse = order == "desc"

        if sort_by == "due_date":
            with_date = [t for t in tasks if t.due_date is not None]
            without_date = [t for t in tasks if t.due_date is None]
            with_date.sort(key=lambda t: t.due_date, reverse=reverse)
            return with_date + without_date

        if sort_by == "priority":
            return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority], reverse=reverse)

        if sort_by == "completed":
            return sorted(tasks, key=lambda t: t.completed, reverse=reverse)

        # title
        return sorted(tasks, key=lambda t: t.title.lower(), reverse=reverse)

    # ------------------------------------------------------------------ CSV
    def export_csv(self) -> str:
        return export_tasks_to_csv(list(self._tasks.values()))

    def import_csv(self, csv_content: str) -> ImportResult:
        return import_tasks_from_csv(csv_content, self)

    # ------------------------------------------------------------------ AI
    def ai_ask(self, user_id: int, question: str, reference_time: datetime) -> str:
        self.get_user(user_id)  # validiert Existenz, wirft UserNotFoundError sonst
        tasks = [t for t in self._tasks.values() if t.assignee_user_id == user_id]
        return self._ai_provider.answer(question, tasks, reference_time)

    def ai_create_task(self, text: str, reference_time: datetime) -> Task:
        if not text or not text.strip():
            raise ValidationError("Freitext für die KI-Task-Anlage darf nicht leer sein.")
        parsed = self._ai_provider.parse_task(text, reference_time)
        return self.create_task(**parsed)
