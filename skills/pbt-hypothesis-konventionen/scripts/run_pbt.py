#!/usr/bin/env python3
"""Run pytest and print a compact failure summary for PBT/MT tests.

For every failure or error the summary shows the scenario ID (PBT-NN / MT-NN),
the test name, the kind of failure and Hypothesis' minimal counterexample.
The scenario ID is taken from the assertion message, otherwise from the
docstring of the test (found via the source file).

Exit code: the exit code of pytest (non-zero if there are findings).
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ID_RE = re.compile(r"\b(?:PBT|MT)-\d+\b")
DOC_ID_RE = re.compile(r"^\s*((?:PBT|MT)-\d+)\b")
MAX_EXAMPLE_LINES = 25
MAX_MESSAGE_CHARS = 200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Runs pytest, reads the result via --junitxml and prints, per failure, "
        "scenario ID, test name, kind of failure and the minimal Hypothesis counterexample.",
        usage="run_pbt.py [--runner CMD] [--raw] [--] <pytest arguments>",
    )
    parser.add_argument(
        "--runner",
        default=None,
        help='command that starts pytest (default: "<current python> -m pytest"), e.g. "uv run pytest"',
    )
    parser.add_argument("--raw", action="store_true", help="also print the complete pytest output")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="arguments passed to pytest")
    args = parser.parse_args()
    if args.pytest_args and args.pytest_args[0] == "--":
        args.pytest_args = args.pytest_args[1:]
    return args


def docstring_ids(path: Path) -> dict[str, str]:
    """Map test function / class names (and TestXyz = XyzMachine.TestCase aliases) to scenario IDs."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return {}
    ids: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            match = DOC_ID_RE.match(ast.get_docstring(node) or "")
            if match:
                ids.setdefault(node.name, match.group(1))
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute):
            if node.value.attr == "TestCase" and isinstance(node.value.value, ast.Name):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases[target.id] = node.value.value.id
    for alias, machine in aliases.items():
        if machine in ids:
            ids.setdefault(alias, ids[machine])
    return ids


def find_source(classname: str, root: Path) -> Path | None:
    """Resolve a junit classname such as 'tests.pbt.test_mt.TestX' to a file."""
    parts = classname.split(".") if classname else []
    while parts:
        candidate = root.joinpath(*parts).with_suffix(".py")
        if candidate.is_file():
            return candidate
        parts.pop()
    return None


EXAMPLE_RE = re.compile(r"(Falsifying (?:explicit )?example|Failing test case)")
E_PREFIX_RE = re.compile(r"^E {3}")
E_TYPE_RE = re.compile(r"^E {3}([A-Za-z_][\w.]*(?:Error|Exception|Exit))\b", re.MULTILINE)
ERROR_TYPE_RE = re.compile(r":\d+: ([A-Za-z_][\w.]*)\s*$", re.MULTILINE)


def falsifying_example(message: str, text: str) -> str:
    """Extract Hypothesis' minimal example (newer versions print 'Failing test case:')."""
    for source, prefixed in ((message, False), (text, True)):
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if prefixed:
                if not E_PREFIX_RE.match(line):
                    continue
                line = E_PREFIX_RE.sub("", line)
            if not EXAMPLE_RE.search(line):
                continue
            block = [line.strip()]
            for follow in lines[i + 1 : i + MAX_EXAMPLE_LINES]:
                if prefixed:
                    if not E_PREFIX_RE.match(follow):
                        break
                    follow = E_PREFIX_RE.sub("", follow)
                if not follow.strip():
                    break
                block.append(follow.rstrip())
            return "\n".join(block)
    return ""


def error_type(problem: ET.Element) -> str:
    """The exception type, from the traceback's last location line; falls back to the type attribute."""
    matches = ERROR_TYPE_RE.findall(problem.text or "")
    if matches:
        return matches[-1]
    named = E_TYPE_RE.findall(problem.text or "")
    return named[-1] if named else (problem.get("type") or "unbekannt")


def first_message(case_problem: ET.Element) -> str:
    message = (case_problem.get("message") or "").strip().splitlines()
    text = message[0] if message else ""
    if text == "collection failure":  # generic; the real reason is in the traceback
        reasons = [ln[1:].strip() for ln in (case_problem.text or "").splitlines() if E_PREFIX_RE.match(ln)]
        text = reasons[0] if reasons else text
    return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS] + "..."


def summarize(junit_path: Path, root: Path) -> tuple[list[str], dict[str, int]]:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    findings: list[str] = []
    doc_cache: dict[Path, dict[str, str]] = {}
    for case in ET.parse(junit_path).getroot().iter("testcase"):
        problem = case.find("failure")
        kind_label = "Fehlschlag"
        if problem is None:
            problem = case.find("error")
            kind_label = "Fehler"
        if problem is None:
            counts["skipped" if case.find("skipped") is not None else "passed"] += 1
            continue
        counts["failed" if kind_label == "Fehlschlag" else "error"] += 1
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        # Only the message and the "E ..." lines of the traceback, not the echoed source code
        error_lines = [ln for ln in (problem.text or "").splitlines() if E_PREFIX_RE.match(ln)]
        text = (problem.get("message") or "") + "\n" + "\n".join(error_lines)
        base_name = name.split("[")[0]

        scenario = ""
        match = ID_RE.search(text)
        if match:
            scenario = match.group(0)
        else:
            source = find_source(classname, root)
            if source is not None:
                ids = doc_cache.setdefault(source, docstring_ids(source))
                last = classname.split(".")[-1]
                scenario = ids.get(base_name) or ids.get(last) or ""

        header = f"[{scenario or 'ohne ID'}] {classname + '::' if classname else ''}{name}"
        entry = [f"{header}", f"  Art: {kind_label} ({error_type(problem)})", f"  Meldung: {first_message(problem)}"]
        example = falsifying_example(problem.get("message") or "", problem.text or "")
        if example:
            entry.append("  Gegenbeispiel: " + example.replace("\n", "\n    "))
        findings.append("\n".join(entry))
    return findings, counts


def main() -> int:
    args = parse_args()
    runner = shlex.split(args.runner) if args.runner else [sys.executable, "-m", "pytest"]
    root = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        junit_path = Path(tmp) / "junit.xml"
        command = runner + [f"--junitxml={junit_path}", "-p", "no:cacheprovider"] + args.pytest_args
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        try:
            result = subprocess.run(command, capture_output=True, text=True, env=env)
        except FileNotFoundError as error:
            print(f"Runner nicht gefunden: {error}", file=sys.stderr)
            return 2
        if args.raw:
            print(result.stdout + result.stderr)
        if not junit_path.is_file():
            print(f"Kein JUnit-Ergebnis (pytest Exit-Code {result.returncode}). Letzte Ausgabezeilen:")
            print("\n".join((result.stdout + result.stderr).splitlines()[-30:]))
            return result.returncode or 2
        findings, counts = summarize(junit_path, root)

    print(
        f"pytest Exit-Code {result.returncode}: {counts['passed']} bestanden, "
        f"{counts['failed']} fehlgeschlagen, {counts['error']} Fehler, {counts['skipped']} übersprungen"
    )
    for number, finding in enumerate(findings, start=1):
        print(f"\n{number}. {finding}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
