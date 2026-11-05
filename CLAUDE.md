# Projekt: Jack (YouTube Shorts + TikTok, Zombie-Apokalypse und echte Vorsorge)

Diese Datei erklärt dir (Claude Code), worum es geht, welche Regeln gelten und wie die Pipeline funktioniert.
Lies sie vollständig, bevor du etwas baust oder änderst. Anleitung für Menschen: `README.md`. Verlauf: `log.md`.

## 1. Kanal

- **Format:** YouTube Shorts und TikTok, zunächst **30–90 Sekunden**, Hochformat 9:16.
- **Sprache:** Mit dem Nutzer Deutsch. Texte im Video (Sprechertext, Einblendungen, Untertitel) Deutsch.
  Bild- und Video-Prompts für Google Flow Englisch.
- **Konzept:** „Was wäre, wenn eine Zombie-Apokalypse ausbricht?“ Jack macht Fehler, ein trockener Erzähler
  kommentiert. **Jede Folge vermittelt echtes Vorsorge- oder Überlebenswissen.** Der Witz transportiert die Info.
- **Aufbau jeder Folge** (`teil` in thema.toml):
  1. `hook` – in den ersten 3 Sekunden
  2. `falscher_plan` – Jack ist stolz auf einen schlechten Plan
  3. `fakt` – echtes Wissen, mit Quelle
  4. `eskalation` – es wird schlimmer
  5. `schluss` – was richtig wäre, **endet mit einer Frage an die Zuschauer**
- **Wiedererkennung (Pflicht):** Einblendung **„Überlebenschance: X %“** in jedem Video und jeder Szene
  (`chance = 0-100`). Wird im Schnitt eingefügt, zählt am Szenenanfang zum neuen Wert, Farbe grün/gelb/rot.
- **Verboten:** Blut, drastische Gewalt, Markennamen, Logos.

## 2. Figur Jack (verbindlich)

Teenager, anthropomorpher Golden Retriever: schlanker menschlicher Körper, Hundekopf mit Schlappohren, goldenes
Fell, schwarze Nase, braune ausdrucksstarke Augen, menschlich geformte Hände mit Fell, langer buschiger Schwanz.
Trägt immer: dunkelrote College-Jacke mit weißen Ärmeln und rot-weiß gestreiften Bündchen, dunkelgraues T-Shirt,
Blue Jeans, weiße Sneaker, nie barfuß. Rolle: Jack ist nie schlau, ihm passiert das Chaos; der Sarkasmus kommt vom Erzähler.

## 3. Stil (verbindlich)

Kein 3D. 2D handgezeichnet, dunkler postapokalyptischer Comic-Stil, klare schwarze Konturen, flache Farben, weiche
Cel-Schattierung, detaillierte gemalte Hintergründe. Referenz: Bilder und Clips in `bibliothek/` (Katalog:
`bibliothek/katalog.md`, Vorschau `bibliothek/uebersicht.jpg`), Referenzbild für Flow:
`bibliothek/bilder/jack-observing-burning-city-4098f4a9-2k.jpg`.

## 4. Prompt-Vorlage für Flow (Quelle der Wahrheit: `bausteine/bausteine.toml` [flow])

```
Use the reference image for Jack's exact appearance. Vertical 9:16 2D hand-drawn animated scene in a dark post-apocalyptic comic style, with clean black outlines, flat colors, soft cel shading and detailed painted backgrounds.
Jack is a teenage anthropomorphic golden retriever with a slim human body, floppy ears, golden fur and a long fluffy tail. He always wears a dark red varsity jacket with white sleeves and red-white striped trim, a dark gray T-shirt, blue jeans and white sneakers.
Scene: [...]
Action: [...]
Camera: [...]
Mood and lighting: [...]
Jack's expression: [...]
Keep the character design and outfit consistent. Smooth 2D animation, no 3D look, no photorealism, no text, no logos, no subtitles, no watermark, no blood or gore. Ambient sound only, no speech, no music.
```

**Regeln für Prompts** (vom Nutzer, aus Erfahrung):
- Lebendig, mit Atmosphäre und **Kamerabewegung**. **Pro Clip eine Hauptaktion.**
- **Keine Widersprüche:** Nie ein Objekt als voll beschreiben, das erst im Clip gefüllt wird. (Ein früherer Prompt
  mit „overflowing cart“ ließ Tüten von selbst im Wagen erscheinen.) Startzustand beschreiben („empty cart“).
  `jack.py` warnt, wenn „full/overflowing/…“ und „into/fills/…“ zusammen vorkommen.
- **Keine langen Regel-Listen und keine feste Kamera als Standard** (hat die Atmosphäre verschlechtert).
  Genauere Angaben nur, wenn ein Clip wirklich fehlerhaft war → `korrektur = ["ohren"]` usw. (Bausteine [korrektur]).
- **Kein Text in Flow.** Schrift, Zahlen, Überlebenschance und Pop-up-Icons kommen in den Schnitt.
- Bekannter Flow-Fehler: In Nahaufnahmen mit Schreck werden die Ohren gegen Ende spitz (Referenzclips
  Tankstelle und Wasserflasche). Dann Korrektur `ohren` ergänzen oder den Clip mit `#von-bis` kürzen.

## 5. Leitplanken (nicht verhandelbar)

- **Faktencheck:** Jede Sachbehauptung braucht eine Quelle (`[[fakt]]` mit `status = "geprueft"`, `quelle`, `beleg`)
  oder bleibt `offen`. Rechnungen (`[[rechnung]]`) werden automatisch nachgerechnet. Nichts aus dem Gedächtnis als
  geprüft markieren – Quelle lesen. Die Überlebenschance ist ein fiktiver Gag-Wert.
- Keine Markennamen, keine Logos, kein Blut, keine drastische Gewalt (automatische Prüfung in `jack.py`).
- **Niemals Zugangsdaten oder API-Schlüssel ins Repo.** Nur `.env` (in .gitignore) oder Umgebungsvariable.
  In der Cloud-Umgebung steckt der Schlüssel in `ELEVENLABS_API_KEY` (nur TTS-Recht, kein voices_read/user_read).
- **Kosten:** Vor jeder Vertonung Zeichenzahl zeigen und den Nutzer fragen (`vertonung.py` fragt selbst; nie
  `--ja` ohne ausdrückliche Zustimmung im Chat). Auch vor anderen Kosten fragen.
- **Nie automatisch veröffentlichen.** Der Nutzer prüft `checkliste.md` und lädt selbst hoch.
- **Nichts löschen ohne Rückfrage**, besonders keine Uploads (auch keine Duplikate).
- KI-Kennzeichnung nicht vergessen und nicht als unnötig bezeichnen (Checklistenpunkt, Stand siehe log.md).

## 6. Repo und Git

- Arbeits-Branch: **`pipeline`**. Der Nutzer lädt manchmal per GitHub-Weboberfläche auf **`main`** hoch.
  Zu Beginn jeder Sitzung: `git fetch origin main pipeline` und neue Uploads von main in pipeline übernehmen
  (`git merge origin/main`), dann `python3 tools/katalog.py einsortieren` für Dateien, die nicht nach dem
  Schema `NN-szene-NN.mp4` heißen, und im Katalog beschreiben (Clips ansehen: Standbilder mit ffmpeg).
- Uploads im Hauptordner von main (z. B. `Dog_….mp4`) wurden am 2026-11-05 per `git mv` nach `bibliothek/` verschoben.
- `.gitignore`: mp4/mp3/wav sind ausgeschlossen, **außer** in `eingang/`, `bibliothek/`, `fertig/`,
  `videos/*/medien/` (bezahlte Vertonungen!) und `proben/`. `output/` = Probeschnitte, nicht im Repo.

## 7. Pipeline (Python 3.11+, ffmpeg mit libass, Pillow)

```
bausteine/bausteine.toml   Flow-Vorlage, Figur-Pflichtmerkmale, Mimik/Kamera/Stimmung/Booster/Korrektur, Icons, Prüflisten
bausteine/stimme.toml      ElevenLabs: voice_id Georg (LRpNiUBlcqgIsKUzcrlN), model_id, voice_settings
tools/jack.py              neu | baue | pruefe-bausteine  (Mappe erzeugen + alle Prüfungen)
tools/vertonung.py         ElevenLabs mit Zeitstempeln, am Stück, Aufteilung in Szenen; --probe für Testsätze
tools/schnitt.py           Clips + Stimme + Untertitel + Überlebenschance + Einblendungen + Pop-ups -> MP4
tools/icons.py             zeichnet die Pop-up-Icons (bibliothek/icons/); eigene PNGs haben Vorrang (eigene.txt)
tools/katalog.py           eingang/ -> bibliothek/, Katalog, Übersicht, Suche
schriften/                 Inter (OFL) für die Einblendungen, damit der Look überall gleich ist
videos/NN-name/thema.toml  EINGABE pro Video; alles andere im Ordner wird daraus erzeugt
fertig/                    fertige Videos zum Herunterladen (jack-NN-name.mp4)
```

Ablauf pro Video: `jack.py neu` → thema.toml ausfüllen → `jack.py baue` → Nutzer erzeugt Clips in Flow mit
`prompts.md` und lädt sie nach `eingang/NN-szene-NN.mp4` (Liste: `hochladen.md`) → `vertonung.py` (fragt wegen
Kosten) → `schnitt.py --plan`, dann `schnitt.py` → Ergebnis in `fertig/` → Nutzer prüft `checkliste.md` und lädt hoch.

**Schnitt-Regeln (anders als Brokey):** Flow-Clips laufen möglichst vollständig, **keine schnellen Zoom-Ausschnitte**.
**Clips nie auffällig verlangsamen oder dehnen** (Nutzer). **Stimme synchron zum Bild:** Texte auf den Clipinhalt schreiben,
Wörter mit `anker = [{ wort, zeit }]` auf Bildmomente legen (z. B. eingebrannte Icons), kein Standbild am Ende. Szene = Cliplänge; die Stimme ist eine durchgehende Spur und darf
bis 1,5 s in die nächste Szene laufen (`max_ueberhang`) oder mit `vorziehen` vor dem Schnitt beginnen. Passt ein Text
trotzdem nicht, meldet der Plan „TEXT ZU LANG“ → dem Nutzer eine Kürzung vorschlagen, **Text nie ohne Rückfrage ändern**. Clip-Ton leise unter der Stimme (`clip_ton`, plus Ducking). **Pop-ups erscheinen genau beim
gesprochenen Wort** (Wort-Zeitstempel aus vo-NN.json). Ohne Stimme: geschätzte Zeiten, Ausgabe nach `output/`.
Optionen in thema.toml: `[video] clip_ton, vorlauf, nachlauf, clip_min_tempo, einblend_dauer, ducking`,
pro Szene `anker`, `vorlauf`, `nachlauf`, `vorziehen`, `ueberhang = false`, `kuerzen = true`, `medien = ["pfad#von-bis"]`,
`einblendungen = [{text, wort}]` (nacheinander zum Wort), `texte_unten = true` (wenn oben Icons im Clip eingebrannt sind),
Pop-ups mit `x`, `y`, `groesse`. Folgen nur aus Bibliotheksclips: `[video] nur_bibliothek = true`.
Vor dem Schneiden **jeden Clip selbst ansehen** (Standbilder im 0,5-s-Raster, an Problemstellen 0,1 s) und den Katalog
beachten bzw. ergänzen. Nach dem Rendern Standbilder zu den Wortzeiten prüfen (Icons, Texte, Untertitel-Überdeckung).

## 8. Stimme (ElevenLabs)

- Stimme **Georg** (`LRpNiUBlcqgIsKUzcrlN`, deutsch, alt, rau). Nur TTS-Endpunkt `/v1/text-to-speech/{id}/with-timestamps`.
- Doku gelesen 2026-11-05: Audio-Tags (`[sarcastic]`, `[sighs]`, `[whispers]` …) nur mit `eleven_v4`, `eleven_v4_turbo`,
  `eleven_v3`. **Nicht** mit `eleven_multilingual_v2` (dort entfernt `vertonung.py` die Tags vor dem Senden).
  `eleven_v4`: keine Speed-/Style-Regler, kein SSML. Speed sonst 0,7–1,2. Der Tag heißt in der Doku `[sarcastic]`.
- **Gewählt (Probe 2026-11-05):** `eleven_multilingual_v2`, seit Folge 02 speed 1.15, stability 0.45, style 0.15
  (trocken-ironischer Georg). Humor kommt vor allem aus dem Text: kurze Sätze, Understatement, Kommentar zu Jacks Fehlern. Georg spricht bei Tempo 1.0 nur ca. 13 Zeichen/s;
  nur v2 erlaubt höheres Tempo. Proben in `proben/`. `eleven_v4` klang gleich schnell, Alternative für Audio-Tags.
  Faustregel für Texte: ca. 14 Zeichen pro Sekunde Clip (bei speed 1.1).

## 9. Stand

Siehe `log.md`. Folge 01 „Der Chips-Einkauf“: Mappe fertig, Clips vom Nutzer ausstehend. Folge 02 „Die ersten 3 Tage“ (nur Bibliotheksclips): **fertig** (Überarbeitung 2) in `fertig/jack-02-die-ersten-3-tage.mp4` (46,9 s), nicht veröffentlicht.
