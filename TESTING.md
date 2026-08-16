# Testen ohne den produktiven Skill zu beeinträchtigen

## Hintergrund

Der Skill läuft produktiv in der **Development-Version** der Alexa Developer
Console (kostenfrei, ausschließlich für private Zwecke). Das bedeutet:

- Änderungen am Interaction Model („Build Model") wirken **sofort** auf den
  produktiven Skill.
- Code-Deploys auf die Lambda-Funktion wirken ebenfalls sofort.

Es gibt also **keine Trennung** zwischen „Test" und „Produktion" innerhalb
eines einzelnen Skills. Um neue Funktionen gefahrlos auszuprobieren, wird ein
**separater Test-Skill** mit eigenem Invocation Name angelegt. Der produktive
Skill bleibt dabei vollständig unberührt.

## Voraussetzungen

- Amazon Developer Account (Zugang zur [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask))
- Optional: [ASK CLI](https://developer.amazon.com/en-US/docs/alexa/ask-toolkit/get-started-with-the-ask-cli.html) für die Verwaltung per Kommandozeile
- Optional: `ngrok` + `@ask-sdk-local-debug`, falls die Lambda lokal laufen soll

## Schritt 1: Test-Skill anlegen

1. In der Dev Console auf **„Create Skill"** klicken.
2. Name: z. B. **„Mein Plex Test"**.
3. **Invocation Name: zwingend anders** als beim produktiven Skill, z. B.
   **„Plex Test"**. Zwei Skills mit demselben Invocation Name können nicht
   parallel aktiv sein und kollidieren bei der Spracherkennung.
4. Modell: **Custom**, Hosting: je nach gewählter Backend-Variante (siehe
   Schritt 3).

## Schritt 2: Interaction Model übernehmen

Die Interaction Models liegen versioniert im Repo unter
`skill-package/interactionModels/custom/` (z. B. `de-DE.json`).

**Variante A – ASK CLI (empfohlen):**

```bash
ask deploy
```

**Variante B – Console (JSON-Editor):**

1. Im Test-Skill unter **„Interaction Model" → „JSON Editor"** den Inhalt der
   gewünschten Locale-Datei einfügen.
2. **„Save Model"** klicken.
3. **„Build Model"** klicken (dauert ca. 30 Sekunden). Erst danach werden die
   neuen Intents und Samples erkannt.

> Der Build betrifft **nur den Test-Skill** – der produktive Skill bleibt
> unverändert.

## Schritt 3: Backend (Lambda)

| Variante | Code-Trennung | Aufwand |
|---|---|---|
| **A: Zweite Lambda** (`askplex-dev`) | ✅ Vollständig | Mittel |
| **B: Lokal + ngrok** (`@ask-sdk-local-debug`) | ✅ Vollständig | Mittel |
| **C: Dieselbe Lambda** | ❌ Code wirkt sofort produktiv | Gering |

Für das Testen neuer Funktionalität kommen nur **A** oder **B** in Frage.

> **Hinweis (Alexa-hosted):** Wird der Skill direkt als **Alexa-hosted Skill
> aus dem Git-Repo importiert** (Skill-Package-Format, siehe README), entfällt
> die eigene Lambda. Änderungen landen dann über den **Code-Editor** der
> Konsole (Git-Sync + **Deploy**-Button) in der verwalteten Lambda; danach im
> **Test-Tab** prüfen. Der Skill-Code liegt im Repo unter `lambda/`, das
> Manifest unter `skill-package/`.

### Variante A: Zweite Lambda-Funktion

1. In AWS eine neue Lambda-Funktion **`askplex-dev`** anlegen (gleiche Runtime
   wie die produktive Funktion).
2. Den Code aus `lambda/` deployen (inkl. `requirements.txt`).
3. **Wichtig:** Eine **eigene DynamoDB-Tabelle** verwenden
   (Env-Var `DYNAMODB_PERSISTENCE_TABLE_NAME` auf eine neue Tabelle setzen).
   Der Skill speichert den Playlist-Zustand (aktuelle Playlist, Index,
   Shuffle) persistent – teilen sich beide Skills eine Tabelle, überschreiben
   sie sich gegenseitig den Zustand.

### Variante B: Lokal + ngrok

1. `@ask-sdk-local-debug` installieren und die Lambda lokal starten.
2. Mit `ngrok http <port>` einen öffentlichen HTTPS-Endpoint erzeugen.
3. Diesen Endpoint im Test-Skill als Endpoint eintragen.

## Schritt 4: Endpoint verknüpfen

Im Test-Skill unter **„Endpoint"** die ARN der Test-Lambda (Variante A) bzw.
den ngrok-URL (Variante B) eintragen.

## Schritt 5: Testen

1. Im Test-Skill den **Test-Tab** öffnen.
2. Oben die Locale **de-DE** auswählen.
3. Entweder per **Text** eingeben (z. B. „Spiele das Lied X von Y") oder die
   **Voice-Simulation** nutzen.
4. Im **JSON-Request/Response**-Panel die Slot-Erkennung und die Antwort
   prüfen.

## Wichtige Hinweise

- **DynamoDB-Tabelle trennen** (siehe Schritt 3) – sonst teilen sich Test- und
  produktiver Skill den Playlist-Zustand.
- **Plex-Zugriff:** Beide Skills können denselben Plex-Server nutzen
  (URL + Token in `config.py`). Plex erlaubt mehrere parallele Clients.
- **`config.py` ist versioniert (leere Vorlage):** Persönliche Werte (URL,
  Token, Bibliotheksname) werden lokal in `lambda/askplex/config.py`
  eingetragen bzw. nach dem Git-Import im **Code-Editor der Alexa-Konsole**
  gesetzt. Die versionierte Datei darf keine echten Zugangsdaten enthalten –
  sie wird bei `git pull`/`git checkout` mit der Vorlage überschrieben.
- **Spracherkennung (NLU) kann lokal nicht simuliert werden** – die
  Slot-Erkennung passiert server-seitig bei Amazon. Deshalb ist der Test-Tab
  der Dev Console der richtige Ort, um neue deutsche Samples zu prüfen.

## Workflow-Zusammenfassung

1. Änderungen im Repo entwickeln (Code + Interaction Model).
2. In den **Test-Skill** deployen (Model bauen, Code auf `askplex-dev`).
3. Im Test-Tab (Locale de-DE) ausprobieren.
4. Erst wenn alles passt: Änderungen in den **produktiven Skill** übernehmen.