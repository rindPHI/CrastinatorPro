from datetime import datetime

from fastapi.testclient import TestClient

from crastinator_pro.service import TaskService

NOW = datetime(2026, 1, 10, 9, 0, 0)


def _titles(tasks) -> list[str]:
    return [t.title for t in tasks]


def test_search_single_term_matches_title(service: TaskService):
    service.create_task(title="Folien vorbereiten")
    service.create_task(title="Einkaufen")

    tasks = service.list_tasks(reference_time=NOW, query="folien")

    assert _titles(tasks) == ["Folien vorbereiten"]


def test_search_single_term_matches_description(service: TaskService):
    service.create_task(title="Vortrag", description="Demo mit Hypothesis zeigen")
    service.create_task(title="Einkaufen", description="Milch")

    tasks = service.list_tasks(reference_time=NOW, query="hypothesis")

    assert _titles(tasks) == ["Vortrag"]


def test_search_multiple_terms_must_all_match_across_fields(service: TaskService):
    service.create_task(title="Folien vorbereiten", description="Für die Konferenz")
    service.create_task(title="Folien drucken", description="Büro")
    service.create_task(title="Konferenz buchen")

    tasks = service.list_tasks(reference_time=NOW, query="folien konferenz")

    assert _titles(tasks) == ["Folien vorbereiten"]


def test_search_is_case_insensitive(service: TaskService):
    service.create_task(title="Folien Vorbereiten")

    tasks = service.list_tasks(reference_time=NOW, query="fOLIEN vORBEREITEN")

    assert _titles(tasks) == ["Folien Vorbereiten"]


def test_search_empty_or_blank_query_returns_all_tasks(service: TaskService):
    service.create_task(title="A")
    service.create_task(title="B")

    assert _titles(service.list_tasks(reference_time=NOW, query="")) == ["A", "B"]
    assert _titles(service.list_tasks(reference_time=NOW, query="   ")) == ["A", "B"]


def test_search_combined_with_filter_and_sort(service: TaskService):
    service.create_task(title="Bericht schreiben", assignee_user_id=1)
    service.create_task(title="Bericht prüfen", assignee_user_id=1)
    service.create_task(title="Bericht archivieren", assignee_user_id=2)
    service.create_task(title="Einkaufen", assignee_user_id=1)

    tasks = service.list_tasks(
        reference_time=NOW,
        query="bericht",
        assignee_user_id=1,
        sort_by="title",
        order="asc",
    )

    assert _titles(tasks) == ["Bericht prüfen", "Bericht schreiben"]


def test_search_combined_with_completed_filter(service: TaskService):
    open_task = service.create_task(title="Bericht offen")
    done_task = service.create_task(title="Bericht fertig")
    service.toggle_task(done_task.id)

    tasks = service.list_tasks(reference_time=NOW, query="bericht", completed=False)

    assert [t.id for t in tasks] == [open_task.id]


def test_api_search_query_parameter(client: TestClient):
    client.post("/api/tasks", json={"title": "Folien vorbereiten", "description": "Konferenz"})
    client.post("/api/tasks", json={"title": "Einkaufen"})

    response = client.get("/api/tasks?q=folien%20konferenz")

    assert response.status_code == 200
    assert [t["title"] for t in response.json()] == ["Folien vorbereiten"]
