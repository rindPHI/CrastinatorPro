from datetime import date, datetime

import pytest

from crastinator_pro.exceptions import ValidationError
from crastinator_pro.models import Priority
from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)


def test_ai_create_task_simple_title(service: TaskService):
    task = service.ai_create_task("Präsentation vorbereiten", NOW)

    assert "Präsentation vorbereiten" in task.title
    assert task.priority == Priority.MEDIUM
    assert task.assignee_user_id is None


def test_ai_create_task_detects_high_priority(service: TaskService):
    task = service.ai_create_task("Dringend: Server neustarten", NOW)

    assert task.priority == Priority.HIGH


def test_ai_create_task_detects_low_priority(service: TaskService):
    task = service.ai_create_task("Unwichtig: Schreibtisch aufräumen", NOW)

    assert task.priority == Priority.LOW


def test_ai_create_task_detects_assignee(service: TaskService):
    task = service.ai_create_task("Für Bob: Testfälle schreiben", NOW)

    assert task.assignee_user_id == 2


def test_ai_create_task_detects_relative_due_date_morgen(service: TaskService):
    task = service.ai_create_task("Rechnung morgen bezahlen", NOW)

    assert task.due_date == date(2026, 1, 11)


def test_ai_create_task_detects_explicit_iso_date(service: TaskService):
    task = service.ai_create_task("Vertrag unterschreiben 2026-03-15", NOW)

    assert task.due_date == date(2026, 3, 15)


def test_ai_create_task_strips_leading_punctuation_after_cleanup(service: TaskService):
    task = service.ai_create_task("Dringend: Bericht für Bob morgen schreiben", NOW)

    assert task.title == "Bericht schreiben"
    assert task.assignee_user_id == 2
    assert task.priority == Priority.HIGH


def test_ai_create_task_empty_text_raises(service: TaskService):
    with pytest.raises(ValidationError):
        service.ai_create_task("   ", NOW)
