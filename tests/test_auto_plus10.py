from datetime import date, datetime

from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)


def test_auto_plus10_disabled_by_default(service: TaskService):
    assert service.get_auto_plus10() is False


def test_set_auto_plus10_enabled(service: TaskService):
    service.set_auto_plus10(True)

    assert service.get_auto_plus10() is True


def test_auto_plus10_shifts_overdue_task_on_list(service: TaskService):
    task = service.create_task(title="Überfällig", due_date=date(2025, 12, 1))
    service.set_auto_plus10(True)

    tasks = service.list_tasks(reference_time=NOW)

    updated = next(t for t in tasks if t.id == task.id)
    assert updated.due_date == date(2026, 1, 12)
    assert updated.due_date >= NOW.date()


def test_auto_plus10_disabled_does_not_shift(service: TaskService):
    task = service.create_task(title="Überfällig", due_date=date(2025, 12, 1))

    tasks = service.list_tasks(reference_time=NOW)

    updated = next(t for t in tasks if t.id == task.id)
    assert updated.due_date == date(2025, 12, 1)


def test_auto_plus10_ignores_tasks_without_due_date(service: TaskService):
    task = service.create_task(title="Ohne Datum")
    service.set_auto_plus10(True)

    tasks = service.list_tasks(reference_time=NOW)

    updated = next(t for t in tasks if t.id == task.id)
    assert updated.due_date is None


def test_auto_plus10_does_not_shift_future_task(service: TaskService):
    task = service.create_task(title="Zukünftig", due_date=date(2026, 6, 1))
    service.set_auto_plus10(True)

    tasks = service.list_tasks(reference_time=NOW)

    updated = next(t for t in tasks if t.id == task.id)
    assert updated.due_date == date(2026, 6, 1)


def test_auto_plus10_shift_is_persisted_across_calls(service: TaskService):
    task = service.create_task(title="Überfällig", due_date=date(2025, 12, 1))
    service.set_auto_plus10(True)

    service.list_tasks(reference_time=NOW)
    tasks_again = service.list_tasks(reference_time=NOW)

    updated = next(t for t in tasks_again if t.id == task.id)
    assert updated.due_date == date(2026, 1, 12)
