"""Metamorphic tests: MT-01 to MT-15 and MT-22."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Optional

from hypothesis import assume, given, strategies as st

from conftest import (
    ASSIGNEE_CYCLE,
    KNOWN_USER_IDS,
    REF_TIME,
    assert_sorted,
    content,
    current_tasks,
    fetch,
    id_set,
    populate,
    replicate,
    sort_key,
)
from crastinator_pro import Task, TaskService
from crastinator_pro.csv_io import ImportResult
from strategies import (
    IMPORT_COLUMNS,
    MAX_TASKS,
    ORDERS,
    PLUS10_MAX,
    SORT_FIELDS,
    ImportFile,
    assignees,
    creation_kwargs,
    invalid_import_rows,
    list_filters,
    mixed_import_files,
    mixed_tasks,
    plus10_due_dates,
    plus10_tasks,
    query_terms,
    reference_times,
    relative_stocks,
    render_csv,
    search_queries,
    search_tasks,
    sort_tasks,
    stocks_with_duplicates,
    task_to_row,
    tasks,
    user_ids,
    valid_import_files,
)

# --- shared helpers --------------------------------------------------------------------


def class_sequence(listed: list[Task], sort_by: str) -> list[Any]:
    """Sequence of key equivalence classes (title: DIN 5007-1 key from PBT-02)."""
    return [sort_key(task, sort_by) for task in listed]


def hits(service: TaskService, query: str) -> set[int]:
    return id_set(service.list_tasks(reference_time=REF_TIME, query=query))


def earlier(moment: datetime, days: int, minutes: int) -> datetime:
    return moment - timedelta(days=days, minutes=minutes)


def auto_dues(stock: list[Task], times: list[datetime]) -> list[Optional[date]]:
    """due_date of every task (in insertion order) after list_tasks calls with auto +10 on."""
    service, added = populate(stock)
    service.set_auto_plus10(True)
    for moment in times:
        service.list_tasks(reference_time=moment)
    return [service.get_task(task.id).due_date for task in added]


def import_fresh(file: ImportFile) -> ImportResult:
    return TaskService().import_csv(file.text)


# --- MT-01 -----------------------------------------------------------------------------


def invert_order(order: str) -> str:
    return "desc" if order == "asc" else "asc"


@given(stock=stocks_with_duplicates(sort_tasks()), sort_by=st.sampled_from(SORT_FIELDS))
def test_mt01_ascending_vs_descending(stock: list[Task], sort_by: str) -> None:
    """MT-01: desc yields the reversed class sequence of asc over the same ids."""
    service, _ = populate(stock)
    ascending = service.list_tasks(
        reference_time=REF_TIME, sort_by=sort_by, order="asc"
    )
    descending = service.list_tasks(
        reference_time=REF_TIME, sort_by=sort_by, order=invert_order("asc")
    )
    assert len(descending) == len(ascending) and id_set(descending) == id_set(
        ascending
    ), "MT-01: ids differ"
    assert (
        class_sequence(descending, sort_by) == class_sequence(ascending, sort_by)[::-1]
    ), f"MT-01: desc is not the reverse of asc for {sort_by}"


# --- MT-02 -----------------------------------------------------------------------------


def permute_insertion(
    entries: list[dict[str, Any]], permutation: list[int]
) -> list[dict[str, Any]]:
    return [entries[index] for index in permutation]


def _sorted_classes(
    entries: list[dict[str, Any]], sort_by: str, order: str
) -> list[Any]:
    service = TaskService()
    for kwargs in entries:
        service.create_task(**kwargs)
    return class_sequence(
        service.list_tasks(reference_time=REF_TIME, sort_by=sort_by, order=order),
        sort_by,
    )


@given(
    entries=st.lists(creation_kwargs(), max_size=MAX_TASKS),
    sort_by=st.sampled_from(SORT_FIELDS),
    order=st.sampled_from(ORDERS),
    data=st.data(),
)
def test_mt02_sorting_independent_of_insertion_order(
    entries: list[dict[str, Any]], sort_by: str, order: str, data: st.DataObject
) -> None:
    """MT-02: permuting the insertion order keeps the sorted class sequence."""
    base = _sorted_classes(entries, sort_by, order)
    permutations = data.draw(
        st.lists(st.permutations(range(len(entries))), min_size=1, max_size=3)
    )
    for permutation in permutations:
        assert (
            _sorted_classes(permute_insertion(entries, permutation), sort_by, order)
            == base
        ), f"MT-02: insertion order {permutation} changes the {sort_by} {order} sequence"


# --- MT-03 -----------------------------------------------------------------------------


def add_term(query: str, term: str) -> str:
    return f"{query} {term}"


def remove_term(terms: list[str], index: int) -> str:
    return " ".join(term for position, term in enumerate(terms) if position != index)


@given(
    stock=st.lists(search_tasks(), max_size=MAX_TASKS),
    terms=st.lists(query_terms(), min_size=1, max_size=3),
    extra=query_terms(),
    index=st.integers(min_value=0),
)
def test_mt03_adding_and_removing_terms(
    stock: list[Task], terms: list[str], extra: str, index: int
) -> None:
    """MT-03: an added term intersects the hits, a removed term yields a superset."""
    service, _ = populate(stock)
    query = " ".join(terms)
    base = hits(service, query)
    extended = hits(service, add_term(query, extra))
    assert extended == base & hits(
        service, extra
    ), f"MT-03: hits({query!r} {extra!r}) != intersection"
    assert extended <= base, f"MT-03: adding {extra!r} enlarged the hits"
    assert (
        hits(service, remove_term(terms, index % len(terms))) >= base
    ), "MT-03: removing a term shrank the hits"


# --- MT-04 -----------------------------------------------------------------------------


def permute_terms(terms: list[str], permutation: list[int]) -> str:
    return " ".join(terms[index] for index in permutation)


def duplicate_term(terms: list[str], index: int) -> str:
    return " ".join([*terms[: index + 1], terms[index], *terms[index + 1 :]])


def widen_spacing(terms: list[str], extra: list[int]) -> str:
    """extra[0] leading, extra[1:-1] additional spaces between terms, extra[-1] trailing."""
    separators = [" " * (1 + count) for count in extra[1:-1]]
    body = terms[0] + "".join(
        separator + term for separator, term in zip(separators, terms[1:])
    )
    return " " * extra[0] + body + " " * extra[-1]


@given(
    stock=st.lists(search_tasks(), max_size=MAX_TASKS),
    terms=st.lists(query_terms(), min_size=2, max_size=4),
    data=st.data(),
)
def test_mt04_term_order_repetition_and_spacing(
    stock: list[Task], terms: list[str], data: st.DataObject
) -> None:
    """MT-04: permuting, duplicating or spacing out terms keeps the hits."""
    service, _ = populate(stock)
    base = hits(service, " ".join(terms))
    permutation = data.draw(st.permutations(range(len(terms))), label="permutation")
    index = data.draw(st.integers(0, len(terms) - 1), label="duplicated term")
    extra = data.draw(
        st.lists(st.integers(1, 3), min_size=len(terms) + 1, max_size=len(terms) + 1),
        label="spaces",
    )
    for variant in (
        permute_terms(terms, permutation),
        duplicate_term(terms, index),
        widen_spacing(terms, extra),
    ):
        assert hits(service, variant) == base, f"MT-04: {variant!r} changes the hits"


# --- MT-05 -----------------------------------------------------------------------------

CASE_MODES = ("upper", "lower", "swapcase")


def case_variants(query: str, flags: list[bool]) -> list[str]:
    mixed = "".join(
        char.upper() if flag else char.lower() for char, flag in zip(query, flags)
    )
    return [query.upper(), query.lower(), mixed]


def recase(text: Optional[str], mode: str) -> Optional[str]:
    return None if text is None else getattr(text, mode)()


def recase_task(task: Task, mode: str) -> Task:
    return replace(
        task, title=recase(task.title, mode), description=recase(task.description, mode)
    )


def hit_positions(service: TaskService, added: list[Task], query: str) -> set[int]:
    position = {task.id: index for index, task in enumerate(added)}
    return {
        position[task.id]
        for task in service.list_tasks(reference_time=REF_TIME, query=query)
    }


@given(
    stock=st.lists(search_tasks(), max_size=MAX_TASKS),
    terms=st.lists(query_terms(), min_size=1, max_size=4),
    data=st.data(),
)
def test_mt05_case_insensitive_search(
    stock: list[Task], terms: list[str], data: st.DataObject
) -> None:
    """MT-05: changing the case of the query or of the task texts keeps the hits."""
    query = " ".join(terms)
    service, added = populate(stock)
    base = hit_positions(service, added, query)
    flags = data.draw(
        st.lists(st.booleans(), min_size=len(query), max_size=len(query)),
        label="case flags",
    )
    for variant in case_variants(query, flags):
        assert (
            hit_positions(service, added, variant) == base
        ), f"MT-05: query {variant!r} changes the hits"
    modes = data.draw(
        st.lists(st.sampled_from(CASE_MODES), min_size=len(stock), max_size=len(stock)),
        label="modes",
    )
    recased_service, recased = populate(
        [recase_task(task, mode) for task, mode in zip(stock, modes)]
    )
    assert (
        hit_positions(recased_service, recased, query) == base
    ), "MT-05: recased task texts change the hits"


# --- MT-06 -----------------------------------------------------------------------------


def shrink_term(terms: list[str], index: int, start: int, end: int) -> str:
    changed = list(terms)
    changed[index] = terms[index][start:end]
    return " ".join(changed)


@given(
    stock=st.lists(search_tasks(), max_size=MAX_TASKS),
    terms=st.lists(query_terms(), min_size=1, max_size=4),
    data=st.data(),
)
def test_mt06_substring_of_term(
    stock: list[Task], terms: list[str], data: st.DataObject
) -> None:
    """MT-06: replacing a term by a non-empty substring yields a superset of hits."""
    service, _ = populate(stock)
    base = hits(service, " ".join(terms))
    index = data.draw(st.integers(0, len(terms) - 1), label="term")
    start = data.draw(st.integers(0, len(terms[index]) - 1), label="start")
    end = data.draw(st.integers(start + 1, len(terms[index])), label="end")
    variant = shrink_term(terms, index, start, end)
    assert hits(service, variant) >= base, f"MT-06: {variant!r} lost hits"


# --- MT-07 -----------------------------------------------------------------------------


def combine(query: str, completed: bool, assignee: int, sort_by: str) -> dict[str, Any]:
    return {
        "query": query,
        "completed": completed,
        "assignee_user_id": assignee,
        "sort_by": sort_by,
    }


@given(
    stock=st.lists(search_tasks(), max_size=MAX_TASKS),
    query=search_queries(),
    completed=st.booleans(),
    assignee=user_ids(),
    sort_by=st.sampled_from(SORT_FIELDS),
)
def test_mt07_combined_search_filter_sort(
    stock: list[Task], query: str, completed: bool, assignee: int, sort_by: str
) -> None:
    """MT-07: the combined call equals the intersection of the single calls and is sorted as in PBT-02."""
    service, _ = populate(stock)
    separate = (
        hits(service, query)
        & id_set(service.list_tasks(reference_time=REF_TIME, completed=completed))
        & id_set(service.list_tasks(reference_time=REF_TIME, assignee_user_id=assignee))
    )
    combined = service.list_tasks(
        reference_time=REF_TIME, **combine(query, completed, assignee, sort_by)
    )
    assert (
        len(combined) == len(separate) and id_set(combined) == separate
    ), "MT-07: combined result != intersection"
    assert_sorted(combined, sort_by, "asc", "MT-07")


# --- MT-08 -----------------------------------------------------------------------------


def status_filters() -> list[dict[str, Any]]:
    return [{"completed": True}, {"completed": False}]


def assignee_filters() -> list[dict[str, Any]]:
    return [{"assignee_user_id": user_id} for user_id in KNOWN_USER_IDS]


@given(stock=st.lists(mixed_tasks(), max_size=MAX_TASKS))
def test_mt08_filters_partition_stock(stock: list[Task]) -> None:
    """MT-08: status filters partition the stock, assignee filters partition the assigned tasks."""
    service, added = populate(stock)
    everything = id_set(service.list_tasks(reference_time=REF_TIME))
    done, open_ = (
        id_set(service.list_tasks(reference_time=REF_TIME, **kwargs))
        for kwargs in status_filters()
    )
    assert not done & open_, "MT-08: status results overlap"
    assert done | open_ == everything, "MT-08: status results do not cover the stock"
    per_user = [
        id_set(service.list_tasks(reference_time=REF_TIME, **kwargs))
        for kwargs in assignee_filters()
    ]
    union = set().union(*per_user)
    assert sum(len(part) for part in per_user) == len(
        union
    ), "MT-08: assignee results overlap"
    assert union == {
        task.id for task in added if task.assignee_user_id is not None
    }, "MT-08: assignee results do not cover exactly the assigned tasks"


# --- MT-09 -----------------------------------------------------------------------------


def shift_due(task: Task, days: int) -> Task:
    return replace(task, due_date=task.due_date + timedelta(days=days))


def _plus_10_due(task: Task, reference_time: datetime) -> date:
    service, (stored,) = populate([task])
    service.plus_10(stored.id, reference_time)
    return service.get_task(stored.id).due_date


@st.composite
def _week_offsets(draw: Any, due: date) -> int:
    low = max(-520, -((due - date.min).days // 7))
    high = min(520, (PLUS10_MAX - due).days // 7)
    return draw(st.integers(low, high))


@given(
    task=plus10_tasks(),
    reference_time=reference_times(),
    other_time=st.one_of(reference_times(), st.datetimes()),
    data=st.data(),
)
def test_mt09_plus_10_weekly_periodic_and_time_independent(
    task: Task, reference_time: datetime, other_time: datetime, data: st.DataObject
) -> None:
    """MT-09: shifting d by 7k days shifts the result by 7k; another reference_time changes nothing."""
    weeks = data.draw(_week_offsets(task.due_date), label="k")
    base = _plus_10_due(task, reference_time)
    shifted = _plus_10_due(shift_due(task, 7 * weeks), reference_time)
    assert shifted == base + timedelta(
        weeks=weeks
    ), f"MT-09: shift by {weeks} weeks gives {shifted}, base {base}"
    assert (
        _plus_10_due(task, other_time) == base
    ), f"MT-09: reference_time {other_time} changes the result"


# --- MT-10 -----------------------------------------------------------------------------


def weekend_block(day: date) -> Optional[date]:
    """Friday of the Friday-Saturday-Sunday block containing day, None on Monday to Thursday."""
    return day - timedelta(days=day.weekday() - 4) if day.weekday() >= 4 else None


def same_weekend_block(first: date, second: date) -> bool:
    block = weekend_block(first)
    return block is not None and block == weekend_block(second)


@st.composite
def _ordered_due_pairs(draw: Any) -> tuple[date, date]:
    first = draw(plus10_due_dates())
    if draw(st.booleans()):
        second = draw(plus10_due_dates())
    else:
        low = max(-6, -(first - date.min).days)
        high = min(6, (PLUS10_MAX - first).days)
        second = first + timedelta(days=draw(st.integers(low, high)))
    assume(first != second)
    return min(first, second), max(first, second)


@given(pair=_ordered_due_pairs(), first=plus10_tasks(), second=plus10_tasks())
def test_mt10_plus_10_monotonic(
    pair: tuple[date, date], first: Task, second: Task
) -> None:
    """MT-10: d1 < d2 implies plus_10(d1) <= plus_10(d2), equal exactly within one Friday-to-Sunday block."""
    d1, d2 = pair
    service, (low, high) = populate(
        [replace(first, due_date=d1), replace(second, due_date=d2)]
    )
    service.plus_10(low.id, REF_TIME)
    service.plus_10(high.id, REF_TIME)
    p1, p2 = service.get_task(low.id).due_date, service.get_task(high.id).due_date
    assert p1 <= p2, f"MT-10: plus_10({d1})={p1} > plus_10({d2})={p2}"
    assert (p1 == p2) == same_weekend_block(
        d1, d2
    ), f"MT-10: equality {p1 == p2} wrong for {d1}, {d2}"


# --- MT-11 -----------------------------------------------------------------------------


@given(t2=reference_times(), data=st.data())
def test_mt11_auto_plus_10_path_independent_and_idempotent(
    t2: datetime, data: st.DataObject
) -> None:
    """MT-11: earlier, repeated or later list_tasks calls lead to the same due dates."""
    stock = data.draw(relative_stocks(t2), label="stock")
    t1 = earlier(
        t2,
        data.draw(st.integers(0, 800), label="t1 days"),
        data.draw(st.integers(0, 1439), label="t1 min"),
    )
    t0 = earlier(
        t2,
        data.draw(st.integers(0, 800), label="t0 days"),
        data.draw(st.integers(1, 1439), label="t0 min"),
    )
    base = auto_dues(stock, [t2])
    assert (
        auto_dues(stock, [t1, t2]) == base
    ), f"MT-11: calling at {t1} before {t2} changes the due dates"
    assert (
        auto_dues(stock, [t2, t2, t0]) == base
    ), f"MT-11: repeating {t2} or calling {t0} changes the due dates"


# --- MT-12 -----------------------------------------------------------------------------


def insert_invalid_rows(
    file: ImportFile, insertions: list[tuple[int, dict[str, str]]]
) -> ImportFile:
    rows, expected = list(file.rows), list(file.expected)
    for position, row in insertions:
        index = position % (len(rows) + 1)
        rows.insert(index, row)
        expected.insert(index, None)
    return ImportFile(file.columns, tuple(rows), tuple(expected))


def remove_rows(file: ImportFile, removed: set[int]) -> ImportFile:
    keep = [index for index in range(len(file.rows)) if index not in removed]
    return ImportFile(
        file.columns,
        tuple(file.rows[i] for i in keep),
        tuple(file.expected[i] for i in keep),
    )


@given(
    file=valid_import_files(),
    insertions=st.lists(
        st.tuples(st.integers(min_value=0), invalid_import_rows()), max_size=5
    ),
    data=st.data(),
)
def test_mt12_invalid_rows_in_import(
    file: ImportFile, insertions: list[tuple[int, dict[str, str]]], data: st.DataObject
) -> None:
    """MT-12: inserted invalid rows only add errors; removed valid rows only drop their tasks."""
    base = import_fresh(file)
    assert (
        base.errors == []
    ), f"MT-12: valid source file produced errors {base.errors!r}"
    base_contents = [content(task) for task in base.created]
    inserted = import_fresh(insert_invalid_rows(file, insertions))
    assert [
        content(task) for task in inserted.created
    ] == base_contents, "MT-12: inserted rows change created"
    assert len(inserted.errors) == len(base.errors) + len(
        insertions
    ), "MT-12: errors do not grow by the inserted rows"
    removed = (
        data.draw(st.sets(st.integers(0, len(file.rows) - 1)), label="removed")
        if file.rows
        else set()
    )
    reduced = import_fresh(remove_rows(file, removed))
    expected = [
        entry for index, entry in enumerate(base_contents) if index not in removed
    ]
    assert [
        content(task) for task in reduced.created
    ] == expected, "MT-12: removing rows changes the other tasks"
    assert (
        reduced.errors == []
    ), f"MT-12: removing rows produced errors {reduced.errors!r}"


# --- MT-13 -----------------------------------------------------------------------------

EXISTING_SIZES = (1, 100, 10_000)


def build_existing(templates: list[Task], size: int, source: str) -> TaskService:
    """Instance with `size` tasks added directly or by an earlier import."""
    service = TaskService()
    stock = replicate(templates, size, ASSIGNEE_CYCLE)
    if source == "import":
        service.import_csv(
            render_csv(IMPORT_COLUMNS, [task_to_row(task) for task in stock])
        )
    else:
        for task in stock:
            service.add_task(task)
    return service


@given(
    file=valid_import_files(),
    templates=st.lists(tasks(), min_size=1, max_size=5),
    size=st.sampled_from(EXISTING_SIZES),
    source=st.sampled_from(("add", "import")),
    repeats=st.integers(1, 3),
)
def test_mt13_import_independent_of_stock(
    file: ImportFile, templates: list[Task], size: int, source: str, repeats: int
) -> None:
    """MT-13: importing into a filled instance, also repeatedly, creates the same tasks and keeps the stock."""
    base = [content(task) for task in import_fresh(file).created]
    service = build_existing(templates, size, source)
    existing = current_tasks(service)
    for round_number in range(repeats):
        result = service.import_csv(file.text)
        assert len(result.created) == len(
            file.rows
        ), f"MT-13: import {round_number + 1} created a different count"
        assert [
            content(task) for task in result.created
        ] == base, f"MT-13: import {round_number + 1} differs"
    after = current_tasks(service)
    assert len(after) == len(existing) + repeats * len(
        file.rows
    ), "MT-13: stock is not N + k*m"
    assert {
        task_id: after.get(task_id) for task_id in existing
    } == existing, "MT-13: existing tasks changed"


# --- MT-14 -----------------------------------------------------------------------------


def permute_rows(file: ImportFile, permutation: list[int]) -> ImportFile:
    return ImportFile(
        file.columns,
        tuple(file.rows[i] for i in permutation),
        tuple(file.expected[i] for i in permutation),
    )


def permute_columns(file: ImportFile, permutation: list[int]) -> ImportFile:
    return ImportFile(
        tuple(file.columns[i] for i in permutation), file.rows, file.expected
    )


def raw_key(raw: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in raw.items()))


@given(file=mixed_import_files(), data=st.data())
def test_mt14_row_and_column_order(file: ImportFile, data: st.DataObject) -> None:
    """MT-14: row permutation keeps the multisets, column permutation keeps created order and errors."""
    base = import_fresh(file)
    by_rows = import_fresh(
        permute_rows(
            file, data.draw(st.permutations(range(len(file.rows))), label="rows")
        )
    )
    assert Counter(content(t) for t in by_rows.created) == Counter(
        content(t) for t in base.created
    ), "MT-14: row permutation changes the created contents"
    assert Counter(raw_key(e.raw) for e in by_rows.errors) == Counter(
        raw_key(e.raw) for e in base.errors
    ), "MT-14: row permutation changes the raw errors"
    by_columns = import_fresh(
        permute_columns(
            file, data.draw(st.permutations(range(len(file.columns))), label="cols")
        )
    )
    assert [content(t) for t in by_columns.created] == [
        content(t) for t in base.created
    ], "MT-14: column permutation changes created"
    assert sorted(e.row_number for e in by_columns.errors) == sorted(
        e.row_number for e in base.errors
    ), "MT-14: column permutation changes the error rows"
    assert {e.row_number: e.raw for e in by_columns.errors} == {
        e.row_number: e.raw for e in base.errors
    }, "MT-14: column permutation changes raw"


# --- MT-15 -----------------------------------------------------------------------------


def create_then_delete(service: TaskService, kwargs: dict[str, Any]) -> None:
    service.delete_task(service.create_task(**kwargs).id)


def reassign_and_restore(
    service: TaskService, task_id: int, user_id: Optional[int]
) -> None:
    original = service.get_task(task_id).assignee_user_id
    service.assign_task(task_id, user_id)
    service.assign_task(task_id, original)


@given(
    stock=st.lists(tasks(), max_size=MAX_TASKS),
    kwargs=creation_kwargs(),
    user_id=assignees(),
    pick=st.integers(min_value=0),
    variant=st.sampled_from(("create_delete", "reassign")),
)
def test_mt15_inverse_operations(
    stock: list[Task],
    kwargs: dict[str, Any],
    user_id: Optional[int],
    pick: int,
    variant: str,
) -> None:
    """MT-15: create+delete and assign+reassign back restore list_tasks and every get_task."""
    service, added = populate(stock)
    before = current_tasks(service)
    if variant == "reassign" and added:
        reassign_and_restore(service, added[pick % len(added)].id, user_id)
    else:  # an empty stock has no task to reassign
        create_then_delete(service, kwargs)
    assert current_tasks(service) == before, f"MT-15: {variant} changed list_tasks"
    assert (
        fetch(service, before) == before
    ), f"MT-15: {variant} changed get_task results"


# --- MT-22 -----------------------------------------------------------------------------


@given(reference_time=reference_times(), data=st.data())
def test_mt22_auto_plus_10_independent_of_filtered_calls(
    reference_time: datetime, data: st.DataObject
) -> None:
    """MT-22: earlier filtered calls and reopening a completed task do not change the final due dates."""
    t = reference_time
    stock = data.draw(relative_stocks(t), label="stock")
    overdue = replace(
        data.draw(tasks(), label="T"),
        completed=False,
        due_date=t.date()
        - timedelta(days=data.draw(st.integers(1, 400), label="overdue days")),
    )
    position = data.draw(st.integers(0, len(stock)), label="T position")
    stock.insert(position, overdue)
    base = auto_dues(stock, [t])

    service, added = populate(stock)
    service.set_auto_plus10(True)
    t1 = earlier(
        t,
        data.draw(st.integers(0, 400), label="t1 days"),
        data.draw(st.integers(0, 1439), label="t1 min"),
    )
    result = id_set(
        service.list_tasks(
            reference_time=t1, **data.draw(list_filters(added, require_one=True))
        )
    )
    for task in added:
        if task.id not in result:
            assert (
                service.get_task(task.id).due_date == task.due_date
            ), f"MT-22: task {task.id} outside R moved"
    service.list_tasks(reference_time=t)
    assert [
        service.get_task(task.id).due_date for task in added
    ] == base, "MT-22: filtered call changes the result"

    service, added = populate(stock)
    service.toggle_task(added[position].id)  # T starts completed
    service.set_auto_plus10(True)
    service.toggle_task(added[position].id)
    service.list_tasks(reference_time=t)
    assert [
        service.get_task(task.id).due_date for task in added
    ] == base, "MT-22: reopened T differs from open T"
