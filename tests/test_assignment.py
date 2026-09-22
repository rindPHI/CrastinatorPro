import pytest

from crastinator_pro.exceptions import TaskNotFoundError, UserNotFoundError
from crastinator_pro.service import TaskService


def test_assign_task_to_user(service: TaskService):
    task = service.create_task(title="Task")

    updated = service.assign_task(task.id, 2)

    assert updated.assignee_user_id == 2


def test_remove_assignment(service: TaskService):
    task = service.create_task(title="Task", assignee_user_id=1)

    updated = service.assign_task(task.id, None)

    assert updated.assignee_user_id is None


def test_assign_to_unknown_user_raises(service: TaskService):
    task = service.create_task(title="Task")

    with pytest.raises(UserNotFoundError):
        service.assign_task(task.id, 999)


def test_assign_unknown_task_raises(service: TaskService):
    with pytest.raises(TaskNotFoundError):
        service.assign_task(999, 1)


def test_reassign_task_to_different_user(service: TaskService):
    task = service.create_task(title="Task", assignee_user_id=1)

    updated = service.assign_task(task.id, 3)

    assert updated.assignee_user_id == 3
