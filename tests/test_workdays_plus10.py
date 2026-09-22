from datetime import date, datetime

import pytest

from crastinator_pro.exceptions import NoDueDateError, TaskNotFoundError
from crastinator_pro.service import TaskService
from crastinator_pro.workdays import add_business_days

NOW = datetime(2026, 1, 10, 9, 0, 0)


def test_add_business_days_from_monday():
    # 2026-01-05 ist ein Montag.
    assert add_business_days(date(2026, 1, 5), 10) == date(2026, 1, 19)


def test_add_business_days_skips_weekend_for_one_day():
    # 2026-01-09 ist ein Freitag, +1 Werktag landet auf Montag.
    assert add_business_days(date(2026, 1, 9), 1) == date(2026, 1, 12)


def test_add_business_days_from_saturday_start():
    # 2026-01-10 ist ein Samstag; der Starttag selbst zaehlt nicht mit.
    assert add_business_days(date(2026, 1, 10), 1) == date(2026, 1, 12)


def test_add_business_days_zero_returns_same_date():
    d = date(2026, 1, 5)
    assert add_business_days(d, 0) == d


def test_add_business_days_negative_raises():
    with pytest.raises(ValueError):
        add_business_days(date(2026, 1, 5), -1)


def test_plus_10_shifts_due_date(service: TaskService):
    task = service.create_task(title="Task", due_date=date(2026, 1, 5))

    updated = service.plus_10(task.id, NOW)

    assert updated.due_date == date(2026, 1, 19)


def test_plus_10_without_due_date_raises(service: TaskService):
    task = service.create_task(title="Task ohne Datum")

    with pytest.raises(NoDueDateError):
        service.plus_10(task.id, NOW)


def test_plus_10_unknown_task_raises(service: TaskService):
    with pytest.raises(TaskNotFoundError):
        service.plus_10(999, NOW)


def test_plus_10_can_be_applied_repeatedly(service: TaskService):
    task = service.create_task(title="Task", due_date=date(2026, 1, 5))

    service.plus_10(task.id, NOW)
    updated = service.plus_10(task.id, NOW)

    assert updated.due_date == date(2026, 2, 2)
