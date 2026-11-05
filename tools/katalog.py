#!/usr/bin/env python3
"""Medien-Bibliothek verwalten: neue Uploads einsortieren, Katalog anzeigen, passende Medien suchen.

Benutzung (aus dem Repo-Hauptordner):
    python3 tools/katalog.py einsortieren     # eingang/ -> bibliothek/bilder|clips, saubere Namen, Katalog-Einträge
    python3 tools/katalog.py suche abo panik  # Medien, die zu diesen Stichworten passen
    python3 tools/katalog.py uebersicht       # bibliothek/katalog.md + bibliothek/uebersicht.jpg neu erzeugen
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "bibliothek"
EINGANG = ROOT / "eingang"
KATALOG = BIB / "katalog.toml"
BILD = (".png", ".jpg", ".jpeg", ".webp")
CLIP = (".mp4", ".mov", ".webm", ".mkv")


def lade() -> dict:
    return tomllib.loads(KATALOG.read_text(encoding="utf-8")) if KATALOG.exists() else {}


def sauberer_name(name: str) -> str:
    stamm, endung = Path(name).stem, Path(name).suffix.lower()
    stamm = stamm.lower().replace("…", "")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        stamm = stamm.replace(a, b)
    stamm = re.sub(r"[^a-z0-9]+", "-", stamm).strip("-") or "datei"
    return stamm + (".jpg" if endung == ".jpeg" else endung)


def dateien():
    for unter in ("bilder", "clips"):
        d = BIB / unter
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in BILD + CLIP:
                    yield f"{unter}/{f.name}", f


def ist_getrackt(p: Path) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", str(p)], cwd=ROOT,
                          capture_output=True).returncode == 0


def cmd_einsortieren(_a):
    neu = []
    for f in sorted(EINGANG.rglob("*")) if EINGANG.exists() else []:
        if not f.is_file() or f.suffix.lower() not in BILD + CLIP:
            continue
        unter = "clips" if f.suffix.lower() in CLIP else "bilder"
        ziel = BIB / unter / sauberer_name(f.name)
        i = 2
        while ziel.exists():
            ziel = ziel.with_name(f"{ziel.stem}-{i}{ziel.suffix}")
            i += 1
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if ist_getrackt(f):
            subprocess.run(["git", "mv", str(f), str(ziel)], cwd=ROOT, check=True)
        else:
            f.rename(ziel)
        neu.append(f"{unter}/{ziel.name}")
        print(f"  {f.relative_to(ROOT)} -> {ziel.relative_to(ROOT)}")
    if not neu:
        print("Nichts Neues in eingang/.")
        return
    with open(KATALOG, "a", encoding="utf-8") as k:
        for n in neu:
            k.write(f'\n["{n}"]\nbeschreibung = ""\ntags = []\n')
    print(f"{len(neu)} Datei(en) einsortiert und im Katalog eingetragen (Beschreibung/Tags noch leer).")


def cmd_suche(a):
    kat = lade()
    woerter = [w.lower() for w in a.stichworte]
    treffer = []
    for key, _f in dateien():
        e = kat.get(key, {})
        text = " ".join([key, e.get("beschreibung", ""), " ".join(e.get("tags", []))]).lower()
        punkte = sum(1 for w in woerter if w in text)
        if punkte:
            treffer.append((punkte, key, e))
    for p, key, e in sorted(treffer, key=lambda x: (-x[0], x[1])):
        warn = f"  ⚠️ {e['hinweis']}" if e.get("hinweis") else ""
        print(f"[{p}] {key}: {e.get('beschreibung', '')}{warn}")
    if not treffer:
        print("Keine Treffer.")


def dauer(f: Path) -> float | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def cmd_uebersicht(_a):
    kat = lade()
    zeilen = ["# Medien-Bibliothek\n\n_Erzeugt von `python3 tools/katalog.py uebersicht`. Beschreibungen in `katalog.toml` pflegen._\n\n",
              "Vorschaubild aller Medien: `uebersicht.jpg`\n\n",
              "| Nr. | Datei | Typ | Beschreibung | Tags | Hinweis |\n|---|---|---|---|---|---|\n"]
    liste = list(dateien())
    offen = []
    for i, (key, f) in enumerate(liste, 1):
        e = kat.get(key, {})
        typ = "Clip" if f.suffix.lower() in CLIP else "Bild"
        if typ == "Clip":
            d = dauer(f)
            typ += f" {d:.1f}s" if d else ""
        if not e.get("beschreibung"):
            offen.append(key)
        zeilen.append(f"| {i} | `{key}` | {typ} | {e.get('beschreibung', '')} | {', '.join(e.get('tags', []))} | {e.get('hinweis', '')} |\n")
    (BIB / "katalog.md").write_text("".join(zeilen), encoding="utf-8")

    from PIL import Image, ImageDraw, ImageFont
    cols, w, h = 6, 220, 391
    rows = (len(liste) + cols - 1) // cols or 1
    sheet = Image.new("RGB", (cols * w, rows * (h + 30)), "white")
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    with tempfile.TemporaryDirectory() as tmp:
        for i, (key, f) in enumerate(liste):
            quelle = f
            if f.suffix.lower() in CLIP:  # Standbild aus der Clip-Mitte
                quelle = Path(tmp) / f"{i}.jpg"
                mitte = (dauer(f) or 0) / 2
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{mitte:.2f}", "-i", str(f),
                                "-frames:v", "1", str(quelle)], check=False)
            try:
                im = Image.open(quelle).convert("RGB")
                im.thumbnail((w, h))
            except OSError:
                continue
            x, y = (i % cols) * w, (i // cols) * (h + 30)
            sheet.paste(im, (x, y))
            d.text((x + 4, y + h + 6), f"{i + 1}. {'▶ ' if f.suffix.lower() in CLIP else ''}{f.stem[:26]}", fill="black", font=font)
    sheet.save(BIB / "uebersicht.jpg", quality=80)
    print(f"{len(liste)} Medien. katalog.md und uebersicht.jpg aktualisiert.")
    if offen:
        print("Noch ohne Beschreibung:")
        for o in offen:
            print("  -", o)


def main():
    p = argparse.ArgumentParser(description="Jack-Medienbibliothek")
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("einsortieren").set_defaults(f=cmd_einsortieren)
    s = sub.add_parser("suche")
    s.add_argument("stichworte", nargs="+")
    s.set_defaults(f=cmd_suche)
    sub.add_parser("uebersicht").set_defaults(f=cmd_uebersicht)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
