from datetime import date

import pytest

from crastinator_pro.exceptions import TaskNotFoundError, UserNotFoundError, ValidationError
from crastinator_pro.models import Priority
from crastinator_pro.service import TaskService


def test_create_task_happy_path(service: TaskService):
    task = service.create_task(title="Folien vorbereiten", description="Für den Talk")

    assert task.id == 1
    assert task.title == "Folien vorbereiten"
    assert task.description == "Für den Talk"
    assert task.completed is False
    assert task.priority == Priority.MEDIUM
    assert task.assignee_user_id is None


def test_create_task_with_all_fields(service: TaskService):
    task = service.create_task(
        title="Review vorbereiten",
        due_date=date(2026, 1, 15),
        assignee_user_id=2,
        priority=Priority.HIGH,
    )

    assert task.due_date == date(2026, 1, 15)
    assert task.assignee_user_id == 2
    assert task.priority == Priority.HIGH


def test_create_task_without_title_raises(service: TaskService):
    with pytest.raises(ValidationError):
        service.create_task(title="")


def test_create_task_with_blank_title_raises(service: TaskService):
    with pytest.raises(ValidationError):
        service.create_task(title="   ")


def test_create_task_with_unknown_assignee_raises(service: TaskService):
    with pytest.raises(UserNotFoundError):
        service.create_task(title="Task", assignee_user_id=999)


def test_task_ids_are_unique_and_increasing(service: TaskService):
    first = service.create_task(title="Erster Task")
    second = service.create_task(title="Zweiter Task")

    assert second.id == first.id + 1


def test_toggle_task_flips_completed(service: TaskService):
    task = service.create_task(title="Task")

    toggled = service.toggle_task(task.id)
    assert toggled.completed is True

    toggled_again = service.toggle_task(task.id)
    assert toggled_again.completed is False


def test_toggle_unknown_task_raises(service: TaskService):
    with pytest.raises(TaskNotFoundError):
        service.toggle_task(999)


def test_delete_task_removes_it(service: TaskService):
    task = service.create_task(title="Task")
    service.delete_task(task.id)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id)


def test_delete_unknown_task_raises(service: TaskService):
    with pytest.raises(TaskNotFoundError):
        service.delete_task(999)
