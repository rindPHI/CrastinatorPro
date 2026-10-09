"""Non-functional tests: PBT-18 (determinism) and MT-16 (sorting runtime)."""

from __future__ import annotations

import math
import random
import statistics
import time
from datetime import date, timedelta
from itertools import combinations
from typing import Callable, Optional

import pytest
from hypothesis import given, settings, strategies as st

from conftest import (
    AI_EXAMPLES,
    READ_OPERATIONS,
    REF_TIME,
    Operation,
    RecordingProvider,
    apply_operation,
    requires_default_ai,
    strip_columns,
)
from crastinator_pro import AIProvider, Priority, TaskService
from strategies import ORDERS, SORT_FIELDS, operations

# --- PBT-18 ----------------------------------------------------------------------------


def _repeatable(service: TaskService, name: str) -> bool:
    # list_tasks only reads while auto +10 is off (API doc), so it is repeated only then
    return name in READ_OPERATIONS and not (
        name == "list_tasks" and service.get_auto_plus10()
    )


def _determinism_check(
    make_provider: Callable[[], Optional[AIProvider]],
) -> Callable[[], None]:
    @given(steps=st.lists(operations(include_ai_ask=True), max_size=30))
    def check(steps: list[Operation]) -> None:
        first = TaskService(ai_provider=make_provider())
        second = TaskService(ai_provider=make_provider())
        for step in steps:
            outcome = apply_operation(first, step)
            assert outcome == apply_operation(
                second, step
            ), f"PBT-18: {step[0]} differs between instances"
            if _repeatable(first, step[0]):
                assert (
                    apply_operation(first, step) == outcome
                ), f"PBT-18: repeated {step[0]} differs"
        assert strip_columns(first.export_csv(), ["createdAt"]) == strip_columns(
            second.export_csv(), ["createdAt"]
        ), "PBT-18: final export_csv differs"

    return check


@pytest.mark.parametrize(
    "provider",
    ["stub", pytest.param("default", marks=[pytest.mark.ai, requires_default_ai])],
)
def test_pbt18_determinism(provider: str) -> None:
    """PBT-18: two fresh instances given the same operation sequence return identical results."""
    if provider == "stub":
        _determinism_check(RecordingProvider)()
    else:
        settings(max_examples=AI_EXAMPLES)(_determinism_check(lambda: None))()


# --- MT-16 -----------------------------------------------------------------------------

SIZES = (1_000, 2_000, 5_000, 10_000, 50_000, 100_000)
RUNS = 7
DISTRIBUTIONS = ("random", "presorted", "reversed", "all_equal", "few_distinct")
BASE_DATE = date(2000, 1, 1)
PRIORITY_LEVELS = (Priority.LOW, Priority.MEDIUM, Priority.HIGH)


def ranks(distribution: str, n: int) -> list[int]:
    generator = random.Random(n)
    if distribution == "random":
        values = list(range(n))
        generator.shuffle(values)
        return values
    if distribution == "presorted":
        return list(range(n))
    if distribution == "reversed":
        return list(range(n - 1, -1, -1))
    if distribution == "all_equal":
        return [0] * n
    return [generator.randrange(5) for _ in range(n)]


def build_stock(distribution: str, n: int) -> TaskService:
    """Stock of size n; every sort key follows the same rank distribution."""
    service = TaskService()
    values = ranks(distribution, n)
    top = max(values) + 1
    for rank in values:
        task = service.create_task(
            title=f"Task {rank:06d}",
            due_date=BASE_DATE + timedelta(days=rank),
            priority=PRIORITY_LEVELS[rank * 3 // top],
        )
        if top > 1 and rank * 2 >= top:
            service.toggle_task(task.id)
    return service


def median_runtime(service: TaskService, sort_by: str, order: str) -> float:
    durations = []
    for _ in range(RUNS):
        start = time.perf_counter()
        service.list_tasks(reference_time=REF_TIME, sort_by=sort_by, order=order)
        durations.append(time.perf_counter() - start)
    return statistics.median(durations)


def allowed_ratio(n: int, n_prime: int) -> float:
    return 2 * (n_prime * math.log(n_prime)) / (n * math.log(n))


@pytest.mark.performance
@pytest.mark.parametrize("distribution", DISTRIBUTIONS)
def test_mt16_sort_runtime_scaling(distribution: str) -> None:
    """MT-16: t(n')/t(n) <= 2 * (n' log n')/(n log n) for all size pairs, sort fields and orders."""
    timings: dict[tuple[str, str], dict[int, float]] = {}
    for n in SIZES:
        service = build_stock(distribution, n)
        for sort_by in SORT_FIELDS:
            for order in ORDERS:
                timings.setdefault((sort_by, order), {})[n] = median_runtime(
                    service, sort_by, order
                )
        del service
    violations = [
        f"{sort_by}/{order} {n}->{n_prime}: {by_size[n_prime] / by_size[n]:.2f} > {allowed_ratio(n, n_prime):.2f}"
        for (sort_by, order), by_size in timings.items()
        for n, n_prime in combinations(SIZES, 2)
        if by_size[n_prime] / max(by_size[n], 1e-9)
        > allowed_ratio(n, n_prime)  # guard against a zero timer reading
    ]
    assert (
        not violations
    ), f"MT-16 ({distribution}): runtime grows too fast: {violations}"
