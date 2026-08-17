# Mein Plex (Alexa-Skill)

**Mein Plex** ist ein Alexa-Skill, mit dem du Musik von deinem eigenen Plex
Media Server (PMS) abspielen kannst – per Sprache auf jedem Alexa-Gerät.

Dieses Projekt ist ein **eigenständiger deutscher Hard Fork von
[AskPlex](https://github.com/andresponte/askplex)**. Der Upstream wird nicht
mehr übernommen; stattdessen wird der Skill gezielt für deutsche Umgebungen
weiterentwickelt:

- **Deutsch zuerst:** Interaction Models, Sprachausgaben und Hilfe-Texte sind
  auf `de-DE` ausgelegt (weitere Locales bleiben als Vorlage erhalten).
- **Deterministische Suche:** Künstler, Songs, Alben und Playlists werden
  über eine stabile Auflösung gefunden (exakt → Alias → Vergleichsschlüssel),
  inkl. nummerierter Auswahl bei Mehrdeutigkeit – keine Zufallstreffer.
- **Robust gegen Alexa-Besonderheiten:** buchstabierte Namen
  (`a. b. c. d.` → `AB/CD`), Umlaute, Satzzeichen.

> ***Hinweis:*** Mein Plex stellt keine Medieninhalte oder Quellen bereit. Du
> musst deine eigenen Inhalte von einem Plex Media Server bereitstellen. Das
> Projekt unterstützt keine Raubkopien oder anderweitig illegal beschafften
> Inhalte.

### Einrichtung in der Alexa Developer Console

Der Skill wird als **Alexa-hosted Skill** direkt aus diesem Git-Repo
importiert. So richtest du ihn ein:

1. Öffne die [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
   und melde dich mit deinem Amazon-Dev-Konto an.
2. Klicke auf **Create Skill**.
3. **Skill name:** `Mein Plex` eingeben.
4. **Default language:** **German (Germany)** auswählen.
5. **Experience:** `Music & Audio` wählen (bei deutscher Sprache ist nur
   **Custom** als Modell verfügbar – genau das brauchen wir).
6. **Hosting:** **Alexa-Hosted (Python)** wählen.
7. **Import skill** klicken und die Repo-URL angeben:
   `https://github.com/dezihh/askplex` – **Language: German**.
   Amazon klont das Repo und legt die Skill-Ressourcen an.
8. **Invocation Name prüfen (wichtig!):** Der Invocation Name muss **aus
   zwei Wörtern bestehen** (`mein plex`) – mit nur einem Wort startet der
   Skill nicht. Unter *Interaction Model → Build* den Invocation Name
   bestätigen und **Build Model** klicken.
9. Im **Code**-Tab die Datei `lambda/askplex/config.py` öffnen und deine
   Plex-Zugangsdaten eintragen (siehe unten), dann **Deploy** klicken.

Danach kannst du den Skill im **Test**-Tab ausprobieren:
„Alexa, starte Mein Plex" bzw. „spiele Musik von … auf Mein Plex".

#### Woher kommen die Plex-Zugangsdaten?

In `config.py` werden drei Werte benötigt:

- **`PMS_SERVER_URL`** – die Adresse, unter der dein Plex Media Server erreichbar
  ist (z. B. `http://192.168.1.10:32400` im Heimnetz oder
  `https://plex.example.com` hinter einem Reverse-Proxy). Den genauen Wert
  findest du in Plex unter *Settings → Server → Allgemein → „Konnektivität"*
  bzw. in der Plex Web App in der Adressleiste, wenn du Musik abspielst.
  **Wichtig:** Alexa verlangt für die Wiedergabe **HTTPS**-Streams – ein
  reines `http://` im Heimnetz funktioniert nur eingeschränkt. Am
  zuverlässigsten ist eine öffentlich erreichbare `https://`-Adresse
  (z. B. über Plex Remote Access oder einen Reverse-Proxy mit gültigem
  Zertifikat).
- **`PMS_SERVER_TOKEN`** – ein **Authentifizierungs-Token** (auch
  `X-Plex-Token` genannt). Es wird **nicht angezeigt**, sondern muss aus der
  Plex Web App **extrahiert** werden (offizielle Methode von Plex):
  1. Melde dich in der [Plex Web App](https://app.plex.tv) mit deinem
     Plex-Konto an.
  2. Öffne einen Eintrag aus deiner Musik-Bibliothek und klicke auf das
     Menü **„…" → „Get Info" / „Info anzeigen" → „View XML"** (bzw. öffne
     das XML des Eintrags).
  3. In der URL des XML siehst du den Parameter `X-Plex-Token=…` – genau
     diesen Wert trägst du als `PMS_SERVER_TOKEN` ein.
  - Hinweis: Dieser Token ist an dein Plex-Konto gebunden und bleibt gültig,
    bis du das Passwort änderst bzw. alle Geräte abmeldest. Er ist geheim –
    niemals teilen oder in das Git-Repo committen.
- **`PMS_DEFAULT_SECTION_NAME`** – der Name deiner Musik-Bibliothek in Plex,
  z. B. `Musik`. Du findest ihn in Plex unter *Einstellungen → Server →
  Bibliotheken* bzw. als Namen der Bibliothek in der Plex Web App.

### Konfiguration (Plex-Zugangsdaten)

Das Repo verwendet das **Skill-Package-Format** (Manifest + Interaction
Models unter `skill-package/`, Lambda-Code unter `lambda/`) – das von Amazon
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

### CloudWatch-Logs (How-to)

Die Lambda-Logs des Alexa-hosted Skills liegen in Amazon CloudWatch – so
erreichst du sie:

1. [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
   öffnen und in der Skill-Liste auf **„Mein Plex"** klicken.
2. Den **Code**-Tab öffnen.
3. In der Toolbar auf den **Pfeil neben dem Logs-Icon** klicken und die Region
   wählen – für dieses Projekt ist das **eu-west-1 (Irland)**.
4. Die AWS-Konsole öffnet sich (Login über das Skill-Konto, nicht über ein
   privates AWS-Konto). In der Log-Gruppe der Skill-Lambda erscheinen die
   Logs, sobald der Skill im **Test**-Tab oder auf einem Gerät genutzt wird.

Hinweise:

- **`cloudwatch:GetMetricData`-Fehler sind harmlos** – die Metrik-Grafiken
  oben sind mit der Skill-Rolle nicht abrufbar, die Log-Events funktionieren
  trotzdem.
- **Unsichtbarer Text:** Dunkler Text auf dunklem Grund ist ein Theme-Problem –
  unten links auf das Zahnrad klicken und das **Theme auf „Light"** stellen.
- **Diagnose-Zeilen:** Der Skill loggt die gewählte Stream-Strategie, z. B.
  `Stream: Datei-Endpoint fuer Container 'mp3': https://...` (Originaldatei
  mit Content-Length) oder `Stream: HLS-Fallback (Container: ...): https://...`.
  Das Plex-Token ist in den Log-Zeilen maskiert (`X-Plex-Token=***`).
- **Deploy:** Nach einem `git push` ggf. im Code-Tab einmal **Deploy** klicken,
  da der automatische Deploy nicht immer sofort greift.

### Anzeige auf Geräten mit Bildschirm

Auf Echo-Geräten mit Display (z. B. Echo Show) zeigt Alexa für den
AudioPlayer nur **zwei Textzeilen** an: Titel und Untertitel. Der Skill nutzt
das wie folgt:

- **Titel:** `Songtitel (4:52)` – die Dauer wird in Klammern angehängt,
  sofern Plex sie kennt (sonst nur der Songtitel). Die Echo-Anzeige zeigt
  sonst keine Laufzeit an, da Alexa sie bei Plex-Streams nicht selbst
  ermittelt.
- **Untertitel:** `Künstler • Album` – vorhandene Teile werden kombiniert,
  fehlende entfallen.
- **Album-Cover** wird als Artwork eingeblendet, sofern verfügbar.

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
   und `a. b. c. d.` ab; `acdc` → `AC/DC` fängt die Alexa-Buchstabierung
   `a. c. d. c.` ab; `pink` → `P!nk`).
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

- [ ] **Zeitanzeige/Fortschrittsbalken auf Echo-Geräten** – Diagnose-Stand:
      Server liefert `Content-Length` + Range korrekt, Dateien sind CBR mit
      bekannter Dauer, Alexa zeigt trotzdem einen Live-/Streaming-Balken ohne
      Zeitangabe. Nächster Schritt: S3-Isolationstest mit statischer MP3
      (Zwischenschritt, kein eigenes To-Do).
- [ ] **Sterne-Wiedergabe (`PlayMusicByRating`)** – „spiele meine 4-Sterne-Songs":
      Plex übernimmt das Rating aus den MP3-Tags als `userRating` (intern 0–10,
      5 Sterne = 10), Filter `userRating >= sterns*2`, sortiert nach Rating.
- [ ] **Mood-Wiedergabe (`PlayMusicByMood`)** – „spiele fröhliche Musik": Filter
      `mood=` auf den in den MP3-Dateien gepflegten Mood-Tags (Plex liest den
      ID3-Tag `TMOO`; ohne gepflegte Tags liefert die Suche keine Treffer).
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

Dieser Skill ist ein **Hard Fork von
[AskPlex](https://github.com/andresponte/askplex)**, das wiederum von
[AskNavidrome](https://github.com/rosskouk/asknavidrome) inspiriert wurde.
Vielen Dank an beide Projekte für die Grundlage.
