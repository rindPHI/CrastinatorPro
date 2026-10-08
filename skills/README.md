# PBT-/MT-Skills für Claude Code

Fünf Claude Code Skills für Property-Based Testing (PBT) und Metamorphic Testing (MT) mit Python, pytest und Hypothesis. Die Systemprompts in `prompts/` bleiben unverändert und sind weiterhin das Angebot für Nutzer ohne Claude Code.

## Übersicht

| Skill | Zweck | Auslösung | Eingaben | Ausgaben |
|---|---|---|---|---|
| `pbt-blackbox-api` | Blackbox-API-Dokumentation aus dem Quellcode (Prompt 1) | automatisch oder explizit | Umfang, Requirements | `blackbox_api.md`, Abschluss im Chat |
| `pbt-eigenschaften-finden` | Heuristiken für Eigenschaften und metamorphe Relationen (aus Prompt 2) | automatisch oder explizit | Requirements, Fragen des Nutzers | Hilfe im Gespräch |
| `pbt-hypothesis-konventionen` | Standardnamen, Hypothesis-Konventionen, Szenario-Format (aus Prompt 2 und 3), `run_pbt.py` | automatisch oder explizit; wird von den Reparatur-Skills geladen | – | Regeln, kompakte Testauswertung |
| `pbt-tests-reparieren` | Fehler im Testcode einordnen und mit Zustimmung reparieren (Prompt 4) | automatisch oder explizit | Tests, `blackbox_api.md`, `eigenschaften.md`, Testbefehl | geänderter Testcode, Bericht |
| `pbt-code-reparieren` | Produktivcode autonom reparieren, bis die Tests grün sind (Prompt 5) | nur explizit | Tests, `eigenschaften.md`, `blackbox_api.md`, Testbefehle | geänderter Produktivcode, Abschlussbericht |

Skripte: `check_scenario_ids.py` (in `pbt-tests-reparieren`), `run_pbt.py` (in `pbt-hypothesis-konventionen`), `guard_tests.py` (in `pbt-code-reparieren`). Alle laufen mit Python 3 ohne zusätzliche Pakete und haben `--help`.

## Einordnung in die Kette

```
Quellcode ──[Skill pbt-blackbox-api]──▶ blackbox_api.md
Requirements + blackbox_api.md ──[Prompt 2, Chat ohne Codezugriff]──▶ eigenschaften.md
eigenschaften.md + blackbox_api.md ──[Prompt 3, Chat ohne Codezugriff]──▶ tests/pbt
tests/pbt ──[Skill pbt-tests-reparieren]──▶ korrigierte Tests
tests/pbt ──[Skill pbt-code-reparieren]──▶ korrigierter Produktivcode
```

Prompt 2 (`prompts/02_eigenschaften_ableiten.md`) und Prompt 3 (`prompts/03_tests_generieren.md`) sind bewusst keine Skills. Sie arbeiten strikt Blackbox und laufen deshalb in einem Chat ohne Codezugriff. In Claude Code ließe sich das nur per Anweisung absichern, nicht technisch. Die Heuristiken aus Prompt 2 und die Konventionen aus Prompt 3 stehen als Wissen in `pbt-eigenschaften-finden` und `pbt-hypothesis-konventionen`.

## Installation

Die Skills ergänzen sich und müssen zusammen im selben Skills-Ordner installiert werden:

- `pbt-tests-reparieren`, `pbt-code-reparieren` und `pbt-blackbox-api` verweisen auf `pbt-hypothesis-konventionen` (Skill laden, relativer Pfad `../pbt-hypothesis-konventionen/`). Das gilt auch für `run_pbt.py`.
- `pbt-eigenschaften-finden` verweist auf das Szenario-Format in `pbt-hypothesis-konventionen`.

Alle fünf Ordner immer gemeinsam kopieren.

Projektweit (Befehle im Wurzelverzeichnis des Zielprojekts, `<pfad>` ist der Ordner dieses Repos):

```bash
# Linux/macOS
mkdir -p .claude/skills && cp -R <pfad>/skills/pbt-* .claude/skills/
```
```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force .claude\skills | Out-Null
Copy-Item -Recurse <pfad>\skills\pbt-* .claude\skills\
```

Nutzerweit:

```bash
# Linux/macOS
mkdir -p ~/.claude/skills && cp -R <pfad>/skills/pbt-* ~/.claude/skills/
```
```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse <pfad>\skills\pbt-* "$env:USERPROFILE\.claude\skills\"
```

Das `README.md` im Ordner `skills/` selbst wird nicht kopiert (es passt nicht auf `pbt-*`).
## Aufruf

- Automatisch auslösbare Skills (`pbt-blackbox-api`, `pbt-tests-reparieren`, `pbt-hypothesis-konventionen`, `pbt-eigenschaften-finden`) starten bei passender Anfrage von selbst. Explizit: `/pbt-blackbox-api`, `/pbt-tests-reparieren` usw., optional mit Zusatzangaben, z. B. `/pbt-blackbox-api Umfang: Paket crastinator, Requirements: docs/requirements.md`.
- `pbt-code-reparieren` hat `disable-model-invocation: true` und startet nur durch ausdrücklichen Aufruf: `/pbt-code-reparieren`. Die Eingaben (Testordner, Szenario-Dokument, API-Dokumentation, Testbefehle) sucht der Skill selbst im Projekt und im Gespräch. Fehlt etwas, bricht er mit einem kurzen Bericht ab.
- Empfohlene Reihenfolge nach einem roten Testlauf: zuerst `/pbt-tests-reparieren`, dann `/pbt-code-reparieren`.

## Voraussetzungen

- Python 3.9 oder neuer für die Skripte. Ab Python 3.11 prüft `guard_tests.py` bei `pyproject.toml` nur die pytest- und Hypothesis-Abschnitte. Davor wird die ganze Datei gehasht, und jede Änderung daran (auch an Abhängigkeiten) meldet eine Abweichung.
- pytest und Hypothesis im Projekt installiert.
- Ein Testbefehl, der pytest startet. Andere Starter (z. B. `uv run pytest`) gehen über `run_pbt.py --runner`.

## Bekannte Grenzen und offene Punkte

- Das Frontmatter-Feld `disable-model-invocation: true` und das Verhalten (Aufruf nur per `/name`) habe ich aus meinem Kenntnisstand übernommen und nicht gegen die aktuelle Claude-Code-Dokumentation geprüft. Nach der Installation prüfen: `/pbt-code-reparieren` muss auftauchen, und eine Anfrage wie „mach die Tests grün“ darf ihn nicht auslösen.
- Das Laden eines Skills durch einen anderen (Skill-Tool) hängt vom Modell ab. Die Skills enthalten dafür einen Ersatzweg über den relativen Pfad `../pbt-hypothesis-konventionen/`. Der setzt voraus, dass beide im selben Skills-Ordner liegen.
- Skriptpfade in den SKILL.md sind relativ zum jeweiligen Skill-Ordner angegeben. Das Modell muss sie gegen den tatsächlichen Installationsort auflösen. Eine Variable wie `${CLAUDE_SKILL_DIR}` habe ich nicht verwendet, weil ich ihre Verfügbarkeit nicht geprüft habe.
- Das Blackbox-Prinzip gilt in Claude Code nur per Anweisung. `pbt-blackbox-api` und die Reparatur-Skills lesen Code, und nichts verhindert technisch, dass Wissen daraus in die Ausgaben gelangt.
- `guard_tests.py` und `.hypothesis/`: Hypothesis legt beim normalen Testlauf selbst Einträge an und löscht Beispiele, die nicht mehr fehlschlagen. Deshalb gilt nur das Entfernen oder Leeren des gesamten Verzeichnisses als Verstoß. Neue, geänderte und einzeln entfernte Einträge werden als Zahlen gemeldet. Gezieltes Löschen einzelner Einträge fällt nicht auf.
- `guard_tests.py` schützt nur, was es kennt: Testordner (Standard `tests/pbt`), alle `conftest.py`, `pytest.ini`, `.pytest.ini`, die pytest-/Hypothesis-Abschnitte in `pyproject.toml`, `tox.ini`, `setup.cfg` und `.hypothesis/`. Eine Zustandsdatei im Temp-Verzeichnis hält den Snapshot. Sie kann der Agent technisch auch verändern.
- `check_scenario_ids.py` erkennt Szenarien an einer Zeile, die mit der ID beginnt (z. B. `### PBT-01` oder `- **PBT-01**`), und Tests am Docstring, der mit der ID beginnt. Das Format des Szenario-Dokuments legt Prompt 2 nicht genauer fest.
- `run_pbt.py` ordnet Szenario-IDs über die Assertion-Meldung und, falls dort keine steht, über den Docstring im Testcode zu. Die Quelldatei wird aus dem JUnit-Klassennamen relativ zum aktuellen Verzeichnis abgeleitet. Bei ungewöhnlichen Projektlayouts erscheint „ohne ID“.
- Wenn `pbt-tests-reparieren` fehlende, doppelte oder unbekannte Szenario-IDs findet, nimmt es sie in den Bericht auf und schreibt keine neuen Tests.
