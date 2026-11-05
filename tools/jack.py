#!/usr/bin/env python3
"""Jack-Pipeline: aus einer Themen-Datei (thema.toml) eine Video-Mappe erzeugen.

Benutzung (aus dem Repo-Hauptordner):
    python3 tools/jack.py neu 02 der-wasserkanister --titel "Der Wasserkanister"
    python3 tools/jack.py baue videos/01-der-chips-einkauf
    python3 tools/jack.py pruefe-bausteine

Braucht nur Python 3.11 oder neuer, keine Zusatzpakete.
"""
from __future__ import annotations

import argparse
import ast
import operator
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAUSTEINE = ROOT / "bausteine" / "bausteine.toml"
VORLAGE = ROOT / "tools" / "vorlage-thema.toml"

PAUSE = "[pause]"
TEILE = ["hook", "falscher_plan", "fakt", "eskalation", "schluss"]
WOERTER_PRO_SEKUNDE = 2.3  # nur für den Hook-Check
ZEICHEN_PRO_SEKUNDE = 14.5  # Schätzung (deutsche Komposita!); nach der Vertonung gelten echte Zeiten
SRT_WOERTER_PRO_ZEILE = 6
NACHLAUF = 0.4             # Schätzung: Luft nach dem Sprechertext
CLIP_ENDUNGEN = (".mp4", ".mov", ".webm", ".mkv")
BILD_ENDUNGEN = (".png", ".jpg", ".jpeg", ".webp")
PROMPT_FELDER = ("scene", "action", "camera", "mood", "expression")


# ---------------------------------------------------------------- Hilfen

def lade_toml(pfad: Path) -> dict:
    with open(pfad, "rb") as f:
        return tomllib.load(f)


def ohne_tags(text: str) -> str:
    """Audio-Tags wie [sarcastic] und [pause] entfernen (für Untertitel, Wortzahl)."""
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", text or "")).strip()


def woerter(text: str) -> int:
    return len(re.findall(r"\S+", ohne_tags(text)))


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg}


def rechne(ausdruck: str) -> float:
    """Sicheres Nachrechnen: nur Zahlen, + - * / und Klammern."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError(f"Nicht erlaubter Ausdruck: {ausdruck!r}")
    return ev(ast.parse(ausdruck.replace(",", "."), mode="eval"))


def zeit_srt(sek: float) -> str:
    ms = int(round(sek * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def fuer_tts(text: str, tags: bool = True) -> str:
    """Sprechertext für ElevenLabs aufbereiten. tags=False entfernt Audio-Tags (Modelle ohne Tag-Support)."""
    t = (text or "").replace(PAUSE, " ")
    if not tags:
        t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"(\d)\s*€", r"\1 Euro", t).replace("€", "Euro")
    t = re.sub(r"(\d)\s*%", r"\1 Prozent", t)
    t = re.sub(r"[*_#`]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def saetze(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", ohne_tags(text)) if x]


def saetze_mit_zahlen(text: str) -> list[str]:
    zahlwort = r"\b(null|eins?|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|zwanzig|dreißig|vierzig|fünfzig|hundert)\b"
    return [s for s in saetze(text) if re.search(r"\d", s) or re.search(zahlwort, s, re.IGNORECASE)]


# ---------------------------------------------------------------- Mappe

class Mappe:
    def __init__(self, ordner: Path):
        self.ordner = ordner
        self.b = lade_toml(BAUSTEINE)
        self.t = lade_toml(ordner / "thema.toml")
        self.v = self.t.get("video", {})
        self.szenen = self.t.get("szene", [])
        self.fehler: list[str] = []
        self.warnungen: list[str] = []
        for i, s in enumerate(self.szenen, 1):
            s["_nn"] = f"{i:02d}"
            s["_text"] = ohne_tags(s.get("sprechertext", ""))
        self._timing()

    def _timing(self):
        """Geschätzte Zeiten: Szene dauert so lange wie der Clip, mindestens so lange wie die Stimme."""
        start = 0.0
        for s in self.szenen:
            sprech = len(ohne_tags(s.get("sprechertext", ""))) / ZEICHEN_PRO_SEKUNDE
            s["_sprech"] = sprech
            d = max(float(s.get("clip_dauer", 8)), sprech + NACHLAUF)
            s["_start"], s["_ende"] = start, start + d
            start += d
        self.dauer = start

    # --- Bausteine
    def baustein(self, gruppe: str, wert: str, s: dict) -> str:
        """Name eines Bausteins -> Text. Text mit Leerzeichen = eigener Satz, wird direkt übernommen."""
        wert = (wert or "").strip()
        if not wert:
            return ""
        if wert in self.b.get(gruppe, {}):
            return self.b[gruppe][wert]
        if " " in wert:
            return wert
        self.fehler.append(f"Szene {s['_nn']}: unbekannter {gruppe}-Baustein '{wert}'. "
                           f"Erlaubt: {', '.join(self.b.get(gruppe, {}))} oder ein eigener Satz.")
        return ""

    def felder(self, s: dict) -> dict:
        action = s.get("action", "").strip()
        for k in s.get("booster", []):
            extra = self.baustein("booster", k, s)
            if extra:
                action = f"{action} {extra}".strip()
        for k in s.get("korrektur", []):
            extra = self.baustein("korrektur", k, s)
            if extra:
                action = f"{action} {extra}".strip()
        return {
            "scene": s.get("scene", "").strip(),
            "action": action,
            "camera": self.baustein("kamera", s.get("camera", ""), s),
            "mood": self.baustein("stimmung", s.get("mood", ""), s),
            "expression": self.baustein("mimik", s.get("expression", ""), s),
        }

    def flow_prompt(self, s: dict) -> str:
        f, fl = self.felder(s), self.b["flow"]
        satz = lambda x: x.strip().rstrip(".") + "." if x.strip() else "TODO"  # noqa: E731
        return "\n".join([
            fl["intro"],
            fl["character"],
            f"Scene: {satz(f['scene'])}",
            f"Action: {satz(f['action'])}",
            f"Camera: {satz(f['camera'])}",
            f"Mood and lighting: {satz(f['mood'])}",
            f"Jack's expression: {satz(f['expression'])}",
            fl["schluss"],
        ])

    # --- Medien (gemeinsam mit schnitt.py)
    def medien_fuer(self, s: dict) -> list[str]:
        """Clips/Bilder einer Szene: medien = [...] in thema.toml, sonst Dateien nach Namensschema
        <nummer>-szene-<NN>*.mp4 in eingang/ oder bibliothek/clips/ (z. B. 01-szene-03.mp4)."""
        if s.get("medien"):
            return s["medien"] if isinstance(s["medien"], list) else [s["medien"]]
        muster = f"{self.v.get('nummer', '00')}-szene-{s['_nn']}"
        gefunden = []
        for ordner in (ROOT / "eingang", ROOT / "bibliothek" / "clips", ROOT / "bibliothek" / "bilder"):
            if ordner.exists():
                gefunden += sorted(str(p.relative_to(ROOT)) for p in ordner.rglob(f"{muster}*")
                                   if p.suffix.lower() in CLIP_ENDUNGEN + BILD_ENDUNGEN)
        return gefunden

    # --- Prüfungen
    def pruefe(self):
        p, v = self.b["pruefung"], self.v
        texte = " ".join(" ".join([s.get("sprechertext", ""), s.get("einblendtext", "")]) for s in self.szenen)
        texte += " " + v.get("caption", "") + " " + " ".join(v.get("hashtags", []))
        prompts = " ".join(self.flow_prompt(s) for s in self.szenen)
        for marke in p["markennamen"]:
            if re.search(rf"(?<![\w-]){re.escape(marke)}(?![\w-])", texte + " " + prompts, re.IGNORECASE):
                self.fehler.append(f"Markenname gefunden: '{marke}' – bitte neutral beschreiben.")
        for wort in p["gewalt"]:
            frei = " ".join(" ".join(self.felder(s).values()) for s in self.szenen) + " " + texte
            if re.search(rf"\b{re.escape(wort)}", frei, re.IGNORECASE):
                self.fehler.append(f"Gewalt/Blut: '{wort}' gefunden – kein Blut, keine drastische Gewalt.")
        if "TODO" in str(self.t):
            self.warnungen.append("Es stehen noch TODO-Platzhalter in thema.toml.")

        teile = [s.get("teil") for s in self.szenen]
        for t in teile:
            if t not in TEILE:
                self.fehler.append(f"Unbekannter Teil '{t}'. Erlaubt: {', '.join(TEILE)}")
        for pflicht in TEILE:
            if pflicht not in teile:
                self.warnungen.append(f"Kein Szenen-Teil '{pflicht}' – gehört zum Aufbau "
                                      "(Hook, falscher Plan, Fakt, Eskalation, Schluss mit Frage).")
        if teile and teile[0] != "hook":
            self.warnungen.append("Die erste Szene ist kein Hook.")
        if self.szenen:
            erster = saetze(self.szenen[0].get("sprechertext", ""))[:1]
            sek = woerter(erster[0]) / WOERTER_PRO_SEKUNDE if erster else 0
            if sek > p["hook_max_sekunden"]:
                self.warnungen.append(f"Erster Hook-Satz dauert ca. {sek:.1f} s (Ziel: Hook in den ersten 3 s).")
            if not self.szenen[-1]["_text"].rstrip().endswith("?"):
                self.fehler.append("Der Schluss endet nicht mit einer Frage an die Zuschauer.")

        # Pflicht: Überlebenschance in jedem Video (und jeder Szene)
        for s in self.szenen:
            c = s.get("chance")
            if c is None:
                self.fehler.append(f"Szene {s['_nn']}: keine Überlebenschance (chance = 0-100).")
            elif not (isinstance(c, int) and 0 <= c <= 100):
                self.fehler.append(f"Szene {s['_nn']}: chance muss eine ganze Zahl von 0 bis 100 sein.")

        for s in self.szenen:
            nn, f = s["_nn"], self.felder(s)
            if len(s.get("booster", [])) > 1:
                self.warnungen.append(f"Szene {nn}: mehr als 1 Booster – pro Clip eine Hauptaktion.")
            for feld in PROMPT_FELDER:
                if self.v.get("nur_bibliothek"):
                    break
                if not f[feld]:
                    self.fehler.append(f"Szene {nn}: Feld '{feld}' ist leer.")
                if re.search(r"\d", f[feld]):
                    self.warnungen.append(f"Szene {nn}: Ziffern in '{feld}' – Flow schreibt dann evtl. Text ins Bild.")
                if re.search(r"[\"„“]", f[feld]) or re.search(r"\b(sign|label|caption|text|lettering|writing)\b", f[feld], re.I):
                    self.warnungen.append(f"Szene {nn}: '{feld}' erwähnt Schrift/Schilder – kein Text in Flow.")
            scene, action = f["scene"].lower(), f["action"].lower()
            voll = [w for w in p["voll_woerter"] if re.search(rf"\b{re.escape(w)}\b", scene + " " + action)]
            fuell = [w for w in p["fuell_woerter"] if re.search(rf"\b{re.escape(w)}\b", action)]
            if voll and fuell:
                self.warnungen.append(f"Szene {nn}: möglicher Widerspruch – Prompt sagt '{voll[0]}', "
                                      f"Action füllt erst ('{fuell[0]}'). Startzustand beschreiben (z. B. 'empty').")
            if any(w in f["camera"].lower() for w in p["fest_kamera"]) and not s.get("kamera_fest_ok"):
                self.warnungen.append(f"Szene {nn}: feste Kamera – nur wenn ein Clip sonst fehlerhaft war "
                                      "(dann kamera_fest_ok = true).")
            for e in s.get("einblendungen", []):
                if e.get("wort") and e["wort"].lower() not in s["_text"].lower():
                    self.fehler.append(f"Szene {nn}: Einblend-Wort '{e['wort']}' kommt im Sprechertext nicht vor.")
            if self.v.get("nur_bibliothek") and not self.medien_fuer(s):
                self.fehler.append(f"Szene {nn}: nur_bibliothek, aber keine medien angegeben.")
            namen = self.b["icons"]["namen"]
            for pop in s.get("popup", []):
                if pop.get("icon") not in namen:
                    self.fehler.append(f"Szene {nn}: unbekanntes Icon '{pop.get('icon')}'. Erlaubt: {', '.join(namen)}")
                if pop.get("wort", "").lower() not in s["_text"].lower():
                    self.fehler.append(f"Szene {nn}: Pop-up-Wort '{pop.get('wort')}' kommt im Sprechertext nicht vor.")

        self.rechen_ergebnisse = []
        for r in self.t.get("rechnung", []):
            try:
                ist = rechne(r["ausdruck"])
                ok = abs(ist - float(r["ergebnis"])) < 0.005
            except Exception as e:  # noqa: BLE001
                ist, ok = f"Fehler: {e}", False
            self.rechen_ergebnisse.append((r, ist, ok))
            if not ok:
                self.fehler.append(f"Rechnung stimmt nicht: {r['ausdruck']} = {ist}, angegeben {r['ergebnis']}.")

        for f in self.t.get("fakt", []):
            st = f.get("status", "offen")
            if st.startswith("geprueft") and not f.get("quelle"):
                self.fehler.append(f"Fakt ohne Quelle als geprüft markiert: {f.get('text', '')[:60]}")
            elif not st.startswith("geprueft"):
                self.warnungen.append(f"Fakt offen: {f.get('text', '')[:70]}")

        if not p["dauer_min"] <= self.dauer <= p["dauer_max"]:
            self.warnungen.append(f"Geschätzte Dauer {self.dauer:.0f} s (Ziel {p['dauer_min']}-{p['dauer_max']} s).")

    # --- Dateien
    def kopf(self, titel: str) -> str:
        return (f"# {titel}: {self.v.get('titel', '')}\n\n"
                "_Automatisch erzeugt aus `thema.toml` – Änderungen bitte dort machen und neu bauen._\n\n")

    def schreibe(self):
        v, o = self.v, self.ordner
        zeit = lambda s: f"ca. {s['_start']:.0f}–{s['_ende']:.0f} s"  # noqa: E731

        # skript.md
        z = [self.kopf("Skript"),
             f"- **Thema:** {v.get('thema', '')}\n- **Lerneffekt:** {v.get('lerneffekt', '')}\n",
             f"- **Ton:** {v.get('ton', '')}\n",
             f"- **Wörter:** {self.wortzahl} · **geschätzte Dauer:** ca. {self.dauer:.0f} s\n\n"]
        for s in self.szenen:
            z.append(f"## {s['_nn']} {s.get('name', '')} ({s.get('teil', '')}, {zeit(s)})\n\n"
                     f"**Erzähler:** {s.get('sprechertext', '').strip()}\n\n"
                     f"**Überlebenschance:** {s.get('chance', '–')} %\n\n")
            if s.get("einblendtext"):
                z.append(f"**Einblendung:** {s['einblendtext']}\n\n")
            if s.get("einblendungen"):
                z.append("**Einblendungen nacheinander:** " + " → ".join(f"„{e['text']}“" for e in s["einblendungen"]) + "\n\n")
            if s.get("medien"):
                z.append(f"**Clip:** {', '.join(f'`{x}`' for x in self.medien_fuer(s))}\n\n")
            if s.get("popup"):
                z.append("**Pop-ups (zur Stimme):** " + ", ".join(f"{p['icon']} bei „{p['wort']}“" for p in s["popup"]) + "\n\n")
        (o / "skript.md").write_text("".join(z), encoding="utf-8")

        # szenen.md
        z = [self.kopf("Szenenliste")]
        for s in self.szenen:
            z.append(f"## {s['_nn']}. {s.get('name', '')} ({s.get('teil', '')}, {zeit(s)}, Clip {s.get('clip_dauer', 8)} s)\n\n"
                     f"- **Bild (de):** {s.get('bild_de', '')}\n"
                     f"- **Sprechertext:** {s.get('sprechertext', '').strip()}\n"
                     f"- **Überlebenschance:** {s.get('chance', '–')} %\n"
                     f"- **Einblendtext:** {' → '.join([s['einblendtext']] if s.get('einblendtext') else [e['text'] for e in s.get('einblendungen', [])]) or '–'}\n"
                     f"- **Pop-ups:** {', '.join(p['icon'] + ' @ ' + p['wort'] for p in s.get('popup', [])) or '–'}\n"
                     f"- **Medien:** {', '.join(self.medien_fuer(s)) or 'noch keine'}\n\n")
        (o / "szenen.md").write_text("".join(z), encoding="utf-8")

        # prompts.md
        if v.get("nur_bibliothek"):
            z = [self.kopf("Flow-Prompts"), "Diese Folge nutzt nur vorhandene Clips aus `bibliothek/clips/` – keine neuen Flow-Clips.\n\n"]
            z += [f"- Szene {s['_nn']} {s.get('name', '')}: {', '.join(f'`{x}`' for x in self.medien_fuer(s))}"
                  + (f" – {s['hinweis_schnitt']}" if s.get("hinweis_schnitt") else "") + "\n" for s in self.szenen]
            (o / "prompts.md").write_text("".join(z), encoding="utf-8")
        else:
            self._schreibe_prompts()
        self._schreibe_rest()

    def _schreibe_prompts(self):
        v, o = self.v, self.ordner
        z = [self.kopf("Flow-Prompts"),
             f"Referenzbild bei jedem Prompt mit hochladen: `{v.get('referenzbild', 'TODO')}`\n\n",
             "Kein Text in Flow: Schrift, Zahlen, Überlebenschance und Pop-up-Icons kommen im Schnitt dazu.\n\n"]
        for s in self.szenen:
            z.append(f"## {s['_nn']}. {s.get('name', '')} ({s.get('clip_dauer', 8)} s)\n\n"
                     f"Datei danach: `eingang/{v.get('nummer', '00')}-szene-{s['_nn']}.mp4`\n\n"
                     f"```\n{self.flow_prompt(s)}\n```\n\n")
            if s.get("hinweis_flow"):
                z.append(f"> Hinweis: {s['hinweis_flow']}\n\n")
        z.append("## Falls ein Clip fehlerhaft ist\n\nNur dann in `thema.toml` bei der Szene `korrektur = [\"name\"]` "
                 "ergänzen und neu bauen. Verfügbar:\n\n")
        z += [f"- `{k}`: {t}\n" for k, t in self.b["korrektur"].items()]
        (o / "prompts.md").write_text("".join(z), encoding="utf-8")

    def _schreibe_rest(self):
        v, o = self.v, self.ordner

        # faktencheck.md
        z = [self.kopf("Faktencheck"),
             "Jede Sachbehauptung braucht eine Quelle oder ist **offen**. Automatisch gefunden heißt nicht geprüft.\n\n",
             "## Rechnungen (automatisch nachgerechnet)\n\n"]
        for r, ist, ok in self.rechen_ergebnisse:
            z.append(f"- {'✅' if ok else '❌'} {r.get('beschreibung', '')}: `{r['ausdruck']}` = {ist} "
                     f"(angegeben: {r['ergebnis']} {r.get('einheit', '')}) – {r.get('hinweis', '')}\n")
        if not self.rechen_ergebnisse:
            z.append("- keine Rechnungen eingetragen\n")
        z.append("\n## Behauptungen\n\n")
        for f in self.t.get("fakt", []):
            st = f.get("status", "offen")
            symbol = "✅" if st.startswith("geprueft") else "❓"
            z.append(f"- {symbol} **{st}** (Szene {f.get('szene', '–')}): {f.get('text', '')}\n")
            if f.get("quelle"):
                z.append(f"  - Quelle: {f['quelle']}\n")
            if f.get("beleg"):
                z.append(f"  - Beleg: {f['beleg']}\n")
            if f.get("notiz"):
                z.append(f"  - Notiz: {f['notiz']}\n")
        if not self.t.get("fakt"):
            z.append("- keine eingetragen\n")
        z.append("\n## Sätze mit Zahlen (gegen die Liste oben abgleichen)\n\n")
        for s in self.szenen:
            for satz in saetze_mit_zahlen(s.get("sprechertext", "")):
                z.append(f"- (Szene {s['_nn']}) {satz}\n")
        z.append("\n## Fiktiv (kein Faktencheck nötig)\n\n- „Überlebenschance: X %“ ist ein erfundener Gag-Wert, keine Statistik.\n")
        (o / "faktencheck.md").write_text("".join(z), encoding="utf-8")

        # untertitel.srt (geschätzt) und einblendungen.srt
        srt, nr = [], 1
        for s in self.szenen:
            w = s["_text"].split()
            if not w:
                continue
            stuecke = [w[i:i + SRT_WOERTER_PRO_ZEILE] for i in range(0, len(w), SRT_WOERTER_PRO_ZEILE)]
            t = s["_start"]
            for st in stuecke:
                d = s["_sprech"] * len(st) / len(w)
                srt.append(f"{nr}\n{zeit_srt(t)} --> {zeit_srt(t + d)}\n{' '.join(st)}\n")
                t += d
                nr += 1
        (o / "untertitel.srt").write_text("\n".join(srt), encoding="utf-8")
        ein, nr = [], 1
        for s in self.szenen:
            extra = ([s["einblendtext"]] if s.get("einblendtext") else []) + [e["text"] for e in s.get("einblendungen", [])]
            for txt in [f"Überlebenschance: {s.get('chance', '?')} %"] + extra:
                ein.append(f"{nr}\n{zeit_srt(s['_start'])} --> {zeit_srt(s['_ende'])}\n{txt}\n")
                nr += 1
        (o / "einblendungen.srt").write_text("\n".join(ein), encoding="utf-8")

        # voiceover.txt (mit Tags, so wie er an ElevenLabs geht)
        vo = "\n\n".join(fuer_tts(s.get("sprechertext", "")) for s in self.szenen if s.get("sprechertext"))
        (o / "voiceover.txt").write_text(vo + "\n", encoding="utf-8")

        # hochladen.md: welche Clips noch fehlen
        if v.get("nur_bibliothek"):
            (o / "hochladen.md").write_text(self.kopf("Hochladen") + "Nichts hochzuladen: diese Folge nutzt nur Clips aus `bibliothek/clips/`.\n", encoding="utf-8")
            return self._schreibe_checkliste()
        z = [self.kopf("Hochladen"), "Clips aus Flow nach `eingang/` hochladen, mit genau diesen Namen:\n\n",
             "| Szene | Datei | Länge | Status |\n|---|---|---|---|\n"]
        for s in self.szenen:
            m = self.medien_fuer(s)
            z.append(f"| {s['_nn']} {s.get('name', '')} | `eingang/{v.get('nummer', '00')}-szene-{s['_nn']}.mp4` | "
                     f"{s.get('clip_dauer', 8)} s | {'✅ ' + ', '.join(m) if m else 'fehlt'} |\n")
        (o / "hochladen.md").write_text("".join(z), encoding="utf-8")
        self._schreibe_checkliste()

    def _schreibe_checkliste(self):
        v, o = self.v, self.ordner

        # checkliste.md (immer manuell)
        auto = "".join(f"  - ❌ {x}\n" for x in self.fehler) + "".join(f"  - ⚠️ {x}\n" for x in self.warnungen)
        tags = " ".join(v.get("hashtags", []))
        (o / "checkliste.md").write_text(f"""{self.kopf("Veröffentlichungs-Checkliste")}Diese Liste hakst **du** vor dem Upload ab. Die Pipeline veröffentlicht nichts.

Automatische Prüfung beim letzten Bauen: {"keine Probleme gefunden" if not auto else ""}
{auto}
## Inhalt
- [ ] Alle Punkte in `faktencheck.md` geprüft (keine offenen Fakten mehr)
- [ ] Rechnungen stimmen (automatisch nachgerechnet, trotzdem ansehen)
- [ ] Echtes Vorsorgewissen drin: {v.get('lerneffekt', '')}
- [ ] Schluss mit Frage an die Zuschauer
- [ ] Einblendung „Überlebenschance: X %“ in jeder Szene sichtbar
- [ ] Kein Blut, keine drastische Gewalt
- [ ] Keine Markennamen oder Logos (Packungen, Kleidung, Untertitel, Caption)

## Bild und Ton
- [ ] Jack sieht in jedem Clip aus wie im Referenzbild (Schlappohren, Jacke, Jeans, weiße Sneaker, Schwanz)
- [ ] 2D-Look, kein 3D, kein Fotorealismus
- [ ] Kein Text/Kauderwelsch in Flow-Clips
- [ ] Hook in den ersten 3 Sekunden
- [ ] Pop-ups erscheinen passend zur Stimme
- [ ] Untertitel stimmen mit der Stimme überein

## KI-Kennzeichnung und Rechte (aktuelle Regeln vor jedem Upload kurz prüfen)
- [ ] **YouTube Shorts:** Beim Upload „Veränderte oder synthetische Inhalte“ beantworten. Laut YouTube-Hilfe (gelesen 2026-11-05,
      https://support.google.com/youtube/answer/14328491) ist die Angabe Pflicht bei realistisch wirkenden KI-Inhalten; klar
      unrealistische Animation ist als Beispiel ausgenommen. Bei Unsicherheit „Ja“ – die Angabe schränkt laut YouTube
      Reichweite und Monetarisierung nicht ein.
- [ ] **TikTok:** Schalter „KI-generierte Inhalte“ beim Posten (unter weitere Optionen) – aktuelle Regel in der App prüfen.
      Konnte am 2026-11-05 nicht automatisch gelesen werden (TikTok blockt Abrufe). Empfehlung: einschalten.
- [ ] **ElevenLabs-Lizenz:** Bezahlter Plan (ab Starter) aktiv – laut Preisseite (2026-11-05) enthält erst Starter die
      „Commercial License“, der Free-Plan nicht.
- [ ] Flow-Clips: Nutzungsbedingungen von Google Flow für eigene Uploads geprüft

## Upload (machst du selbst)
- [ ] Caption/Beschreibung: {v.get('caption', '')}
- [ ] Hashtags: {tags}
- [ ] Ergebnis in `log.md` eingetragen
""", encoding="utf-8")

    @property
    def wortzahl(self) -> int:
        return sum(woerter(s.get("sprechertext", "")) for s in self.szenen)


# ---------------------------------------------------------------- Befehle

def cmd_baue(args):
    ordner = Path(args.ordner).resolve()
    if not (ordner / "thema.toml").exists():
        sys.exit(f"Keine thema.toml in {ordner}")
    m = Mappe(ordner)
    m.pruefe()
    m.schreibe()
    print(f"Mappe gebaut: {ordner.relative_to(ROOT) if ordner.is_relative_to(ROOT) else ordner}")
    print(f"  {len(m.szenen)} Szenen · {m.wortzahl} Wörter · ca. {m.dauer:.0f} s (geschätzt)")
    for f in m.fehler:
        print(f"  FEHLER:  {f}")
    for w in m.warnungen:
        print(f"  WARNUNG: {w}")
    if not (m.fehler or m.warnungen):
        print("  Alle automatischen Prüfungen ok.")
    return 1 if m.fehler else 0


def cmd_neu(args):
    slug = re.sub(r"[^a-z0-9]+", "-", args.slug.lower()).strip("-")
    nummer = f"{int(args.nummer):02d}"
    ordner = ROOT / "videos" / f"{nummer}-{slug}"
    ziel = ordner / "thema.toml"
    if ziel.exists():
        sys.exit(f"{ziel} gibt es schon – nichts überschrieben.")
    ordner.mkdir(parents=True, exist_ok=True)
    text = VORLAGE.read_text(encoding="utf-8")
    text = text.replace("{{NUMMER}}", nummer).replace("{{SLUG}}", slug).replace("{{TITEL}}", args.titel or "TODO")
    ziel.write_text(text, encoding="utf-8")
    print(f"Angelegt: {ziel.relative_to(ROOT)}\nJetzt ausfüllen und dann: python3 tools/jack.py baue {ordner.relative_to(ROOT)}")


def cmd_pruefe_bausteine(_args):
    b = lade_toml(BAUSTEINE)
    fehlt = [m for m in b["figur"]["pflicht"] if m.lower() not in b["flow"]["character"].lower()]
    for pflicht in ("no 3D look", "no text", "no logos", "no blood or gore", "no speech, no music"):
        if pflicht.lower() not in b["flow"]["schluss"].lower():
            fehlt.append(pflicht)
    if fehlt:
        print("In der Flow-Vorlage fehlen Pflichtangaben:")
        for f in fehlt:
            print("  -", f)
        return 1
    print("Flow-Vorlage enthält alle Pflichtmerkmale von Jack und alle Verbote.")
    return 0


def main():
    p = argparse.ArgumentParser(description="Jack-Pipeline")
    sub = p.add_subparsers(dest="befehl", required=True)
    b = sub.add_parser("baue", help="Mappe aus videos/<ordner>/thema.toml erzeugen")
    b.add_argument("ordner")
    b.set_defaults(f=cmd_baue)
    n = sub.add_parser("neu", help="Neuen Video-Ordner mit leerer thema.toml anlegen")
    n.add_argument("nummer")
    n.add_argument("slug")
    n.add_argument("--titel")
    n.set_defaults(f=cmd_neu)
    k = sub.add_parser("pruefe-bausteine", help="Flow-Vorlage auf Pflichtmerkmale prüfen")
    k.set_defaults(f=cmd_pruefe_bausteine)
    a = p.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
