"""Stateful property-based tests: PBT-07 to PBT-17 and PBT-24."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import pytest
from hypothesis import given, strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    initialize,
    invariant,
    multiple,
    rule,
)
from hypothesis.strategies import SearchStrategy

from conftest import (
    INITIAL_USERS,
    NO_OVERDUE_TIME,
    REF_TIME,
    Operation,
    RecordingProvider,
    TaskContent,
    ai_settings,
    apply_operation,
    auto_shift_model,
    by_id,
    content,
    created_between,
    current_tasks,
    fetch,
    holds_in_majority,
    id_set,
    is_workday,
    loose_content,
    normalize,
    plus_10_model,
    populate,
    read_csv_rows,
    requires_default_ai,
    satisfies_task_invariants,
    strip_columns,
    system_now,
    workdays_in,
)
from crastinator_pro import (
    NoDueDateError,
    Priority,
    Task,
    TaskNotFoundError,
    TaskService,
    UserNotFoundError,
    ValidationError,
)
from strategies import (
    INVALID_ORDERS,
    INVALID_SORT_FIELDS,
    MAX_TASKS,
    ORDERS,
    PLAIN_TODO_TEXTS,
    SORT_FIELDS,
    ImportFile,
    assignees,
    blank_titles,
    creation_kwargs,
    csv_tasks,
    descriptions,
    expected_import_content,
    list_filters,
    list_kwargs,
    mixed_import_files,
    operations,
    optional_edge_dates,
    plus10_tasks,
    priorities,
    reference_times,
    relative_stocks,
    stocks_with_duplicates,
    task_strategy,
    task_to_row,
    tasks,
    unknown_user_ids,
    user_ids,
    valid_titles,
)

# --- PBT-07 ----------------------------------------------------------------------------

TITLE, DESCRIPTION, DUE_DATE, COMPLETED, ASSIGNEE, PRIORITY = range(6)


def _with_field(entry: TaskContent, index: int, value: Any) -> TaskContent:
    fields = list(entry)
    fields[index] = value
    return tuple(fields)  # type: ignore[return-value]


def addable_tasks() -> SearchStrategy[Task]:
    return task_strategy(
        vary={
            "title": valid_titles(),
            "description": descriptions(),
            "due_date": optional_edge_dates(),
            "completed": st.booleans(),
            "assignee_user_id": assignees(),
            "priority": priorities(),
        }
    )


class ReferenceModelMachine(RuleBasedStateMachine):
    """PBT-07: random valid operation sequences behave like a map from id to task content."""

    ids = Bundle("ids")

    def __init__(self) -> None:
        super().__init__()
        self.service = TaskService()  # auto +10 stays off
        self.model: dict[int, TaskContent] = {}

    def _add(self, task: Task) -> int:
        # Annahme: add_task übernimmt title, description, due_date, completed, assignee_user_id und priority
        # des übergebenen Objekts unverändert, nur die id wird neu vergeben.
        stored = self.service.add_task(copy.deepcopy(task))
        assert (
            stored.id not in self.model
        ), f"PBT-07: add_task returned the taken id {stored.id}"
        self.model[stored.id] = content(task)
        return stored.id

    @initialize(target=ids, stock=st.lists(addable_tasks(), max_size=10))
    def seed(self, stock: list[Task]) -> Any:
        return multiple(*(self._add(task) for task in stock))

    @rule(target=ids, kwargs=creation_kwargs())
    def create(self, kwargs: dict[str, Any]) -> int:
        task = self.service.create_task(**kwargs)
        assert (
            task.id not in self.model
        ), f"PBT-07: create_task returned the taken id {task.id}"
        self.model[task.id] = (
            kwargs["title"],
            kwargs["description"],
            kwargs["due_date"],
            False,
            kwargs["assignee_user_id"],
            Priority(kwargs["priority"]),
        )
        return task.id

    @rule(target=ids, task=addable_tasks())
    def add(self, task: Task) -> int:
        return self._add(task)

    @rule(target=ids, taken=ids, task=addable_tasks())
    def add_with_taken_id(self, taken: int, task: Task) -> int:
        existing = copy.deepcopy(self.service.get_task(taken))
        new_id = self._add(replace(task, id=taken))
        assert (
            self.service.get_task(taken) == existing
        ), f"PBT-07: add_task changed the task with id {taken}"
        return new_id

    @rule(task_id=ids)
    def toggle(self, task_id: int) -> None:
        self.service.toggle_task(task_id)
        entry = self.model[task_id]
        self.model[task_id] = _with_field(entry, COMPLETED, not entry[COMPLETED])

    @rule(task_id=consumes(ids))
    def delete(self, task_id: int) -> None:
        self.service.delete_task(task_id)
        del self.model[task_id]

    @rule(task_id=ids, user_id=assignees())
    def assign(self, task_id: int, user_id: Optional[int]) -> None:
        self.service.assign_task(task_id, user_id)
        self.model[task_id] = _with_field(self.model[task_id], ASSIGNEE, user_id)

    @rule(task_id=ids, reference_time=reference_times())
    def plus_10(self, task_id: int, reference_time: datetime) -> None:
        due = self.model[task_id][DUE_DATE]
        if due is None:
            return  # only valid operations: plus_10 requires a due_date
        self.service.plus_10(task_id, reference_time)
        self.model[task_id] = _with_field(
            self.model[task_id], DUE_DATE, plus_10_model(due)
        )

    @invariant()
    def matches_model(self) -> None:
        listed = self.service.list_tasks(reference_time=REF_TIME)
        listed_ids = [task.id for task in listed]
        assert len(listed_ids) == len(
            set(listed_ids)
        ), f"PBT-07: duplicate ids {listed_ids}"
        assert {
            task.id: content(task) for task in listed
        } == self.model, "PBT-07: list_tasks differs from the model"
        for task_id, entry in self.model.items():
            assert (
                content(self.service.get_task(task_id)) == entry
            ), f"PBT-07: get_task({task_id}) differs"


TestReferenceModel = ReferenceModelMachine.TestCase

# --- PBT-08 ----------------------------------------------------------------------------

OPTIONAL_CREATE_FIELDS = ("description", "due_date", "assignee_user_id")
GIVEN_IMPORT_COLUMNS = ("description", "dueDate", "assigneeUserId")
STATUS_COLUMNS = ("completed", "priority")


def _given_fields(task: Task, names: frozenset[str]) -> dict[str, Any]:
    return {
        name: getattr(task, name) for name in OPTIONAL_CREATE_FIELDS if name in names
    }


def _assert_defaults(task: Task, given_fields: dict[str, Any]) -> None:
    assert task.completed is False, f"PBT-08: completed is {task.completed!r}"
    assert (
        Priority(task.priority) == Priority.MEDIUM
    ), f"PBT-08: priority is {task.priority!r}"
    for name, value in given_fields.items():
        assert (
            getattr(task, name) == value
        ), f"PBT-08: {name} is {getattr(task, name)!r}, expected {value!r}"


@st.composite
def _imports_without_status(draw: Any) -> ImportFile:
    given_columns = draw(st.sets(st.sampled_from(GIVEN_IMPORT_COLUMNS)))
    empty_columns = draw(
        st.sets(st.sampled_from(STATUS_COLUMNS))
    )  # present but empty; absent otherwise
    columns = ("title", *sorted(given_columns), *sorted(empty_columns))
    rows = []
    for task in draw(st.lists(tasks(), min_size=1, max_size=5)):
        full = task_to_row(task)
        rows.append(
            {
                column: "" if column in empty_columns else full[column]
                for column in columns
            }
        )
    return ImportFile(
        columns, tuple(rows), tuple(expected_import_content(row) for row in rows)
    )


@given(task=tasks(), names=st.frozensets(st.sampled_from(OPTIONAL_CREATE_FIELDS)))
def _defaults_create_task(task: Task, names: frozenset[str]) -> None:
    service = TaskService()
    fields = _given_fields(task, names)
    before = system_now()
    created = service.create_task(title=task.title, **fields)
    after = system_now()
    _assert_defaults(created, fields)
    _assert_defaults(service.get_task(created.id), fields)
    assert created_between(
        created.created_at, before, after
    ), f"PBT-08: created_at {created.created_at} out of range"


@given(task=tasks(), names=st.frozensets(st.sampled_from(OPTIONAL_CREATE_FIELDS)))
def _defaults_add_task(task: Task, names: frozenset[str]) -> None:
    # Annahme: Bei add_task wird created_at nicht geprüft, weil "sofern nicht angegeben" (REQ-101)
    # bei einem Objekt mit Default-Wert nicht eindeutig ist.
    service = TaskService()
    fields = _given_fields(task, names)
    created = service.add_task(Task(id=task.id, title=task.title, **fields))
    _assert_defaults(created, fields)
    _assert_defaults(service.get_task(created.id), fields)


@given(file=_imports_without_status())
def _defaults_import_csv(file: ImportFile) -> None:
    service = TaskService()
    before = system_now()
    result = service.import_csv(file.text)
    after = system_now()
    assert result.errors == [], f"PBT-08: import rejected rows {result.errors!r}"
    assert Counter(loose_content(task) for task in result.created) == Counter(
        file.expected
    ), "PBT-08: imported values differ from the given values plus defaults"
    for task in result.created:
        _assert_defaults(task, {})
        assert created_between(
            task.created_at, before, after
        ), f"PBT-08: created_at {task.created_at} out of range"


@ai_settings
@given(text=st.sampled_from(PLAIN_TODO_TEXTS), reference_time=reference_times())
def _defaults_ai_create_task(text: str, reference_time: datetime) -> None:
    def run() -> bool:
        service = TaskService()
        before = system_now()
        task = service.ai_create_task(text, reference_time)
        after = system_now()
        return (
            task.completed is False
            and Priority(task.priority) == Priority.MEDIUM
            and created_between(task.created_at, before, after)
        )

    assert holds_in_majority(
        run
    ), f"PBT-08: defaults violated in more than 1 of 5 runs for {text!r}"


DEFAULT_CHECKS: dict[str, Callable[[], None]] = {
    "create_task": _defaults_create_task,
    "add_task": _defaults_add_task,
    "import_csv": _defaults_import_csv,
    "ai_create_task": _defaults_ai_create_task,
}


@pytest.mark.parametrize(
    "channel",
    [
        "create_task",
        "add_task",
        "import_csv",
        pytest.param("ai_create_task", marks=[pytest.mark.ai, requires_default_ai]),
    ],
)
def test_pbt08_creation_defaults(channel: str) -> None:
    """PBT-08: new tasks get completed=False, priority=MEDIUM, a current created_at and keep given fields."""
    DEFAULT_CHECKS[channel]()


# --- PBT-09 ----------------------------------------------------------------------------

INVALID_CALLS = (
    "create_blank_title",
    "add_blank_title",
    "create_unknown_assignee",
    "add_unknown_assignee",
    "assign_unknown_user",
    "toggle_missing",
    "delete_missing",
    "plus_10_missing",
    "plus_10_no_due_date",
    "invalid_sort_by",
    "invalid_order",
)
LIST_ERROR_TIME = datetime(
    2300, 1, 1
)  # all generated due dates lie before, so open dated tasks are overdue
Expectation = tuple[Callable[[], Any], type[Exception], Optional[str], Any]


def _missing_task_id(service: TaskService, ids: list[int], data: st.DataObject) -> int:
    """A deleted id (double delete) or an id that never existed."""
    if ids and data.draw(st.booleans(), label="use deleted id"):
        task_id = ids.pop(
            data.draw(st.integers(0, len(ids) - 1), label="deleted index")
        )
        service.delete_task(task_id)
        return task_id
    return max(ids, default=0) + data.draw(st.integers(1, 1000), label="id offset")


def _prepare_invalid_call(
    service: TaskService, ids: list[int], kind: str, data: st.DataObject
) -> Expectation:
    if kind == "create_blank_title":
        title = data.draw(blank_titles(), label="title")
        return (lambda: service.create_task(title=title)), ValidationError, None, None
    if kind == "add_blank_title":
        blank = data.draw(task_strategy(title=blank_titles()), label="task")
        return (lambda: service.add_task(blank)), ValidationError, None, None
    if kind == "create_unknown_assignee":
        title, user = data.draw(valid_titles(), label="title"), data.draw(
            unknown_user_ids(), label="user"
        )
        return (
            (lambda: service.create_task(title=title, assignee_user_id=user)),
            UserNotFoundError,
            "user_id",
            user,
        )
    if kind == "add_unknown_assignee":
        foreign = data.draw(
            task_strategy(assignee_user_id=unknown_user_ids()), label="task"
        )
        return (
            (lambda: service.add_task(foreign)),
            UserNotFoundError,
            "user_id",
            foreign.assignee_user_id,
        )
    if kind == "assign_unknown_user":
        if not ids:
            ids.append(service.create_task(title="Ziel").id)
        task_id, user = data.draw(st.sampled_from(ids), label="task"), data.draw(
            unknown_user_ids(), label="user"
        )
        return (
            (lambda: service.assign_task(task_id, user)),
            UserNotFoundError,
            "user_id",
            user,
        )
    if kind in ("toggle_missing", "delete_missing", "plus_10_missing"):
        missing = _missing_task_id(service, ids, data)
        calls = {
            "toggle_missing": lambda: service.toggle_task(missing),
            "delete_missing": lambda: service.delete_task(missing),
            "plus_10_missing": lambda: service.plus_10(missing, REF_TIME),
        }
        return calls[kind], TaskNotFoundError, "task_id", missing
    if kind == "plus_10_no_due_date":
        undated = service.add_task(
            data.draw(task_strategy(due_date=st.none()), label="task")
        ).id
        ids.append(undated)
        return (
            (lambda: service.plus_10(undated, REF_TIME)),
            NoDueDateError,
            "task_id",
            undated,
        )
    sort_by = data.draw(
        st.sampled_from(
            INVALID_SORT_FIELDS if kind == "invalid_sort_by" else SORT_FIELDS
        )
    )
    order = data.draw(
        st.sampled_from(INVALID_ORDERS if kind == "invalid_order" else ORDERS)
    )
    return (
        (
            lambda: service.list_tasks(
                reference_time=LIST_ERROR_TIME, sort_by=sort_by, order=order
            )
        ),
        ValidationError,
        None,
        None,
    )


@given(
    stock=st.lists(tasks(), max_size=MAX_TASKS),
    auto=st.booleans(),
    kind=st.sampled_from(INVALID_CALLS),
    data=st.data(),
)
def test_pbt09_errors_leave_state_unchanged(
    stock: list[Task], auto: bool, kind: str, data: st.DataObject
) -> None:
    """PBT-09: every invalid call raises the matching exception and leaves the state unchanged."""
    # Annahme: Unzulässiges sort_by oder order führt zu ValidationError ohne Zustandsänderung, auch ohne
    # Auto-+10-Verschiebung. Ein unzulässiges order ohne sort_by wird ignoriert und nicht als Fehlerfall geprüft.
    service, added = populate(stock)
    service.set_auto_plus10(auto)
    ids = [task.id for task in added]
    call, error_type, attribute, value = _prepare_invalid_call(service, ids, kind, data)
    exported, snapshot = service.export_csv(), fetch(service, ids)
    with pytest.raises(error_type) as caught:
        call()
    if attribute is not None:
        actual = getattr(caught.value, attribute)
        assert (
            actual == value
        ), f"PBT-09: {kind} raised with {attribute}={actual!r}, expected {value!r}"
    assert service.export_csv() == exported, f"PBT-09: {kind} changed export_csv"
    assert fetch(service, ids) == snapshot, f"PBT-09: {kind} changed get_task results"


# --- PBT-10 ----------------------------------------------------------------------------

FAR_FUTURE = st.datetimes(datetime(2200, 1, 1), datetime(9999, 1, 1))


def _with_reference_time(
    kwargs: dict[str, Any], moment: Optional[datetime]
) -> dict[str, Any]:
    return kwargs if moment is None else {**kwargs, "reference_time": moment}


def read_operations() -> SearchStrategy[Operation]:
    picks = st.none() | st.integers(0, 10_000)

    def op(name: str, **fields: SearchStrategy[Any]) -> SearchStrategy[Operation]:
        return st.tuples(st.just(name), st.fixed_dictionaries(fields))

    listing = st.builds(_with_reference_time, list_kwargs(), st.none() | FAR_FUTURE)
    return st.one_of(
        op("list_tasks", kwargs=listing),
        op("get_task", pick=picks),
        op("get_user", user_id=st.integers()),
        op("list_users"),
        op("get_auto"),
        op("export_csv"),
        op(
            "ai_ask",
            user_id=st.one_of(user_ids(), unknown_user_ids()),
            question=st.text(max_size=40),
            reference_time=st.one_of(reference_times(), FAR_FUTURE),
        ),
    )


@given(
    stock=st.lists(tasks(), max_size=MAX_TASKS),
    reads=st.lists(read_operations(), max_size=20),
)
def test_pbt10_reads_do_not_change_state(
    stock: list[Task], reads: list[Operation]
) -> None:
    """PBT-10: read-only calls leave export_csv and get_auto_plus10 unchanged."""
    service, _ = populate(stock, ai_provider=RecordingProvider())
    exported, auto = service.export_csv(), service.get_auto_plus10()
    for operation in reads:
        apply_operation(service, operation)
    assert (
        service.export_csv() == exported
    ), "PBT-10: read-only calls changed export_csv"
    assert (
        service.get_auto_plus10() == auto
    ), "PBT-10: read-only calls changed get_auto_plus10"


# --- PBT-11 ----------------------------------------------------------------------------


@given(
    stock=st.lists(tasks(), min_size=1, max_size=MAX_TASKS),
    pick=st.integers(min_value=0),
)
def test_pbt11_toggle_is_involution(stock: list[Task], pick: int) -> None:
    """PBT-11: toggling negates completed only; toggling twice restores the task."""
    service, added = populate(stock)
    target = added[pick % len(added)].id
    before = current_tasks(service)
    service.toggle_task(target)
    expected = {
        **before,
        target: replace(before[target], completed=not before[target].completed),
    }
    assert (
        current_tasks(service) == expected
    ), f"PBT-11: one toggle of {target} changed more than completed"
    service.toggle_task(target)
    assert (
        current_tasks(service) == before
    ), f"PBT-11: two toggles of {target} did not restore the state"


# --- PBT-12 ----------------------------------------------------------------------------

DAYS_BY_WEEKDAY = {0: 14, 1: 14, 2: 14, 3: 14, 4: 14, 5: 13, 6: 12}


@given(task=plus10_tasks(), reference_time=reference_times())
def test_pbt12_plus_10_counts_ten_workdays(
    task: Task, reference_time: datetime
) -> None:
    """PBT-12: plus_10 moves due_date to the 10th Monday-to-Friday day after the old date."""
    service, (stored,) = populate([task])
    old = stored.due_date
    service.plus_10(stored.id, reference_time)
    updated = service.get_task(stored.id)
    new = updated.due_date
    assert new > old, f"PBT-12: {new} is not after {old}"
    assert (
        workdays_in(old, new) == 10
    ), f"PBT-12: ({old}, {new}] has {workdays_in(old, new)} workdays"
    assert is_workday(new), f"PBT-12: {new} is no workday"
    assert new - old == timedelta(
        days=DAYS_BY_WEEKDAY[old.weekday()]
    ), f"PBT-12: wrong step from {old} to {new}"
    assert (
        replace(updated, due_date=old) == stored
    ), "PBT-12: plus_10 changed other fields"


# --- PBT-13 ----------------------------------------------------------------------------


@given(reference_time=reference_times(), data=st.data())
def test_pbt13_auto_plus_10_shifts_overdue_results(
    reference_time: datetime, data: st.DataObject
) -> None:
    """PBT-13: with auto +10 on, only open overdue tasks in the result move, by the smallest sufficient k."""
    stock = data.draw(relative_stocks(reference_time), label="stock")
    service, added = populate([replace(task, completed=False) for task in stock])
    for stored, original in zip(added, stock):
        if original.completed:
            service.toggle_task(stored.id)
    before = current_tasks(service)
    filters = data.draw(list_filters(added), label="filters")
    service.set_auto_plus10(True)
    result = service.list_tasks(reference_time=reference_time, **filters)
    after = current_tasks(service)
    today, hits = reference_time.date(), id_set(result)
    for task_id, old in before.items():
        due = old.due_date
        overdue = (
            task_id in hits and not old.completed and due is not None and due < today
        )
        expected = replace(
            old, due_date=auto_shift_model(due, today) if overdue else due
        )
        assert (
            after[task_id] == expected
        ), f"PBT-13: task {task_id} is {after[task_id]!r}, expected {expected!r}"
    assert by_id(result) == {
        task_id: after[task_id] for task_id in hits
    }, "PBT-13: result does not show new values"


# --- PBT-14 ----------------------------------------------------------------------------


@given(
    stock=st.lists(tasks(), max_size=MAX_TASKS),
    switches=st.lists(st.booleans(), max_size=20),
)
def test_pbt14_switch_state(stock: list[Task], switches: list[bool]) -> None:
    """PBT-14: the switch starts False, reports the last set value and setting it moves no due date."""
    assert (
        TaskService().get_auto_plus10() is False
    ), "PBT-14: fresh instance reports auto +10 on"
    service, _ = populate(stock)
    assert (
        service.get_auto_plus10() is False
    ), "PBT-14: adding tasks switched auto +10 on"
    exported = service.export_csv()
    for enabled in switches:
        service.set_auto_plus10(enabled)
        assert (
            service.get_auto_plus10() is enabled
        ), f"PBT-14: get_auto_plus10 is not {enabled}"
    assert (
        service.export_csv() == exported
    ), "PBT-14: setting the switch changed due dates"


# --- PBT-15 ----------------------------------------------------------------------------


@given(stock=st.lists(tasks(), max_size=MAX_TASKS), file=mixed_import_files())
def test_pbt15_import_with_mixed_rows(stock: list[Task], file: ImportFile) -> None:
    """PBT-15: valid rows become tasks, every invalid row is reported once with row_number, reason and raw."""
    service, _ = populate(stock)
    before = current_tasks(service)
    result = service.import_csv(file.text)
    assert len(result.created) + len(result.errors) == len(
        file.rows
    ), "PBT-15: |created| + |errors| != m"
    invalid_rows = [
        index + 1 for index, expected in enumerate(file.expected) if expected is None
    ]
    assert (
        sorted(error.row_number for error in result.errors) == invalid_rows
    ), "PBT-15: wrong error rows"
    for error in result.errors:
        row = file.rows[error.row_number - 1]
        assert error.reason, f"PBT-15: empty reason for row {error.row_number}"
        assert all(
            error.raw.get(column) == value for column, value in row.items()
        ), f"PBT-15: raw {error.raw!r} differs from row {row!r}"
    expected_created = Counter(
        expected for expected in file.expected if expected is not None
    )
    assert (
        Counter(loose_content(task) for task in result.created) == expected_created
    ), "PBT-15: wrong created values"
    after = current_tasks(service)
    assert len(after) == len(before) + len(
        result.created
    ), "PBT-15: stock did not grow by |created|"
    assert {
        task_id: after.get(task_id) for task_id in before
    } == before, "PBT-15: existing tasks changed"
    assert id_set(result.created) <= set(after) - set(
        before
    ), "PBT-15: created tasks are not new tasks in the stock"


# --- PBT-16 ----------------------------------------------------------------------------


@given(stock=stocks_with_duplicates(csv_tasks()))
def test_pbt16_export_import_round_trip(stock: list[Task]) -> None:
    """PBT-16: importing an export into a fresh instance reproduces the stock 1:1 (without id and created_at)."""
    source, added = populate(stock)
    exported = source.export_csv()
    target = TaskService()
    result = target.import_csv(exported)
    assert result.errors == [], f"PBT-16: round trip produced errors {result.errors!r}"
    assert len(result.created) == len(added), "PBT-16: |created| != |S|"
    assert Counter(loose_content(task) for task in result.created) == Counter(
        loose_content(task) for task in added
    ), "PBT-16: no 1:1 assignment between S and the imported tasks"
    first = strip_columns(exported, ("id", "createdAt"))
    second = strip_columns(target.export_csv(), ("id", "createdAt"))
    assert first[:1] == second[:1] and Counter(first[1:]) == Counter(
        second[1:]
    ), "PBT-16: second export does not match the first one 1:1"


# --- PBT-17 ----------------------------------------------------------------------------


class GlobalInvariantMachine(RuleBasedStateMachine):
    """PBT-17: id uniqueness and field invariants hold after every valid or invalid operation."""

    def __init__(self) -> None:
        super().__init__()
        self.provider = RecordingProvider()
        self.service = TaskService(ai_provider=self.provider)

    @initialize(stock=st.lists(tasks(), max_size=10))
    def seed(self, stock: list[Task]) -> None:
        for task in stock:
            self.service.add_task(copy.deepcopy(task))

    @rule(operation=operations(include_ai_create=True))
    def step(self, operation: Operation) -> None:
        apply_operation(self.service, operation, self.provider)

    @invariant()
    def invariants_hold(self) -> None:
        listed = self.service.list_tasks(reference_time=NO_OVERDUE_TIME)
        listed_ids = [task.id for task in listed]
        assert len(listed_ids) == len(
            set(listed_ids)
        ), f"PBT-17: duplicate ids {listed_ids}"
        for task in listed:
            assert satisfies_task_invariants(
                task
            ), f"PBT-17: invariant violated by {task!r}"
        users = sorted((user.id, user.name) for user in self.service.list_users())
        assert users == INITIAL_USERS, f"PBT-17: users changed to {users}"


TestGlobalInvariants = GlobalInvariantMachine.TestCase

# --- PBT-24 ----------------------------------------------------------------------------


def _observe(service: TaskService) -> tuple[Any, ...]:
    return (
        service.export_csv(),
        service.get_auto_plus10(),
        service.list_users(),
        normalize(service.list_tasks(reference_time=NO_OVERDUE_TIME)),
    )


@given(
    steps=st.lists(st.tuples(st.integers(0, 2), operations()), max_size=30),
    times=st.lists(
        st.one_of(reference_times(), st.datetimes()), min_size=1, max_size=5
    ),
)
def test_pbt24_fresh_instances_are_empty_and_independent(
    steps: list[tuple[int, Operation]], times: list[datetime]
) -> None:
    """PBT-24: operations on one instance never affect another; a fresh instance is empty with auto +10 off."""
    instances = [TaskService() for _ in range(3)]
    for index, operation in steps:
        others = [
            service for position, service in enumerate(instances) if position != index
        ]
        before = [_observe(service) for service in others]
        apply_operation(instances[index], operation)
        assert [
            _observe(service) for service in others
        ] == before, (
            f"PBT-24: {operation[0]} on instance {index} changed another instance"
        )
    fresh = TaskService()
    for moment in times:
        assert (
            fresh.list_tasks(reference_time=moment) == []
        ), f"PBT-24: fresh instance lists tasks at {moment}"
    assert (
        len(read_csv_rows(fresh.export_csv())) == 1
    ), "PBT-24: fresh export is not header-only"
    assert (
        fresh.get_auto_plus10() is False
    ), "PBT-24: fresh instance reports auto +10 on"
    users = sorted((user.id, user.name) for user in fresh.list_users())
    assert users == INITIAL_USERS, f"PBT-24: fresh instance has users {users}"
