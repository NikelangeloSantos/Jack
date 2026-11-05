# Jack – Was wäre, wenn die Zombie-Apokalypse kommt?

Pipeline für YouTube Shorts und TikTok (30–90 s) mit **Jack**, einem Golden-Retriever-Teenager, der in der
Zombie-Apokalypse alles falsch macht, während ein trockener Erzähler kommentiert. Jede Folge enthält echtes
Vorsorgewissen mit Quelle. Wiedererkennung: „Überlebenschance: X %“ in jedem Video.

Projektregeln für Claude: `CLAUDE.md` · Verlauf: `log.md`

## Ordner

```
bausteine/bausteine.toml   Flow-Prompt-Vorlage, Figur, Mimik, Kamera, Stimmung, Booster, Korrekturen, Prüflisten
bausteine/stimme.toml      Stimme Georg (ElevenLabs), Modell, Tempo
eingang/                   HIER neue Clips hochladen (Name z. B. 01-szene-03.mp4)
bibliothek/                Referenzbilder, Clips, Pop-up-Icons, katalog.md + uebersicht.jpg
videos/NN-name/thema.toml  DEINE Eingabe pro Video – alles andere im Ordner wird erzeugt
fertig/                    fertige Videos zum Herunterladen
tools/                     jack.py, vertonung.py, schnitt.py, icons.py, katalog.py
```

## Benutzung

Python 3.11+, für Schnitt ffmpeg (Windows `winget install ffmpeg`, Mac `brew install ffmpeg`) und Pillow (`pip install pillow`).
Alle Befehle im Repo-Hauptordner.

**1. Neues Video anlegen und ausfüllen**
```bash
python3 tools/jack.py neu 02 der-wasserkanister --titel "Der Wasserkanister"
```
In `videos/02-der-wasserkanister/thema.toml` pro Szene: `teil`, `scene`/`action` (Englisch), `camera`/`mood`/`expression`
(Baustein-Name oder eigener Satz), `sprechertext` (Deutsch), `chance` (Überlebenschance), optional `einblendtext`, `popup`.
Fakten als `[[fakt]]` mit Quelle, Rechnungen als `[[rechnung]]`.

**2. Mappe bauen**
```bash
python3 tools/jack.py baue videos/01-der-chips-einkauf
```
Erzeugt `prompts.md` (fertige Flow-Prompts), `hochladen.md` (welche Clips fehlen), `skript.md`, `szenen.md`,
`faktencheck.md`, `untertitel.srt`, `einblendungen.srt`, `voiceover.txt`, `checkliste.md`.
Prüft automatisch: Aufbau (Hook bis Schluss mit Frage), Überlebenschance in jeder Szene, Rechnungen, Fakten ohne
Quelle, Markennamen, Blut/Gewalt, Ziffern oder Schrift im Prompt, Widersprüche („overflowing“ + „into“),
feste Kamera, Pop-up-Wörter, Länge 30–90 s.

**3. Clips in Flow erzeugen** mit `prompts.md` + Referenzbild, dann nach `eingang/` hochladen
(Namen aus `hochladen.md`, z. B. `01-szene-01.mp4`).

**4. Stimme** (kostet ElevenLabs-Guthaben, das Tool zeigt vorher die Zeichenzahl und fragt):
```bash
python3 tools/vertonung.py videos/01-der-chips-einkauf
```
Vertont alles in einer Anfrage mit Zeitstempeln und teilt in Szenen auf. Neu aufteilen ohne Kosten: `--nur-schneiden`.
Testsatz: `python3 tools/vertonung.py --probe "Zombie-Apokalypse, Tag eins." --modelle eleven_v4,eleven_multilingual_v2`

**5. Schneiden**
```bash
python3 tools/schnitt.py videos/01-der-chips-einkauf --plan
```
```bash
python3 tools/schnitt.py videos/01-der-chips-einkauf
```
Clips laufen möglichst vollständig, Flow-Ton leise unter der Stimme, Untertitel, Einblendungen, Überlebenschance und
Pop-up-Icons (erscheinen genau beim gesprochenen Wort). Sind alle Clips und die Stimme da → `fertig/jack-01-der-chips-einkauf.mp4`,
sonst Probeschnitt mit Platzhaltern in `output/`. Clip kürzen: in `medien` `"eingang/01-szene-05.mp4#0-6"`.

**6. Veröffentlichen machst du selbst** – vorher `checkliste.md` abhaken (Fakten, Marken, KI-Kennzeichnung, ElevenLabs-Lizenz).

## Neue Uploads

Auf GitHub per „Add file → Upload files“ nach `eingang/` (Branch `pipeline` oder `main`). Claude übernimmt main in
pipeline, sortiert Dateien mit anderen Namen per `python3 tools/katalog.py einsortieren` ein und beschreibt sie.

## Wichtig

- API-Schlüssel nur in `.env` (Vorlage `.env.example`), nie ins Repo.
- Die Pipeline veröffentlicht nichts.
