"""Fehlerklassen der Crastinator-Pro-Bibliothek."""

from __future__ import annotations


class CrastinatorError(Exception):
    """Basisklasse für alle fachlichen Fehler der Bibliothek."""


class ValidationError(CrastinatorError):
    """Eingabedaten sind fachlich ungültig (z. B. fehlender Titel)."""


class TaskNotFoundError(CrastinatorError):
    def __init__(self, task_id: int):
        super().__init__(f"Task mit ID {task_id} wurde nicht gefunden.")
        self.task_id = task_id


class UserNotFoundError(CrastinatorError):
    def __init__(self, user_id: int):
        super().__init__(f"User mit ID {user_id} wurde nicht gefunden.")
        self.user_id = user_id


class NoDueDateError(CrastinatorError):
    def __init__(self, task_id: int):
        super().__init__(f"Task {task_id} hat kein dueDate und kann nicht verschoben werden.")
        self.task_id = task_id
