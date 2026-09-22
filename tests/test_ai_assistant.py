from datetime import date, datetime

import pytest

from crastinator_pro.exceptions import UserNotFoundError
from crastinator_pro.models import Priority
from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)


def test_ai_ask_counts_open_tasks(service: TaskService):
    service.create_task(title="Task 1", assignee_user_id=1)
    task2 = service.create_task(title="Task 2", assignee_user_id=1)
    service.toggle_task(task2.id)

    answer = service.ai_ask(1, "Wie viele Tasks sind offen?", NOW)

    assert "1" in answer


def test_ai_ask_reports_no_tasks(service: TaskService):
    answer = service.ai_ask(1, "Wie viele Tasks habe ich?", NOW)

    assert "keine Tasks" in answer


def test_ai_ask_finds_overdue_tasks(service: TaskService):
    service.create_task(title="Überfällig", assignee_user_id=1, due_date=date(2025, 1, 1))

    answer = service.ai_ask(1, "Was ist überfällig?", NOW)

    assert "Überfällig" in answer


def test_ai_ask_only_considers_own_tasks(service: TaskService):
    service.create_task(title="Bobs Task", assignee_user_id=2, due_date=date(2025, 1, 1))
    service.create_task(title="Alices Task", assignee_user_id=1, due_date=date(2026, 6, 1))

    answer = service.ai_ask(1, "Was ist überfällig?", NOW)

    assert "keine überfälligen" in answer


def test_ai_ask_filters_by_priority(service: TaskService):
    service.create_task(title="Wichtige Sache", assignee_user_id=1, priority=Priority.HIGH)
    service.create_task(title="Kleinkram", assignee_user_id=1, priority=Priority.LOW)

    answer = service.ai_ask(1, "Welche Tasks haben hohe Priorität?", NOW)

    assert "Wichtige Sache" in answer
    assert "Kleinkram" not in answer


def test_ai_ask_unknown_user_raises(service: TaskService):
    with pytest.raises(UserNotFoundError):
        service.ai_ask(999, "Wie viele Tasks?", NOW)
