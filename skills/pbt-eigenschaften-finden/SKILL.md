---
name: pbt-eigenschaften-finden
description: Heuristiken zum Formulieren von Eigenschaften (Property-Based Testing) und metamorphen Relationen (Metamorphic Testing) aus Requirements - vier Muster, MT-Transformationen, Grenzfälle. Verwenden, wenn jemand Eigenschaften oder metamorphe Relationen von Hand formuliert oder prüft. Nicht zum Schreiben von Testcode oder für das Format des Szenario-Dokuments, dafür gibt es pbt-hypothesis-konventionen.
---

# Eigenschaften und metamorphe Relationen finden

Du hilfst dabei, aus Requirements testbare Eigenschaften (PBT) und metamorphe Relationen (MT) abzuleiten. Jede Eigenschaft muss aus den Requirements oder aus Antworten des Nutzers folgen.

Das Format, in dem Szenarien festgehalten werden (IDs, Felder, Gliederung), steht in `../pbt-hypothesis-konventionen/references/szenario-format.md`. Lies die Datei, wenn der Nutzer Szenarien als Dokument aufschreiben will.

## Heuristiken

- Nutze diese vier Muster: Modellierung (eine sehr einfache Referenzimplementierung), Verallgemeinerung von Beispielen aus den Requirements, Invarianten (Teilaspekte, die immer gelten müssen) und Symmetrie (Round-Trip, Umkehroperation).
- Bevorzuge Eigenschaften ohne vollständige Modellimplementierung: Invarianten, Round-Trip, Idempotenz, Monotonie, Erhaltung von Elementen oder Mengen.
- Prüfe für MT systematisch diese Eingabetransformationen: additiv, multiplikativ, permutativ, invertierend (Negation, Kehrwert, umgekehrte Reihenfolge), inklusiv (etwas hinzufügen) und exklusiv (etwas entfernen). Nimm nur die auf, für die sich eine Relation aus den Requirements ergibt.
- Achte auf Grenzfälle: leere Eingaben, Extremwerte, Kalendergrenzen, Sonderzeichen, Groß- und Kleinschreibung, Duplikate.
- Jede Eigenschaft muss aus den Requirements oder den Antworten des Nutzers folgen. Vermeide Duplikate und triviale Szenarien, die nur ein einzelnes Beispiel prüfen.
