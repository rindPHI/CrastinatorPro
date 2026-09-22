# Crastinator Pro

*"Later is greater."*

Demo-Task-Management-Tool für einen Konferenzvortrag über Property-Based und
Metamorphic Testing. Der Zustand ist ausschließlich In-Memory (kein
Persistieren über einen Neustart hinweg) und es gibt drei fest hinterlegte
User: **Alice (1)**, **Bob (2)**, **Carol (3)**.

## Architektur

- `crastinator_pro/` – direkt importierbare Python-Bibliothek mit der
  gesamten Geschäftslogik (`TaskService`). Kein HTTP-Zwang: die Bibliothek
  kann ohne laufenden Server aus jedem Python-Skript genutzt werden.
  - `models.py` – Datenmodell (`User`, `Task`, `Priority`).
  - `service.py` – `TaskService`: CRUD, Sortierung/Filterung, +10, Auto-+10,
    CSV, KI-Anbindung.
  - `workdays.py` – Werktags-Arithmetik (Mo–Fr, Feiertage werden ignoriert).
  - `csv_io.py` – CSV-Export/-Import.
  - `ai.py` – austauschbare `AIProvider`-Abstraktion; mitgeliefert ist eine
    einfache, regelbasierte `KeywordAIProvider`.
  - `api.py` – FastAPI-Anwendung, ein dünner HTTP-Wrapper um `TaskService`.
- `frontend/` – statische HTML/JS-Oberfläche, die ausschließlich die REST-API
  konsumiert.
- `tests/` – pytest-Suite (Bibliothek + API).

Alle zeitabhängigen Funktionen (`plus_10`, Auto-+10, KI-Textanlage mit
relativen Datumsangaben wie "morgen") nehmen den Referenzzeitpunkt als
expliziten Parameter entgegen und greifen nicht implizit auf die Systemuhr
zu. Das ist Voraussetzung für deterministisches, property-based Testen.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Server starten

```bash
uvicorn crastinator_pro.api:app --reload
```

Die API läuft danach unter `http://127.0.0.1:8000/api/...`, das Frontend wird
unter `http://127.0.0.1:8000/` mit ausgeliefert (einfach im Browser öffnen).

## Tests ausführen

```bash
pytest
```

## Nutzung als Bibliothek (ohne HTTP)

```python
from datetime import datetime
from crastinator_pro import TaskService

service = TaskService()
task = service.create_task(title="Folien vorbereiten", assignee_user_id=1)
service.plus_10(task.id, reference_time=datetime.now())
```

## Beispiel-Requests (curl)

Task anlegen:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Folien vorbereiten", "dueDate": "2026-01-05", "assigneeUserId": 1, "priority": "high"}'
```

Taskliste sortiert nach Fälligkeitsdatum abrufen, nur offene Tasks von Alice:

```bash
curl "http://127.0.0.1:8000/api/tasks?sortBy=dueDate&order=asc&assigneeUserId=1&completed=false"
```

Task abhaken / löschen:

```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/1/toggle
curl -X DELETE http://127.0.0.1:8000/api/tasks/1
```

Zuweisung ändern (oder mit `"userId": null` entfernen):

```bash
curl -X PUT http://127.0.0.1:8000/api/tasks/1/assignee \
  -H "Content-Type: application/json" -d '{"userId": 2}'
```

Task um 10 Werktage verschieben:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/1/plus10
```

Auto-+10 aktivieren:

```bash
curl -X PUT http://127.0.0.1:8000/api/settings/auto-plus10 \
  -H "Content-Type: application/json" -d '{"enabled": true}'
```

CSV exportieren / importieren:

```bash
curl http://127.0.0.1:8000/api/tasks/export -o tasks.csv
curl -X POST http://127.0.0.1:8000/api/tasks/import -F "file=@tasks.csv"
```

KI-Assistent fragen:

```bash
curl -X POST http://127.0.0.1:8000/api/users/1/ask \
  -H "Content-Type: application/json" -d '{"question": "Wie viele Tasks sind offen?"}'
```

KI-gestützt Task anlegen:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/ai-create \
  -H "Content-Type: application/json" \
  -d '{"text": "Dringend: Bericht für Bob morgen schreiben"}'
```

## Bekannte Einschränkungen (bewusst, für diese Demo-Phase)

- Die Beispiel-Tests decken Happy-Path-Fälle und naheliegende Grenzfälle ab,
  nicht aber exotische Datumskombinationen (Monatsenden, Jahreswechsel,
  Feiertage, große Datenmengen). Diese Lücke wird im Talk gezielt durch
  Property-Based und Metamorphic Testing aufgedeckt.
- Feiertage werden bei der Werktagsberechnung nicht berücksichtigt.
- Der KI-Assistent ist keyword-/regelbasiert (austauschbare Abstraktion,
  siehe `crastinator_pro/ai.py`), keine Anbindung an ein echtes LLM.
