"""AI tests: PBT-19 to PBT-23, MT-17 to MT-21, MT-23 and MT-24."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

import pytest
from hypothesis import assume, given, strategies as st
from hypothesis.strategies import SearchStrategy

from conftest import (
    ASSIGNEE_CYCLE,
    CONFIRMED,
    EQUIVALENT,
    KNOWN_USER_IDS,
    SAME_TASKS,
    RecordingProvider,
    ai_settings,
    content,
    holds_in_majority,
    id_set,
    judge_confirmation,
    judge_equivalence,
    judge_same_tasks,
    populate,
    replicate,
    requires_default_ai,
    requires_judge,
    satisfies_task_invariants,
)
from crastinator_pro import (
    Priority,
    Task,
    TaskService,
    UserNotFoundError,
    ValidationError,
)
from strategies import (
    DISTINCTIVE_TITLES,
    FACTS,
    GENERAL_QUESTIONS,
    MAX_TASKS,
    TIME_QUESTIONS,
    ai_free_texts,
    ai_questions,
    assignees,
    blank_titles,
    boundary_reference_times,
    explicit_task_texts,
    invalid_parsed_tasks,
    mixed_tasks,
    priority_hint_texts,
    reference_times,
    reformulation_cases,
    relative_date_texts,
    tasks,
    unknown_user_ids,
    user_ids,
)

# --- shared helpers --------------------------------------------------------------------


def fact_task(title: str, user_id: Optional[int]) -> Task:
    return Task(id=1, title=title, assignee_user_id=user_id)


def foreign_owners(user_id: int) -> list[Optional[int]]:
    return [None, *(other for other in KNOWN_USER_IDS if other != user_id)]


def answer_for(
    stock: list[Task], user_id: int, question: str, reference_time: datetime
) -> str:
    service, _ = populate(stock)
    return service.ai_ask(user_id, question, reference_time)


@st.composite
def distributed_stock(draw: Any, sizes: SearchStrategy[int]) -> list[Task]:
    templates = draw(st.lists(tasks(), min_size=1, max_size=5))
    owners = draw(st.lists(assignees(), min_size=1, max_size=8))
    return replicate(templates, draw(sizes), owners)


# --- PBT-19 ----------------------------------------------------------------------------


@pytest.mark.ai
@given(
    stock=distributed_stock(
        st.one_of(st.integers(0, 30), st.sampled_from([1_000, 5_000]))
    ),
    user_id=st.one_of(user_ids(), unknown_user_ids()),
    question=st.text(max_size=40),
    reference_time=reference_times(),
)
def test_pbt19_ai_ask_passes_exactly_the_users_tasks(
    stock: list[Task], user_id: int, question: str, reference_time: datetime
) -> None:
    """PBT-19: answer() receives exactly the tasks assigned to user_id; unknown users raise before answer()."""
    provider = RecordingProvider()
    service, added = populate(stock, ai_provider=provider)
    if user_id not in {user.id for user in service.list_users()}:
        with pytest.raises(UserNotFoundError):
            service.ai_ask(user_id, question, reference_time)
        assert (
            provider.answer_calls == []
        ), f"PBT-19: answer() called for unknown user {user_id}"
        return
    service.ai_ask(user_id, question, reference_time)
    assert (
        len(provider.answer_calls) == 1
    ), f"PBT-19: answer() called {len(provider.answer_calls)} times"
    received = provider.answer_calls[0][1]
    expected = {
        task.id: content(task) for task in added if task.assignee_user_id == user_id
    }
    assert len(received) == len(
        expected
    ), f"PBT-19: {len(received)} tasks passed, expected {len(expected)}"
    assert {
        task.id: content(task) for task in received
    } == expected, "PBT-19: wrong tasks passed to answer()"


# --- PBT-20 ----------------------------------------------------------------------------


def unassign_user(stock: list[Task], user_id: int) -> list[Task]:
    return [
        (
            replace(task, assignee_user_id=None)
            if task.assignee_user_id == user_id
            else task
        )
        for task in stock
    ]


@pytest.mark.ai
@requires_default_ai
@ai_settings
@given(
    stock=st.lists(mixed_tasks(), max_size=MAX_TASKS),
    user_id=user_ids(),
    without_tasks=st.booleans(),
    question=ai_questions(),
    reference_time=reference_times(),
)
def test_pbt20_ai_ask_weak_properties(
    stock: list[Task],
    user_id: int,
    without_tasks: bool,
    question: str,
    reference_time: datetime,
) -> None:
    """PBT-20: ai_ask returns a non-empty string, identical for identical calls."""
    service, _ = populate(unassign_user(stock, user_id) if without_tasks else stock)
    first = service.ai_ask(user_id, question, reference_time)
    assert (
        isinstance(first, str) and first
    ), f"PBT-20: answer {first!r} is no non-empty string"
    assert (
        service.ai_ask(user_id, question, reference_time) == first
    ), "PBT-20: identical calls differ"


# --- PBT-21 ----------------------------------------------------------------------------


@ai_settings
@given(
    stock=st.lists(tasks(), max_size=10),
    text=ai_free_texts(),
    reference_time=reference_times(),
)
def _valid_free_text(stock: list[Task], text: str, reference_time: datetime) -> None:
    def run() -> bool:
        service, added = populate(stock)
        task = service.ai_create_task(text, reference_time)
        listed = {
            item.id: item for item in service.list_tasks(reference_time=reference_time)
        }
        return (
            task.id not in id_set(added)
            and task.id in listed
            and len(listed) == len(added) + 1
            and satisfies_task_invariants(listed[task.id])
            and listed[task.id].completed is False
        )

    assert holds_in_majority(
        run
    ), f"PBT-21 (a): violated in more than 1 of 5 runs for {text[:60]!r}"


@given(
    stock=st.lists(tasks(), max_size=10),
    text=blank_titles(),
    reference_time=reference_times(),
)
def _blank_text(stock: list[Task], text: str, reference_time: datetime) -> None:
    service, _ = populate(stock, ai_provider=RecordingProvider())
    exported = service.export_csv()
    with pytest.raises(ValidationError):
        service.ai_create_task(text, reference_time)
    assert (
        service.export_csv() == exported
    ), f"PBT-21 (b): rejected text {text!r} changed the stock"


@given(
    stock=st.lists(tasks(), max_size=10),
    case=invalid_parsed_tasks(),
    text=ai_free_texts(),
    reference_time=reference_times(),
)
def _invalid_parse_result(
    stock: list[Task],
    case: tuple[dict[str, Any], type[Exception]],
    text: str,
    reference_time: datetime,
) -> None:
    parsed, error_type = case
    service, _ = populate(stock, ai_provider=RecordingProvider(parsed))
    exported = service.export_csv()
    with pytest.raises(error_type):
        service.ai_create_task(text, reference_time)
    assert (
        service.export_csv() == exported
    ), f"PBT-21 (c): rejected dict {parsed!r} changed the stock"


VALIDATION_PARTS: dict[str, Callable[[], None]] = {
    "a": _valid_free_text,
    "b": _blank_text,
    "c": _invalid_parse_result,
}


@pytest.mark.ai
@pytest.mark.parametrize(
    "part", [pytest.param("a", marks=requires_default_ai), "b", "c"]
)
def test_pbt21_ai_create_task_validation(part: str) -> None:
    """PBT-21: ai_create_task creates valid tasks and rejects empty texts and invalid parse results."""
    VALIDATION_PARTS[part]()


# --- PBT-22 ----------------------------------------------------------------------------


@pytest.mark.ai
@requires_default_ai
@ai_settings
@given(case=explicit_task_texts(), reference_time=reference_times())
def test_pbt22_ai_create_task_takes_explicit_values(
    case: tuple[str, Optional[date], Optional[int]], reference_time: datetime
) -> None:
    """PBT-22: an explicit ISO date and user name end up in due_date and assignee_user_id."""
    text, due, user_id = case

    def run() -> bool:
        task = TaskService().ai_create_task(text, reference_time)
        return task.due_date == due and task.assignee_user_id == user_id

    assert holds_in_majority(
        run
    ), f"PBT-22: {text!r} did not give due={due}, assignee={user_id} in 4 of 5 runs"


# --- PBT-23 ----------------------------------------------------------------------------


@pytest.mark.ai
@requires_default_ai
@ai_settings
@given(case=priority_hint_texts(), reference_time=reference_times())
def test_pbt23_ai_create_task_priority_hints(
    case: tuple[str, Priority], reference_time: datetime
) -> None:
    """PBT-23: high hints give HIGH, low hints give LOW, no hint gives MEDIUM."""
    text, expected = case

    def run() -> bool:
        return (
            Priority(TaskService().ai_create_task(text, reference_time).priority)
            == expected
        )

    assert holds_in_majority(
        run
    ), f"PBT-23: {text!r} did not give {expected} in 4 of 5 runs"


# --- MT-17 -----------------------------------------------------------------------------

ADDED_COUNTS = (1, 10, 100, 1_000)


def add_unrelated_tasks(
    service: TaskService, templates: list[Task], count: int
) -> None:
    for task in replicate(templates, count, ASSIGNEE_CYCLE):
        service.add_task(copy.deepcopy(task))


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(
    fact=st.sampled_from(FACTS),
    user_id=user_ids(),
    templates=st.lists(tasks(), min_size=1, max_size=5),
    count=st.sampled_from(ADDED_COUNTS),
    reference_time=reference_times(),
)
def test_mt17_more_tasks_keep_facts(
    fact: tuple[str, str],
    user_id: int,
    templates: list[Task],
    count: int,
    reference_time: datetime,
) -> None:
    """MT-17: adding N tasks does not turn a confirmed fact into a non-confirmed one."""
    title, question = fact
    service, _ = populate([fact_task(title, user_id)])
    assume(
        judge_confirmation(question, service.ai_ask(user_id, question, reference_time))
        == CONFIRMED
    )
    add_unrelated_tasks(service, templates, count)
    verdict = judge_confirmation(
        question, service.ai_ask(user_id, question, reference_time)
    )
    assert (
        verdict == CONFIRMED
    ), f"MT-17: {count} added tasks changed the verdict to {verdict!r}"


# --- MT-18 -----------------------------------------------------------------------------

FOREIGN_ACTIONS = ("add", "assign", "toggle", "delete")
ForeignAction = tuple[str, int, int, Task]


def foreign_actions() -> SearchStrategy[ForeignAction]:
    return st.tuples(
        st.sampled_from(FOREIGN_ACTIONS),
        st.integers(0, 1000),
        st.integers(0, 1000),
        tasks(),
    )


def mutate_foreign_tasks(
    service: TaskService,
    foreign_ids: list[int],
    owners: list[Optional[int]],
    actions: list[ForeignAction],
) -> None:
    """Adds, changes or deletes only tasks that are not assigned to the asking user."""
    for kind, task_pick, owner_pick, task in actions:
        owner = owners[owner_pick % len(owners)]
        if kind == "add":
            foreign_ids.append(
                service.add_task(replace(task, assignee_user_id=owner)).id
            )
            continue
        if not foreign_ids:
            continue
        task_id = foreign_ids[task_pick % len(foreign_ids)]
        if kind == "assign":
            service.assign_task(task_id, owner)
        elif kind == "toggle":
            service.toggle_task(task_id)
        else:
            service.delete_task(task_id)
            foreign_ids.remove(task_id)


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(
    stock=st.lists(mixed_tasks(), max_size=MAX_TASKS),
    user_id=user_ids(),
    question=st.sampled_from(GENERAL_QUESTIONS),
    actions=st.lists(foreign_actions(), min_size=1, max_size=10),
    fact=st.sampled_from(FACTS),
    fact_owner=st.integers(0, 1000),
    reference_time=reference_times(),
)
def test_mt18_foreign_tasks_do_not_influence_answers(
    stock: list[Task],
    user_id: int,
    question: str,
    actions: list[ForeignAction],
    fact: tuple[str, str],
    fact_owner: int,
    reference_time: datetime,
) -> None:
    """MT-18: changes to foreign tasks keep the answer string; facts in foreign tasks are not confirmed."""
    service, added = populate(stock)
    owners = foreign_owners(user_id)
    foreign_ids = [task.id for task in added if task.assignee_user_id != user_id]
    before = service.ai_ask(user_id, question, reference_time)
    mutate_foreign_tasks(service, foreign_ids, owners, actions)
    assert (
        service.ai_ask(user_id, question, reference_time) == before
    ), "MT-18: foreign changes alter the answer"
    title, fact_question = fact
    service.add_task(fact_task(title, owners[fact_owner % len(owners)]))
    verdict = judge_confirmation(
        fact_question, service.ai_ask(user_id, fact_question, reference_time)
    )
    assert (
        verdict != CONFIRMED
    ), f"MT-18: fact {title!r} from a foreign task was confirmed"


# --- MT-19 -----------------------------------------------------------------------------

TOTAL_COUNTS = (10, 100, 1_000)


def place_fact(fillers: list[Task], fact: Task, position: int) -> list[Task]:
    return [*fillers[:position], fact, *fillers[position:]]


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(
    fact=st.sampled_from(FACTS),
    user_id=user_ids(),
    templates=st.lists(tasks(), min_size=1, max_size=5),
    count=st.sampled_from(TOTAL_COUNTS),
    reference_time=reference_times(),
    data=st.data(),
)
def test_mt19_position_of_fact_task(
    fact: tuple[str, str],
    user_id: int,
    templates: list[Task],
    count: int,
    reference_time: datetime,
    data: st.DataObject,
) -> None:
    """MT-19: the judge verdict does not depend on the position of the fact task."""
    title, question = fact
    fillers = replicate(templates, count - 1, [user_id])
    first = place_fact(fillers, fact_task(title, user_id), 0)
    permutation = data.draw(st.permutations(range(count)), label="insertion order")
    variants = {
        "first": first,
        "last": place_fact(fillers, fact_task(title, user_id), len(fillers)),
        "middle": place_fact(fillers, fact_task(title, user_id), len(fillers) // 2),
        "random": [first[index] for index in permutation],
    }
    verdicts = {
        name: judge_confirmation(
            question, answer_for(stock, user_id, question, reference_time)
        )
        for name, stock in variants.items()
    }
    assert (
        len(set(verdicts.values())) == 1
    ), f"MT-19: verdicts differ by position: {verdicts}"


# --- MT-20 -----------------------------------------------------------------------------


def shift_reference(reference_time: datetime, days: int) -> datetime:
    return reference_time + timedelta(days=days)


def boundary_shifts(day: date) -> list[int]:
    """Shifts k in [1, 400] that land on a month start or month end (includes 29.02. in leap years)."""
    targets: list[date] = []
    for step in range(1, 15):
        index = day.month - 1 + step
        first = date(day.year + index // 12, index % 12 + 1, 1)
        targets += [first, first - timedelta(days=1)]
    return sorted({(target - day).days for target in targets} & set(range(1, 401)))


@pytest.mark.ai
@requires_default_ai
@ai_settings
@given(
    case=relative_date_texts(),
    reference_time=boundary_reference_times(),
    data=st.data(),
)
def test_mt20_relative_dates_follow_reference_time(
    case: tuple[str, str, str], reference_time: datetime, data: st.DataObject
) -> None:
    """MT-20: shifting reference_time by k (or 7k) days shifts due_date by the same amount."""
    text, phrase, kind = case
    if kind == "day":
        shifts = boundary_shifts(reference_time.date())
        days = data.draw(
            st.one_of(st.integers(1, 400), st.sampled_from(shifts)), label="k"
        )
    else:
        days = 7 * data.draw(st.integers(1, 52), label="k")
    shifted = shift_reference(reference_time, days)

    def run() -> bool:
        base = TaskService().ai_create_task(text, reference_time).due_date
        follow = TaskService().ai_create_task(text, shifted).due_date
        if base is None or follow is None or follow - base != timedelta(days=days):
            return False
        return phrase != "morgen" or base == reference_time.date() + timedelta(days=1)

    assert holds_in_majority(
        run
    ), f"MT-20: {text!r} shifted by {days} days failed in more than 1 of 5 runs"


# --- MT-21 -----------------------------------------------------------------------------


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(case=reformulation_cases(), reference_time=reference_times())
def test_mt21_reformulation_gives_equivalent_task(
    case: tuple[str, list[str]], reference_time: datetime
) -> None:
    """MT-21: reformulations keep due_date, assignee and priority and give equivalent title and description."""
    base_text, variants = case
    for variant in variants:

        def run(text: str = variant) -> bool:
            base = TaskService().ai_create_task(base_text, reference_time)
            other = TaskService().ai_create_task(text, reference_time)
            same_fields = (
                base.due_date,
                base.assignee_user_id,
                Priority(base.priority),
            ) == (other.due_date, other.assignee_user_id, Priority(other.priority))
            return (
                same_fields
                and judge_equivalence(
                    base.title, base.description, other.title, other.description
                )
                == EQUIVALENT
            )

        assert holds_in_majority(
            run
        ), f"MT-21: {variant!r} is not equivalent to {base_text!r} in 4 of 5 runs"


# --- MT-23 -----------------------------------------------------------------------------

EXTRA_COUNTS = (0, 10, 100)


def delete_fact(service: TaskService, task_id: int, other_user: int) -> None:
    service.delete_task(task_id)


def reassign_fact(service: TaskService, task_id: int, other_user: int) -> None:
    service.assign_task(task_id, other_user)


def unassign_fact(service: TaskService, task_id: int, other_user: int) -> None:
    service.assign_task(task_id, None)


FACT_REMOVALS: dict[str, Callable[[TaskService, int, int], None]] = {
    "delete": delete_fact,
    "reassign": reassign_fact,
    "unassign": unassign_fact,
}


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(
    fact=st.sampled_from(FACTS),
    user_id=user_ids(),
    templates=st.lists(tasks(), min_size=1, max_size=5),
    count=st.sampled_from(EXTRA_COUNTS),
    other_pick=st.integers(0, 1000),
    reference_time=reference_times(),
)
def test_mt23_removing_fact_task_revokes_confirmation(
    fact: tuple[str, str],
    user_id: int,
    templates: list[Task],
    count: int,
    other_pick: int,
    reference_time: datetime,
) -> None:
    """MT-23: after deleting or reassigning the fact task the fact is no longer confirmed."""
    title, question = fact
    stock = [fact_task(title, user_id), *replicate(templates, count, ASSIGNEE_CYCLE)]
    assume(
        judge_confirmation(
            question, answer_for(stock, user_id, question, reference_time)
        )
        == CONFIRMED
    )
    others = [other for other in KNOWN_USER_IDS if other != user_id]
    for name, transform in FACT_REMOVALS.items():
        service, added = populate(stock)
        transform(service, added[0].id, others[other_pick % len(others)])
        verdict = judge_confirmation(
            question, service.ai_ask(user_id, question, reference_time)
        )
        assert (
            verdict != CONFIRMED
        ), f"MT-23 ({name}): fact {title!r} is still confirmed"


# --- MT-24 -----------------------------------------------------------------------------

DUE_KINDS = ("none", "past", "today", "this_week", "later")
Entry = tuple[str, Optional[date], bool]


def _due_for(draw: Any, kind: str, today: date) -> Optional[date]:
    monday = today - timedelta(days=today.weekday())
    if kind == "none":
        return None
    if kind == "past":
        return today - timedelta(days=draw(st.integers(1, 400)))
    if kind == "today":
        return today
    if kind == "this_week":
        return monday + timedelta(days=draw(st.integers(0, 6)))
    return monday + timedelta(days=7 + draw(st.integers(0, 400)))


@st.composite
def time_bound_entries(draw: Any, reference_time: datetime) -> list[Entry]:
    titles = draw(
        st.lists(
            st.sampled_from(DISTINCTIVE_TITLES), min_size=3, max_size=8, unique=True
        )
    )
    today = reference_time.date()
    return [
        (
            title,
            _due_for(draw, draw(st.sampled_from(DUE_KINDS)), today),
            draw(st.booleans()),
        )
        for title in titles
    ]


def shift_by_weeks(
    entries: list[Entry], reference_time: datetime, weeks: int
) -> tuple[list[Entry], datetime]:
    delta = timedelta(weeks=weeks)
    shifted = [
        (title, None if due is None else due + delta, done)
        for title, due, done in entries
    ]
    return shifted, reference_time + delta


def ask_with(
    entries: list[Entry], user_id: int, question: str, reference_time: datetime
) -> str:
    service = TaskService()
    for title, due, done in entries:
        task = service.create_task(title=title, due_date=due, assignee_user_id=user_id)
        if done:
            service.toggle_task(task.id)
    return service.ai_ask(user_id, question, reference_time)


@pytest.mark.ai
@requires_default_ai
@requires_judge
@ai_settings
@given(
    reference_time=boundary_reference_times(),
    user_id=user_ids(),
    question=st.sampled_from(TIME_QUESTIONS),
    weeks=st.one_of(st.integers(-52, -1), st.integers(1, 52)),
    data=st.data(),
)
def test_mt24_time_questions_shift_invariant(
    reference_time: datetime,
    user_id: int,
    question: str,
    weeks: int,
    data: st.DataObject,
) -> None:
    """MT-24: shifting all due dates and reference_time by 7k days names the same tasks."""
    entries = data.draw(time_bound_entries(reference_time), label="tasks")
    shifted, shifted_time = shift_by_weeks(entries, reference_time, weeks)
    first = ask_with(entries, user_id, question, reference_time)
    second = ask_with(shifted, user_id, question, shifted_time)
    verdict = judge_same_tasks([title for title, _, _ in entries], first, second)
    assert (
        verdict == SAME_TASKS
    ), f"MT-24: shift by {weeks} weeks names different tasks for {question!r}"
