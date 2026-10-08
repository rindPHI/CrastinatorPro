---
name: pbt-code-reparieren
description: Repariert Produktivcode autonom und ohne Rückfragen, bis die vorhandenen PBT-/MT-Tests grün sind, ohne Testdateien zu verändern. Nur explizit per /pbt-code-reparieren aufrufen, nie automatisch. Zum Reparieren fehlerhafter oder nicht laufender Tests nicht verwenden, dafür gibt es pbt-tests-reparieren.
disable-model-invocation: true
---

# Produktivcode reparieren, bis die PBT-/MT-Tests grün sind

Du bist erfahrener Python-Entwickler mit Erfahrung in Property-Based Testing (PBT) und Metamorphic Testing (MT) mit pytest und Hypothesis. In diesem Projekt gibt es PBT- und MT-Tests, die aus freigegebenen Eigenschaften erzeugt und bereits geprüft wurden. Sie gelten als korrekt. Deine Aufgabe ist, den Produktivcode so zu reparieren, dass diese Tests grün werden, ohne bestehendes Verhalten kaputt zu machen. Du arbeitest selbstständig und stellst keine Rückfragen.

## Konventionen laden

Lade als Erstes den Skill pbt-hypothesis-konventionen mit dem Skill-Tool, bevor du Tests einordnest. Ist das Laden nicht möglich, lies `../pbt-hypothesis-konventionen/SKILL.md` und die dort genannten Referenzdateien direkt. Er legt die Standardnamen (blackbox_api.md, eigenschaften.md, tests/pbt) fest, enthält die Regeln zur Umsetzung von Hypothesis-Tests und das Skript `run_pbt.py`. Abweichende Angaben des Nutzers haben Vorrang.

## Eingaben

1. Die PBT- und MT-Testdateien bzw. der Testordner, meist tests/pbt.
2. Szenario-Dokument mit den freigegebenen Eigenschaften, meist eigenschaften.md. Die Tests verweisen über IDs wie PBT-01 oder MT-01 darauf.
3. Blackbox-API-Dokumentation, meist blackbox_api.md. Sie beschreibt die öffentliche Schnittstelle, die erhalten bleiben muss.
4. Optional: Requirements und die Befundübersicht aus der vorherigen Testreparatur, falls sie im Projekt oder im bisherigen Gesprächsverlauf vorliegen.
5. Die Befehle, mit denen die PBT- und MT-Tests und die übrige Testsuite laufen.

Suche alle Eingaben selbst im Projekt und im bisherigen Gesprächsverlauf. Fehlen die Tests, das Szenario-Dokument oder ein ausführbarer Testbefehl, beginne nicht und beende mit einem kurzen Bericht, was fehlt.

## Maßstab

Richtiges Verhalten legen das Szenario-Dokument und, soweit vorhanden, die Requirements fest. Die Tests setzen das um. Ein Fehlschlag bedeutet, dass der Produktivcode falsch ist, nicht der Test.

## Leitplanken

- Verändere keine Testdateien. Dazu gehören auch conftest.py, strategies.py, Hypothesis-Einstellungen, pytest-Konfiguration und die Hypothesis-Beispieldatenbank (.hypothesis). Lösche sie nicht und setze sie nicht zurück.
- Verändere nicht das Szenario-Dokument, die API-Dokumentation und die Requirements.
- Behalte die öffentliche Schnittstelle laut API-Dokumentation bei: Import-Pfade, Signaturen, Datentypen und vertragliche Exceptions.
- Behebe die Ursache, nicht das Symptom. Keine Sonderfälle, die nur die Eingaben aus Gegenbeispielen abfangen, keine Erkennung von Testläufen, keine fest eingebauten Ergebnisse.
- Füge keine neuen Abhängigkeiten hinzu, außer es geht nicht anders. Nenne sie dann im Abschlussbericht.
- Halte Änderungen so klein wie möglich und im Stil des bestehenden Codes.

## Vorgehen

0. Schutz der Tests: Rufe vor der ersten Änderung am Produktivcode `python scripts/guard_tests.py snapshot` auf (Pfad relativ zu diesem Skill-Ordner; im Projektwurzelverzeichnis ausführen, `--tests` setzt einen abweichenden Testordner, `--help` zeigt die Optionen). Rufe vor dem Abschlussbericht `python scripts/guard_tests.py verify` auf. Jede gemeldete Abweichung ist ein Leitplankenverstoß und kommt in den Abschlussbericht.1. Ausgangslage: Führe die übrige Testsuite und die PBT- und MT-Tests aus und notiere das Ergebnis. Nutze für die PBT- und MT-Tests `run_pbt.py` aus pbt-hypothesis-konventionen. Tests der übrigen Suite, die schon jetzt fehlschlagen, gelten als Ausgangszustand und nicht als Regression.
2. Ordne jeden Fehlschlag einer Szenario-ID zu. Fasse Fehlschläge mit derselben Ursache zusammen.
3. Arbeite die Ursachen nacheinander ab. Lies dazu das betroffene Szenario, das minimale Gegenbeispiel von Hypothesis und den relevanten Produktivcode. Repariere die Ursache und führe die betroffenen Tests erneut aus.
4. Eine Iteration besteht aus einer Änderung am Produktivcode und einem anschließenden Testlauf. Nach höchstens 10 Iterationen hörst du auf, auch wenn noch Tests fehlschlagen.
5. Sind alle Pflichttests grün, führe die gesamte Testsuite aus, um Regressionen zu erkennen. Führe die funktionalen PBT- und MT-Tests zusätzlich einmal mit dem gründlichen Hypothesis-Profil aus, falls es eines gibt. Tritt dabei ein neuer Fehlschlag auf, behandle ihn wie in Schritt 3, solange Iterationen übrig sind.
6. Prüfe mit `guard_tests.py verify` und gib den Abschlussbericht aus.

Lies `references/pflicht-kuer-abbruch.md`, wenn du entscheiden musst, welche Tests Pflicht sind, wie instabile Tests zu behandeln sind oder ob du abbrechen musst. Lies `references/abschlussbericht.md` vor dem Abschlussbericht.
