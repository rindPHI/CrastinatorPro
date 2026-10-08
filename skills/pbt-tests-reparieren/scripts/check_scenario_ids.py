#!/usr/bin/env python3
"""Check that every scenario ID of the scenario document is implemented exactly once.

Scenario IDs (PBT-NN, MT-NN) are read from the scenario document: a scenario
starts with a line whose first token (after Markdown markers such as '#', '-',
'*') is the ID. Lines in the section "Nicht abgedeckte Requirements" are ignored.

A test counts as implementing an ID if its docstring begins with the ID. Tests
are functions named test* and classes derived from RuleBasedStateMachine.

Exit code: 0 = everything matches, 1 = findings, 2 = usage error.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

LINE_ID_RE = re.compile(r"^[\s#>*_\-\d.]*\**\s*((?:PBT|MT)-\d+)\b")
DOC_ID_RE = re.compile(r"^\s*((?:PBT|MT)-\d+)\b")
NOT_COVERED_RE = re.compile(r"^#+\s*.*nicht abgedeckt", re.IGNORECASE)
HEADING_RE = re.compile(r"^#+\s")


def scenario_ids(doc: Path) -> list[str]:
    ids: list[str] = []
    in_not_covered = False
    for line in doc.read_text(encoding="utf-8").splitlines():
        if HEADING_RE.match(line):
            in_not_covered = bool(NOT_COVERED_RE.match(line))
        if in_not_covered:
            continue
        match = LINE_ID_RE.match(line)
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def is_state_machine(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        if name == "RuleBasedStateMachine":
            return True
    return False


def test_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("test_*.py")))
        elif path.is_file():
            files.append(path)
    return files


def implemented(files: list[Path]) -> tuple[dict[str, list[str]], list[str]]:
    """Return ({ID: [locations]}, [tests without ID])."""
    found: dict[str, list[str]] = defaultdict(list)
    without_id: list[str] = []
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            print(f"Warnung: {file} nicht lesbar ({error})", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            is_test = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")
            if not (is_test or (isinstance(node, ast.ClassDef) and is_state_machine(node))):
                continue
            match = DOC_ID_RE.match(ast.get_docstring(node) or "")
            location = f"{file}::{node.name}"
            if match:
                found[match.group(1)].append(location)
            elif is_test:
                without_id.append(location)
    return found, without_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Checks that every scenario ID (PBT-NN, MT-NN) from the scenario document is "
        "implemented exactly once as a test. Prints missing, duplicate and unknown IDs."
    )
    parser.add_argument("scenarios", type=Path, help="scenario document, e.g. eigenschaften.md")
    parser.add_argument("tests", type=Path, nargs="+", help="test directory or test files, e.g. tests/pbt")
    args = parser.parse_args()

    if not args.scenarios.is_file():
        print(f"Szenario-Dokument nicht gefunden: {args.scenarios}", file=sys.stderr)
        return 2
    files = test_files(args.tests)
    if not files:
        print(f"Keine Testdateien gefunden in: {', '.join(map(str, args.tests))}", file=sys.stderr)
        return 2

    expected = scenario_ids(args.scenarios)
    found, without_id = implemented(files)

    missing = [i for i in expected if i not in found]
    duplicate = {i: locs for i, locs in found.items() if i in expected and len(locs) > 1}
    unknown = {i: locs for i, locs in found.items() if i not in expected}

    print(f"{len(expected)} Szenario-IDs im Dokument, {len(found)} verschiedene IDs in {len(files)} Testdateien")
    if missing:
        print("Fehlend (kein Test): " + ", ".join(missing))
    for scenario_id, locations in duplicate.items():
        print(f"Doppelt: {scenario_id} -> " + "; ".join(locations))
    for scenario_id, locations in unknown.items():
        print(f"Unbekannt (nicht im Dokument): {scenario_id} -> " + "; ".join(locations))
    if without_id:
        print("Hinweis, Tests ohne Szenario-ID im Docstring: " + "; ".join(without_id))
    if not (missing or duplicate or unknown):
        print("OK: jede ID genau einmal umgesetzt")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
