"""Crastinator Pro - direkt importierbare Bibliothek (kein HTTP-Zwang).

Beispiel:
    from crastinator_pro import TaskService

    service = TaskService()
    task = service.create_task(title="Folien fertigstellen")
"""

from .ai import AIProvider, KeywordAIProvider, provider_from_env
from .client import CrastinatorClient
from .exceptions import (
    AIProviderError,
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
    "CrastinatorClient",
    "Task",
    "User",
    "USERS",
    "Priority",
    "AIProvider",
    "KeywordAIProvider",
    "provider_from_env",
    "add_business_days",
    "CrastinatorError",
    "ValidationError",
    "TaskNotFoundError",
    "UserNotFoundError",
    "NoDueDateError",
    "AIProviderError",
]
