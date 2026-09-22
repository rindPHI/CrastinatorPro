import io

from fastapi.testclient import TestClient


def test_list_users(client: TestClient):
    response = client.get("/api/users")

    assert response.status_code == 200
    names = [u["name"] for u in response.json()]
    assert names == ["Alice", "Bob", "Carol"]


def test_create_and_get_task(client: TestClient):
    create_response = client.post("/api/tasks", json={"title": "Neuer Task"})
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    get_response = client.get(f"/api/tasks/{task_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Neuer Task"


def test_create_task_without_title_returns_400(client: TestClient):
    response = client.post("/api/tasks", json={"title": ""})

    assert response.status_code == 400


def test_create_task_with_unknown_assignee_returns_400(client: TestClient):
    response = client.post("/api/tasks", json={"title": "Task", "assigneeUserId": 999})

    assert response.status_code == 400


def test_list_tasks_sorted_by_title(client: TestClient):
    client.post("/api/tasks", json={"title": "Banane"})
    client.post("/api/tasks", json={"title": "Apfel"})

    response = client.get("/api/tasks?sortBy=title&order=asc")

    assert [t["title"] for t in response.json()] == ["Apfel", "Banane"]


def test_toggle_and_delete_task(client: TestClient):
    task_id = client.post("/api/tasks", json={"title": "Task"}).json()["id"]

    toggle_response = client.patch(f"/api/tasks/{task_id}/toggle")
    assert toggle_response.json()["completed"] is True

    delete_response = client.delete(f"/api/tasks/{task_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/tasks/{task_id}")
    assert get_response.status_code == 404


def test_toggle_unknown_task_returns_404(client: TestClient):
    response = client.patch("/api/tasks/999/toggle")

    assert response.status_code == 404


def test_plus10_endpoint(client: TestClient):
    task_id = client.post(
        "/api/tasks", json={"title": "Task", "dueDate": "2026-01-05"}
    ).json()["id"]

    response = client.post(f"/api/tasks/{task_id}/plus10")

    assert response.status_code == 200
    assert response.json()["dueDate"] == "2026-01-19"


def test_auto_plus10_setting_roundtrip(client: TestClient):
    response = client.put("/api/settings/auto-plus10", json={"enabled": True})
    assert response.json() == {"enabled": True}

    response = client.get("/api/settings/auto-plus10")
    assert response.json() == {"enabled": True}


def test_csv_export_and_import(client: TestClient):
    client.post("/api/tasks", json={"title": "Exportierter Task"})

    export_response = client.get("/api/tasks/export")
    assert export_response.status_code == 200
    csv_content = export_response.text

    import_response = client.post(
        "/api/tasks/import",
        files={"file": ("tasks.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
    )
    assert import_response.status_code == 200
    body = import_response.json()
    assert len(body["created"]) == 1
    assert len(body["errors"]) == 0


def test_ai_ask_endpoint(client: TestClient):
    client.post("/api/tasks", json={"title": "Task für Alice", "assigneeUserId": 1})

    response = client.post("/api/users/1/ask", json={"question": "Wie viele Tasks habe ich?"})

    assert response.status_code == 200
    assert "1" in response.json()["answer"]


def test_ai_create_endpoint(client: TestClient):
    response = client.post("/api/tasks/ai-create", json={"text": "Dringend: Bericht schreiben"})

    assert response.status_code == 201
    assert response.json()["priority"] == "high"
