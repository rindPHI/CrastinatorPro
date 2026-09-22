from datetime import date, datetime

from crastinator_pro.models import Priority
from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)


def test_sort_by_due_date_ascending(service: TaskService):
    service.create_task(title="C", due_date=date(2026, 3, 1))
    service.create_task(title="A", due_date=date(2026, 1, 1))
    service.create_task(title="B", due_date=date(2026, 2, 1))

    tasks = service.list_tasks(reference_time=NOW, sort_by="due_date", order="asc")

    assert [t.title for t in tasks] == ["A", "B", "C"]


def test_sort_by_due_date_descending(service: TaskService):
    service.create_task(title="C", due_date=date(2026, 3, 1))
    service.create_task(title="A", due_date=date(2026, 1, 1))
    service.create_task(title="B", due_date=date(2026, 2, 1))

    tasks = service.list_tasks(reference_time=NOW, sort_by="due_date", order="desc")

    assert [t.title for t in tasks] == ["C", "B", "A"]


def test_sort_by_due_date_puts_tasks_without_due_date_last(service: TaskService):
    service.create_task(title="Ohne Datum")
    service.create_task(title="Mit Datum", due_date=date(2026, 1, 1))

    tasks = service.list_tasks(reference_time=NOW, sort_by="due_date", order="asc")

    assert [t.title for t in tasks] == ["Mit Datum", "Ohne Datum"]


def test_sort_by_title(service: TaskService):
    service.create_task(title="Banane")
    service.create_task(title="Apfel")

    tasks = service.list_tasks(reference_time=NOW, sort_by="title", order="asc")

    assert [t.title for t in tasks] == ["Apfel", "Banane"]


def test_sort_by_priority(service: TaskService):
    service.create_task(title="Niedrig", priority=Priority.LOW)
    service.create_task(title="Hoch", priority=Priority.HIGH)
    service.create_task(title="Mittel", priority=Priority.MEDIUM)

    tasks = service.list_tasks(reference_time=NOW, sort_by="priority", order="asc")

    assert [t.title for t in tasks] == ["Niedrig", "Mittel", "Hoch"]


def test_sort_by_completed(service: TaskService):
    open_task = service.create_task(title="Offen")
    done_task = service.create_task(title="Erledigt")
    service.toggle_task(done_task.id)

    tasks = service.list_tasks(reference_time=NOW, sort_by="completed", order="asc")

    assert [t.id for t in tasks] == [open_task.id, done_task.id]


def test_filter_by_assignee(service: TaskService):
    service.create_task(title="Für Alice", assignee_user_id=1)
    service.create_task(title="Für Bob", assignee_user_id=2)

    tasks = service.list_tasks(reference_time=NOW, assignee_user_id=1)

    assert [t.title for t in tasks] == ["Für Alice"]


def test_filter_by_completed(service: TaskService):
    open_task = service.create_task(title="Offen")
    done_task = service.create_task(title="Erledigt")
    service.toggle_task(done_task.id)

    open_tasks = service.list_tasks(reference_time=NOW, completed=False)

    assert [t.id for t in open_tasks] == [open_task.id]


def test_list_tasks_without_filters_returns_all(service: TaskService):
    service.create_task(title="A")
    service.create_task(title="B")

    tasks = service.list_tasks(reference_time=NOW)

    assert len(tasks) == 2
