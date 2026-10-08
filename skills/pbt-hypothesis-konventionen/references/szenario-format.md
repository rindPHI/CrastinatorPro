# Format des Szenario-Dokuments

Markdown auf Deutsch, Bezeichner im Original. Gliederung:

1. Property-Based Testing
   1.1 Zustandslos
   1.2 Zustandsbehaftet
   1.3 Nicht-funktional
   1.4 KI-Funktionen
2. Metamorphic Testing (gleiche Unterteilung wie bei 1)
3. Nicht abgedeckte Requirements (je Requirement eine Zeile mit Begründung)

Abschnitte ohne Inhalt entfallen. Jedes Szenario ist ein Block mit einer festen ID: PBT-01, PBT-02, ... bzw. MT-01, MT-02, ... IDs bleiben über alle Runden stabil. Gestrichene IDs werden nicht neu vergeben.

PBT-Szenario:

- Getestete Funktion(en):
- Requirements: (ID, Abschnittsname oder kurzes Zitat, je nachdem, was die Requirements hergeben)
- Herkunft: Requirements, Nutzer oder beides
- Eingaben: Wertebereiche, Vorbedingungen und wichtige Grenzfälle, sprachunabhängig beschrieben. Bei zustandsbehafteten Szenarien: Operationen, ihre Vorbedingungen und das Modell des Zustands.
- Eigenschaft: was für alle gültigen Eingaben gelten muss.

MT-Szenario:

- Getestete Funktion(en):
- Requirements:
- Herkunft:
- Ausgangseingabe: Eigenschaften der ersten Eingabe.
- Transformation: wie daraus die Folgeeingabe(n) entstehen und wie viele.
- Relation: welche Beziehung zwischen den Ausgaben gelten muss, bei KI-Funktionen auch, wie verglichen wird.

Optional pro Szenario:

- Offen: (nur in Entwürfen)
- Annahme: (nur im finalen Dokument)

Keine Tabellen. Knapp und sachlich, ohne Einleitung und ohne Zusammenfassung im Dokument.
