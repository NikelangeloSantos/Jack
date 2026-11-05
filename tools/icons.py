#!/usr/bin/env python3
"""Pop-up-Icons für den Schnitt zeichnen: weiße runde Sprechblase mit schwarzer Kontur, flaches Symbol.

    python3 tools/icons.py            # alle fehlenden Icons nach bibliothek/icons/<name>.png
    python3 tools/icons.py --neu      # alle neu zeichnen (überschreibt nur gezeichnete Icons)

Eigene Icons (z. B. aus Flow, transparenter Hintergrund) einfach als bibliothek/icons/<name>.png ablegen
und in bibliothek/icons/eigene.txt eintragen, dann werden sie hier nie überschrieben.
Braucht Pillow.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ZIEL = ROOT / "bibliothek" / "icons"
G = 1024          # Zeichenfläche (wird auf 256 verkleinert -> glatte Kanten)
K = 26            # Konturstärke
SCHWARZ = (20, 20, 24, 255)


def blase() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    schatten = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    ds = ImageDraw.Draw(schatten)
    ds.ellipse((70, 90, G - 50, G - 30), fill=(0, 0, 0, 110))
    im = Image.alpha_composite(im, schatten.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)
    d.ellipse((50, 50, G - 70, G - 70), fill=(250, 248, 240, 255), outline=SCHWARZ, width=K)
    return im, d


def rr(d, box, r, fill, w=K):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=SCHWARZ, width=w)


def wasser(d):
    for x0, farbe in ((300, (120, 180, 230, 255)), (520, (95, 160, 220, 255))):
        rr(d, (x0, 400, x0 + 200, 800), 50, farbe)
        rr(d, (x0 + 55, 290, x0 + 145, 410), 18, (95, 160, 220, 255))
        rr(d, (x0 + 45, 240, x0 + 155, 300), 14, (60, 90, 150, 255))
        d.rectangle((x0 + 20, 520, x0 + 180, 620), fill=(240, 248, 255, 255))
        d.line((x0 + 20, 520, x0 + 180, 520), fill=SCHWARZ, width=12)
        d.line((x0 + 20, 620, x0 + 180, 620), fill=SCHWARZ, width=12)
        d.line((x0 + 50, 440, x0 + 50, 490), fill=(255, 255, 255, 200), width=18)


def konserven(d):
    for x0, y0 in ((250, 470), (510, 470), (380, 250)):
        rr(d, (x0, y0, x0 + 240, y0 + 300), 30, (165, 170, 178, 255))
        d.ellipse((x0, y0 - 30, x0 + 240, y0 + 50), fill=(205, 210, 215, 255), outline=SCHWARZ, width=K)
        d.rectangle((x0 + 14, y0 + 110, x0 + 226, y0 + 200), fill=(200, 80, 60, 255))
        d.line((x0 + 14, y0 + 110, x0 + 226, y0 + 110), fill=SCHWARZ, width=12)
        d.line((x0 + 14, y0 + 200, x0 + 226, y0 + 200), fill=SCHWARZ, width=12)


def erste_hilfe(d):
    rr(d, (400, 250, 620, 360), 40, None)
    rr(d, (230, 330, 790, 760), 60, (205, 50, 55, 255))
    d.rectangle((460, 420, 560, 680), fill=(250, 248, 240, 255))
    d.rectangle((380, 500, 640, 600), fill=(250, 248, 240, 255))


def medikamente(d):
    rr(d, (330, 330, 610, 790), 40, (235, 160, 60, 255))
    rr(d, (300, 230, 640, 350), 30, (250, 248, 240, 255))
    d.rectangle((345, 470, 595, 640), fill=(250, 248, 240, 255))
    d.rectangle((440, 500, 500, 610), fill=(205, 50, 55, 255))
    d.rectangle((415, 525, 525, 585), fill=(205, 50, 55, 255))
    rr(d, (620, 560, 780, 640), 40, (250, 248, 240, 255), 18)
    d.line((700, 565, 700, 635), fill=SCHWARZ, width=14)


def radio(d):
    d.line((620, 330, 760, 180), fill=SCHWARZ, width=22)
    d.ellipse((740, 160, 790, 210), fill=SCHWARZ)
    rr(d, (210, 330, 810, 750), 60, (105, 110, 120, 255))
    d.ellipse((260, 400, 540, 680), fill=(60, 62, 70, 255), outline=SCHWARZ, width=K)
    for r in (40, 85):
        d.ellipse((400 - r, 540 - r, 400 + r, 540 + r), outline=(150, 150, 160, 255), width=12)
    rr(d, (580, 410, 760, 500), 16, (240, 200, 90, 255), 16)
    d.ellipse((600, 560, 680, 640), fill=(220, 220, 225, 255), outline=SCHWARZ, width=16)
    d.ellipse((690, 560, 770, 640), fill=(220, 220, 225, 255), outline=SCHWARZ, width=16)
    d.line((180, 560, 210, 560), fill=SCHWARZ, width=K)
    rr(d, (130, 520, 200, 600), 18, (105, 110, 120, 255), 18)


def taschenlampe(d):
    d.polygon([(560, 330), (850, 170), (850, 650), (560, 490)], fill=(255, 240, 150, 150))
    rr(d, (200, 360, 520, 470), 30, (70, 75, 85, 255))
    d.polygon([(500, 330), (600, 300), (600, 530), (500, 500)], fill=(70, 75, 85, 255), outline=SCHWARZ)
    d.line([(500, 330), (600, 300), (600, 530), (500, 500), (500, 330)], fill=SCHWARZ, width=K, joint="curve")
    d.ellipse((575, 300, 625, 530), fill=(255, 245, 180, 255), outline=SCHWARZ, width=16)
    rr(d, (300, 380, 360, 450), 10, (205, 50, 55, 255), 12)


def bargeld(d):
    for dx, dy, farbe in ((-30, 70, (90, 160, 100, 255)), (0, 0, (120, 190, 120, 255))):
        rr(d, (230 + dx, 330 + dy, 790 + dx, 640 + dy), 30, farbe)
        d.ellipse((430 + dx, 400 + dy, 590 + dx, 570 + dy), fill=(200, 235, 190, 255), outline=SCHWARZ, width=16)
        d.rectangle((270 + dx, 370 + dy, 330 + dx, 410 + dy), fill=(200, 235, 190, 255))
        d.rectangle((690 + dx, 560 + dy, 750 + dx, 600 + dy), fill=(200, 235, 190, 255))
    for x, y in ((600, 690), (680, 720)):
        d.ellipse((x, y, x + 130, y + 90), fill=(240, 195, 70, 255), outline=SCHWARZ, width=16)


ZEICHNER = {"wasser": wasser, "konserven": konserven, "erste_hilfe": erste_hilfe, "medikamente": medikamente,
            "radio": radio, "taschenlampe": taschenlampe, "bargeld": bargeld}


def zeichne(name: str, ziel: Path):
    im, d = blase()
    ZEICHNER[name](d)
    im.resize((256, 256), Image.LANCZOS).save(ziel)


def main():
    p = argparse.ArgumentParser(description="Pop-up-Icons zeichnen")
    p.add_argument("--neu", action="store_true")
    a = p.parse_args()
    ZIEL.mkdir(parents=True, exist_ok=True)
    eigene = set((ZIEL / "eigene.txt").read_text().split()) if (ZIEL / "eigene.txt").exists() else set()
    for name in ZEICHNER:
        ziel = ZIEL / f"{name}.png"
        if name in eigene or (ziel.exists() and not a.neu):
            continue
        zeichne(name, ziel)
        print(f"  {ziel.relative_to(ROOT)}")
    # Vorschau
    bilder = [Image.open(ZIEL / f"{n}.png") for n in ZEICHNER if (ZIEL / f"{n}.png").exists()]
    vorschau = Image.new("RGBA", (256 * len(bilder), 256), (40, 45, 60, 255))
    for i, b in enumerate(bilder):
        vorschau.alpha_composite(b, (i * 256, 0))
    vorschau.convert("RGB").save(ZIEL / "vorschau.jpg", quality=85)
    print(f"Vorschau: {(ZIEL / 'vorschau.jpg').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
