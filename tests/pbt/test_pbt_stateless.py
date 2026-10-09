"""Stateless property-based tests: PBT-01 to PBT-06."""

from __future__ import annotations

from datetime import datetime

from hypothesis import example, given, strategies as st

from conftest import (
    INITIAL_USERS,
    KNOWN_USER_IDS,
    REF_TIME,
    assert_sorted,
    by_id,
    id_set,
    matches_query,
    parse_csv,
    populate,
    read_csv_rows,
    split_query,
)
from crastinator_pro import Priority, Task, TaskService, UserNotFoundError
from strategies import (
    MAX_TASKS,
    ORDERS,
    SORT_FIELDS,
    completed_tokens,
    csv_tasks,
    mixed_tasks,
    search_queries,
    search_tasks,
    sort_tasks,
    tasks,
    unknown_user_ids,
    user_ids,
)


@given(
    user_id=st.one_of(
        st.integers(), st.sampled_from([0, -1, 1, 2, 3, 4, 2**63, -(2**63)])
    )
)
def test_pbt01_fixed_user_base(user_id: int) -> None:
    """PBT-01: exactly Alice, Bob and Carol exist; any other id raises UserNotFoundError."""
    service = TaskService()
    listed = service.list_users()
    assert (
        len(listed) == 3 and len({u.id for u in listed}) == 3
    ), f"PBT-01: unexpected users {listed!r}"
    assert (
        sorted((u.id, u.name) for u in listed) == INITIAL_USERS
    ), f"PBT-01: unexpected users {listed!r}"
    known = {u.id: u for u in listed}
    if user_id in known:
        assert (
            service.get_user(user_id) == known[user_id]
        ), f"PBT-01: get_user({user_id}) differs from list_users"
        return
    try:
        service.get_user(user_id)
    except UserNotFoundError as error:
        assert (
            error.user_id == user_id
        ), f"PBT-01: user_id attribute {error.user_id!r} != {user_id}"
    else:
        raise AssertionError(
            f"PBT-01: get_user({user_id}) did not raise UserNotFoundError"
        )


@given(
    stock=st.lists(sort_tasks(), max_size=MAX_TASKS),
    sort_by=st.sampled_from(SORT_FIELDS),
    order=st.sampled_from(ORDERS),
)
def test_pbt02_sort_order(stock: list[Task], sort_by: str, order: str) -> None:
    """PBT-02: sorting returns a permutation of the stock in the defined order."""
    service, added = populate(stock)
    result = service.list_tasks(reference_time=REF_TIME, sort_by=sort_by, order=order)
    assert len(result) == len(added) and by_id(result) == by_id(
        added
    ), "PBT-02: result is no permutation of the stock"
    assert_sorted(result, sort_by, order, "PBT-02")


@given(
    stock=st.lists(mixed_tasks(), max_size=MAX_TASKS),
    assignee=st.one_of(st.none(), user_ids(), unknown_user_ids()),
    completed=st.one_of(st.none(), st.booleans()),
)
def test_pbt03_filter_by_assignee_and_status(
    stock: list[Task], assignee: int | None, completed: bool | None
) -> None:
    """PBT-03: filters return exactly the matching tasks; unknown assignees give an empty list."""
    service, added = populate(stock)
    result = service.list_tasks(
        reference_time=REF_TIME, assignee_user_id=assignee, completed=completed
    )
    expected = [
        t
        for t in added
        if (assignee is None or t.assignee_user_id == assignee)
        and (completed is None or t.completed == completed)
    ]
    assert len(result) == len(expected) and by_id(result) == by_id(
        expected
    ), "PBT-03: filter result differs"
    if assignee is not None and assignee not in KNOWN_USER_IDS:
        assert result == [], f"PBT-03: unknown assignee {assignee} returned tasks"


@given(stock=st.lists(search_tasks(), max_size=MAX_TASKS), query=search_queries())
@example(stock=[Task(id=1, title="ab", description="cd")], query="bc")
@example(stock=[Task(id=1, title="ab", description="cd")], query="  a   d ")
def test_pbt04_full_text_search(stock: list[Task], query: str) -> None:
    """PBT-04: search returns exactly the tasks where every term is a substring of title or description."""
    service, added = populate(stock)
    terms = split_query(query)
    result = service.list_tasks(reference_time=REF_TIME, query=query)
    expected = id_set(t for t in added if matches_query(t, terms))
    assert (
        len(result) == len(expected) and id_set(result) == expected
    ), f"PBT-04: wrong hits for {query!r}"


@given(
    stock=st.lists(tasks(), max_size=MAX_TASKS),
    query=st.one_of(
        st.sampled_from(["", " "]), st.integers(2, 20).map(lambda n: " " * n)
    ),
)
def test_pbt05_empty_query(stock: list[Task], query: str) -> None:
    """PBT-05: an empty or blank query returns the same set as no query."""
    service, _ = populate(stock)
    with_query = service.list_tasks(reference_time=REF_TIME, query=query)
    assert by_id(with_query) == by_id(
        service.list_tasks(reference_time=REF_TIME)
    ), f"PBT-05: {query!r} filters"


def _record_matches(record: dict[str, str], task: Task) -> bool:
    return (
        record["title"] == task.title
        and record["description"] == (task.description or "")
        and record["dueDate"]
        == ("" if task.due_date is None else task.due_date.isoformat())
        and record["completed"] == completed_tokens()[task.completed]
        and datetime.fromisoformat(record["createdAt"]) == task.created_at
        and (int(record["assigneeUserId"]) if record["assigneeUserId"] else None)
        == task.assignee_user_id
        and record["priority"] == Priority(task.priority).value
    )


@given(stock=st.lists(csv_tasks(), max_size=MAX_TASKS))
def test_pbt06_export_complete_and_faithful(stock: list[Task]) -> None:
    """PBT-06: export_csv is parseable, complete and reproduces every field value."""
    service, added = populate(stock)
    exported = service.export_csv()
    records = parse_csv(exported)
    assert len(records) == len(added), "PBT-06: record count differs from task count"
    by_record_id = {int(r["id"]): r for r in records}
    assert set(by_record_id) == id_set(
        added
    ), "PBT-06: exported ids differ from the stock"
    for task in added:
        assert _record_matches(
            by_record_id[task.id], task
        ), f"PBT-06: {by_record_id[task.id]!r} != {task!r}"
    if not added:
        assert (
            len(read_csv_rows(exported)) == 1
        ), "PBT-06: empty export is not header-only"
        result = TaskService().import_csv(exported)
        assert (
            len(result.created) == 0 and result.errors == []
        ), f"PBT-06: importing the empty export gave {result!r}"
