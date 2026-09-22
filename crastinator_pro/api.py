"""FastAPI-Anwendung - dünner HTTP-Wrapper um `TaskService`."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .exceptions import NoDueDateError, TaskNotFoundError, UserNotFoundError, ValidationError
from .models import Priority, Task, User
from .service import TaskService

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_SORT_FIELD_MAP = {
    "dueDate": "due_date",
    "title": "title",
    "priority": "priority",
    "completed": "completed",
}


# ---------------------------------------------------------------- Schemas
class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    dueDate: Optional[date] = None
    assigneeUserId: Optional[int] = None
    priority: Priority = Priority.MEDIUM


class AssigneeUpdateRequest(BaseModel):
    userId: Optional[int] = None


class AutoPlus10Request(BaseModel):
    enabled: bool


class AskRequest(BaseModel):
    question: str


class AiCreateRequest(BaseModel):
    text: str


def serialize_user(user: User) -> dict:
    return {"id": user.id, "name": user.name}


def serialize_task(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "dueDate": task.due_date.isoformat() if task.due_date else None,
        "completed": task.completed,
        "createdAt": task.created_at.isoformat(),
        "assigneeUserId": task.assignee_user_id,
        "priority": task.priority.value,
    }


def create_app(service: Optional[TaskService] = None) -> FastAPI:
    app = FastAPI(title="Crastinator Pro API", version="0.1.0")
    task_service = service or TaskService()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_service() -> TaskService:
        return task_service

    @app.get("/api/users")
    def list_users(svc: TaskService = Depends(get_service)):
        return [serialize_user(u) for u in svc.list_users()]

    @app.post("/api/tasks", status_code=201)
    def create_task(body: TaskCreateRequest, svc: TaskService = Depends(get_service)):
        try:
            task = svc.create_task(
                title=body.title,
                description=body.description,
                due_date=body.dueDate,
                assignee_user_id=body.assigneeUserId,
                priority=body.priority,
            )
        except (ValidationError, UserNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return serialize_task(task)

    @app.get("/api/tasks")
    def list_tasks(
        sortBy: Optional[str] = Query(None),
        order: str = Query("asc"),
        assigneeUserId: Optional[int] = Query(None),
        completed: Optional[bool] = Query(None),
        referenceTime: Optional[datetime] = Query(None),
        svc: TaskService = Depends(get_service),
    ):
        reference_time = referenceTime or datetime.now()
        internal_sort_by = _SORT_FIELD_MAP.get(sortBy) if sortBy else None
        if sortBy is not None and internal_sort_by is None:
            raise HTTPException(
                status_code=400,
                detail=f"Ungültiges sortBy '{sortBy}'. Erlaubt: {sorted(_SORT_FIELD_MAP)}.",
            )
        try:
            tasks = svc.list_tasks(
                reference_time=reference_time,
                sort_by=internal_sort_by,
                order=order,
                assignee_user_id=assigneeUserId,
                completed=completed,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [serialize_task(t) for t in tasks]

    @app.get("/api/tasks/export", response_class=PlainTextResponse)
    def export_tasks(svc: TaskService = Depends(get_service)):
        csv_content = svc.export_csv()
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tasks.csv"},
        )

    @app.post("/api/tasks/import")
    async def import_tasks(file: UploadFile, svc: TaskService = Depends(get_service)):
        raw = await file.read()
        result = svc.import_csv(raw.decode("utf-8"))
        return {
            "created": [serialize_task(t) for t in result.created],
            "errors": [
                {"row": e.row_number, "reason": e.reason, "raw": e.raw} for e in result.errors
            ],
        }

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: int, svc: TaskService = Depends(get_service)):
        try:
            return serialize_task(svc.get_task(task_id))
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/tasks/{task_id}/toggle")
    def toggle_task(task_id: int, svc: TaskService = Depends(get_service)):
        try:
            return serialize_task(svc.toggle_task(task_id))
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/tasks/{task_id}", status_code=204)
    def delete_task(task_id: int, svc: TaskService = Depends(get_service)):
        try:
            svc.delete_task(task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return None

    @app.put("/api/tasks/{task_id}/assignee")
    def assign_task(
        task_id: int, body: AssigneeUpdateRequest, svc: TaskService = Depends(get_service)
    ):
        try:
            return serialize_task(svc.assign_task(task_id, body.userId))
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except UserNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/plus10")
    def plus_10(
        task_id: int,
        referenceTime: Optional[datetime] = Query(None),
        svc: TaskService = Depends(get_service),
    ):
        reference_time = referenceTime or datetime.now()
        try:
            return serialize_task(svc.plus_10(task_id, reference_time))
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except NoDueDateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/settings/auto-plus10")
    def get_auto_plus10(svc: TaskService = Depends(get_service)):
        return {"enabled": svc.get_auto_plus10()}

    @app.put("/api/settings/auto-plus10")
    def set_auto_plus10(body: AutoPlus10Request, svc: TaskService = Depends(get_service)):
        svc.set_auto_plus10(body.enabled)
        return {"enabled": svc.get_auto_plus10()}

    @app.post("/api/users/{user_id}/ask")
    def ask_ai(
        user_id: int,
        body: AskRequest,
        referenceTime: Optional[datetime] = Query(None),
        svc: TaskService = Depends(get_service),
    ):
        reference_time = referenceTime or datetime.now()
        try:
            answer = svc.ai_ask(user_id, body.question, reference_time)
        except UserNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"answer": answer}

    @app.post("/api/tasks/ai-create", status_code=201)
    def ai_create_task(
        body: AiCreateRequest,
        referenceTime: Optional[datetime] = Query(None),
        svc: TaskService = Depends(get_service),
    ):
        reference_time = referenceTime or datetime.now()
        try:
            task = svc.ai_create_task(body.text, reference_time)
        except (ValidationError, UserNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return serialize_task(task)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app


app = create_app()
