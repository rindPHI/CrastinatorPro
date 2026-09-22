"""Crastinator Pro - direkt importierbare Bibliothek (kein HTTP-Zwang).

Beispiel:
    from crastinator_pro import TaskService

    service = TaskService()
    task = service.create_task(title="Folien fertigstellen")
"""

from .ai import AIProvider, KeywordAIProvider
from .exceptions import (
    CrastinatorError,
    NoDueDateError,
    TaskNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from .models import USERS, Priority, Task, User
from .service import TaskService
from .workdays import add_business_days

__all__ = [
    "TaskService",
    "Task",
    "User",
    "USERS",
    "Priority",
    "AIProvider",
    "KeywordAIProvider",
    "add_business_days",
    "CrastinatorError",
    "ValidationError",
    "TaskNotFoundError",
    "UserNotFoundError",
    "NoDueDateError",
]
