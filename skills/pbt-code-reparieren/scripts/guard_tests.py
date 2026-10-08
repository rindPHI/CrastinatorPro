#!/usr/bin/env python3
"""Guard test files against changes while production code is being repaired.

snapshot: writes SHA-256 checksums of the protected paths to a state file
          outside of those paths.
verify:   compares the current state with the snapshot and reports every deviation.

Protected: all files in the test directory (default tests/pbt), every conftest.py
in the project, pytest.ini / .pytest.ini, the pytest and Hypothesis sections of
pyproject.toml, tox.ini and setup.cfg, and .hypothesis/.

.hypothesis/ is special: Hypothesis itself adds and removes entries there during
a normal test run (it deletes saved examples that no longer fail). Therefore
only the removal or reset of the whole directory counts as a violation; changed,
added and removed single entries are reported as numbers only.

Exit code: 0 = ok, 1 = deviations (guardrail violation), 2 = usage error.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "site-packages", "__pycache__", ".tox", ".hypothesis"}
CONFIG_SECTIONS = {
    "tox.ini": ("pytest", "tool:pytest", "hypothesis"),
    "setup.cfg": ("tool:pytest", "tool:hypothesis", "pytest", "hypothesis"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def walk_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield path


def project_conftests(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in sorted(current.iterdir()):
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            elif entry.name == "conftest.py":
                yield entry


def pyproject_sections(path: Path) -> dict[str, str]:
    """Hash only [tool.pytest*] / [tool.hypothesis*]; unrelated edits (dependencies) are allowed."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        return {"pyproject.toml (komplette Datei, tomllib fehlt)": sha256(path.read_bytes())}
    tool = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {})
    return {
        f"pyproject.toml#tool.{name}": sha256(json.dumps(tool[name], sort_keys=True, default=str).encode())
        for name in ("pytest", "hypothesis")
        if name in tool
    }


def ini_sections(path: Path, names: tuple[str, ...]) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    return {
        f"{path.name}#{name}": sha256(json.dumps(dict(parser[name]), sort_keys=True).encode())
        for name in names
        if parser.has_section(name)
    }


def collect(root: Path, tests: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if tests.is_dir():
        for path in walk_files(tests):
            files[rel(path, root)] = sha256(path.read_bytes())
    for path in project_conftests(root):
        files[rel(path, root)] = sha256(path.read_bytes())
    for name in ("pytest.ini", ".pytest.ini"):
        if (root / name).is_file():
            files[name] = sha256((root / name).read_bytes())
    if (root / "pyproject.toml").is_file():
        files.update(pyproject_sections(root / "pyproject.toml"))
    for name, sections in CONFIG_SECTIONS.items():
        if (root / name).is_file():
            files.update(ini_sections(root / name, sections))
    return files


def hypothesis_state(root: Path) -> dict:
    base = root / ".hypothesis"
    if not base.is_dir():
        return {"exists": False, "files": {}, "entries": 0}
    return {
        "exists": True,
        "files": {rel(p, root): sha256(p.read_bytes()) for p in walk_files(base)},
        "entries": sum(1 for _ in base.rglob("*")),
    }


def default_state(root: Path) -> Path:
    return Path(tempfile.gettempdir()) / f"pbt_guard_{sha256(str(root).encode())[:12]}.json"


def is_inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def snapshot(root: Path, tests: Path, state: Path) -> int:
    state.parent.mkdir(parents=True, exist_ok=True)
    files = collect(root, tests)
    hyp = hypothesis_state(root)
    state.write_text(
        json.dumps({"root": str(root), "tests": str(tests), "files": files, "hypothesis": hyp}, indent=1),
        encoding="utf-8",
    )
    print(
        f"Snapshot: {len(files)} geschützte Einträge, .hypothesis: "
        f"{len(hyp['files'])} Dateien ({'vorhanden' if hyp['exists'] else 'nicht vorhanden'}). Zustandsdatei: {state}"
    )
    return 0


def verify(root: Path, tests: Path, state: Path) -> int:
    if not state.is_file():
        print(f"Kein Snapshot gefunden: {state}. Zuerst 'snapshot' ausführen.", file=sys.stderr)
        return 2
    saved = json.loads(state.read_text(encoding="utf-8"))
    before, now = saved["files"], collect(root, tests)
    violations: list[str] = []
    violations += [f"Geändert: {name}" for name in sorted(now) if name in before and now[name] != before[name]]
    violations += [f"Gelöscht: {name}" for name in sorted(before) if name not in now]
    violations += [f"Neu hinzugekommen: {name}" for name in sorted(now) if name not in before]

    old_hyp, new_hyp = saved["hypothesis"], hypothesis_state(root)
    if old_hyp["exists"] and not new_hyp["exists"]:
        violations.append("Gelöscht: .hypothesis/ (gesamtes Verzeichnis)")
    elif old_hyp["files"] and new_hyp["entries"] == 0:
        violations.append("Zurückgesetzt: .hypothesis/ ist jetzt leer")

    if violations:
        print(f"Leitplankenverstoß: {len(violations)} Abweichung(en) gegenüber dem Snapshot")
        print("\n".join(violations))
    else:
        print("OK: keine Abweichungen bei Testordner, conftest.py und pytest-Konfiguration")
    old_files, new_files = old_hyp["files"], new_hyp["files"]
    changed = sum(1 for k in new_files if k in old_files and new_files[k] != old_files[k])
    print(
        f"Info .hypothesis (kein Verstoß): {sum(k not in old_files for k in new_files)} neu, "
        f"{changed} geändert, {sum(k not in new_files for k in old_files)} entfernt"
    )
    return 1 if violations else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guards test files: 'snapshot' stores checksums of the test directory, conftest.py, "
        "pytest configuration and .hypothesis/; 'verify' reports every deviation."
    )
    parser.add_argument("command", choices=("snapshot", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    parser.add_argument("--tests", type=Path, default=Path("tests/pbt"), help="test directory, relative to root (default: tests/pbt)")
    parser.add_argument("--state", type=Path, default=None, help="state file outside the protected paths (default: system temp directory)")
    args = parser.parse_args()

    root = args.root.resolve()
    tests = args.tests if args.tests.is_absolute() else root / args.tests
    tests = tests.resolve()
    state = (args.state or default_state(root)).resolve()
    protected = [tests, root / ".hypothesis"]
    if any(is_inside(state, p) for p in protected) or state.name == "conftest.py":
        print("Die Zustandsdatei darf nicht in den geschützten Pfaden liegen.", file=sys.stderr)
        return 2
    if not tests.is_dir():
        print(f"Testordner nicht gefunden: {tests}", file=sys.stderr)
        return 2
    return snapshot(root, tests, state) if args.command == "snapshot" else verify(root, tests, state)


if __name__ == "__main__":
    sys.exit(main())
