# Inhalt und Aufbau der Blackbox-API-Dokumentation

## Was in die Dokumentation gehört

- Programmiersprache und Version, soweit aus der Projektkonfiguration ersichtlich, sowie die Abhängigkeiten, die ein Test zum Ausführen braucht.
- Import-Pfade bzw. Einbindung, exakt so, wie eine Testdatei sie verwenden würde.
- Erzeugung und Setup: Konstruktoren, Fabrikfunktionen, Konfiguration, benötigte Umgebungsvariablen, injizierbare Abhängigkeiten wie Uhrzeit, Zufall oder externe Dienste, und wie man eine frische, unabhängige Instanz erhält.
- Öffentliche Funktionen und Methoden mit vollständiger Signatur: Parameter, Typen, Standardwerte, Rückgabetyp.
- Öffentliche Datentypen (Klassen, Datenklassen, Records, Structs, Enums) mit Feldern, Typen, optionalen Feldern und erlaubten Werten.
- Vorbedingungen an Eingaben, die dokumentiert sind oder an der Schnittstelle geprüft werden, z. B. Pflichtfelder oder Wertebereiche.
- Fehler und Exceptions, die zum Vertrag gehören: welcher Typ bei welcher Art von ungültiger Eingabe.
- Ob ein Aufruf den Zustand eines Objekts verändert oder nur liest.
- Bei Dateiformaten und externen Schnittstellen (z. B. Import, Export, REST, CLI): die Struktur der Ein- und Ausgaben, soweit sie nötig ist, um gültige Eingaben zu erzeugen und Ausgaben zu lesen.
- Pro Funktion bzw. Methode genau ein Satz zum Zweck, formuliert als Absicht aus Sicht eines Aufrufers.

## Was nicht in die Dokumentation gehört

- Private oder interne Funktionen, Methoden, Klassen und Hilfsfunktionen, auch wenn sie technisch erreichbar sind.
- Algorithmen, verwendete Datenstrukturen, interne Konstanten und Grenzwerte, Caching und Optimierungen.
- Implementierungskommentare, TODOs und bekannte Probleme.
- Jede Beschreibung von Verhalten, die du aus dem Code abliest statt aus Namen, Typen oder Docstrings, z. B. wie sortiert, gerundet, gefiltert oder berechnet wird.
- Details aus Docstrings, die beschreiben, wie ein Ergebnis zustande kommt. Übernimm daraus nur die Absicht. Ein Docstring kann das tatsächliche statt des gewollten Verhaltens beschreiben und so einen Fehler weitergeben.
- Bewertungen der Codequalität und Hinweise auf vermutete Fehler.

Im Zweifel lass eine Information weg. Leitfrage: Brauche ich diese Information, um die Funktion korrekt aufzurufen und ihr Ergebnis zu verarbeiten? Wenn nein, gehört sie nicht hinein.

## Aufbau der Datei

Schreibe Markdown auf Deutsch. Bezeichner und Code bleiben im Original. Verwende diese Gliederung:

1. Überblick: zwei bis drei Sätze dazu, was das System aus Nutzersicht tut, nur auf Basis öffentlicher Namen und Dokumentation.
2. Umgebung und Setup
3. Datentypen
4. API: je Modul oder Klasse ein Unterabschnitt. Je Funktion: Signatur als Codeblock, Zweck, Parameter, Rückgabe, Vorbedingungen, Fehler, Zustand.
5. Minimales Aufrufbeispiel: ein kurzer Codeblock, der eine Instanz erzeugt und zwei bis drei typische Aufrufe zeigt, ohne Erwartungswerte und ohne Assertions.

Abschnitte ohne Inhalt entfallen. Keine Einleitung, kein Fazit, keine Verweise auf Quelldateien oder Zeilennummern außer Import-Pfaden.
