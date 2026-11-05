#!/usr/bin/env python3
"""Schnitt: Flow-Clips + Stimme + Untertitel + Überlebenschance + Pop-ups -> fertiges 9:16-Video (ffmpeg).

Benutzung (aus dem Repo-Hauptordner):
    python3 tools/schnitt.py videos/01-der-chips-einkauf --plan    # nur zeigen, was gefunden wurde
    python3 tools/schnitt.py videos/01-der-chips-einkauf           # rendern

Grundsätze (anders als bei Brokey):
- Flow-Clips laufen möglichst vollständig, ohne schnelle Zoom-Ausschnitte. Eine Szene dauert so lange wie
  ihr Clip. Clips werden standardmäßig NICHT verlangsamt (clip_min_tempo = 1.0).
- Die Stimme ist eine durchgehende Spur: Ein Satz darf bis max_ueberhang Sekunden in die nächste Szene
  laufen. Reicht das nicht (oder in der letzten Szene), wird das letzte Bild gehalten und der Plan
  meldet „TEXT ZU LANG“ -> dann dem Nutzer eine Textkürzung vorschlagen, nicht still dehnen.
- Pro Szene: einblendungen = [{ text = "...", wort = "..." }] erscheinen nacheinander zum Wort;
  texte_unten = true setzt Überlebenschance und Einblendungen nach unten (z. B. wenn oben Icons im Clip sind);
  popup-Einträge können x, y, groesse haben.
- Der Clip-Ton läuft leise unter der Stimme (clip_ton) und wird beim Sprechen zusätzlich abgesenkt.
- Untertitel, Einblendungen, „Überlebenschance: X %“ und Pop-up-Icons werden hier eingefügt (nie in Flow).
- Untertitel und Pop-ups folgen den Wort-Zeitstempeln aus tools/vertonung.py (vo-NN.json).

Medien pro Szene: `medien = [...]` in thema.toml, sonst <nummer>-szene-<NN>*.mp4 in eingang/ oder
bibliothek/clips/. Pro Medium optional "datei.mp4#von-bis" (Sekunden), z. B. "#0-6.5" schneidet ab 6,5 s ab.
Fehlt ein Clip, kommt ein Platzhalter. Fehlt die Stimme, bleibt es stumm mit geschätzten Zeiten.

Ausgabe: fertig/jack-<ordner>.mp4, wenn alle Clips und die Stimme da sind, sonst output/<ordner>-probe.mp4.
Braucht ffmpeg mit libass und Pillow.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jack import BILD_ENDUNGEN, CLIP_ENDUNGEN, ROOT, Mappe, ohne_tags, zeit_srt  # noqa: E402

B, H, FPS = 1080, 1920, 30
SCHRIFTEN = ROOT / "schriften"
ICONS = ROOT / "bibliothek" / "icons"
STANDARD = {
    "clip_ton": 0.35,        # Lautstärke Flow-Ton (1.0 = original)
    "ducking": True,         # Clip-Ton beim Sprechen zusätzlich absenken
    "vorlauf": 0.25,         # Sekunden Bild vor Einsatz der Stimme (pro Szene überschreibbar)
    "nachlauf": 0.35,        # Mindest-Luft nach der Stimme
    "clip_min_tempo": 1.0,   # 1.0 = nie verlangsamen (Nutzerwunsch); z. B. 0.9 erlaubt leichtes Verlangsamen
    "einblend_dauer": 2.5,   # Einblendtext so viele Sekunden am Szenenanfang (0 = ganze Szene)
    "zaehl_dauer": 0.7,      # Überlebenschance zählt so lange zum neuen Wert
    "icon_groesse": 230,
    "luecke": 0.2,           # Mindestpause zwischen zwei Sätzen der Stimme
    "max_ueberhang": 1.5,    # so weit darf ein Satz in die nächste Szene laufen (statt Clip zu dehnen)
    "schluss_nachlauf": 0.8, # nach dem letzten Wort noch so lange Bild
}
UT_ZEICHEN = 30              # Untertitel: max. ca. 30 Zeichen pro Zeile, 2 Zeilen


def ffmpeg(*args: str):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg-Fehler:\n{r.stderr[-3000:]}")


def probe(datei: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", str(datei)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def dauer(datei: Path) -> float:
    return float(probe(datei)["format"]["duration"])


def hat_audio(datei: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(datei).get("streams", []))


def ist_clip(p: Path) -> bool:
    return p.suffix.lower() in CLIP_ENDUNGEN


# ---------------------------------------------------------------- ASS

def ass_zeit(sek: float) -> str:
    cs = int(round(max(0, sek) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def ass_text(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


ASS_KOPF = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {B}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Untertitel,Inter ExtraBold,66,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,6,3,2,80,80,430,1
Style: Chance,Inter Black,56,&H00FFFFFF,&H00FFFFFF,&H00141414,&HC8141414,0,0,0,0,100,100,0,0,3,18,0,8,60,60,190,1
Style: Einblendung,Inter Black,62,&H00141414,&H00141414,&H0050D8F5,&H00000000,0,0,0,0,100,100,0,0,3,14,0,8,80,80,330,1
Style: ChanceU,Inter Black,56,&H00FFFFFF,&H00FFFFFF,&H00141414,&HC8141414,0,0,0,0,100,100,0,0,3,18,0,2,60,60,760,1
Style: EinblendungU,Inter Black,62,&H00141414,&H00141414,&H0050D8F5,&H00000000,0,0,0,0,100,100,0,0,3,14,0,2,80,80,640,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def farbe_chance(c: int) -> str:
    """ASS-Farbe (&HBBGGRR&): grün ab 60 %, gelb ab 30 %, sonst rot."""
    return "&H5AD26E&" if c >= 60 else ("&H3CC8F0&" if c >= 30 else "&H3C3CF0&")


def chance_zeilen(t0: float, t1: float, alt: int | None, neu: int, zaehl: float) -> list[str]:
    """Anzeige 'Überlebenschance: X %', zählt am Szenenanfang vom alten zum neuen Wert."""
    zeilen, schritte = [], 12
    if alt is None or alt == neu or zaehl <= 0:
        werte = [(t0, neu)]
    else:
        werte = [(t0 + zaehl * k / schritte, round(alt + (neu - alt) * k / schritte)) for k in range(schritte + 1)]
    for i, (a, wert) in enumerate(werte):
        e = werte[i + 1][0] if i + 1 < len(werte) else t1
        pop = "{\\t(0,120,\\fscx112\\fscy112)\\t(120,260,\\fscx100\\fscy100)}" if i == len(werte) - 1 else ""
        zeilen.append(f"Dialogue: 2,{ass_zeit(a)},{ass_zeit(e)},Chance,,0,0,0,,{pop}Überlebenschance: "
                      f"{{\\c{farbe_chance(wert)}}}{wert} %\n")
    return zeilen


def zeilen_umbruch(text: str, breite: int = UT_ZEICHEN) -> list[str]:
    out, akt = [], ""
    for w in text.split():
        if akt and len(akt) + 1 + len(w) > breite:
            out.append(akt)
            akt = w
        else:
            akt = f"{akt} {w}".strip()
    return out + ([akt] if akt else [])


def untertitel_bloecke(woerter: list[dict]) -> list[tuple[float, float, str]]:
    """Wörter (mit Zeiten) zu Untertiteln mit max. 2 Zeilen gruppieren; neuer Block nach Satzende."""
    bloecke, akt = [], []
    for w in woerter:
        probe_text = " ".join(x["wort"] for x in akt + [w])
        if akt and (len(zeilen_umbruch(probe_text)) > 2 or re.search(r"[.!?]$", akt[-1]["wort"])):
            bloecke.append(akt)
            akt = []
        akt.append(w)
    if akt:
        bloecke.append(akt)
    out = []
    for i, b in enumerate(bloecke):
        ende = bloecke[i + 1][0]["start"] if i + 1 < len(bloecke) else b[-1]["ende"] + 0.3
        out.append((b[0]["start"], max(ende, b[-1]["ende"]), "\n".join(zeilen_umbruch(" ".join(x["wort"] for x in b)))))
    return out


def geschaetzte_woerter(text: str, sprech: float) -> list[dict]:
    """Ohne Zeitstempel: Wortzeiten nach Zeichenanteil schätzen."""
    ws = ohne_tags(text).split()
    gesamt = sum(len(w) + 1 for w in ws) or 1
    t, out = 0.0, []
    for w in ws:
        d = sprech * (len(w) + 1) / gesamt
        out.append({"wort": w, "start": t, "ende": t + d})
        t += d
    return out


# ---------------------------------------------------------------- Bild

def platzhalter(ziel: Path, text: str):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (B, H), (32, 36, 48))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype(str(SCHRIFTEN / "Inter-ExtraBold.otf"), 54)
    except OSError:
        f = ImageFont.load_default()
    d.multiline_text((B // 2, H // 2), text, fill=(170, 175, 190), font=f, anchor="mm", align="center", spacing=20)
    img.save(ziel)


def zerlege(eintrag: str) -> tuple[Path, float, float | None]:
    """'datei.mp4#1.5-6' -> (Pfad, von, bis)."""
    pfad, _, bereich = eintrag.partition("#")
    von, bis = 0.0, None
    if bereich:
        a, _, b = bereich.partition("-")
        von, bis = float(a or 0), (float(b) if b else None)
    return ROOT / pfad, von, bis


def baue_bild(medien: list[tuple[Path, float, float | None]], d: float, min_tempo: float, ziel: Path, tmp: Path):
    """Video-Spur einer Szene (ohne Text): Clips nacheinander, vollständig; Rest = letztes Bild halten."""
    teile, laengen = [], []
    for k, (m, von, bis) in enumerate(medien):
        if ist_clip(m):
            bis = min(bis or dauer(m), dauer(m))
            laengen.append(max(0.1, bis - von))
        else:
            laengen.append(None)
    clip_summe = sum(x for x in laengen if x)
    bilder = sum(1 for x in laengen if x is None)
    # Tempo: Clips verlangsamen, wenn die Szene länger ist als die Clips (nur wenn keine Standbilder füllen)
    tempo = 1.0
    if clip_summe and not bilder and d > clip_summe:
        tempo = max(min_tempo, clip_summe / d)
    rest_bild = (d - clip_summe / tempo) / bilder if bilder else 0
    for k, ((m, von, _), laenge) in enumerate(zip(medien, laengen)):
        t = tmp / f"{ziel.stem}-{k}.mp4"
        skal = (f"scale={B}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={B}:{H},"
                f"unsharp=5:5:0.5,setsar=1,fps={FPS},format=yuv420p")
        if laenge:
            ffmpeg("-ss", f"{von:.3f}", "-t", f"{laenge:.3f}", "-i", str(m), "-an", "-vf",
                   f"setpts=(PTS-STARTPTS)/{tempo:.4f},{skal}", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "16", str(t))
        else:  # Standbild: langsamer Zoom
            n = max(1, round(rest_bild * FPS))
            ffmpeg("-loop", "1", "-t", f"{rest_bild:.3f}", "-i", str(m), "-vf",
                   f"scale={B * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={B * 2}:{H * 2},"
                   f"zoompan=z='1+0.06*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={B}x{H}:fps={FPS},"
                   "setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(t))
        teile.append(t)
    eingabe = [x for t in teile for x in ("-i", str(t))]
    f = "".join(f"[{i}:v]" for i in range(len(teile))) + f"concat=n={len(teile)}:v=1:a=0,"
    f += f"tpad=stop_mode=clone:stop_duration={d + 1:.2f},trim=duration={d:.3f},setpts=PTS-STARTPTS[v]"
    ffmpeg(*eingabe, "-filter_complex", f, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(ziel))
    return tempo


def baue_sfx(medien, tempo: float, d: float, cfg: dict, ziel: Path):
    """Clip-Ton einer Szene (leise), ohne Stimme. Die Stimme kommt als durchgehende Spur dazu."""
    eingabe, ketten, n = [], [], 0
    for m, von, bis in medien:
        if ist_clip(m) and hat_audio(m):
            laenge = min(bis or dauer(m), dauer(m)) - von
            eingabe += ["-ss", f"{von:.3f}", "-t", f"{laenge:.3f}", "-i", str(m)]
            ketten.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atempo={max(0.5, tempo):.4f}[c{n}]")
            n += 1
    if n:
        sfx = "".join(f"[c{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,volume={cfg['clip_ton']},apad,atrim=duration={d:.3f}[a]"
    else:
        eingabe += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        sfx = f"[{n}:a]atrim=duration={d:.3f}[a]"
    ffmpeg(*eingabe, "-filter_complex", ";".join(ketten + [sfx]), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(ziel))


def mische_ton(sfx: Path, stimmen: list[tuple[Path, float]], gesamt: float, cfg: dict, ziel: Path):
    """Durchgehende Stimmspur (jede vo-NN.wav ab ihrer Startzeit) über den Clip-Ton legen, mit Ducking."""
    eingabe = ["-i", str(sfx)]
    for datei, _ in stimmen:
        eingabe += ["-i", str(datei)]
    if not stimmen:
        ffmpeg(*eingabe, "-c:a", "pcm_s16le", str(ziel))
        return
    f = ""
    for k, (_, ab) in enumerate(stimmen, 1):
        f += f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={int(max(0, ab) * 1000)}:all=1[s{k}];"
    f += "".join(f"[s{k}]" for k in range(1, len(stimmen) + 1))
    f += f"amix=inputs={len(stimmen)}:normalize=0,apad,atrim=duration={gesamt:.3f},asplit=2[st][sc];"
    if cfg["ducking"]:
        f += "[0:a][sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[duck];"
        f += f"[st][duck]amix=inputs=2:normalize=0,atrim=duration={gesamt:.3f}[a]"
    else:
        f += f"[sc]anullsink;[st][0:a]amix=inputs=2:normalize=0,atrim=duration={gesamt:.3f}[a]"
    ffmpeg(*eingabe, "-filter_complex", f, "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(ziel))


def icon_pfad(name: str) -> Path:
    p = ICONS / f"{name}.png"
    if not p.exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "icons.py")], check=True)
    return p


def icon_positionen(n: int, groesse: int) -> list[tuple[int, int]]:
    """Mittelpunkte der Pop-ups über Jacks Kopf: bis 3 in einer Reihe, sonst zwei Reihen."""
    abstand = groesse + 40
    reihen = [n] if n <= 3 else [(n + 1) // 2, n // 2]
    ys = [560] if len(reihen) == 1 else [520, 520 + abstand]
    pos = []
    for r, anzahl in enumerate(reihen):
        x0 = B / 2 - (anzahl - 1) * abstand / 2
        pos += [(int(x0 + i * abstand), ys[r]) for i in range(anzahl)]
    return pos


def wort_zeit(woerter: list[dict], wort: str) -> float | None:
    """Startzeit (relativ) des ersten gesprochenen Wortes, das `wort` enthält."""
    ziel = re.sub(r"\W", "", wort.lower())
    for w in woerter:
        if ziel and ziel in re.sub(r"\W", "", w["wort"].lower()):
            return w["start"]
    return None


# ---------------------------------------------------------------- Hauptablauf

def plane(m: Mappe, cfg: dict, medien_dir: Path) -> list[dict]:
    """Zeitplan: Szene = Cliplänge. Die Stimme bildet eine durchgehende Spur: Satz k beginnt bei
    Szenenstart + vorlauf, frühestens nach dem vorigen Satz. Ragt er über das Clipende, darf er bis
    max_ueberhang Sekunden in die nächste Szene laufen; sonst wird das letzte Bild gehalten (Warnung)."""
    plan, t, frei_ab = [], 0.0, None
    for i, s in enumerate(m.szenen):
        nn = s["_nn"]
        eintraege = [zerlege(e) for e in m.medien_fuer(s)]
        for p, _, _ in eintraege:
            if not p.exists():
                print(f"  WARNUNG: Szene {nn}: {p} gibt es nicht.")
        eintraege = [e for e in eintraege if e[0].exists()]
        wav, info = medien_dir / f"vo-{nn}.wav", medien_dir / f"vo-{nn}.json"
        if wav.exists() and info.exists():
            j = json.loads(info.read_text(encoding="utf-8"))
            woerter, s0, s1, quelle = j["woerter"], j["sprech_start"], j["sprech_ende"], "Stimme"
        else:
            wav, s0, s1, quelle = None, 0.0, s["_sprech"], "geschätzt"
            woerter = geschaetzte_woerter(s.get("sprechertext", ""), s1)
        clip_len = sum(min(b or dauer(p), dauer(p)) - v for p, v, b in eintraege if ist_clip(p))
        d = clip_len or float(s.get("clip_dauer", 8))
        vorlauf = s.get("vorlauf", cfg["vorlauf"])
        nachlauf = s.get("nachlauf", cfg["nachlauf"])
        # vorziehen = x: Satz darf x s vor dem Schnitt beginnen (über dem Ende der vorigen Szene)
        wunsch = t + vorlauf - s.get("vorziehen", 0.0)
        sprech_ab = wunsch if frei_ab is None else max(wunsch, frei_ab + cfg["luecke"])  # erstes Wort, absolut
        sprech_bis = sprech_ab + (s1 - s0)
        halten, ueberhang = 0.0, 0.0
        letzte = i == len(m.szenen) - 1
        if s.get("kuerzen"):
            d = max(0.5, sprech_bis + nachlauf - t)
        elif letzte:
            halten = max(0.0, sprech_bis + cfg["schluss_nachlauf"] - (t + d))
        else:
            ueber = sprech_bis - (t + d)          # so weit ragt die Stimme über das Clipende
            if ueber > 0:
                erlaubt = cfg["max_ueberhang"] if s.get("ueberhang", True) else 0.0
                ueberhang = min(ueber, erlaubt)
                halten = ueber - ueberhang
        d += halten
        plan.append(dict(s=s, nn=nn, medien=eintraege, wav=wav, woerter=woerter, d=d, start=t, quelle=quelle,
                         clip_len=clip_len, versatz=sprech_ab - s0, sprech_ab=sprech_ab, sprech_bis=sprech_bis,
                         halten=halten, ueberhang=ueberhang))
        frei_ab = sprech_bis
        t += d
    return plan


def schneide(ordner: Path, nur_plan: bool = False, ausgabe: Path | None = None, arbeit: Path | None = None):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg nicht gefunden. Bitte installieren (siehe README).")
    m = Mappe(ordner)
    m.pruefe()
    cfg = {k: m.v.get(k, v) for k, v in STANDARD.items()}
    plan = plane(m, cfg, ordner / "medien")
    gesamt = sum(p["d"] for p in plan)

    vollstaendig = all(p["medien"] and p["wav"] for p in plan)
    print(f"Schnittplan {ordner.name}:")
    for p in plan:
        namen = ", ".join(x.name + (f" ({v:g}-{b:g} s)" if (v or b) else "") for x, v, b in p["medien"]) or "FEHLT -> Platzhalter"
        hinweis = ""
        if p["ueberhang"] > 0.05:
            hinweis += f"  Stimme läuft {p['ueberhang']:.1f} s in die nächste Szene"
        if p["halten"] > 0.05:
            hinweis += f"  ⚠️ TEXT ZU LANG: letztes Bild {p['halten']:.1f} s gehalten -> Kürzung nötig"
        print(f"  {p['nn']} {p['start']:5.1f}-{p['start'] + p['d']:5.1f}s  Clip {p['clip_len']:4.1f}s  "
              f"Stimme ({p['quelle']}) {p['sprech_ab']:5.1f}-{p['sprech_bis']:5.1f}s  Chance {p['s'].get('chance')} %"
              f"  {namen}{hinweis}")
    print(f"  Gesamt: {gesamt:.1f} s")
    for f in m.fehler:
        print(f"  FEHLER:  {f}")
    if nur_plan:
        return None
    if m.fehler:
        sys.exit("Erst die Fehler in thema.toml beheben (python3 tools/jack.py baue ...).")

    if ausgabe is None:
        ausgabe = (ROOT / "fertig" / f"jack-{ordner.name}.mp4") if vollstaendig else (ROOT / "output" / f"{ordner.name}-probe.mp4")
    ausgabe.parent.mkdir(parents=True, exist_ok=True)

    with (tempfile.TemporaryDirectory() if arbeit is None else _Ordner(arbeit)) as tmp:
        tmp = Path(tmp)
        vliste, sliste, stimmen = [], [], []
        ass, srt, alt, popups = [ASS_KOPF], [], None, []
        for p in plan:
            s, d, t0 = p["s"], p["d"], p["start"]
            medien = p["medien"]
            if not medien:
                ph = tmp / f"platzhalter-{p['nn']}.png"
                platzhalter(ph, f"Szene {p['nn']}\n{s.get('name', '')}\n\neingang/{m.v.get('nummer')}-szene-{p['nn']}.mp4\nfehlt noch")
                medien = [(ph, 0.0, None)]
            vseg, aseg = tmp / f"v-{p['nn']}.mp4", tmp / f"a-{p['nn']}.wav"
            tempo = baue_bild(medien, d, cfg["clip_min_tempo"], vseg, tmp)
            baue_sfx(medien, tempo, d, cfg, aseg)
            vliste.append(f"file '{vseg}'")
            sliste.append(aseg)
            if p["wav"]:
                stimmen.append((p["wav"], p["versatz"]))
            print(f"  Szene {p['nn']}: {d:.1f} s" + (f", Clip-Tempo {tempo:.2f}" if tempo < 1 else ""))

            # Überlebenschance und Einblendungen (oben, oder unten mit texte_unten = true)
            unten = "U" if s.get("texte_unten") else ""
            ass += [z.replace(",Chance,", f",Chance{unten},") for z in
                    chance_zeilen(t0, t0 + d, alt, s["chance"], cfg["zaehl_dauer"])]
            alt = s["chance"]
            v = p["versatz"]
            if s.get("einblendtext"):
                e_ende = t0 + d if not cfg["einblend_dauer"] else min(t0 + d, t0 + cfg["einblend_dauer"])
                ass.append(f"Dialogue: 1,{ass_zeit(t0 + 0.15)},{ass_zeit(e_ende)},Einblendung{unten},,0,0,0,,"
                           f"{{\\fad(120,150)}}{ass_text(s['einblendtext'])}\n")
            folge = s.get("einblendungen", [])
            zeiten = []
            for k, e in enumerate(folge):
                wz = wort_zeit(p["woerter"], e.get("wort", "")) if e.get("wort") else None
                zeiten.append(v + wz if wz is not None else t0 + 0.3 + k * 1.5)
            for k, e in enumerate(folge):
                bis = zeiten[k + 1] if k + 1 < len(folge) else t0 + d
                ass.append(f"Dialogue: 1,{ass_zeit(zeiten[k])},{ass_zeit(bis)},Einblendung{unten},,0,0,0,,"
                           f"{{\\fad(100,100)}}{ass_text(e['text'])}\n")
            for a, e, txt in untertitel_bloecke(p["woerter"]):
                a, e = v + a, min(v + e, gesamt)
                ass.append(f"Dialogue: 0,{ass_zeit(a)},{ass_zeit(e)},Untertitel,,0,0,0,,{ass_text(txt)}\n")
                srt.append(f"{len(srt) + 1}\n{zeit_srt(a)} --> {zeit_srt(e)}\n{txt}\n")
            # Pop-ups zur Stimme (pro Icon optional x, y, groesse)
            pops = s.get("popup", [])
            for k, (pop, (x, y)) in enumerate(zip(pops, icon_positionen(len(pops), cfg["icon_groesse"]))):
                wz = wort_zeit(p["woerter"], pop["wort"])
                zeit = v + wz if wz is not None else t0 + 0.3 + k * 0.6
                popups.append(dict(datei=icon_pfad(pop["icon"]), t=zeit, ende=t0 + d, x=pop.get("x", x),
                                   y=pop.get("y", y), g=pop.get("groesse", cfg["icon_groesse"])))

        (tmp / "liste.txt").write_text("\n".join(vliste))
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(tmp / "liste.txt"), "-c", "copy", str(tmp / "bild.mp4"))
        eingabe = [x for a in sliste for x in ("-i", str(a))]
        ffmpeg(*eingabe, "-filter_complex", "".join(f"[{i}:a]" for i in range(len(sliste))) +
               f"concat=n={len(sliste)}:v=0:a=1[a]", "-map", "[a]", "-c:a", "pcm_s16le", str(tmp / "sfx.wav"))
        mische_ton(tmp / "sfx.wav", stimmen, gesamt, cfg, tmp / "ton.wav")
        (tmp / "text.ass").write_text("".join(ass), encoding="utf-8")

        # Pop-ups (skalieren beim Erscheinen auf 115 % und zurück auf 100 %), dann Texte einbrennen
        eingabe = ["-i", str(tmp / "bild.mp4"), "-i", str(tmp / "ton.wav")]
        f, letzte = "", "[0:v]"
        for k, pop in enumerate(popups):
            eingabe += ["-loop", "1", "-t", f"{gesamt:.3f}", "-i", str(pop["datei"])]
            i, g = k + 2, pop["g"]
            tt = f"(t-{pop['t']:.3f})"
            groesse = f"if(lt({tt},0),2,if(lt({tt},0.12),2+{g * 1.15 - 2:.1f}*{tt}/0.12,if(lt({tt},0.24),{g * 1.15:.1f}-{g * 0.15:.1f}*({tt}-0.12)/0.12,{g})))"
            f += f"[{i}:v]format=rgba,scale=w='{groesse}':h='{groesse}':eval=frame[i{k}];"
            f += (f"{letzte}[i{k}]overlay=x='{pop['x']}-overlay_w/2':y='{pop['y']}-overlay_h/2':eval=frame:"
                  f"enable='between(t,{pop['t']:.3f},{pop['ende']:.3f})'[o{k}];")
            letzte = f"[o{k}]"
        ass_pfad = str(tmp / "text.ass").replace("\\", "/").replace(":", "\\:")
        fonts = str(SCHRIFTEN).replace("\\", "/").replace(":", "\\:")
        f += f"{letzte}ass='{ass_pfad}':fontsdir='{fonts}'[v]"
        print("  füge Pop-ups, Überlebenschance, Einblendungen und Untertitel ein ...")
        ffmpeg(*eingabe, "-filter_complex", f, "-map", "[v]", "-map", "1:a", "-t", f"{gesamt:.3f}",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
               "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-movflags", "+faststart", str(ausgabe))
        (ordner / "untertitel-final.srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"Fertig: {ausgabe.relative_to(ROOT) if ausgabe.is_relative_to(ROOT) else ausgabe} ({dauer(ausgabe):.1f} s)")
    if not vollstaendig:
        print("  Probeschnitt: Clips oder Stimme fehlen noch, deshalb nicht in fertig/.")
    print("  Vor dem Upload: checkliste.md abhaken (inkl. KI-Kennzeichnung). Veröffentlichen machst du selbst.")
    return ausgabe


class _Ordner:
    def __init__(self, pfad: Path):
        self.pfad = pfad

    def __enter__(self):
        self.pfad.mkdir(parents=True, exist_ok=True)
        return str(self.pfad)

    def __exit__(self, *a):
        return False


def main():
    p = argparse.ArgumentParser(description="Jack-Video schneiden")
    p.add_argument("ordner")
    p.add_argument("--plan", action="store_true", help="nur Schnittplan anzeigen, nichts rendern")
    p.add_argument("--ausgabe", help="Zieldatei (Standard: fertig/ wenn vollständig, sonst output/)")
    p.add_argument("--arbeitsordner", help="Zwischendateien hier behalten")
    a = p.parse_args()
    schneide(Path(a.ordner).resolve(), nur_plan=a.plan,
             ausgabe=Path(a.ausgabe).resolve() if a.ausgabe else None,
             arbeit=Path(a.arbeitsordner).resolve() if a.arbeitsordner else None)


if __name__ == "__main__":
    main()
