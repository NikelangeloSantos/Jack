# Hier neue Clips und Bilder hochladen

Per GitHub „Add file → Upload files“ in diesen Ordner, auf den Branch **pipeline** (oder main, Claude übernimmt sie).

**Am einfachsten:** Clip vor dem Upload so benennen: `<Video>-szene-<Szene>.mp4`, z. B. `01-szene-03.mp4`.
Dann findet der Schnitt ihn automatisch. Welche Namen gerade fehlen, steht in `videos/<NN-name>/hochladen.md`.

Andere Namen gehen auch: Claude sortiert sie mit `python3 tools/katalog.py einsortieren` nach `bibliothek/` und beschreibt sie.
