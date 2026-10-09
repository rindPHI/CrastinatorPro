"""Hypothesis profiles, pytest markers and shared helpers for the Crastinator Pro tests."""

from __future__ import annotations

import copy
import csv
import io
import json
import os
import urllib.request
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

import pytest
from hypothesis import settings

from crastinator_pro import AIProvider, CrastinatorError, Priority, Task, TaskService
from crastinator_pro.csv_io import ImportResult

# deadline=None: example runtime depends on the generated stock size and on the one-off TDP
# dataset load; runtime is measured deterministically in test_nonfunctional.py instead.
settings.register_profile(
    "default", max_examples=100, stateful_step_count=50, deadline=None
)
settings.register_profile(
    "thorough", max_examples=1000, stateful_step_count=100, deadline=None
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

AI_EXAMPLES = 10
ai_settings = settings(max_examples=AI_EXAMPLES)

AI_ENABLED = os.environ.get("CRASTINATOR_AI_TESTS") == "1"
JUDGE_ENABLED = bool(os.environ.get("JUDGE_API_KEY"))
requires_default_ai = pytest.mark.skipif(
    not AI_ENABLED, reason="set CRASTINATOR_AI_TESTS=1 to call the standard AI provider"
)
requires_judge = pytest.mark.skipif(
    not JUDGE_ENABLED, reason="set JUDGE_API_KEY to enable the LLM judge"
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "performance: runtime measurements with large stocks (slow)"
    )
    config.addinivalue_line("markers", "ai: tests of ai_ask and ai_create_task")


REF_TIME = datetime(2026, 1, 15, 9, 0)
NO_OVERDUE_TIME = datetime(
    1, 1, 1
)  # no due_date lies before date.min, so auto +10 never shifts
KNOWN_USER_IDS = (1, 2, 3)
INITIAL_USERS = [(1, "Alice"), (2, "Bob"), (3, "Carol")]
ASSIGNEE_CYCLE: list[Optional[int]] = [None, 1, 2, 3]

TaskContent = tuple[str, Optional[str], Optional[date], bool, Optional[int], Priority]
Operation = tuple[str, dict[str, Any]]


def content(task: Task) -> TaskContent:
    """All fields except id and created_at."""
    return (
        task.title,
        task.description,
        task.due_date,
        task.completed,
        task.assignee_user_id,
        Priority(task.priority),
    )


def loose_content(task: Task) -> TaskContent:
    """Like content(), but description None and "" count as equal."""
    return (
        task.title,
        task.description or "",
        task.due_date,
        task.completed,
        task.assignee_user_id,
        Priority(task.priority),
    )


def by_id(tasks: Iterable[Task]) -> dict[int, Task]:
    return {task.id: copy.deepcopy(task) for task in tasks}


def id_set(tasks: Iterable[Task]) -> set[int]:
    return {task.id for task in tasks}


def populate(
    tasks: Iterable[Task], ai_provider: Optional[AIProvider] = None
) -> tuple[TaskService, list[Task]]:
    """Fresh service filled via add_task; returns deep copies of the stored tasks."""
    service = TaskService(ai_provider=ai_provider)
    added = [copy.deepcopy(service.add_task(copy.deepcopy(task))) for task in tasks]
    return service, added


def current_tasks(service: TaskService) -> dict[int, Task]:
    """All tasks, read without triggering auto +10."""
    return by_id(service.list_tasks(reference_time=NO_OVERDUE_TIME))


def fetch(service: TaskService, task_ids: Iterable[int]) -> dict[int, Task]:
    return {task_id: copy.deepcopy(service.get_task(task_id)) for task_id in task_ids}


def replicate(
    templates: list[Task], count: int, assignees: list[Optional[int]]
) -> list[Task]:
    return [
        replace(
            templates[i % len(templates)],
            assignee_user_id=assignees[i % len(assignees)],
        )
        for i in range(count)
    ]


def read_csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline=""), strict=True))


def parse_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text, newline=""), strict=True))


def strip_columns(text: str, dropped: Iterable[str]) -> list[tuple[str, ...]]:
    """CSV rows (header included) without the given columns."""
    rows = read_csv_rows(text)
    if not rows:
        return []
    skip = set(dropped)
    keep = [i for i, name in enumerate(rows[0]) if name not in skip]
    return [tuple(row[i] if i < len(row) else "" for i in keep) for row in rows]


# --- workday model from PBT-12 ---------------------------------------------------------


def is_workday(day: date) -> bool:
    return day.weekday() < 5


def workdays_in(start: date, end: date) -> int:
    """Monday-to-Friday days in the half-open interval (start, end]."""
    return sum(
        1
        for offset in range(1, (end - start).days + 1)
        if is_workday(start + timedelta(days=offset))
    )


def plus_10_model(day: date) -> date:
    counted = 0
    while counted < 10:
        day += timedelta(days=1)
        counted += is_workday(day)
    return day


def auto_shift_model(day: date, today: date) -> date:
    """Repeated +10 until the date is no longer before today (smallest k >= 1, PBT-13)."""
    if day >= today:
        return day
    shifted = plus_10_model(day)
    if shifted >= today:
        return shifted
    # after the first step the date is a workday, so every further step adds 14 days (PBT-12)
    return shifted + timedelta(days=14 * -(-(today - shifted).days // 14))


# --- ordering from PBT-02 --------------------------------------------------------------

PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}
_PLAIN_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")


def din5007(text: str) -> str:
    """DIN 5007-1 key from PBT-02: case-insensitive, ä=a, ö=o, ü=u, ß=ss."""
    return (
        text.lower()
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ß", "ss")
    )


def sort_key(task: Task, sort_by: str) -> Any:
    if sort_by == "due_date":
        return (task.due_date is None, task.due_date or date.min)
    if sort_by == "priority":
        return PRIORITY_RANK[Priority(task.priority)]
    if sort_by == "completed":
        return task.completed
    return din5007(task.title)


def _title_order_defined(first: str, second: str) -> bool:
    """PBT-02 fixes only the order of letters; pairs decided by other characters are skipped."""
    for a, b in zip(first, second):
        if a != b:
            return a in _PLAIN_LETTERS and b in _PLAIN_LETTERS
    rest = first[len(second) :] or second[len(first) :]
    return all(char in _PLAIN_LETTERS for char in rest)


def assert_sorted(tasks: list[Task], sort_by: str, order: str, scenario: str) -> None:
    keys = [sort_key(task, sort_by) for task in tasks]
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            first, second = keys[i], keys[j]
            if sort_by == "title" and not _title_order_defined(first, second):
                continue
            if order == "desc":
                first, second = second, first
            assert (
                first <= second
            ), f"{scenario}: {tasks[i]!r} precedes {tasks[j]!r} against {sort_by} {order}"


# --- search model from PBT-04 ----------------------------------------------------------


def split_query(query: str) -> list[str]:
    return [term for term in query.split(" ") if term]


def matches_query(task: Task, terms: list[str]) -> bool:
    def contains(field: Optional[str], term: str) -> bool:
        return field is not None and term.lower() in field.lower()

    return all(contains(task.title, t) or contains(task.description, t) for t in terms)


def satisfies_task_invariants(task: Task) -> bool:
    """Invariants from PBT-17 for a single task."""
    return (
        any(not char.isspace() for char in task.title)
        and task.assignee_user_id in (None, *KNOWN_USER_IDS)
        and isinstance(task.priority, Priority)
        and type(task.completed) is bool
    )


# --- system time (created_at, PBT-08) --------------------------------------------------


def system_now() -> tuple[datetime, datetime]:
    return datetime.now(), datetime.now(timezone.utc)


def created_between(
    created_at: datetime,
    before: tuple[datetime, datetime],
    after: tuple[datetime, datetime],
) -> bool:
    if created_at.tzinfo is not None:
        return before[1] <= created_at <= after[1]
    # a naive timestamp may be local time or UTC; the scenario only says "system time"
    naive_utc = (before[1].replace(tzinfo=None), after[1].replace(tzinfo=None))
    return (
        before[0] <= created_at <= after[0]
        or naive_utc[0] <= created_at <= naive_utc[1]
    )


def holds_in_majority(
    check: Callable[[], bool], runs: int = 5, required: int = 4
) -> bool:
    """Repetition rule: at least `required` of `runs` runs satisfy the check."""

    def one_run() -> bool:
        try:
            return check()
        except CrastinatorError:
            return False

    return sum(one_run() for _ in range(runs)) >= required


# --- stub provider ---------------------------------------------------------------------

# due_date stays None: the value type parse_task() must use for dates is not documented.
STUB_PARSED: dict[str, Any] = {
    "title": "Stub-Task",
    "description": None,
    "due_date": None,
    "assignee_user_id": None,
    "priority": Priority.MEDIUM,
}


class RecordingProvider(AIProvider):
    """Deterministic stub: records answer() calls, returns a configurable parse_task() dict."""

    def __init__(self, parsed: Optional[dict[str, Any]] = None) -> None:
        self.parsed = dict(parsed or STUB_PARSED)
        self.answer_calls: list[tuple[str, list[Task], datetime]] = []

    def answer(self, question: str, tasks: list[Task], reference_time: datetime) -> str:
        received = copy.deepcopy(list(tasks))
        self.answer_calls.append((question, received, reference_time))
        listed = ";".join(f"{task.id}:{task.title}" for task in received)
        return f"stub|{question}|{reference_time.isoformat()}|{listed}"

    def parse_task(self, text: str, reference_time: datetime) -> dict:
        return dict(self.parsed)


# --- generic operations (PBT-17, PBT-18, PBT-24) ---------------------------------------

READ_OPERATIONS = frozenset(
    {
        "export_csv",
        "get_task",
        "get_user",
        "list_users",
        "get_auto",
        "ai_ask",
        "list_tasks",
    }
)


def _existing_ids(service: TaskService) -> list[int]:
    return sorted(
        task.id for task in service.list_tasks(reference_time=NO_OVERDUE_TIME)
    )


def _resolve(service: TaskService, pick: Optional[int]) -> int:
    """Existing id chosen by pick, or a non-existing id for pick=None or an empty stock."""
    ids = _existing_ids(service)
    if pick is None or not ids:
        return max(ids, default=0) + 1000
    return ids[pick % len(ids)]


def _dispatch(
    service: TaskService,
    name: str,
    args: dict[str, Any],
    provider: Optional[RecordingProvider],
) -> Any:
    if name == "create":
        return service.create_task(**args)
    if name == "add":
        task = copy.deepcopy(args["task"])
        if args["reuse"] is not None and _existing_ids(service):
            task.id = _resolve(service, args["reuse"])
        return service.add_task(task)
    if name == "toggle":
        return service.toggle_task(_resolve(service, args["pick"]))
    if name == "delete":
        return service.delete_task(_resolve(service, args["pick"]))
    if name == "get_task":
        return service.get_task(_resolve(service, args["pick"]))
    if name == "assign":
        return service.assign_task(_resolve(service, args["pick"]), args["user_id"])
    if name == "plus_10":
        return service.plus_10(_resolve(service, args["pick"]), args["reference_time"])
    if name == "set_auto":
        return service.set_auto_plus10(args["enabled"])
    if name == "list_tasks":
        return service.list_tasks(**args["kwargs"])
    if name == "import_csv":
        return service.import_csv(args["csv"])
    if name == "list_users":
        return service.list_users()
    if name == "get_user":
        return service.get_user(args["user_id"])
    if name == "get_auto":
        return service.get_auto_plus10()
    if name == "ai_ask":
        return service.ai_ask(args["user_id"], args["question"], args["reference_time"])
    if name == "ai_create":
        if provider is not None:
            provider.parsed = dict(args["parsed"])
        return service.ai_create_task(args["text"], args["reference_time"])
    raise ValueError(f"unknown operation {name!r}")


def normalize(value: Any) -> Any:
    """Comparable outcome without created_at."""
    if isinstance(value, Task):
        return ("task", value.id, content(value))
    if isinstance(value, ImportResult):
        return (
            "import",
            normalize(value.created),
            [(e.row_number, e.reason, e.raw) for e in value.errors],
        )
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def apply_operation(
    service: TaskService,
    operation: Operation,
    provider: Optional[RecordingProvider] = None,
) -> Any:
    name, args = operation
    try:
        if name == "export_csv":
            return strip_columns(service.export_csv(), ["createdAt"])
        return normalize(_dispatch(service, name, args, provider))
    except CrastinatorError as error:
        return (
            "error",
            type(error).__name__,
            getattr(error, "task_id", None),
            getattr(error, "user_id", None),
        )


# --- LLM-as-a-judge --------------------------------------------------------------------

CONFIRMED, DENIED, UNCLEAR = "bestätigt", "verneint", "unklar"
EQUIVALENT, NOT_EQUIVALENT = "gleichwertig", "nicht gleichwertig"
SAME_TASKS, DIFFERENT_TASKS = "gleiche Tasks genannt", "abweichend"

_CONFIRMATION_PROMPT = (
    "Du bewertest die Antwort eines Task-Assistenten.\nFrage: {question}\nAntwort: {answer}\n\n"
    "Bestätigt die Antwort den in der Ja/Nein-Frage erfragten Sachverhalt, verneint sie ihn oder ist sie "
    "unklar? Antworte ausschließlich mit genau einem Wort: bestätigt, verneint oder unklar."
)
_EQUIVALENCE_PROMPT = (
    "Vergleiche zwei Tasks, die aus umformulierten Freitexten erzeugt wurden.\n"
    "Task A: Titel: {title_a} | Beschreibung: {description_a}\n"
    "Task B: Titel: {title_b} | Beschreibung: {description_b}\n\n"
    "Sind Titel und Beschreibung inhaltlich gleichwertig? Antworte ausschließlich mit "
    "'gleichwertig' oder 'nicht gleichwertig'."
)
_SAME_TASKS_PROMPT = (
    "Referenzliste der Task-Titel:\n{titles}\n\nAntwort 1:\n{first}\n\nAntwort 2:\n{second}\n\n"
    "Nennen beide Antworten dieselben Tasks aus der Referenzliste? Ignoriere konkrete Datumsangaben "
    "und Formulierungen. Antworte ausschließlich mit 'gleiche Tasks genannt' oder 'abweichend'."
)


def _ask_judge(prompt: str) -> str:
    base_url = os.environ.get("JUDGE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": os.environ.get("JUDGE_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['JUDGE_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.load(response)
    return str(body["choices"][0]["message"]["content"])


def _classify(reply: str, labels: list[str], fallback: str) -> str:
    text = reply.strip().lower()
    return next((label for label in labels if label in text), fallback)


def judge_confirmation(question: str, answer: str) -> str:
    reply = _ask_judge(_CONFIRMATION_PROMPT.format(question=question, answer=answer))
    return _classify(reply, [DENIED, UNCLEAR, CONFIRMED], UNCLEAR)


def judge_equivalence(
    title_a: str,
    description_a: Optional[str],
    title_b: str,
    description_b: Optional[str],
) -> str:
    reply = _ask_judge(
        _EQUIVALENCE_PROMPT.format(
            title_a=title_a,
            description_a=description_a or "",
            title_b=title_b,
            description_b=description_b or "",
        )
    )
    return _classify(reply, [NOT_EQUIVALENT, EQUIVALENT], NOT_EQUIVALENT)


def judge_same_tasks(titles: list[str], first: str, second: str) -> str:
    reply = _ask_judge(
        _SAME_TASKS_PROMPT.format(
            titles="\n".join(f"- {t}" for t in titles), first=first, second=second
        )
    )
    return _classify(reply, [SAME_TASKS, DIFFERENT_TASKS], DIFFERENT_TASKS)
