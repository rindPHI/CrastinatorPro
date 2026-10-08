"""Datenmodell fuer Crastinator Pro: User, Task und Priority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __repr__(self) -> str:
        return f'Priority("{self.value}")'


@dataclass(frozen=True)
class User:
    id: int
    name: str


# Fest hinterlegte User, keine Verwaltung zur Laufzeit.
USERS: dict[int, User] = {
    1: User(id=1, name="Alice"),
    2: User(id=2, name="Bob"),
    3: User(id=3, name="Carol"),
}


@dataclass
class Task:
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    assignee_user_id: Optional[int] = None
    priority: Priority = Priority.MEDIUM

    def __hash__(self) -> int:
        # Hash nur ueber die (unveraenderliche) id, damit Tasks trotz veraenderlicher
        # Felder in Sets/Dicts verwendbar sind. Konsistent mit dem feldbasierten __eq__.
        return hash(self.id)
