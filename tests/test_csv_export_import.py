from datetime import date

from crastinator_pro.models import Priority
from crastinator_pro.service import TaskService


def test_export_csv_contains_header_and_task(service: TaskService):
    service.create_task(title="Task A", due_date=date(2026, 1, 1))

    csv_content = service.export_csv()

    lines = csv_content.strip().splitlines()
    assert lines[0].startswith("id,title,description,dueDate,completed,createdAt")
    assert "Task A" in lines[1]


def test_export_csv_empty_when_no_tasks(service: TaskService):
    csv_content = service.export_csv()

    lines = csv_content.strip().splitlines()
    assert len(lines) == 1  # nur Header


def test_import_csv_creates_valid_tasks(service: TaskService):
    csv_content = (
        "title,description,dueDate,assigneeUserId,priority,completed\n"
        "Neuer Task,Eine Beschreibung,2026-02-01,1,high,false\n"
        "Zweiter Task,,,,,\n"
    )

    result = service.import_csv(csv_content)

    assert len(result.created) == 2
    assert len(result.errors) == 0
    assert result.created[0].title == "Neuer Task"
    assert result.created[0].priority == Priority.HIGH
    assert result.created[1].priority == Priority.MEDIUM


def test_import_csv_rejects_row_without_title_but_keeps_others(service: TaskService):
    csv_content = (
        "title,description,dueDate,assigneeUserId,priority,completed\n"
        ",Fehlt der Titel,,,,\n"
        "Gültiger Task,,,,,\n"
    )

    result = service.import_csv(csv_content)

    assert len(result.created) == 1
    assert result.created[0].title == "Gültiger Task"
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 2


def test_import_csv_rejects_row_with_unknown_assignee(service: TaskService):
    csv_content = (
        "title,description,dueDate,assigneeUserId,priority,completed\n"
        "Task mit ungültigem User,,,999,,\n"
    )

    result = service.import_csv(csv_content)

    assert len(result.created) == 0
    assert len(result.errors) == 1


def test_import_csv_marks_completed_tasks(service: TaskService):
    csv_content = (
        "title,description,dueDate,assigneeUserId,priority,completed\n"
        "Erledigter Task,,,,,true\n"
    )

    result = service.import_csv(csv_content)

    assert result.created[0].completed is True


def test_export_then_import_round_trip(service: TaskService):
    service.create_task(title="Task 1", due_date=date(2026, 3, 3), priority=Priority.LOW)
    service.create_task(title="Task 2", assignee_user_id=2)

    csv_content = service.export_csv()

    other_service = TaskService()
    result = other_service.import_csv(csv_content)

    assert len(result.created) == 2
    assert len(result.errors) == 0
