#!/usr/bin/env python3
"""Vertonung mit ElevenLabs: ganzer Sprechertext in EINER Anfrage (natürlicher Fluss), mit Zeitstempeln.

Benutzung (aus dem Repo-Hauptordner):
    python3 tools/vertonung.py videos/01-der-chips-einkauf          # zeigt Zeichenzahl, fragt vor dem Senden
    python3 tools/vertonung.py videos/01-der-chips-einkauf --neu    # vorhandene Aufnahme ersetzen (kostet)
    python3 tools/vertonung.py videos/01-der-chips-einkauf --nur-schneiden   # vorhandene Aufnahme neu aufteilen (gratis)
    python3 tools/vertonung.py --probe "Zombie-Apokalypse, Tag eins." --modelle eleven_v4,eleven_multilingual_v2 --tempi 1.0

Ergebnis in videos/<ordner>/medien/:
    vo-voll.mp3 + vo-voll.json   ganze Aufnahme + Zeitstempel pro Zeichen (von ElevenLabs)
    vo-NN.wav  + vo-NN.json      pro Szene geschnitten, mit Wort-Zeiten (für Untertitel und Pop-ups)

Stimme, Modell und Einstellungen: bausteine/stimme.toml (kein Geheimnis).
API-Schlüssel NUR aus ELEVENLABS_API_KEY (Umgebung oder .env, steht in .gitignore). In der Cloud setzt ihn der Proxy ein.

Schnittstelle laut ElevenLabs-Doku (gelesen 2026-11-05,
https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps):
    POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128
    JSON: text, model_id, voice_settings -> Antwort: audio_base64, alignment{characters,
    character_start_times_seconds, character_end_times_seconds}, normalized_alignment
Audio-Tags wie [sarcastic] laut Doku nur bei eleven_v4 / eleven_v4_turbo / eleven_v3. Bei anderen Modellen
werden sie hier vor dem Senden entfernt. eleven_v4 hat laut Doku keine Style- und Speed-Regler.
Jede Anfrage verbraucht Guthaben in deinem ElevenLabs-Konto.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jack import ROOT, Mappe, fuer_tts  # noqa: E402

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128"
STIMME = ROOT / "bausteine" / "stimme.toml"
TAG_MODELLE = {"eleven_v4", "eleven_v4_turbo", "eleven_v3", "eleven_v3_conversational"}
OHNE_SPEED_STYLE = {"eleven_v4", "eleven_v4_turbo"}


def lade_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for zeile in env.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            k, v = zeile.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def einstellungen_fuer(modell: str, basis: dict) -> dict:
    e = dict(basis)
    if modell in OHNE_SPEED_STYLE:
        e.pop("speed", None)
        e.pop("style", None)
    return e


def tts(text: str, stimme: str, modell: str, einstellungen: dict) -> dict:
    schluessel = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    body = {"text": text, "model_id": modell}
    if einstellungen:
        body["voice_settings"] = einstellungen
    req = urllib.request.Request(
        API.format(voice_id=stimme), data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **({"xi-api-key": schluessel} if schluessel else {})})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs hat mit {e.code} geantwortet: {e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"ElevenLabs nicht erreichbar ({e.reason}). Netzwerkzugriff auf api.elevenlabs.io prüfen.")


def frage(text: str, ja: bool) -> bool:
    print(text)
    if ja:
        return True
    return input("Senden? [j/N] ").strip().lower() in ("j", "ja", "y", "yes")


def audio_dauer(datei: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(datei)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout)


def lade_cfg() -> dict:
    return tomllib.loads(STIMME.read_text(encoding="utf-8")) if STIMME.exists() else {}


# ---------------------------------------------------------------- Aufteilen nach Zeitstempeln

def zeiten_fuer_text(gesendet: str, al: dict) -> tuple[list[float], list[float]]:
    """Start-/Endzeit für jedes Zeichen des gesendeten Textes. Normalfall: alignment.characters == gesendeter Text.
    Sonst (z. B. Tags entfernt) per Abgleich der Buchstaben in Reihenfolge."""
    zeichen = al["characters"]
    st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
    if "".join(zeichen) == gesendet:
        return list(st), list(en)
    starts, endes, j = [], [], 0
    for c in gesendet:
        k = j
        while k < len(zeichen) and zeichen[k].lower() != c.lower():
            k += 1
        if k < len(zeichen) and c.strip():
            j = k
        idx = min(j, len(zeichen) - 1)
        starts.append(st[idx])
        endes.append(en[idx])
        if k < len(zeichen) and c.strip():
            j += 1
    return starts, endes


def teile_auf(medien: Path, texte: list[str], gesendet: str, al: dict):
    """vo-voll.mp3 an den Szenengrenzen schneiden, Wort-Zeiten pro Szene speichern."""
    voll = medien / "vo-voll.mp3"
    gesamt = audio_dauer(voll)
    starts, endes = zeiten_fuer_text(gesendet, al)
    # Lage jeder Szene im gesendeten Text
    lagen, pos = [], 0
    for t in texte:
        a = gesendet.find(t, pos)
        lagen.append((a, a + len(t)))
        pos = a + len(t)
    grenzen = [0.0]
    for k in range(len(texte) - 1):
        ende_k = endes[lagen[k][1] - 1]
        start_n = starts[lagen[k + 1][0]]
        grenzen.append((ende_k + start_n) / 2)
    grenzen.append(gesamt)
    print(f"Gesamt {gesamt:.2f} s. Szenen:")
    for k, t in enumerate(texte):
        a, e = grenzen[k], grenzen[k + 1]
        ziel = medien / f"vo-{k + 1:02d}.wav"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(voll), "-af",
                            f"atrim={a:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,"
                            f"afade=t=out:st={max(0, e - a - 0.03):.3f}:d=0.03", "-ar", "44100", str(ziel)],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr)
        woerter = []
        for m in re.finditer(r"\[[^\]]*\]|\S+", t):
            if m.group().startswith("["):
                continue  # Audio-Tag, wird nicht gesprochen/untertitelt
            i0, i1 = lagen[k][0] + m.start(), lagen[k][0] + m.end() - 1
            woerter.append({"wort": m.group(), "start": round(starts[i0] - a, 3), "ende": round(endes[i1] - a, 3)})
        sprech_ende = woerter[-1]["ende"] if woerter else e - a
        (medien / f"vo-{k + 1:02d}.json").write_text(json.dumps(
            {"dauer": round(e - a, 3), "sprech_start": woerter[0]["start"] if woerter else 0.0,
             "sprech_ende": sprech_ende, "woerter": woerter}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  Szene {k + 1:02d}: {a:6.2f}-{e:6.2f} s  gesprochen {sprech_ende - (woerter[0]['start'] if woerter else 0):.2f} s")


# ---------------------------------------------------------------- Befehle

def probe(satz: str, modelle: list[str], tempi: list[float], stimme: str, cfg: dict, ja: bool):
    ziel = ROOT / "proben"
    ziel.mkdir(exist_ok=True)
    auftraege = []
    for m in modelle:
        for t in (tempi if m not in OHNE_SPEED_STYLE else [None]):
            text = fuer_tts(satz, tags=m in TAG_MODELLE)
            auftraege.append((m, t, text))
    zeichen = sum(len(x[2]) for x in auftraege)
    zeilen = "\n".join(f"  {m:24} Tempo {t if t else '– (nicht einstellbar)'}: {len(x)} Zeichen" for m, t, x in auftraege)
    if not frage(f"Probe: {len(auftraege)} Anfrage(n), zusammen {zeichen} Zeichen.\n{zeilen}\n"
                 "Das verbraucht Guthaben in deinem ElevenLabs-Konto.", ja):
        print("Abgebrochen, nichts gesendet.")
        return
    for m, t, text in auftraege:
        e = einstellungen_fuer(m, cfg.get("voice_settings", {}))
        if t:
            e["speed"] = t
        antwort = tts(text, stimme, m, e)
        name = f"probe-{m}" + (f"-tempo{t}" if t else "")
        (ziel / f"{name}.mp3").write_bytes(base64.b64decode(antwort["audio_base64"]))
        al = antwort.get("alignment") or {}
        d = audio_dauer(ziel / f"{name}.mp3")
        woerter = len(re.sub(r"\[[^\]]*\]", " ", text).split())
        gesprochen = al.get("characters") and "".join(al["characters"]) == text
        print(f"  {name}.mp3: {d:.2f} s, {woerter / d:.2f} Wörter/s, Zeitstempel {'passen zum Text' if gesprochen else 'weichen ab'}")
    print(f"Proben in {ziel.relative_to(ROOT)}/ – bitte anhören, dann Modell und speed in bausteine/stimme.toml eintragen.")


def main():
    p = argparse.ArgumentParser(description="Voiceover mit ElevenLabs erzeugen")
    p.add_argument("ordner", nargs="?")
    p.add_argument("--ja", action="store_true", help="ohne Rückfrage senden")
    p.add_argument("--neu", action="store_true", help="vorhandene Aufnahme ersetzen (kostet Guthaben)")
    p.add_argument("--nur-schneiden", action="store_true", help="vorhandene vo-voll.mp3 neu aufteilen (gratis)")
    p.add_argument("--tempo", type=float, help="speed 0.7-1.2 (nicht bei eleven_v4)")
    p.add_argument("--stabilitaet", type=float, help="stability 0-1")
    p.add_argument("--modell", help="anderes Modell als in stimme.toml")
    p.add_argument("--probe", metavar="SATZ", help="kurzen Testsatz vertonen (nach proben/)")
    p.add_argument("--modelle", default="", help="mit --probe: Modelle, kommagetrennt")
    p.add_argument("--tempi", default="1.0", help="mit --probe: Tempi, kommagetrennt")
    a = p.parse_args()

    lade_env()
    cfg = lade_cfg()
    stimme = os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or cfg.get("voice_id", "")
    modell = a.modell or os.environ.get("ELEVENLABS_MODEL_ID", "").strip() or cfg.get("model_id", "eleven_multilingual_v2")
    if not stimme:
        sys.exit("Keine Stimme: voice_id in bausteine/stimme.toml eintragen.")

    if a.probe:
        modelle = [x.strip() for x in a.modelle.split(",") if x.strip()] or [modell]
        probe(a.probe, modelle, [float(x) for x in a.tempi.split(",")], stimme, cfg, a.ja)
        return
    if not a.ordner:
        p.error("Video-Ordner fehlt (oder --probe nutzen).")

    ordner = Path(a.ordner).resolve()
    m = Mappe(ordner)
    medien = ordner / "medien"
    medien.mkdir(parents=True, exist_ok=True)
    tags = modell in TAG_MODELLE
    texte = [fuer_tts(s.get("sprechertext", ""), tags=tags) for s in m.szenen]
    gesendet = " ".join(texte)
    voll, info = medien / "vo-voll.mp3", medien / "vo-voll.json"

    if a.nur_schneiden or (voll.exists() and info.exists() and not a.neu):
        if not info.exists():
            sys.exit("Keine vo-voll.json vorhanden – erst vertonen.")
        gespeichert = json.loads(info.read_text(encoding="utf-8"))
        if gespeichert["text"] != gesendet:
            sys.exit("Der Sprechertext hat sich seit der Aufnahme geändert. Mit --neu neu vertonen (kostet).")
        print(f"Nutze vorhandene Aufnahme ({gespeichert['modell']}), nichts gesendet.")
        teile_auf(medien, texte, gesendet, gespeichert["alignment"])
        return

    e = einstellungen_fuer(modell, cfg.get("voice_settings", {}))
    if a.tempo and modell not in OHNE_SPEED_STYLE:
        e["speed"] = a.tempo
    if a.stabilitaet is not None:
        e["stability"] = a.stabilitaet
    hinweis = "" if tags or "[" not in " ".join(s.get("sprechertext", "") for s in m.szenen) else \
        "\nHinweis: Audio-Tags werden entfernt, weil dieses Modell sie laut Doku nicht unterstützt."
    if not frage(f"1 Anfrage, {len(gesendet)} Zeichen, Modell {modell}, Stimme {stimme}, Einstellungen {e}.{hinweis}\n"
                 "Das verbraucht Guthaben in deinem ElevenLabs-Konto.", a.ja):
        print("Abgebrochen, nichts gesendet.")
        return
    antwort = tts(gesendet, stimme, modell, e)
    voll.write_bytes(base64.b64decode(antwort["audio_base64"]))
    al = antwort.get("alignment") or antwort.get("normalized_alignment")
    if not al:
        sys.exit("Antwort ohne Zeitstempel – Aufteilung nicht möglich.")
    info.write_text(json.dumps({"text": gesendet, "modell": modell, "stimme": stimme, "einstellungen": e,
                                "alignment": al}, ensure_ascii=False), encoding="utf-8")
    teile_auf(medien, texte, gesendet, al)
    print(f"Fertig. Jetzt schneiden: python3 tools/schnitt.py {ordner.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
