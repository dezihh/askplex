# AskPlex

AskPlex ist ein Alexa-Skill, mit dem du Musik von deinem Plex Media Server (PMS) abspielen kannst.
Der offizielle Plex-Skill ist nicht in allen Regionen verfügbar – dieser Skill dient als Alternative.

> ***Hinweis:*** AskPlex stellt keine Medieninhalte oder Quellen bereit. Du musst deine eigenen Inhalte von einem Plex Media Server bereitstellen. Das AskPlex-Projekt unterstützt keine Raubkopien oder anderweitig illegal beschafften Inhalte.

### Dokumentation
[AskPlex Wiki](https://github.com/andresponte/askplex/wiki)

### Einrichtung

1. Erstelle deine persönliche Konfiguration aus der Vorlage:

   ```bash
   cp lambda/askplex/config.example.py lambda/askplex/config.py
   ```

2. Trage die Daten deines Plex Media Servers in `lambda/askplex/config.py` ein
   (Server-URL, Token, Name der Musik-Bibliothek).

> `config.py` ist in der `.gitignore` ausgenommen und wird durch `git pull` oder
> `git checkout` niemals überschrieben. Nur `config.example.py` ist als Standardvorlage versioniert.

### Testen

In [TESTING.md](TESTING.md) wird beschrieben, wie du den Skill testen kannst,
ohne deine produktive Installation zu beeinträchtigen.

### Deterministische Künstlersuche

Die Suche wird deterministisch aufgelöst, statt blind den ersten Suchtreffer
zu übernehmen:

1. **Exakter Treffer** – die unveränderte Anfrage wird gesucht und nur akzeptiert,
   wenn sie exakt mit einem Plex-Namen übereinstimmt (Groß-/Kleinschreibung egal).
2. **Alias** – `lambda/askplex/search_aliases.json` bildet häufige Schreib- und
   Sprechvarianten auf den exakten Plex-Namen ab (z. B. `ACDC` / `AC DC` / `A C D C` →
   `AC/DC`, `pink` → `P!nk`).
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
(linke Seite: erwartete Schreib-/Sprechvariante, rechte Seite: exakter Name in Plex).

### Roadmap / Offene To-Dos

Ideen für zukünftige Verbesserungen (noch nicht umgesetzt):

- [ ] `de-DE`-Veröffentlichungsinformationen in `skill.json` ergänzen (Beschreibung,
      Beispielsätze, Name „Mein Plex"), damit der Skill für den deutschen Markt
      zertifiziert werden kann.
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
