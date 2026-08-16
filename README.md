# AskPlex

AskPlex ist ein Alexa-Skill, mit dem du Musik von deinem Plex Media Server (PMS) abspielen kannst.
Der offizielle Plex-Skill ist nicht in allen Regionen verfügbar – dieser Skill dient als Alternative.

> ***Hinweis:*** AskPlex stellt keine Medieninhalte oder Quellen bereit. Du musst deine eigenen Inhalte von einem Plex Media Server bereitstellen. Das AskPlex-Projekt unterstützt keine Raubkopien oder anderweitig illegal beschafften Inhalte.

### Dokumentation
[AskPlex Wiki](https://github.com/andresponte/askplex/wiki)

### Einrichtung

Das Repo verwendet das **Skill-Package-Format** (Manifest + Interaction Models
unter `skill-package/`, Lambda-Code unter `lambda/`) – das von Amazon
dokumentierte Format für den Import aus einem Git-Repo als Alexa-hosted Skill.

1. `lambda/askplex/config.py` ist **versioniert** (leere Vorlage, wie das
   Original-Repo) und wird beim Import in die Alexa Console mitgezogen.
   Trage dort deine Daten ein (Server-URL, Token, Name der Musik-Bibliothek):

   ```bash
   cp lambda/askplex/config.example.py lambda/askplex/config.py
   ```

2. **Wichtig:** Beim Alexa-hosted Import musst du die Werte zusätzlich im
   **Code-Editor der Alexa Developer Console** eintragen – die lokale Datei
   wird bei `git pull`/`git checkout` mit der leeren Vorlage überschrieben.
   Enthält die versionierte `config.py` echte Zugangsdaten, niemals committen!

3. **Import in der Alexa-Konsole:** *Create Skill* → *Custom* →
   *Alexa-Hosted (Python)* → *Import skill* → Git-Repo-URL angeben. Danach im
   Code-Editor `config.py` befüllen, **Deploy** drücken und unter
   *Interaction Model* → **Build Model** den Invocation Name (`mein plex`)
   bauen lassen.

### Testen

In [TESTING.md](TESTING.md) wird beschrieben, wie du den Skill testen kannst,
ohne deine produktive Installation zu beeinträchtigen.

### Deterministische Künstlersuche

Die Suche wird deterministisch aufgelöst, statt blind den ersten Suchtreffer
zu übernehmen:

1. **Exakter Treffer** – die unveränderte Anfrage wird gesucht und nur akzeptiert,
   wenn sie exakt mit einem Plex-Namen übereinstimmt (Groß-/Kleinschreibung egal).
2. **Alias** – `lambda/askplex/search_aliases.json` bildet häufige Schreib- und
   Sprechvarianten auf den exakten Plex-Namen ab. Ein Eintrag wird am besten als
   **Vergleichsschlüssel** gepflegt, damit er möglichst viele Sprechvarianten
   abdeckt (z. B. `abcd` → `AB/CD` fängt `AB/CD`, `ABCD`, `A B C D`, `A.B.C.D.`
   und `a. b. c. d.` ab; `pink` → `P!nk`).
3. **Normalisierter Vergleichsschlüssel** – alle Plex-Künstler werden über einen
   deterministischen Schlüssel verglichen, der Groß-/Kleinschreibung, Satzzeichen
   und Leerzeichen ignoriert (`AC/DC`, `AC DC` und `A.C.D.C.` ergeben alle den
   Schlüssel `acdc`), während Umlaut-Varianten (`Die Ärzte` vs. `Die Aerzte`)
   unterscheidbar bleiben.

Wenn mehrere plausible Treffer existieren, bietet der Skill eine **nummerierte
Auswahl** an (z. B. „Sage Nummer eins oder Nummer zwei") und lädt den gewählten
Künstler über seine Plex-`ratingKey` – niemals über eine erneute Namenssuche.
Aufgerufen über den `SelectSearchResult`-Intent.

Grundsätze:

- Kein Fuzzy Matching und keine Ähnlichkeitsbewertung.
- Songs und Alben werden nur innerhalb des bereits aufgelösten Künstlers gesucht.
- Erfolgs- und Fehlermeldungen verwenden immer den tatsächlichen Plex-Namen,
  damit eine unerwartete Auflösung für den Nutzer hörbar bleibt.

Zum Pflegen der Aliase: `lambda/askplex/search_aliases.json` bearbeiten
(linke Seite: erwartete Schreib-/Sprechvariante bzw. Vergleichsschlüssel,
rechte Seite: exakter Name in Plex). Die zentrale Funktion
`search_aliases.find_alias()` prüft drei Schlüsselformen (Rohwert, normalisierte
Leerzeichen, Vergleichsschlüssel), sodass pro Spezialfall meist ein Eintrag
genügt – die Alias-Liste ist nur für Spezialfälle gedacht (z. B. Akronyme), der
Regelfall läuft über den Vergleichsschlüssel.

### Roadmap / Offene To-Dos

Ideen für zukünftige Verbesserungen (noch nicht umgesetzt):

- [ ] Neue Einzel-Intent-Shortcuts: Song ohne Künstler, Album ohne Künstler,
      Musik nach Jahrzehnt, zufällige Wiedergabe einer Playlist.
- [ ] Natürlichere deutsche Beispielsätze im Interaction Model
      (z. B. „Mach mal Musik", „Leg was von … auf").
- [ ] Warteschlangen-Funktionen: „Füge {song} zur Warteschlange hinzu",
      „Wie viele Songs sind noch übrig?", „Überspringe N Titel".
- [ ] Die Antwort auf „Was spielt gerade?" um Album, Jahr und Laufzeit erweitern
      (die Plex-API liefert diese Daten bereits).
- [ ] Weitere deutschspezifische Tests (Sonderzeichen, „ß", Ligaturen)
      über die aktuelle Umlaut- und Vergleichsschlüssel-Abdeckung hinaus.
- [ ] Weitere Feinschliffe an den deutschen Hilfe-/Fehlertexten in
      `lambda/askplex/language_strings.json`.

### Danksagung
Dieser Skill wurde von [AskNavidrome](https://github.com/rosskouk/asknavidrome) inspiriert.
