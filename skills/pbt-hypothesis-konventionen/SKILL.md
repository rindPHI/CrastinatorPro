---
name: pbt-hypothesis-konventionen
description: Konventionen für Property-Based und Metamorphic Tests mit Python, pytest und Hypothesis - Standardnamen (blackbox_api.md, eigenschaften.md, tests/pbt), Umsetzung von Szenarien in Hypothesis-Tests, Codestil, Format des Szenario-Dokuments und das Skript run_pbt.py zum kompakten Auswerten von Testläufen. Verwenden beim Schreiben oder Einordnen von Hypothesis-Tests von Hand und als Grundlage für pbt-tests-reparieren und pbt-code-reparieren. Zum Finden von Eigenschaften siehe pbt-eigenschaften-finden.
---

# Hypothesis-Konventionen für PBT und MT

Dieser Skill legt Standardnamen und Konventionen für Tests fest, die aus Szenarien (PBT-NN, MT-NN) mit pytest und Hypothesis entstehen. Er gilt für Tests, die von Hand geschrieben werden, und als gemeinsame Grundlage der Skills pbt-tests-reparieren und pbt-code-reparieren.

## Standardnamen

Diese Namen gelten, wenn der Nutzer nichts anderes angibt. Angaben des Nutzers, auch aus dem bisherigen Gespräch, haben Vorrang.

- Blackbox-API-Dokumentation: `blackbox_api.md` im Wurzelverzeichnis des Projekts.
- Szenario-Dokument mit den freigegebenen Eigenschaften: `eigenschaften.md`.
- Ordner der Tests: `tests/pbt`.
- Dateien in diesem Ordner: `conftest.py`, `strategies.py`, `test_pbt_stateless.py`, `test_pbt_stateful.py`, `test_mt.py`, `test_nonfunctional.py`, `test_ai.py`. Dateien ohne Inhalt entfallen.
- Hypothesis-Profile: 100 Beispiele pro Test für den normalen Lauf, 1000 für den gründlichen Lauf, umschaltbar über ein Hypothesis-Profil.
- Marker: `performance` für nicht-funktionale Tests, `ai` für KI-Funktionen.

Datenfluss: `blackbox_api.md` und die Requirements führen zu `eigenschaften.md`, daraus entstehen die Tests in `tests/pbt`.

## Referenzdateien

- `references/hypothesis-umsetzung.md`: Regeln zur Umsetzung von Szenarien als Hypothesis-Tests und zum Codestil. Lies sie, bevor du Tests schreibst, änderst oder einordnest, ob ein Test einen Szenario-Typ korrekt umsetzt (z. B. Isolation, Zustandsmaschine, MT-Relation).
- `references/szenario-format.md`: Format des Szenario-Dokuments (Gliederung, IDs, Felder). Lies sie, wenn du ein Szenario-Dokument liest, schreibst oder prüfst.

## Skript run_pbt.py

`scripts/run_pbt.py` führt pytest aus und gibt je Fehlschlag kompakt Szenario-ID, Testname, Fehlerart und das minimale Gegenbeispiel von Hypothesis aus. Die Szenario-ID kommt aus der Assertion-Meldung bzw. dem Docstring des Tests.

```
python scripts/run_pbt.py [--runner "uv run pytest"] [--raw] [--] <pytest-Argumente>
python scripts/run_pbt.py --help
```

Der Pfad ist relativ zu diesem Skill-Ordner. Der Exit-Code ist der von pytest, bei Fehlschlägen also ungleich null. Nutze das Skript für Testläufe, statt pytest-Rohausgaben zu lesen. Mit `--raw` wird zusätzlich die vollständige pytest-Ausgabe gezeigt.
