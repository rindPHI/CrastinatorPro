"""Hypothesis strategies for the Crastinator Pro tests.

Task and User data come from the InputLab TDP dataset (TASK_SOURCE=tdp, default). Scenario edge
cases are mixed into real rows via ``vary=`` or replace a field via overrides.
TASK_SOURCE=hypothesis switches every data type to plain Hypothesis strategies.
"""

from __future__ import annotations

import csv
import io
import os
import warnings
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from crastinator_pro import USERS, Priority, Task, TaskService, User, UserNotFoundError, ValidationError

TDP_DATASET = os.environ.get("TDP_DATASET", "2026-10-09 Demo Dataset 150 Rows")
TASK_SOURCE = os.environ.get("TASK_SOURCE", "tdp").strip().lower()
MAX_TASKS = 200 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 30

MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2200, 12, 31)
PLUS10_MAX = date.max - timedelta(days=14)

SORT_FIELDS = ("due_date", "title", "priority", "completed")
ORDERS = ("asc", "desc")
INVALID_SORT_FIELDS = ("created_at", "", "Title", "DUE_DATE", "id")
INVALID_ORDERS = ("ASC", "up", "Desc", "", "descending")


def _tdp_configured() -> bool:
    """TDP is usable with a token (environment or .env) or an already downloaded dataset."""
    if os.environ.get("INPUTLAB_TDP_TOKEN"):
        return True
    env_file = Path(".env")
    if env_file.is_file() and "INPUTLAB_TDP_TOKEN" in env_file.read_text(encoding="utf-8", errors="ignore"):
        return True
    cache = Path(os.environ.get("INPUTLAB_TDP_CACHE", ".tdp_cache")) / "datasets"
    return cache.is_dir() and any(cache.glob("*.zip"))


def _select_tdp() -> bool:
    if TASK_SOURCE != "tdp":
        return False
    if _tdp_configured():
        return True
    warnings.warn("InputLab TDP not configured (no INPUTLAB_TDP_TOKEN, no cached dataset); "
                  "falling back to Hypothesis strategies.", stacklevel=1)
    return False


USE_TDP = _select_tdp()
if USE_TDP:
    import inputlab_tdp as tdp

# --- basic values ----------------------------------------------------------------------

TEXT_CHARS = st.characters(exclude_categories=("Cs",), exclude_characters="\x00")
COLLATION_TITLES = ("Apfel", "Äpfel", "apfel", "äpfel", "Strasse", "Straße", "STRASSE", "Zebra", "zebra",
                    "Öl", "Oel", "über", "Ufer", "Müller", "Muller", "Mueller", "a1", "A10", "#3 Notiz", "Ärger")
SORT_ALPHABET = "aAäÄbBoOöÖuUüÜsSßzZ019 #-."
SEARCH_CHARS = "abcABCäÄöÖüÜ01" + ".*%_(\\\"'"  # only characters with unambiguous case mapping
CSV_SPECIAL_TEXTS = ("a,b", "a;b", 'Er sagte "Hallo"', '""', "Zeile 1\nZeile 2", "=SUM(A1:A2)", "=1+1",
                     "Ünïcödé ✓ 😀 中文", 'ß, "x"; \n=y')
MULTILINE_TEXTS = ("Zeile 1\nZeile 2", "a\n\nb", "Ende\n")


def has_content(text: str) -> bool:
    return any(not char.isspace() for char in text)


def valid_titles() -> SearchStrategy[str]:
    return st.one_of(st.sampled_from(COLLATION_TITLES), st.text(TEXT_CHARS, min_size=1, max_size=40).filter(has_content))


def blank_titles(min_size: int = 0) -> SearchStrategy[str]:
    return st.text(alphabet=" \t\n", min_size=min_size, max_size=6)


def descriptions() -> SearchStrategy[Optional[str]]:
    return st.one_of(st.none(), st.just(""), st.text(TEXT_CHARS, max_size=60))


def priorities() -> SearchStrategy[Priority]:
    return st.sampled_from(list(Priority))


def users() -> SearchStrategy[User]:
    if USE_TDP:
        return tdp.builds(User, dataset=TDP_DATASET)
    return st.sampled_from(sorted(USERS.values(), key=lambda user: user.id))


def user_ids() -> SearchStrategy[int]:
    return users().map(lambda user: user.id)


def assignees() -> SearchStrategy[Optional[int]]:
    return st.none() | user_ids()


def unknown_user_ids() -> SearchStrategy[int]:
    return st.one_of(st.sampled_from([0, -1, 4, 2**31, 2**63]), st.integers(max_value=0), st.integers(min_value=4))


# --- dates and times -------------------------------------------------------------------

def _leap_year_at_or_before(year: int) -> int:
    year -= year % 4
    while not (year % 100 != 0 or year % 400 == 0):
        year -= 4
    return year


@st.composite
def calendar_edge_dates(draw, min_year: int = MIN_DATE.year, max_year: int = MAX_DATE.year) -> date:
    year = draw(st.integers(min_year, max_year))
    kind = draw(st.sampled_from(("year_end", "year_start", "feb_28", "feb_29", "mar_1", "single_digit")))
    if kind == "year_end":
        return date(year, 12, 31)
    if kind == "year_start":
        return date(year, 1, 1)
    if kind == "feb_28":
        return date(year, 2, 28)
    if kind == "feb_29":
        return date(_leap_year_at_or_before(year), 2, 29)
    if kind == "mar_1":
        return date(year, 3, 1)
    return date(year, draw(st.integers(1, 9)), draw(st.integers(1, 9)))


def edge_dates() -> SearchStrategy[date]:
    return st.one_of(st.dates(MIN_DATE, MAX_DATE), calendar_edge_dates())


def optional_edge_dates() -> SearchStrategy[Optional[date]]:
    return st.none() | edge_dates()


@st.composite
def _dates_on_weekday(draw) -> date:
    weeks = draw(st.integers(0, (PLUS10_MAX - date.min).days // 7 - 1))
    return date.min + timedelta(weeks=weeks, days=draw(st.integers(0, 6)))  # date.min is a Monday


@st.composite
def _late_december_dates(draw) -> date:
    return date(draw(st.integers(1, 9998)), 12, draw(st.integers(18, 31)))


@st.composite
def _dates_around_feb_29(draw) -> date:
    return date(draw(st.integers(1, 9998)), 3, 1) + timedelta(days=draw(st.integers(-3, 2)))


def plus10_due_dates() -> SearchStrategy[date]:
    """PBT-12: wide range, all weekdays, 18.-31.12., around 29.02.; result stays <= date.max."""
    return st.one_of(st.dates(max_value=PLUS10_MAX), _dates_on_weekday(), _late_december_dates(), _dates_around_feb_29())


@st.composite
def _special_reference_times(draw) -> datetime:
    day = draw(st.dates(MIN_DATE, MAX_DATE))
    if draw(st.booleans()):
        day += timedelta(days=(5 - day.weekday()) % 7 + draw(st.integers(0, 1)))  # Saturday or Sunday
    return datetime.combine(day, draw(st.sampled_from([time(0, 0), time(23, 59), time(12, 0)])))


def reference_times() -> SearchStrategy[datetime]:
    return st.one_of(st.datetimes(datetime(1900, 1, 1), datetime(2200, 12, 31)), _special_reference_times())


def relative_due_offsets() -> SearchStrategy[Optional[int]]:
    """Days relative to reference_time: none, far past, -1/0/+1, recent past, future."""
    return st.one_of(st.none(), st.integers(-7300, -400), st.sampled_from([-1, 0, 1]),
                     st.integers(-60, -2), st.integers(2, 400))


# --- tasks -----------------------------------------------------------------------------

def _base_task_fields() -> dict[str, SearchStrategy[Any]]:
    return {"id": st.integers(1, 10**9), "title": valid_titles(), "description": descriptions(),
            "due_date": optional_edge_dates(), "completed": st.booleans(),
            "assignee_user_id": assignees(), "priority": priorities()}


def task_strategy(*, vary: Optional[dict[str, SearchStrategy[Any]]] = None,
                  **overrides: SearchStrategy[Any]) -> SearchStrategy[Task]:
    """TDP rows; `vary` mixes edge cases into real rows, overrides replace a field entirely."""
    vary = vary or {}
    if USE_TDP:
        kwargs: dict[str, Any] = dict(overrides)
        if vary:
            kwargs["vary"] = vary
        return tdp.builds(Task, dataset=TDP_DATASET, **kwargs)
    fields = _base_task_fields()
    for name, strategy in vary.items():
        fields[name] = st.one_of(strategy, fields[name])
    fields.update(overrides)
    return st.builds(Task, **fields)


def _general_vary() -> dict[str, SearchStrategy[Any]]:
    return {"title": valid_titles(), "description": descriptions(), "due_date": optional_edge_dates()}


def tasks() -> SearchStrategy[Task]:
    return task_strategy(vary=_general_vary())


def mixed_tasks() -> SearchStrategy[Task]:
    return task_strategy(vary={**_general_vary(), "assignee_user_id": assignees(), "completed": st.booleans()})


def sort_titles() -> SearchStrategy[str]:
    return st.one_of(st.sampled_from(COLLATION_TITLES), st.text(SORT_ALPHABET, min_size=1, max_size=8).filter(has_content))


def sort_tasks() -> SearchStrategy[Task]:
    return task_strategy(vary={"title": sort_titles(), "due_date": optional_edge_dates(),
                               "priority": priorities(), "completed": st.booleans()})


def creation_kwargs() -> SearchStrategy[dict[str, Any]]:
    return sort_tasks().map(lambda t: {"title": t.title, "description": t.description, "due_date": t.due_date,
                                       "assignee_user_id": t.assignee_user_id, "priority": t.priority})


def search_tasks() -> SearchStrategy[Task]:
    return task_strategy(
        title=st.text(SEARCH_CHARS + " ", min_size=1, max_size=6).filter(has_content),
        description=st.none() | st.text(SEARCH_CHARS + " ", max_size=6),
        vary={"assignee_user_id": assignees(), "completed": st.booleans()},
    )


def query_terms() -> SearchStrategy[str]:
    return st.text(SEARCH_CHARS, min_size=1, max_size=3)


@st.composite
def spaced_query(draw, terms: list[str]) -> str:
    parts = [" " * draw(st.integers(0, 2))]
    for index, term in enumerate(terms):
        if index:
            parts.append(" " * draw(st.integers(1, 3)))
        parts.append(term)
    parts.append(" " * draw(st.integers(0, 2)))
    return "".join(parts)


def search_queries(min_terms: int = 1, max_terms: int = 4) -> SearchStrategy[str]:
    return st.lists(query_terms(), min_size=min_terms, max_size=max_terms).flatmap(spaced_query)


def csv_tasks() -> SearchStrategy[Task]:
    texts = st.one_of(st.sampled_from(CSV_SPECIAL_TEXTS), valid_titles())
    return task_strategy(vary={"title": texts, "description": st.one_of(descriptions(), st.sampled_from(CSV_SPECIAL_TEXTS)),
                               "due_date": optional_edge_dates(), "assignee_user_id": assignees(),
                               "priority": priorities(), "completed": st.booleans()})


def plus10_tasks(due_dates: Optional[SearchStrategy[date]] = None) -> SearchStrategy[Task]:
    return task_strategy(due_date=due_dates or plus10_due_dates())


@st.composite
def stocks_with_duplicates(draw, element: SearchStrategy[Task], max_size: int = MAX_TASKS) -> list[Task]:
    stock = draw(st.lists(element, max_size=max_size))
    if not stock:
        return stock
    copies = draw(st.lists(st.integers(0, len(stock) - 1), max_size=5))
    return [*stock, *(replace(stock[i]) for i in copies)]


@st.composite
def relative_stocks(draw, reference_time: datetime, max_size: int = MAX_TASKS) -> list[Task]:
    templates = draw(st.lists(tasks(), max_size=max_size))
    stock = []
    for task in templates:
        offset = draw(relative_due_offsets())
        due = None if offset is None else reference_time.date() + timedelta(days=offset)
        stock.append(replace(task, due_date=due, completed=draw(st.booleans())))
    return stock


def list_filters(added: list[Task], require_one: bool = False) -> SearchStrategy[dict[str, Any]]:
    letters = sorted({c.lower() for task in added for c in task.title if c.isascii() and c.isalpha()})
    query = st.sampled_from(letters) if letters else st.just("x")
    filters = st.fixed_dictionaries({}, optional={"query": query, "completed": st.booleans(),
                                                  "assignee_user_id": user_ids()})
    return filters.filter(bool) if require_one else filters


def list_kwargs() -> SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {"reference_time": reference_times()},
        optional={"sort_by": st.sampled_from(SORT_FIELDS + INVALID_SORT_FIELDS),
                  "order": st.sampled_from(ORDERS + INVALID_ORDERS),
                  "assignee_user_id": st.one_of(user_ids(), unknown_user_ids()),
                  "completed": st.booleans(),
                  "query": st.one_of(search_queries(), st.text(max_size=10))},
    )


# --- CSV import ------------------------------------------------------------------------

IMPORT_COLUMNS = ("title", "description", "dueDate", "assigneeUserId", "priority", "completed")
OPTIONAL_IMPORT_COLUMNS = IMPORT_COLUMNS[1:]
INVALID_DATES = ("15.01.2026", "2026-1-5", "2026-02-30", "2026/01/15", "morgen")
NON_NUMERIC_IDS = ("abc", "1.5", "eins", "1a")
INVALID_PRIORITIES = ("urgent", "critical", "sehr hoch")
INVALID_COMPLETED = ("vielleicht", "maybe", "?")


def render_csv(columns: tuple[str, ...] | list[str], rows: Any) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns))
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _first_record(text: str) -> dict[str, str]:
    return next(csv.DictReader(io.StringIO(text, newline="")))


@lru_cache(maxsize=1)
def completed_tokens() -> dict[bool, str]:
    """`completed` values as written by export_csv itself (valid import values per PBT-15)."""
    service = TaskService()
    task = service.create_task(title="token probe")
    open_value = _first_record(service.export_csv())["completed"]
    service.toggle_task(task.id)
    return {False: open_value, True: _first_record(service.export_csv())["completed"]}


def task_to_row(task: Task) -> dict[str, str]:
    return {"title": task.title, "description": task.description or "",
            "dueDate": "" if task.due_date is None else task.due_date.isoformat(),
            "assigneeUserId": "" if task.assignee_user_id is None else str(task.assignee_user_id),
            "priority": Priority(task.priority).value, "completed": completed_tokens()[task.completed]}


def expected_import_content(row: dict[str, str]) -> tuple:
    """Loose content a valid row must produce; empty or missing optional fields get REQ-101 defaults."""
    return (row["title"], row.get("description", ""),
            date.fromisoformat(row["dueDate"]) if row.get("dueDate") else None,
            row.get("completed") == completed_tokens()[True],
            int(row["assigneeUserId"]) if row.get("assigneeUserId") else None,
            Priority(row["priority"]) if row.get("priority") else Priority.MEDIUM)


@dataclass(frozen=True)
class ImportFile:
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    expected: tuple[Optional[tuple], ...]  # loose content per row, None for invalid rows

    @property
    def text(self) -> str:
        return render_csv(self.columns, self.rows)


@st.composite
def valid_import_rows(draw, columns: tuple[str, ...] = IMPORT_COLUMNS) -> tuple[dict[str, str], tuple]:
    task = draw(task_strategy(vary={"description": st.one_of(descriptions(), st.sampled_from(MULTILINE_TEXTS))}))
    full = task_to_row(task)
    blank = draw(st.sets(st.sampled_from(OPTIONAL_IMPORT_COLUMNS)))
    row = {column: "" if column in blank else full[column] for column in columns}
    return row, expected_import_content(row)


def _row_breakers(single_column: bool) -> dict[str, SearchStrategy[str]]:
    return {"title": blank_titles(min_size=1 if single_column else 0),
            "assigneeUserId": st.one_of(unknown_user_ids().map(str), st.sampled_from(NON_NUMERIC_IDS)),
            "dueDate": st.sampled_from(INVALID_DATES),
            "priority": st.sampled_from(INVALID_PRIORITIES),
            "completed": st.sampled_from(INVALID_COMPLETED)}


@st.composite
def invalid_import_rows(draw, columns: tuple[str, ...] = IMPORT_COLUMNS) -> dict[str, str]:
    row, _ = draw(valid_import_rows(columns))
    breakers = _row_breakers(single_column=len(columns) == 1)
    column = draw(st.sampled_from([c for c in columns if c in breakers]))
    row[column] = draw(breakers[column])
    return row


@st.composite
def valid_import_files(draw, min_rows: int = 0) -> ImportFile:
    entries = draw(st.lists(valid_import_rows(), min_size=min_rows, max_size=MAX_TASKS))
    return ImportFile(IMPORT_COLUMNS, tuple(r for r, _ in entries), tuple(e for _, e in entries))


@st.composite
def mixed_import_files(draw, allow_missing_title: bool = True, max_rows: int = MAX_TASKS) -> ImportFile:
    dropped = draw(st.sets(st.sampled_from(OPTIONAL_IMPORT_COLUMNS)))
    columns = tuple(c for c in IMPORT_COLUMNS if c not in dropped)
    flags = draw(st.lists(st.booleans(), max_size=max_rows))
    without_title = columns[1:]
    if allow_missing_title and len(without_title) >= 2 and draw(st.integers(0, 9)) == 0:
        rows = [draw(valid_import_rows(columns))[0] for _ in flags]
        return ImportFile(without_title, tuple({c: r[c] for c in without_title} for r in rows), tuple(None for _ in rows))
    rows, expected = [], []
    for valid in flags:
        row, exp = draw(valid_import_rows(columns)) if valid else (draw(invalid_import_rows(columns)), None)
        rows.append(row)
        expected.append(exp)
    return ImportFile(columns, tuple(rows), tuple(expected))


# --- AI texts --------------------------------------------------------------------------

TODO_PHRASES = ("Präsentation vorbereiten", "Rechnung bezahlen", "Auto zur Inspektion bringen", "Bericht schreiben",
                "Keller aufräumen", "Geschenk kaufen", "Fenster putzen", "Bücher zurückbringen")
PLAIN_TODO_TEXTS = TODO_PHRASES  # no date, name or priority hint
ODD_TEXTS = ("x", "Buy milk", "Acheter du pain", "asdf qwer zxcv", "🙂", "42")
FILLER_WORDS = ("bitte", "noch", "auch", "dann")
HIGH_HINTS = ("dringend", "wichtig", "ASAP")
LOW_HINTS = ("irgendwann", "unwichtig", "wenn Zeit ist")
DAY_RELATIVE = ("morgen", "übermorgen", "in 3 Tagen")
WEEK_RELATIVE = ("nächsten Montag",)
GENERAL_QUESTIONS = ("Was steht bei mir an?", "Welche Aufgaben habe ich offen?", "Was soll ich als Nächstes tun?")
TIME_QUESTIONS = ("Was ist bei mir überfällig?", "Was ist diese Woche fällig?")
FACTS = (("Zahnarzttermin vereinbaren", "Muss ich einen Zahnarzttermin vereinbaren?"),
         ("Reisepass verlängern", "Muss ich meinen Reisepass verlängern?"),
         ("Geburtstagsgeschenk für Oma kaufen", "Muss ich ein Geburtstagsgeschenk für Oma kaufen?"),
         ("Kaminkehrer anrufen", "Soll ich den Kaminkehrer anrufen?"))
DISTINCTIVE_TITLES = ("Steuerbescheid prüfen", "Fahrradschloss ersetzen", "Kuchen für Lenas Feier backen",
                      "Winterreifen montieren lassen", "Bibliotheksbuch verlängern", "Heizungsablesung eintragen",
                      "Passfoto machen lassen", "Tierarzttermin für Mimi", "Gartenschlauch reparieren",
                      "Konzertkarten abholen")
REFORMULATIONS = (
    ("{name} soll bis {date} die Präsentation vorbereiten.", "Bis {date} muss {name} die Präsentation erstellen.",
     "Die Präsentation soll bis {date} von {name} vorbereitet werden.",
     "Vorbereitung der Präsentation durch {name}, fällig am {date}."),
    ("{name} muss bis {date} die Stromrechnung bezahlen.", "Die Stromrechnung ist bis {date} von {name} zu begleichen.",
     "Bis {date} soll {name} die Stromrechnung überweisen.", "Stromrechnung: Zahlung durch {name} bis {date}."),
    ("{name} soll bis {date} das Auto zur Inspektion bringen.",
     "Das Auto muss bis {date} von {name} zur Inspektion gebracht werden.",
     "Bis {date} bringt {name} den Wagen zur Inspektion.", "Inspektion des Autos: {name} kümmert sich bis {date} darum."),
)


@st.composite
def _sentence(draw, parts: list[str]) -> str:
    words = list(draw(st.permutations(parts)))
    for filler in draw(st.lists(st.sampled_from(FILLER_WORDS), max_size=2)):
        words.insert(draw(st.integers(0, len(words))), filler)
    return " ".join(words) + draw(st.sampled_from(("", ".", "!")))


@st.composite
def _random_case(draw, text: str) -> str:
    return "".join(c.upper() if draw(st.booleans()) else c.lower() for c in text)


def ai_dates() -> SearchStrategy[date]:
    return st.one_of(calendar_edge_dates(2000, 2100), st.dates(date(2000, 1, 1), date(2100, 12, 31)))


def ai_free_texts() -> SearchStrategy[str]:
    return st.one_of(st.sampled_from(PLAIN_TODO_TEXTS + ODD_TEXTS),
                     st.text(TEXT_CHARS, min_size=1, max_size=200).filter(has_content),
                     st.sampled_from(PLAIN_TODO_TEXTS).map(lambda t: " ".join([t] * 150)))


def ai_questions() -> SearchStrategy[str]:
    return st.one_of(st.just(""), blank_titles(min_size=1), st.sampled_from(GENERAL_QUESTIONS),
                     st.text(TEXT_CHARS, max_size=80), st.sampled_from(GENERAL_QUESTIONS).map(lambda q: " ".join([q] * 200)))


@st.composite
def explicit_task_texts(draw) -> tuple[str, Optional[date], Optional[int]]:
    parts = [draw(st.sampled_from(TODO_PHRASES))]
    due, user = draw(st.none() | ai_dates()), draw(st.none() | users())
    if due is not None:
        parts.append(f"{draw(st.sampled_from(('bis', 'am', 'fällig am', 'Termin')))} {due.isoformat()}")
    if user is not None:
        parts.append(draw(st.sampled_from(("für {}", "{} soll das erledigen", "zuständig ist {}"))).format(user.name))
    return draw(_sentence(parts)), due, None if user is None else user.id


@st.composite
def priority_hint_texts(draw) -> tuple[str, Priority]:
    group = draw(st.sampled_from(("high", "low", "none")))
    parts = [draw(st.sampled_from(TODO_PHRASES))]
    due, user = draw(st.none() | ai_dates()), draw(st.none() | users())
    if due is not None:
        parts.append(f"bis {due.isoformat()}")
    if user is not None:
        parts.append(f"für {user.name}")
    if group != "none":
        parts.append(draw(_random_case(draw(st.sampled_from(HIGH_HINTS if group == "high" else LOW_HINTS)))))
    return draw(_sentence(parts)), {"high": Priority.HIGH, "low": Priority.LOW, "none": Priority.MEDIUM}[group]


@st.composite
def relative_date_texts(draw) -> tuple[str, str, str]:
    phrase = draw(st.sampled_from(DAY_RELATIVE + WEEK_RELATIVE))
    text = draw(_sentence([draw(st.sampled_from(TODO_PHRASES)), phrase]))
    return text, phrase, "day" if phrase in DAY_RELATIVE else "week"


@st.composite
def boundary_reference_times(draw) -> datetime:
    anchor = draw(ai_dates()) + timedelta(days=draw(st.integers(-3, 3)))
    return datetime.combine(anchor, draw(st.sampled_from([time(0, 0), time(9, 0), time(23, 59)])))


@st.composite
def reformulation_cases(draw) -> tuple[str, list[str]]:
    templates = draw(st.sampled_from(REFORMULATIONS))
    name, due = draw(users()).name, draw(ai_dates()).isoformat()
    hint = draw(st.none() | st.sampled_from(HIGH_HINTS + LOW_HINTS))
    texts = [t.format(name=name, date=due) + (f" ({hint})" if hint else "") for t in templates]
    return texts[0], texts[1:]


def parsed_task_dicts() -> SearchStrategy[dict[str, Any]]:
    # due_date stays None: the value type parse_task() must use for dates is not documented
    return st.fixed_dictionaries({
        "title": st.one_of(valid_titles(), blank_titles()), "description": st.none() | st.text(TEXT_CHARS, max_size=30),
        "due_date": st.none(), "assignee_user_id": st.one_of(st.none(), user_ids(), unknown_user_ids()),
        "priority": st.one_of(priorities(), st.sampled_from(INVALID_PRIORITIES))})


@st.composite
def invalid_parsed_tasks(draw) -> tuple[dict[str, Any], type[Exception]]:
    parsed = {"title": draw(valid_titles()), "description": None, "due_date": None,
              "assignee_user_id": draw(assignees()), "priority": draw(priorities())}
    kind = draw(st.sampled_from(("blank_title", "unknown_assignee", "invalid_priority")))
    if kind == "blank_title":
        parsed["title"] = draw(blank_titles())
        return parsed, ValidationError
    if kind == "unknown_assignee":
        parsed["assignee_user_id"] = draw(unknown_user_ids())
        return parsed, UserNotFoundError
    parsed["priority"] = draw(st.sampled_from(INVALID_PRIORITIES))
    return parsed, ValidationError


# --- random operation sequences (PBT-17, PBT-18, PBT-24) -------------------------------

def operations(*, include_ai_ask: bool = False, include_ai_create: bool = False) -> SearchStrategy[tuple[str, dict[str, Any]]]:
    picks = st.none() | st.integers(0, 10_000)
    any_assignee = st.one_of(st.none(), user_ids(), unknown_user_ids())

    def op(name: str, **fields: SearchStrategy[Any]) -> SearchStrategy[tuple[str, dict[str, Any]]]:
        return st.tuples(st.just(name), st.fixed_dictionaries(fields))

    options = [
        op("create", title=st.one_of(valid_titles(), blank_titles()), description=descriptions(),
           due_date=optional_edge_dates(), assignee_user_id=any_assignee, priority=priorities()),
        op("add", task=st.one_of(tasks(), task_strategy(title=blank_titles()),
                                 task_strategy(assignee_user_id=unknown_user_ids())), reuse=picks),
        op("toggle", pick=picks), op("delete", pick=picks), op("get_task", pick=picks),
        op("assign", pick=picks, user_id=any_assignee),
        op("plus_10", pick=picks, reference_time=reference_times()),
        op("set_auto", enabled=st.booleans()),
        op("list_tasks", kwargs=list_kwargs()),
        op("import_csv", csv=mixed_import_files(max_rows=5).map(lambda f: f.text)),
        op("export_csv"), op("list_users"), op("get_auto"),
        op("get_user", user_id=st.integers()),
    ]
    if include_ai_ask:
        options.append(op("ai_ask", user_id=st.one_of(user_ids(), unknown_user_ids()),
                          question=st.text(max_size=40), reference_time=reference_times()))
    if include_ai_create:
        options.append(op("ai_create", text=st.one_of(ai_free_texts(), blank_titles()),
                          reference_time=reference_times(), parsed=parsed_task_dicts()))
    return st.one_of(options)