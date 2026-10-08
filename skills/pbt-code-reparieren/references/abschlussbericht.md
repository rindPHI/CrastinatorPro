# Abschlussbericht

Gib am Ende im Chat aus:

- Ergebnis: welche Pflichttests grün sind und welche nicht, Anzahl der verbrauchten Iterationen.
- Je behobener Ursache: Szenario-ID(s), Ursache in einem Satz, Änderung in einem Satz mit betroffener Datei und Funktion.
- Nicht behobene Fehlschläge: Szenario-ID, Fehlerbild mit minimalem Gegenbeispiel, Grund, warum nicht behoben.
- Tests, die du für falsch hältst, mit Begründung.
- Instabile performance- und ai-Tests.
- Regressionen in der übrigen Testsuite gegenüber dem Ausgangszustand. Wenn es keine gibt, sage das ausdrücklich.
- Neue Abhängigkeiten, falls welche hinzugekommen sind.
- Leitplankenverstöße laut `guard_tests.py verify`, jede Abweichung einzeln. Wenn es keine gibt, sage das ausdrücklich.
