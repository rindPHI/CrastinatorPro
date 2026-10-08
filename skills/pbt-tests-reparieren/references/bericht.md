# Bericht und Abschlussübersicht

## Bericht vor der Zustimmung

Gib einen nummerierten Bericht aus. Je Befund:

- Nummer, Szenario-ID, Testname
- Klasse
- Fehlerbild in einem Satz, bei Hypothesis mit dem minimalen Gegenbeispiel
- Begründung der Einstufung in ein bis zwei Sätzen
- Bei Testfehlern: der geplante Diff
- Bei "Unklar": eine konkrete Frage mit Antwortvorschlag

Fasse mehrere Fehlschläge mit derselben Ursache zu einem Befund zusammen. Verändere vor der Zustimmung keine Datei.

Bitte am Ende um Zustimmung. Der Nutzer kann mit "ok" allen geplanten Änderungen zustimmen, mit z. B. "ok außer 3" einzelne ausnehmen und die Fragen zu unklaren Befunden mit z. B. "5: Bug" beantworten.

Die Befunde von check_scenario_ids.py (fehlende, doppelte, unbekannte IDs) stehen als eigener Abschnitt vor den nummerierten Befunden.

## Abschlussübersicht im Chat

Schließe mit einer Übersicht im Chat:

- welche Änderungen du am Testcode vorgenommen hast, je Szenario-ID in einem Satz,
- welche Befunde als Verdacht auf Bug verbleiben, je Szenario-ID mit Fehlerbild und minimalem Gegenbeispiel,
- ob die API-Dokumentation oder das Szenario-Dokument angepasst werden sollte und warum.
