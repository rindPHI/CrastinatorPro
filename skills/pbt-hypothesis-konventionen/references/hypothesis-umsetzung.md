# Umsetzung mit Hypothesis und Codestil

## Umsetzung mit Hypothesis

- Ein Szenario wird zu genau einem Test bzw. einer Zustandsmaschine. Der Docstring beginnt mit der Szenario-ID, gefolgt von einem Satz zur Eigenschaft. Jede Assertion hat eine Meldung, die die Szenario-ID enthält.
- Generatoren: Lege wiederverwendbare Strategien in strategies.py ab, aufgebaut mit st.builds, st.composite und den Basis-Strategien. Erzeuge gültige Eingaben möglichst konstruktiv aus den dokumentierten Vorbedingungen. Nutze filter und assume nur sparsam, damit Hypothesis nicht zu viele Beispiele verwirft. Decke die Grenzfälle aus den Szenarien ab, z. B. leere Listen, leere Strings, Extremwerte und Kalendergrenzen.
- Eigene Generatoren bindest du in strategies.py als Hypothesis-Strategie ein, sodass Tests sie wie jede andere Strategie verwenden. Behalte für jeden betroffenen Datentyp zusätzlich eine Standard-Hypothesis-Strategie, die per Konstante oder Umgebungsvariable gewählt werden kann.
- Isolation: Erzeuge für jedes Beispiel eine frische Instanz des getesteten Systems innerhalb des Tests. Verwende dafür keine function-scoped pytest-Fixtures zusammen mit @given, denn diese werden nicht pro Beispiel neu erzeugt.
- Determinismus: Bietet die API eine injizierbare Uhrzeit, Zufallsquelle oder Ähnliches an, setze sie im Test fest oder generiere sie mit. Verwende im Test nicht die aktuelle Systemzeit, außer die API lässt keine andere Wahl.
- Zustandsbehaftete Szenarien: Verwende RuleBasedStateMachine mit initialize, rule, precondition, invariant und Bundles. Führe ein einfaches Modell des Zustands in der Maschine mit und vergleiche es mit dem System. Erzeuge die Testklasse mit TestXyz = XyzMachine.TestCase.
- MT-Szenarien: Generiere die Ausgangseingabe mit @given, leite die Folgeeingabe(n) im Test über eine eigene, benannte Transformationsfunktion ab, führe das System für alle Eingaben aus und prüfe die Relation. Ist die Relation eine Ordnung oder Teilmengenbeziehung, prüfe genau diese, nicht Gleichheit.
- Nicht-funktionale Szenarien, z. B. Laufzeit: Setze sie nicht als Hypothesis-Schleife mit deadline um. Miss über mehrere feste Eingabegrößen jeweils den Median aus mehreren Wiederholungen und prüfe die Relation mit einer großzügigen Toleranz. Markiere sie mit @pytest.mark.performance.
- KI-Funktionen: Markiere sie mit @pytest.mark.ai. Halte dich bei der Bewertung an das im Szenario genannte Vergleichsverfahren. Ist ein Scorer oder LLM-as-a-Judge nötig, kapsle ihn in einer eigenen Hilfsfunktion, damit er austauschbar ist.
- Einstellungen: Registriere in conftest.py die Hypothesis-Profile und die pytest-Marker. Unterdrücke Health Checks nur gezielt und mit Kommentar, warum.

Zusätzlich gilt beim Umsetzen von Szenarien: Setze jede Eigenschaft und Relation so um, wie sie im Szenario steht. Schwäche sie nicht ab, verschärfe sie nicht und ergänze keine eigenen Erwartungswerte. Steht im Szenario eine Zeile "Annahme:", übernimm sie als Kommentar im Test.

## Codestil

- Python 3, kompatibel mit der in der API-Dokumentation genannten Version. Bezeichner und Kommentare auf Englisch.
- Typannotationen, kurze Hilfsfunktionen statt verschachtelter Logik, keine toten Importe.
- Kein Code, der fachliches Verhalten nachbaut, außer ein Szenario verlangt ausdrücklich ein einfaches Referenzmodell.
