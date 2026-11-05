# Log: was funktioniert hat, was nicht

| Datum | Was | Ergebnis | Notiz |
|---|---|---|---|
| 2026-11-05 | Pipeline nach Vorbild Brokey angelegt (Branch `pipeline`) | – | jack.py, vertonung.py (mit Zeitstempeln), schnitt.py (Clips ganz, Überlebenschance, Pop-ups), icons.py, katalog.py |
| 2026-11-05 | 12 Uploads von main gesichtet und nach `bibliothek/` verschoben (git mv, nichts gelöscht) | – | `person-observing-burning-city…jpg` ist byte-gleich mit `jack-observing-burning-city…jpg` → Löschen nur nach Rückfrage |
| 2026-11-05 | Referenzclips gesichtet | – | Stil passt (2D, Cel-Shading, dunkle Hintergründe). Fehler: Tankstelle + Wasserflasche → am Ende spitze Ohren/anderes Gesicht. Einkaufswagen-Clip: Tüten erscheinen von selbst. Icon-Clip: Icons eingebrannt, ohne Bargeld |
| 2026-11-05 | ElevenLabs-Doku gelesen (elevenlabs.io/docs) | – | Audio-Tags nur eleven_v4/v4_turbo/v3, nicht multilingual_v2. v4 ohne speed/style. Endpunkt with-timestamps liefert Zeit pro Zeichen. Tag heißt `[sarcastic]`. API-Schlüssel hat nur TTS-Recht |
| 2026-11-05 | Faktencheck Folge 01 | – | 2 L/Person/Tag, 3 bzw. 10 Tage, 6 L = 3 Tage: SH-Landesportal + BBK-Ratgeber 11/2025. Pumpen: BBK „Wasserwerke benötigen Strom … fällt die Wasserversorgung aus“ → sinngemäß belegt (Quelle sagt Wasserwerke, nicht Pumpen) |
| 2026-11-05 | KI-Kennzeichnung | – | YouTube-Hilfe gelesen: Pflicht bei realistisch wirkenden Inhalten, klar unrealistische Animation ausgenommen; Angabe schadet Reichweite nicht. TikTok-Hilfe nicht automatisch lesbar → in der App prüfen. ElevenLabs: Commercial License ab Starter |
| 2026-11-05 | Probeschnitt 01 mit Referenzclips als Platzhalter, ohne Stimme | – | 52,5 s. Zähl-Animation, Einblendungen, Pop-ups ok. Icons auf y 520/790 hochgesetzt, Szene 6 Kamera sanfter, damit der Kopf frei bleibt |
| 2026-11-05 | Stimmtest Georg | offen | Nutzer will noch nicht senden. Befehl (fragt vorher): `python3 tools/vertonung.py --probe "Zombie-Apokalypse, Tag eins. [sarcastic] Jack nimmt: Chips." --modelle eleven_v4,eleven_multilingual_v2 --tempi 0.95,1.05`. Bis dahin model_id = eleven_multilingual_v2 (ohne Tags). Folge 01 = 601 Zeichen |
| 2026-11-05 | 02 Die ersten 3 Tage: nur Bibliotheksclips, Mappe + Faktencheck (BBK-Ratgeber 11/2025, SH-Landesportal) | – | 2 Aussagen offen (Zuspitzungen: „Die ersten drei Tage entscheiden“, „Chips zählen nur knapp“) |
| 2026-11-05 | 02 Clips gesichtet (0,1-s-Raster an Problemstellen) | – | Wagen-Clip nur 0–2,1 s; Flaschen-Clip nur 0–5,4 s; Klemmbrett-Icons-Clip hat ab 7,4 s schon ein Geldschein-Icon (Katalog war falsch) → kein bargeld.png darüber; Wohnungs-Klemmbrett-Clip: Klemmbrett verschwindet bei ~5,8 s (neu) |
| 2026-11-05 | schnitt.py: durchgehende Stimmspur, Überhang bis 1,5 s in die nächste Szene, `vorziehen`, `einblendungen` zum Wort, `texte_unten`, Pop-up-Positionen; clip_min_tempo jetzt 1.0 (nie verlangsamen) | – | Probeschnitt 02 ohne Stimme 51,9 s. Geschätzt (14,5 Zeichen/s) ist nur Szene 7 zu lang (~2,7 s) |
