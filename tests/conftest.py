import pytest
from fastapi.testclient import TestClient

from crastinator_pro.api import create_app
from crastinator_pro.service import TaskService


@pytest.fixture
def service() -> TaskService:
    return TaskService()


@pytest.fixture
def client(service: TaskService) -> TestClient:
    app = create_app(service)
    return TestClient(app)
