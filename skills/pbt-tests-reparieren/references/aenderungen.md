# Erlaubte und verbotene Änderungen am Testcode

## Erlaubte Änderungen

- Imports, Syntax, Aufrufe der API entsprechend der Dokumentation
- Nutzung von pytest und Hypothesis: Strategien, Zustandsmaschinen, Fixtures, Isolation zwischen Beispielen, Einstellungen
- Generatoren, die Eingaben erzeugen, die laut API-Dokumentation ungültig sind. Schränke sie konstruktiv auf gültige Eingaben ein und nenne die Vorbedingung in einem Kommentar.
- Gezieltes Unterdrücken eines einzelnen Health Checks, mit Kommentar, warum er hier nicht auf einen echten Fehler hinweist
- Nach einer Antwort des Nutzers zu einem unklaren Befund: genau die Änderung, die sich aus der Antwort ergibt, z. B. eine Generatoreinschränkung mit Kommentar und Verweis auf die Antwort

## Verbotene Änderungen

- Eigenschaften, Relationen, Assertions oder Toleranzen abschwächen, verschärfen, entfernen oder umformulieren, außer der Test weicht nachweislich vom Szenario-Dokument ab. Dann bringst du ihn wieder in Übereinstimmung mit dem Szenario und zitierst die betroffene Stelle im Bericht.
- Eingaben herausfiltern, an denen die Software scheitert, ohne dass die API-Dokumentation oder der Nutzer sie für ungültig erklärt
- Tests überspringen, als erwartet fehlschlagend markieren, auskommentieren oder löschen
- Die Zahl der Beispiele oder Wiederholungen senken, um einen Fehlschlag zu verbergen
- Erwartete Werte aus dem tatsächlichen Verhalten der Software übernehmen
- Änderungen am Produktivcode, am Szenario-Dokument oder an der API-Dokumentation
