#!/usr/bin/env python3
"""Phase 0 der Hofladen-Erkennung: Wie gut findet OpenStreetMap (Overpass)
die Hofläden eines Testsets?

Eigenständiges Werkzeug (nur Python-Standardbibliothek, KEIN Home Assistant
nötig) - gedacht zum Ausführen auf einem Rechner mit Internetzugang:

    python3 overpass_messung.py scan    --lat 46.95 --lon 7.45 --radius 5000 --out scan.csv
    python3 overpass_messung.py messen  --testset testset.json --cache cache/ --out ergebnis
    python3 overpass_messung.py messen  --testset testset.json --cache cache/ --offline --out ergebnis

* ``scan``   Hilfsmittel zum Anlegen des Testsets: listet alle Kandidaten
             um einen Punkt als CSV (zum manuellen Beschriften).
* ``messen`` führt je Testset-Eintrag die Overpass-Abfragen aus und
             berechnet Trefferquote (Recall@N), Rang, Kandidatenzahl,
             Latenz. Schreibt ``ergebnis.json`` und ``ergebnis.md``.

Fair Use: öffentliche Overpass-Instanzen sind ein Gemeinschaftsdienst.
Das Werkzeug wartet zwischen Live-Abfragen (``--pause``, Standard 3 s),
identifiziert sich per User-Agent und legt **jede Antwort im Cache ab**:
Wiederholungen und ``--offline`` verursachen keine Last, und die
Cache-Dateien dienen später als Test-Fixtures (Phase 1/2).

Die Namensähnlichkeit hier ist bewusst NAIV (difflib) und dient nur der
Messung; der echte Algorithmus entsteht in Phase 2.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import re
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "HofKarte-Phase0-Messung/1.0 (+https://github.com/rest-be/HofKarte-HA)"
QUERY_TIMEOUT_S = 25
HTTP_TIMEOUT_S = 40
MAX_RADIUS_M = 5000  # Entscheidung: 5 km als Maximum im ersten Wurf

# --- Abfrage-Varianten -------------------------------------------------------
# Jede Variante ist eine Liste von Overpass-Filtern (ohne "nwr(around…)").
# Die Varianten sind HYPOTHESEN - die Messung entscheidet, welche taugt.
VARIANTEN: dict[str, list[str]] = {
    # Wie die heutige Integration (osm_info.py): ALLE shop=*, plus Hof-Heuristik.
    "bestand": [
        '["shop"]',
        '["craft"="agricultural"]',
        '["amenity"="marketplace"]',
        '["landuse"="farmyard"]',
        '["building"="farm"]',
    ],
    # Nur der Kern-Tag.
    "kern": ['["shop"="farm"]'],
    # Kern + typische Hofladen-Varianten, Namensfilter NUR auf Hofstellen
    # (selektiv, daher günstig).
    "erweitert": [
        '["shop"="farm"]',
        '["craft"="agricultural"]',
        '["amenity"="marketplace"]',
        '["farm_shop"]',
        '["produce"]',
        '["amenity"="vending_machine"]["vending"~"milk|eggs|potatoes|honey|cheese|vegetables|fruit",i]',
        '["landuse"="farmyard"]["name"~"hof|laden|ferme|bauer|bure|käse|milch",i]',
        '["building"="farm"]["name"~"hof|laden|ferme|bauer|bure|käse|milch",i]',
    ],
}

_STOPWOERTER = {"der", "die", "das", "zum", "zur", "beim", "bei", "und", "von", "am", "im", "en", "la", "le", "du"}
_GENERISCH = {"hofladen", "hof", "bauernhof", "laden", "ferme", "buure", "buurehof", "landwirtschaft", "hofverkauf"}


# --- Hilfsfunktionen (rein, gut testbar) -------------------------------------

def normalisiere(text: str) -> str:
    """Kleinschreibung, ohne Diakritika/Interpunktion ('Müller' -> 'muller')."""
    text = (text or "").replace("ß", "ss").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens(text: str, ohne_generisch: bool) -> list[str]:
    toks = [t for t in normalisiere(text).split() if t not in _STOPWOERTER]
    if ohne_generisch:
        toks = [t for t in toks if t not in _GENERISCH]
    return sorted(toks)


def name_aehnlichkeit(a: str, b: str) -> float:
    """0..1; Reihenfolge-unabhängig ('Müller Hofladen' ≈ 'Hofladen Müller'),
    zusätzlich Vergleich ohne generische Wörter ('Hofladen')."""
    voll = difflib.SequenceMatcher(None, " ".join(_tokens(a, False)), " ".join(_tokens(b, False))).ratio()
    ka, kb = _tokens(a, True), _tokens(b, True)
    kern = difflib.SequenceMatcher(None, " ".join(ka), " ".join(kb)).ratio() if ka and kb else 0.0
    return max(voll, kern * 0.95)  # Kernvergleich leicht abgewertet


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def verschiebe(lat: float, lon: float, meter: float, peilung_grad: float) -> tuple[float, float]:
    """Verschiebt einen Punkt (Näherung, für <10 km genau genug)."""
    if meter == 0:
        return lat, lon
    d_lat = meter * math.cos(math.radians(peilung_grad)) / 111_320
    d_lon = meter * math.sin(math.radians(peilung_grad)) / (111_320 * math.cos(math.radians(lat)))
    return lat + d_lat, lon + d_lon


def baue_query(variante: str, lat: float, lon: float, radius: int) -> str:
    radius = max(1, min(int(radius), MAX_RADIUS_M))
    umkreis = f"around:{radius},{lat:.6f},{lon:.6f}"
    zeilen = "\n".join(f"  nwr({umkreis}){f};" for f in VARIANTEN[variante])
    return f"[out:json][timeout:{QUERY_TIMEOUT_S}];\n(\n{zeilen}\n);\nout center tags;"


def parse_elemente(daten: dict[str, Any]) -> list[dict[str, Any]]:
    """Overpass-JSON -> Kandidaten (nur benannte Elemente mit Koordinaten)."""
    ergebnis = []
    for el in daten.get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("brand") or tags.get("operator")
        if not name:
            continue
        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        elif isinstance(el.get("center"), dict):
            lat, lon = el["center"].get("lat"), el["center"].get("lon")
        else:
            continue
        if lat is None or lon is None:
            continue
        ergebnis.append({
            "ref": f"{el.get('type')}/{el.get('id')}",
            "name": str(name),
            "lat": float(lat),
            "lon": float(lon),
            "tags": {k: tags[k] for k in ("shop", "amenity", "craft", "landuse", "building",
                                           "farm_shop", "produce", "vending", "website",
                                           "contact:website", "opening_hours") if k in tags},
        })
    return ergebnis


def bewerte(kandidaten: list[dict[str, Any]], name: str, lat: float, lon: float,
            radius: int) -> list[dict[str, Any]]:
    """Fügt Distanz + naiven Score hinzu, sortiert absteigend nach Score.

    Naiver Score: 0.6*Name + 0.4*Distanz (Distanz linear über den Radius).
    Nur Messzweck - Phase 2 ersetzt das."""
    ausgabe = []
    for k in kandidaten:
        dist = haversine_m(lat, lon, k["lat"], k["lon"])
        sim = name_aehnlichkeit(name, k["name"])
        dscore = max(0.0, 1 - dist / max(radius, 1))
        ausgabe.append({**k, "dist_m": round(dist), "name_sim": round(sim, 3),
                        "score": round(0.6 * sim + 0.4 * dscore, 4)})
    return sorted(ausgabe, key=lambda x: -x["score"])


def ist_treffer(k: dict[str, Any], eintrag: dict[str, Any], rad_nah: int = 150) -> bool:
    """Gilt Kandidat k als der erwartete Hofladen?

    * Mit ``osm_ref`` im Testset: exakter Vergleich.
    * Ohne: Position des Eintrags liegt ≤ rad_nah m neben dem Kandidaten UND
      Namensähnlichkeit ≥ 0.5, oder Namensähnlichkeit ≥ 0.85 (Position des
      Eintrags darf ungenau sein)."""
    if eintrag.get("osm_ref"):
        return k["ref"] == eintrag["osm_ref"]
    d = haversine_m(eintrag["latitude"], eintrag["longitude"], k["lat"], k["lon"])
    sim = name_aehnlichkeit(eintrag["name"], k["name"])
    return (d <= rad_nah and sim >= 0.5) or sim >= 0.85


def rang(liste: list[dict[str, Any]], eintrag: dict[str, Any]) -> int | None:
    for i, k in enumerate(liste, 1):
        if ist_treffer(k, eintrag):
            return i
    return None


# --- Netzwerk + Cache --------------------------------------------------------

def cache_pfad(cache_dir: Path, url: str, query: str) -> Path:
    h = hashlib.sha256(f"{url}\n{query}".encode()).hexdigest()[:24]
    return cache_dir / f"{h}.json"


def hole(url: str, query: str, cache_dir: Path, offline: bool, pause: float,
         opener: Callable[..., Any] | None = None,
         schlafe: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Overpass-Antwort aus dem Cache oder live. Rückgabe:
    {"ok": bool, "daten": {...}|None, "latenz_s": float|None, "bytes": int, "fehler": str|None,
     "aus_cache": bool}"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    pfad = cache_pfad(cache_dir, url, query)
    if pfad.exists():
        eintrag = json.loads(pfad.read_text(encoding="utf-8"))
        eintrag["aus_cache"] = True
        return eintrag
    if offline:
        return {"ok": False, "daten": None, "latenz_s": None, "bytes": 0,
                "fehler": "offline: nicht im Cache", "aus_cache": True}

    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(),
                                 headers={"User-Agent": USER_AGENT})
    ergebnis: dict[str, Any] = {"ok": False, "daten": None, "latenz_s": None, "bytes": 0,
                                "fehler": None, "aus_cache": False}
    for versuch in (1, 2):
        schlafe(pause if versuch == 1 else 30)
        t0 = time.monotonic()
        try:
            with opener(req, timeout=HTTP_TIMEOUT_S) as antwort:
                roh = antwort.read(4 * 1024 * 1024)
            ergebnis.update(ok=True, daten=json.loads(roh), bytes=len(roh), fehler=None,
                            latenz_s=round(time.monotonic() - t0, 2))
            break
        except urllib.error.HTTPError as err:
            ergebnis.update(fehler=f"HTTP {err.code}", latenz_s=round(time.monotonic() - t0, 2))
            if err.code not in (429, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as err:
            ergebnis.update(fehler=f"{type(err).__name__}: {err}",
                            latenz_s=round(time.monotonic() - t0, 2))
    if ergebnis["ok"]:  # Fehler werden NICHT gecacht
        pfad.write_text(json.dumps(ergebnis, ensure_ascii=False), encoding="utf-8")
    return ergebnis


# --- Messung -----------------------------------------------------------------

def lade_testset(pfad: Path) -> list[dict[str, Any]]:
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    eintraege = daten["eintraege"] if isinstance(daten, dict) else daten
    for i, e in enumerate(eintraege):
        for feld in ("name", "latitude", "longitude"):
            if feld not in e:
                raise ValueError(f"Testset-Eintrag {i}: Feld '{feld}' fehlt")
        e.setdefault("typ", "positiv")
        if e["typ"] not in ("positiv", "negativ"):
            raise ValueError(f"Testset-Eintrag {i}: typ muss 'positiv' oder 'negativ' sein")
    return eintraege


def messe_eintrag(eintrag: dict[str, Any], index: int, variante: str, radius: int, versatz: int,
                  hole_fn: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    peilung = (index * 137) % 360  # deterministische, über Einträge gestreute Richtung
    q_lat, q_lon = verschiebe(eintrag["latitude"], eintrag["longitude"], versatz, peilung)
    antwort = hole_fn(baue_query(variante, q_lat, q_lon, radius))
    res: dict[str, Any] = {"name": eintrag["name"], "typ": eintrag["typ"], "variante": variante,
                           "radius": radius, "versatz": versatz, "ok": antwort["ok"],
                           "fehler": antwort.get("fehler"), "latenz_s": antwort.get("latenz_s"),
                           "bytes": antwort.get("bytes", 0), "aus_cache": antwort.get("aus_cache", False)}
    if not antwort["ok"]:
        return res
    kand = parse_elemente(antwort["daten"])
    nach_score = bewerte(kand, eintrag["name"], q_lat, q_lon, radius)
    nach_dist = sorted(nach_score, key=lambda x: x["dist_m"])
    res["kandidaten"] = len(kand)
    if eintrag["typ"] == "positiv":
        res["rang_score"] = rang(nach_score, eintrag)
        res["rang_distanz"] = rang(nach_dist, eintrag)
        res["gefunden"] = res["rang_score"] is not None
    else:
        # Negativfall: Fehlalarm, wenn es einen Kandidaten gibt, der wie der Eintrag
        # aussieht (Name ≥ 0.6 UND ≤ 300 m vom Eintragspunkt).
        res["fehlalarm"] = any(
            name_aehnlichkeit(eintrag["name"], k["name"]) >= 0.6
            and haversine_m(eintrag["latitude"], eintrag["longitude"], k["lat"], k["lon"]) <= 300
            for k in kand)
    return res


def _quote(werte: list[bool]) -> str:
    return f"{100 * sum(werte) / len(werte):.0f} % ({sum(werte)}/{len(werte)})" if werte else "–"


def _perz(werte: list[float], p: float) -> float | None:
    if not werte:
        return None
    s = sorted(werte)
    return s[min(len(s) - 1, math.ceil(p * len(s)) - 1)]


def fasse_zusammen(ergebnisse: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gruppen: dict[tuple, list[dict[str, Any]]] = {}
    for r in ergebnisse:
        gruppen.setdefault((r["variante"], r["radius"], r["versatz"]), []).append(r)
    zeilen = []
    for (variante, radius, versatz), rs in sorted(gruppen.items()):
        pos = [r for r in rs if r["typ"] == "positiv" and r["ok"]]
        neg = [r for r in rs if r["typ"] == "negativ" and r["ok"]]
        lat = [r["latenz_s"] for r in rs if r.get("latenz_s")]
        zeilen.append({
            "variante": variante, "radius": radius, "versatz": versatz,
            "n_positiv": len(pos), "n_negativ": len(neg), "n_fehler": sum(1 for r in rs if not r["ok"]),
            "recall_gefunden": _quote([r["gefunden"] for r in pos]),
            "recall_at1_score": _quote([(r["rang_score"] or 99) <= 1 for r in pos]),
            "recall_at3_score": _quote([(r["rang_score"] or 99) <= 3 for r in pos]),
            "recall_at10_score": _quote([(r["rang_score"] or 99) <= 10 for r in pos]),
            "recall_at3_distanz": _quote([(r["rang_distanz"] or 99) <= 3 for r in pos]),
            "fehlalarm": _quote([r["fehlalarm"] for r in neg]),
            "kandidaten_median": statistics.median([r["kandidaten"] for r in pos + neg]) if pos + neg else None,
            "kandidaten_max": max([r["kandidaten"] for r in pos + neg], default=None),
            "latenz_median_s": statistics.median(lat) if lat else None,
            "latenz_p95_s": _perz(lat, 0.95),
            "antwort_kb_max": round(max([r["bytes"] for r in rs], default=0) / 1024),
        })
    return zeilen


def render_markdown(zeilen: list[dict[str, Any]], ergebnisse: list[dict[str, Any]]) -> str:
    kopf = ("| Variante | Radius | Versatz | n+ | n− | Fehler | gefunden | @1 | @3 | @10 | @3 (nur Distanz) "
            "| Fehlalarm | Kand. med/max | Latenz med/p95 s | max KB |\n"
            "|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---:|\n")
    körper = ""
    for z in zeilen:
        körper += (f"| {z['variante']} | {z['radius']} | {z['versatz']} | {z['n_positiv']} | {z['n_negativ']} "
                   f"| {z['n_fehler']} | {z['recall_gefunden']} | {z['recall_at1_score']} | {z['recall_at3_score']} "
                   f"| {z['recall_at10_score']} | {z['recall_at3_distanz']} | {z['fehlalarm']} "
                   f"| {z['kandidaten_median']}/{z['kandidaten_max']} | {z['latenz_median_s']}/{z['latenz_p95_s']} "
                   f"| {z['antwort_kb_max']} |\n")
    luecken = sorted({(r["name"], r["variante"], r["radius"], r["versatz"])
                      for r in ergebnisse if r["typ"] == "positiv" and r["ok"] and not r["gefunden"]})
    text = ("# Phase 0 – Messung der OSM-Trefferquote\n\n"
            "Legende: *gefunden* = erwarteter Hofladen irgendwo in der Kandidatenliste; *@N* = unter den ersten N "
            "nach naivem Score (0.6 Name + 0.4 Distanz); *Versatz* = Abstand des Suchpunkts vom Hofladen in m "
            "(simuliert ungenauen Standort); *Fehlalarm* = Negativfall, für den ein ähnlich benannter Kandidat "
            "≤ 300 m auftauchte.\n\n" + kopf + körper)
    if luecken:
        text += "\n## Nicht gefundene Hofläden (OSM-Lücken oder Matching-Problem)\n\n"
        text += "\n".join(f"- {n} (Variante {v}, Radius {r}, Versatz {s})" for n, v, r, s in luecken) + "\n"
    return text


def cmd_messen(args: argparse.Namespace) -> int:
    eintraege = lade_testset(Path(args.testset))
    cache_dir = Path(args.cache)
    varianten = args.varianten.split(",")
    for v in varianten:
        if v not in VARIANTEN:
            print(f"Unbekannte Variante: {v}", file=sys.stderr)
            return 2
    radien = [int(r) for r in args.radien.split(",")]
    versaetze = [int(v) for v in args.versatz.split(",")]
    if max(radien) > MAX_RADIUS_M:
        print(f"Radius > {MAX_RADIUS_M} m nicht zugelassen.", file=sys.stderr)
        return 2
    anzahl = len(eintraege) * len(varianten) * len(radien) * len(versaetze)
    print(f"{anzahl} Messungen (Live-Abfragen nur für Nicht-Gecachtes, Pause {args.pause}s).")
    ergebnisse = []
    for variante in varianten:
        for radius in radien:
            for versatz in versaetze:
                for i, e in enumerate(eintraege):
                    ergebnisse.append(messe_eintrag(
                        e, i, variante, radius, versatz,
                        lambda q: hole(args.url, q, cache_dir, args.offline, args.pause)))
    zeilen = fasse_zusammen(ergebnisse)
    out = Path(args.out)
    out.with_suffix(".json").write_text(
        json.dumps({"zusammenfassung": zeilen, "einzel": ergebnisse}, ensure_ascii=False, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(zeilen, ergebnisse), encoding="utf-8")
    print(render_markdown(zeilen, ergebnisse))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Alle benannten Kandidaten um einen Punkt als CSV - Hilfe zum Testset-Bauen."""
    cache_dir = Path(args.cache)
    q = baue_query(args.variante, args.lat, args.lon, args.radius)
    antwort = hole(args.url, q, cache_dir, args.offline, args.pause)
    if not antwort["ok"]:
        print(f"Fehler: {antwort['fehler']}", file=sys.stderr)
        return 1
    kand = bewerte(parse_elemente(antwort["daten"]), "", args.lat, args.lon, args.radius)
    kand.sort(key=lambda k: k["dist_m"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ref", "name", "latitude", "longitude", "dist_m", "tags", "ist_hofladen (j/n)"])
        for k in kand:
            w.writerow([k["ref"], k["name"], k["lat"], k["lon"], k["dist_m"],
                        json.dumps(k["tags"], ensure_ascii=False), ""])
    print(f"{len(kand)} Kandidaten nach {args.out} geschrieben.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("messen", "scan"):
        s = sub.add_parser(name)
        s.add_argument("--url", default=OVERPASS_URL, help="Overpass-Endpunkt (auch eigene Instanz)")
        s.add_argument("--cache", default="cache", help="Verzeichnis für Rohantworten")
        s.add_argument("--offline", action="store_true", help="nur Cache verwenden")
        s.add_argument("--pause", type=float, default=3.0, help="Sekunden Pause vor jeder Live-Abfrage")
        s.add_argument("--out", required=True)
    m = sub.choices["messen"]
    m.add_argument("--testset", required=True)
    m.add_argument("--varianten", default="erweitert", help=f"kommagetrennt aus: {', '.join(VARIANTEN)}")
    m.add_argument("--radien", default="2000,5000")
    m.add_argument("--versatz", default="0,1500", help="Suchpunkt-Abstand zum Hofladen in m (kommagetrennt)")
    m.set_defaults(fn=cmd_messen)
    sc = sub.choices["scan"]
    sc.add_argument("--lat", type=float, required=True)
    sc.add_argument("--lon", type=float, required=True)
    sc.add_argument("--radius", type=int, default=3000)
    sc.add_argument("--variante", default="erweitert", choices=list(VARIANTEN))
    sc.set_defaults(fn=cmd_scan)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
