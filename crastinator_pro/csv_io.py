"""CSV-Export und -Import von Tasks."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from .models import Priority, Task

if TYPE_CHECKING:
    from .service import TaskService

EXPORT_FIELDNAMES = [
    "id",
    "title",
    "description",
    "dueDate",
    "completed",
    "createdAt",
    "assigneeUserId",
    "priority",
]

IMPORT_FIELDNAMES = ["title", "description", "dueDate", "assigneeUserId", "priority", "completed"]


@dataclass
class ImportRowError:
    row_number: int
    reason: str
    raw: dict


@dataclass
class ImportResult:
    created: list[Task]
    errors: list[ImportRowError]


def export_tasks_to_csv(tasks: list[Task]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES)
    writer.writeheader()
    for task in tasks:
        writer.writerow(
            {
                "id": task.id,
                "title": task.title,
                "description": task.description or "",
                "dueDate": task.due_date.isoformat() if task.due_date else "",
                "completed": task.completed,
                "createdAt": task.created_at.isoformat(),
                "assigneeUserId": task.assignee_user_id if task.assignee_user_id is not None else "",
                "priority": task.priority.value,
            }
        )
    return buffer.getvalue()


def import_tasks_from_csv(csv_content: str, service: "TaskService") -> ImportResult:
    reader = csv.DictReader(io.StringIO(csv_content))
    created: list[Task] = []
    errors: list[ImportRowError] = []

    for row_number, row in enumerate(reader, start=2):  # Zeile 1 ist der Header
        try:
            title = (row.get("title") or "").strip()
            description = (row.get("description") or "").strip() or None

            due_date_raw = (row.get("dueDate") or "").strip()
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date() if due_date_raw else None

            assignee_raw = (row.get("assigneeUserId") or "").strip()
            assignee_user_id = int(assignee_raw) if assignee_raw else None

            priority_raw = (row.get("priority") or "").strip() or Priority.MEDIUM.value
            priority = Priority(priority_raw)

            task = service.create_task(
                title=title,
                description=description,
                due_date=due_date,
                assignee_user_id=assignee_user_id,
                priority=priority,
            )

            completed_raw = (row.get("completed") or "").strip().lower()
            if completed_raw in ("true", "1", "yes", "ja"):
                service.toggle_task(task.id)

            created.append(task)
        except Exception as exc:  # noqa: BLE001 - einzelne Zeile wird isoliert abgelehnt
            errors.append(ImportRowError(row_number=row_number, reason=str(exc), raw=row))

    return ImportResult(created=created, errors=errors)
