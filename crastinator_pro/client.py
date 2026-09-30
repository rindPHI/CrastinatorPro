"""HTTP-Client für eine laufende Crastinator-Pro-Instanz.

`CrastinatorClient` bietet dieselbe Schnittstelle wie `TaskService`, spricht
aber über die REST-API mit dem laufenden Server. Rückgabewerte sind die
gewohnten Modellobjekte (`Task`, `User`), Fehler sind dieselben Exceptions.

Beispiel:
    from crastinator_pro import CrastinatorClient

    client = CrastinatorClient("http://127.0.0.1:8000")
    for task in client.list_tasks(completed=False):
        print(task.title)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import httpx

from .csv_io import ImportResult, ImportRowError
from .exceptions import (
    CrastinatorError,
    NoDueDateError,
    TaskNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from .models import Priority, Task, User

_SORT_FIELD_MAP = {
    "due_date": "dueDate",
    "title": "title",
    "priority": "priority",
    "completed": "completed",
}


def _parse_task(data: dict) -> Task:
    return Task(
        id=data["id"],
        title=data["title"],
        description=data["description"],
        due_date=date.fromisoformat(data["dueDate"]) if data["dueDate"] else None,
        completed=data["completed"],
        created_at=datetime.fromisoformat(data["createdAt"]),
        assignee_user_id=data["assigneeUserId"],
        priority=Priority(data["priority"]),
    )


class CrastinatorClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 10.0):
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CrastinatorClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------ intern
    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self._http.request(method, path, **kwargs)
        if response.is_success:
            return response
        self._raise_for_error(response)
        raise AssertionError("unreachable")

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        detail = str(detail)
        status = response.status_code

        # Die API überträgt nur Statuscode + Text; daraus die Exception rekonstruieren.
        if status == 404 and "Task" in detail:
            raise TaskNotFoundError(_first_int(detail))
        if status == 404 and "User" in detail:
            raise UserNotFoundError(_first_int(detail))
        if status == 400 and "User mit ID" in detail:
            raise UserNotFoundError(_first_int(detail))
        if status == 400 and "kein dueDate" in detail:
            raise NoDueDateError(_first_int(detail))
        if status in (400, 422):
            raise ValidationError(detail)
        raise CrastinatorError(f"HTTP {status}: {detail}")

    # ------------------------------------------------------------ Users
    def list_users(self) -> list[User]:
        return [User(id=u["id"], name=u["name"]) for u in self._request("GET", "/api/users").json()]

    def get_user(self, user_id: int) -> User:
        for user in self.list_users():
            if user.id == user_id:
                return user
        raise UserNotFoundError(user_id)

    # ------------------------------------------------------------ CRUD
    def create_task(
        self,
        *,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[date] = None,
        assignee_user_id: Optional[int] = None,
        priority: Priority = Priority.MEDIUM,
    ) -> Task:
        body = {
            "title": title,
            "description": description,
            "dueDate": due_date.isoformat() if due_date else None,
            "assigneeUserId": assignee_user_id,
            "priority": Priority(priority).value,
        }
        return _parse_task(self._request("POST", "/api/tasks", json=body).json())

    def get_task(self, task_id: int) -> Task:
        return _parse_task(self._request("GET", f"/api/tasks/{task_id}").json())

    def list_tasks(
        self,
        *,
        reference_time: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        order: str = "asc",
        assignee_user_id: Optional[int] = None,
        completed: Optional[bool] = None,
        query: Optional[str] = None,
    ) -> list[Task]:
        params: dict = {"order": order}
        if reference_time is not None:
            params["referenceTime"] = reference_time.isoformat()
        if sort_by is not None:
            if sort_by not in _SORT_FIELD_MAP:
                raise ValidationError(
                    f"Ungültiges sort_by '{sort_by}'. Erlaubt: {sorted(_SORT_FIELD_MAP)}."
                )
            params["sortBy"] = _SORT_FIELD_MAP[sort_by]
        if assignee_user_id is not None:
            params["assigneeUserId"] = assignee_user_id
        if completed is not None:
            params["completed"] = str(completed).lower()
        if query is not None:
            params["q"] = query
        return [_parse_task(t) for t in self._request("GET", "/api/tasks", params=params).json()]

    def toggle_task(self, task_id: int) -> Task:
        return _parse_task(self._request("PATCH", f"/api/tasks/{task_id}/toggle").json())

    def delete_task(self, task_id: int) -> None:
        self._request("DELETE", f"/api/tasks/{task_id}")

    def assign_task(self, task_id: int, user_id: Optional[int]) -> Task:
        response = self._request(
            "PUT", f"/api/tasks/{task_id}/assignee", json={"userId": user_id}
        )
        return _parse_task(response.json())

    def plus_10(self, task_id: int, reference_time: Optional[datetime] = None) -> Task:
        params = {"referenceTime": reference_time.isoformat()} if reference_time else None
        return _parse_task(
            self._request("POST", f"/api/tasks/{task_id}/plus10", params=params).json()
        )

    # ------------------------------------------------------------ Settings
    def set_auto_plus10(self, enabled: bool) -> None:
        self._request("PUT", "/api/settings/auto-plus10", json={"enabled": enabled})

    def get_auto_plus10(self) -> bool:
        return self._request("GET", "/api/settings/auto-plus10").json()["enabled"]

    # ------------------------------------------------------------ CSV
    def export_csv(self) -> str:
        return self._request("GET", "/api/tasks/export").text

    def import_csv(self, csv_content: str) -> ImportResult:
        files = {"file": ("tasks.csv", csv_content.encode("utf-8"), "text/csv")}
        data = self._request("POST", "/api/tasks/import", files=files).json()
        return ImportResult(
            created=[_parse_task(t) for t in data["created"]],
            errors=[
                ImportRowError(row_number=e["row"], reason=e["reason"], raw=e["raw"])
                for e in data["errors"]
            ],
        )

    # ------------------------------------------------------------ AI
    def ai_ask(
        self, user_id: int, question: str, reference_time: Optional[datetime] = None
    ) -> str:
        params = {"referenceTime": reference_time.isoformat()} if reference_time else None
        response = self._request(
            "POST", f"/api/users/{user_id}/ask", json={"question": question}, params=params
        )
        return response.json()["answer"]

    def ai_create_task(self, text: str, reference_time: Optional[datetime] = None) -> Task:
        params = {"referenceTime": reference_time.isoformat()} if reference_time else None
        response = self._request("POST", "/api/tasks/ai-create", json={"text": text}, params=params)
        return _parse_task(response.json())


def _first_int(text: str) -> int:
    import re

    match = re.search(r"\d+", text)
    return int(match.group()) if match else -1
