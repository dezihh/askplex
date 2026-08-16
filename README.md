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

1. Erstelle deine persönliche Konfiguration aus der Vorlage:

   ```bash
   cp lambda/askplex/config_example.py lambda/askplex/config.py
   ```

2. Trage die Daten deines Plex Media Servers in `lambda/askplex/config.py` ein
   (Server-URL, Token, Name der Musik-Bibliothek).

> `config.py` ist in der `.gitignore` ausgenommen (enthält sensible
> Zugangsdaten wie den Plex-Token) und wird durch `git pull`/`git checkout`
> niemals überschrieben. Nur `config_example.py` ist als Standardvorlage
> versioniert. Beim Alexa-hosted Import (ohne `config.py` im Repo) fällt der
> Code automatisch auf die leere Vorlage zurück – die echten Werte trägst du
> dann im Code-Editor der Alexa-Konsole ein.

3. **Import in der Alexa-Konsole:** *Create Skill* → *Custom* →
   *Alexa-Hosted (Python)* → *Import skill* → Git-Repo-URL angeben. Danach im
   Code-Editor `config.py` befüllen, **Deploy** drücken und unter
   *Interaction Model* → **Build Model** den Invocation Name (`mein plex`)
   bauen lassen.

### Automatisches Deploy per Push (ASK CLI / GitHub Actions)

> **Status:** Dieses Repo ist an den Alexa-Skill **„Mein Plex"** (Alexa-hosted)
> angebunden. Ein Push auf `main` deployed automatisch in die Development-Stage
> des Skills (GitHub Action „Deploy to Alexa").

Bei Alexa-hosted Skills läuft der Deploy **nicht** über `ask deploy`,
sondern über einen `git push` auf den `master`-Branch des von Amazon
verwalteten Repos (entspricht dem **Deploy**-Button im Code-Tab). Das Repo
enthält dafür eine [GitHub Action](.github/workflows/deploy-alexa.yml), die
bei jedem Push auf `main` automatisch in das Alexa-Repo deployed.

**Einmalige Einrichtung:**

1. **ASK CLI authentifizieren** (erzeugt `~/.ask/ask_cli_config` mit den
   OAuth-Tokens, Browser-Login erforderlich):

   ```bash
   npm install -g ask-cli
   ask configure
   ```

2. **Skill-ID und Alexa-Repo-URL ermitteln:**

   ```bash
   ask init --hosted-skill-id <deine-skill-id>
   git -C <skill-verzeichnis> remote get-url origin
   ```

   Die Skill-ID steht im Test-Tab der Konsole (z. B.
   `amzn1.ask.skill.fbcd5041-...`); die URL ist das von Amazon verwaltete
   Git-Repo des Skills.

3. **GitHub-Secrets hinterlegen** (Repo → *Settings* → *Secrets and
   variables* → *Actions*):

   | Secret | Inhalt |
   |---|---|
   | `ASK_AUTH_INFO` | `base64 -w0 ~/.ask/auth_info` (LWA-API-Zugangsdaten) |
   | `ASK_CLI_CONFIG` | `base64 -w0 ~/.ask/cli_config` (OAuth-Tokens) |
   | `ALEXA_HOSTED_REPO_URL` | Git-URL des Alexa-Repos (Schritt 2) |

   Die Helper-Skripte (`git-credential-helper`, `ask-pre-push`) sind im Repo
   unter `.github/ask/` versioniert und werden von der Action automatisch
   eingesetzt. Die drei Secrets enthalten die echten Zugangsdaten und dürfen
   niemals committet werden.

4. Ab jetzt deployt jeder Push auf `main` automatisch in die
   Development-Stage deines Alexa-Skills (entspricht *Deploy* im Code-Tab).
   Für Tests kann die Action auch manuell über *Actions* →
   *Deploy to Alexa* → *Run workflow* angestoßen werden.

> **Hinweis:** Der Push auf `master` des Alexa-Repos aktualisiert die
> Development-Stage. Für *live* (veröffentlicht) muss zusätzlich
> `master` → `prod` gemerged werden – das entspricht dem **Promote to
> live**-Button und ist für den privaten Testbetrieb nicht nötig.

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
Bump
