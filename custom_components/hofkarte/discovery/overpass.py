"""Overpass-Abfrage für die Hofladen-Discovery: Query, Antwortprüfung,
Kandidaten und Zusammenführung doppelter OSM-Objekte.

## Wiederverwendung des Abrufs

Der HTTP-Abruf (mehrere Instanzen nacheinander, Gesamtbudget, Grössen-
limit, Protokollierung) bleibt unverändert in ``osm_info.py``
(``_rufe_overpass_ab``); dieses Modul ruft ihn zur Laufzeit über das
Modul ``osm_info`` auf. So gelten für beide Funktionen dieselben
Fair-Use-Grenzen, und das Verhalten der bestehenden Funktion "Ort in der
Nähe suchen" bleibt byte-identisch.

## Messbefunde, die hier umgesetzt sind (Phase 0)

- Eine Overpass-Antwort mit HTTP 200, leerem ``elements`` und einem
  ``remark`` "runtime error: Query timed out" ist ein **Fehler**, kein
  "keine Treffer" (und wird nie gecacht).
- OSM-Objekte können **ohne Namen** sein (``shop=farm`` ohne ``name``) oder
  den Namen nur in Varianten tragen (``brand``, ``operator``, ``alt_name``,
  ``name:fr``, ...). Beide bleiben Kandidaten.
- Dasselbe Geschäft ist oft doppelt erfasst (Gebäude + Punkt, wenige
  Meter auseinander); solche Objekte werden zu **einem** Kandidaten
  zusammengeführt.
- Der Name in OSM weicht häufig vom Namen ab, den der Betrieb selbst
  verwendet (Inhaber, Marke, Firma). Der Name ist daher nur ein Signal;
  die Bewertung folgt in Phase 2 (``scoring.py``). Hier wird nach
  Entfernung sortiert.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .geo import haversine_m
from .profile import FARMSHOP, PROFILE
from .text import name_aehnlichkeit

_LOGGER = logging.getLogger(__name__)

STANDARD_RADIUS_METER = 2000
MIN_RADIUS_METER = 50
MAX_RADIUS_METER = 5000  # Entscheid: 5 km Obergrenze (mehr bringt nur Rauschen)

QUERY_TIMEOUT_SEKUNDEN = 20  # kleiner als das HTTP-Zeitlimit des Abrufs (25 s)
CACHE_TTL_SEKUNDEN = 600
CACHE_MAX_EINTRAEGE = 32

# Objekte desselben Geschäfts liegen typischerweise <= 20 m auseinander.
ZUSAMMENFUEHRUNG_METER = 30.0
ZUSAMMENFUEHRUNG_NAME_AB = 0.85

_NAMEN_SCHLUESSEL = (
    "name", "name:de", "name:fr", "name:it", "name:en", "alt_name",
    "short_name", "loc_name", "official_name", "brand", "operator",
)
_TYP_SCHLUESSEL = ("shop", "amenity", "craft", "landuse", "building", "vending")
_MAX_TEXT = 300
_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")


class DiscoveryUngueltigeKoordinatenError(Exception):
    """Keine gültigen Latitude-/Longitude-Werte."""


class DiscoveryNichtErreichbarError(Exception):
    """Overpass nicht erreichbar, Zeitüberschreitung oder unbrauchbare Antwort."""


@dataclass(frozen=True)
class Kandidat:
    """Ein möglicher Hofladen aus OpenStreetMap (Vorschlag, ungeprüft)."""

    refs: tuple[str, ...]  # z. B. ("node/1", "way/2"); das erste ist das Hauptobjekt
    name: str | None
    weitere_namen: tuple[str, ...]
    latitude: float
    longitude: float
    entfernung_meter: float
    typ: tuple[str, ...] = ()  # z. B. ("shop=farm",)
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    website: str | None = None
    telefon: str | None = None
    email: str | None = None
    oeffnungszeiten: str | None = None  # roher OSM-``opening_hours``-Text
    _tags_anzahl: int = field(default=0, repr=False, compare=False)

    @property
    def unbenannt(self) -> bool:
        return self.name is None

    def als_dict(self) -> dict[str, Any]:
        """JSON-taugliche Darstellung für die Verwaltungsoberfläche."""
        return {
            "refs": list(self.refs),
            "name": self.name,
            "weitere_namen": list(self.weitere_namen),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "entfernung_meter": self.entfernung_meter,
            "typ": list(self.typ),
            "adresse": self.adresse,
            "plz": self.plz,
            "ort": self.ort,
            "website": self.website,
            "telefon": self.telefon,
            "email": self.email,
            "oeffnungszeiten": self.oeffnungszeiten,
        }

    @property
    def alle_namen(self) -> tuple[str, ...]:
        return ((self.name,) if self.name else ()) + self.weitere_namen


# --- reine Funktionen --------------------------------------------------------


def _sind_gueltige_koordinaten(latitude: Any, longitude: Any) -> bool:
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180 and lat == lat and lon == lon


def begrenze_radius(radius_meter: Any) -> int:
    """Radius auf ``MIN_RADIUS_METER``-``MAX_RADIUS_METER`` begrenzen; ein
    unbrauchbarer Wert führt zum Standard (kein Fehlerfall)."""
    try:
        radius = int(radius_meter)
    except (TypeError, ValueError):
        radius = STANDARD_RADIUS_METER
    return max(MIN_RADIUS_METER, min(MAX_RADIUS_METER, radius))


def baue_query(
    latitude: float,
    longitude: float,
    radius_meter: int,
    profil: str = "farmshop",
    erweitert: bool = False,
    timeout_s: int = QUERY_TIMEOUT_SEKUNDEN,
) -> str:
    """Overpass-QL für ``profil``. Koordinaten/Radius sind reine Zahlen;
    die Filter stammen aus dem fest hinterlegten Profil (keine Benutzer-
    Freitexte in der Anfrage)."""
    p = PROFILE[profil]
    umkreis = f"around:{begrenze_radius(radius_meter)},{float(latitude):.6f},{float(longitude):.6f}"
    zeilen = "\n".join(f"  nwr({umkreis}){f};" for f in p.filter(erweitert))
    return f"[out:json][timeout:{int(timeout_s)}];\n(\n{zeilen}\n);\nout center tags;"


def pruefe_antwort(daten: Any) -> list[dict[str, Any]]:
    """Liefert die ``elements`` oder wirft ``DiscoveryNichtErreichbarError``.

    Eine leere Liste *mit* ``remark`` "runtime error" (Zeitüberschreitung,
    Speicher) ist ein Fehler, keine "Null Treffer"-Antwort."""
    if not isinstance(daten, dict) or not isinstance(daten.get("elements"), list):
        raise DiscoveryNichtErreichbarError(
            "Die Antwort der Overpass API hat nicht das erwartete Format."
        )
    elemente = daten["elements"]
    remark = str(daten.get("remark") or "")
    if "runtime error" in remark.lower() and not elemente:
        raise DiscoveryNichtErreichbarError(
            "Die Overpass API hat die Anfrage nicht fertig bearbeitet "
            f"({remark[:120]}). Bitte später erneut versuchen."
        )
    return elemente


def _text(wert: Any) -> str | None:
    """Untrusted OSM-Text: String, ohne Steuerzeichen, getrimmt, begrenzt."""
    if not isinstance(wert, str):
        return None
    s = _STEUERZEICHEN.sub(" ", wert).strip()
    return s[:_MAX_TEXT] if s else None


def _koordinate(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        zentrum = element.get("center")
        lat = zentrum.get("lat") if isinstance(zentrum, dict) else None
        lon = zentrum.get("lon") if isinstance(zentrum, dict) else None
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


def _adresse(tags: dict[str, Any]) -> str | None:
    strasse = _text(tags.get("addr:street"))
    nummer = _text(tags.get("addr:housenumber"))
    if strasse and nummer:
        return f"{strasse} {nummer}"
    return strasse


def _kandidat_aus_element(element: Any, lat0: float, lon0: float) -> Kandidat | None:
    if not isinstance(element, dict):
        return None
    tags = element.get("tags")
    tags = tags if isinstance(tags, dict) else {}
    koord = _koordinate(element)
    if koord is None:
        return None
    namen: list[str] = []
    for schluessel in _NAMEN_SCHLUESSEL:
        n = _text(tags.get(schluessel))
        if n and n not in namen:
            namen.append(n)

    def kontakt(*schluessel: str) -> str | None:
        return next((t for k in schluessel if (t := _text(tags.get(k)))), None)

    return Kandidat(
        refs=(f"{element.get('type')}/{element.get('id')}",),
        name=namen[0] if namen else None,
        weitere_namen=tuple(namen[1:]),
        latitude=koord[0],
        longitude=koord[1],
        entfernung_meter=round(haversine_m(lat0, lon0, koord[0], koord[1]), 1),
        typ=tuple(f"{k}={t}" for k in _TYP_SCHLUESSEL if (t := _text(tags.get(k)))),
        adresse=_adresse(tags),
        plz=_text(tags.get("addr:postcode")),
        ort=_text(tags.get("addr:city")),
        website=kontakt("website", "contact:website"),
        telefon=kontakt("phone", "contact:phone", "contact:mobile"),
        email=kontakt("email", "contact:email"),
        oeffnungszeiten=_text(tags.get("opening_hours")),
        _tags_anzahl=len(tags),
    )


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    teile = urlsplit(url if "//" in url else f"//{url}")
    host = (teile.hostname or "").lower()
    return host[4:] if host.startswith("www.") else (host or None)


def _gehoeren_zusammen(a: Kandidat, b: Kandidat) -> bool:
    """Zwei Kandidaten sind dasselbe Geschäft: nahe beieinander UND
    (mindestens einer ohne Namen, gleiche Website-Domain oder sehr ähnlicher
    Name). Zwei verschieden benannte Läden im selben Hof bleiben getrennt."""
    if haversine_m(a.latitude, a.longitude, b.latitude, b.longitude) > ZUSAMMENFUEHRUNG_METER:
        return False
    if a.unbenannt or b.unbenannt:
        return True
    da, db = _domain(a.website), _domain(b.website)
    if da and da == db:
        return True
    return any(
        name_aehnlichkeit(x, y) >= ZUSAMMENFUEHRUNG_NAME_AB
        for x in a.alle_namen
        for y in b.alle_namen
    )


def _verschmelze(haupt: Kandidat, andere: Kandidat) -> Kandidat:
    """Hauptobjekt behalten, fehlende Angaben aus ``andere`` ergänzen."""
    namen = list(haupt.alle_namen)
    for n in andere.alle_namen:
        if n not in namen:
            namen.append(n)
    typen = tuple(dict.fromkeys(haupt.typ + andere.typ))
    return Kandidat(
        refs=haupt.refs + tuple(r for r in andere.refs if r not in haupt.refs),
        name=namen[0] if namen else None,
        weitere_namen=tuple(namen[1:]),
        latitude=haupt.latitude,
        longitude=haupt.longitude,
        entfernung_meter=haupt.entfernung_meter,
        typ=typen,
        adresse=haupt.adresse or andere.adresse,
        plz=haupt.plz or andere.plz,
        ort=haupt.ort or andere.ort,
        website=haupt.website or andere.website,
        telefon=haupt.telefon or andere.telefon,
        email=haupt.email or andere.email,
        oeffnungszeiten=haupt.oeffnungszeiten or andere.oeffnungszeiten,
        _tags_anzahl=max(haupt._tags_anzahl, andere._tags_anzahl),
    )


def fuehre_zusammen(kandidaten: list[Kandidat]) -> list[Kandidat]:
    """Doppelt erfasste Objekte zu je einem Kandidaten verschmelzen.

    Das Objekt mit den meisten Tags ist das Hauptobjekt (reichere Daten);
    bei Gleichstand das nähere. Das Ergebnis ist nach Entfernung sortiert."""
    gruppen: list[Kandidat] = []
    for k in sorted(kandidaten, key=lambda c: (-c._tags_anzahl, c.entfernung_meter, c.refs)):
        for i, g in enumerate(gruppen):
            if _gehoeren_zusammen(g, k):
                gruppen[i] = _verschmelze(g, k)
                break
        else:
            gruppen.append(k)
    return sorted(gruppen, key=lambda c: (c.entfernung_meter, c.refs))


def parse_kandidaten(elemente: list[Any], latitude: float, longitude: float) -> list[Kandidat]:
    """Overpass-``elements`` -> zusammengeführte, nach Entfernung sortierte
    Kandidaten (auch unbenannte)."""
    roh = [k for e in elemente if (k := _kandidat_aus_element(e, latitude, longitude))]
    return fuehre_zusammen(roh)


# --- Abruf (Cache + osm_info-Abruf) ------------------------------------------

_cache: dict[tuple[Any, ...], tuple[float, list[dict[str, Any]]]] = {}


def _cache_leeren() -> None:
    """Cache leeren (Tests)."""
    _cache.clear()


def _cache_lesen(schluessel: tuple[Any, ...]) -> list[dict[str, Any]] | None:
    eintrag = _cache.get(schluessel)
    if eintrag is None:
        return None
    zeit, elemente = eintrag
    if time.monotonic() - zeit > CACHE_TTL_SEKUNDEN:
        del _cache[schluessel]
        return None
    return elemente


def _cache_schreiben(schluessel: tuple[Any, ...], elemente: list[dict[str, Any]]) -> None:
    _cache.pop(schluessel, None)
    while len(_cache) >= CACHE_MAX_EINTRAEGE:
        del _cache[next(iter(_cache))]
    _cache[schluessel] = (time.monotonic(), elemente)


async def async_suche(
    hass: Any,
    latitude: Any,
    longitude: Any,
    radius_meter: Any = STANDARD_RADIUS_METER,
    profil: str = FARMSHOP.name,
    erweitert: bool = False,
) -> tuple[Kandidat, ...]:
    """Hofladen-Kandidaten im Umkreis; nach Entfernung sortiert.

    Wirft ``DiscoveryUngueltigeKoordinatenError`` bzw.
    ``DiscoveryNichtErreichbarError``. Keine Treffer sind **kein** Fehler
    (leeres Ergebnis): die Verwaltungsoberfläche bietet dann die manuelle
    Erfassung an."""
    # Importe erst hier: ``osm_info`` benötigt Home Assistant, der Rest des
    # Pakets nicht (isoliert testbar).
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .. import osm_info

    if not _sind_gueltige_koordinaten(latitude, longitude):
        raise DiscoveryUngueltigeKoordinatenError(
            "Es sind keine gültigen Latitude-/Longitude-Werte vorhanden."
        )
    if profil not in PROFILE:
        raise ValueError(f"Unbekanntes Profil: {profil}")
    lat, lon = float(latitude), float(longitude)
    radius = begrenze_radius(radius_meter)
    schluessel = (profil, bool(erweitert), round(lat, 4), round(lon, 4), radius)

    elemente = _cache_lesen(schluessel)
    if elemente is None:
        query = baue_query(lat, lon, radius, profil, erweitert)
        try:
            daten = await osm_info._rufe_overpass_ab(async_get_clientsession(hass), query)
        except osm_info.OsmNichtErreichbarError as err:
            raise DiscoveryNichtErreichbarError(str(err)) from err
        elemente = pruefe_antwort(daten)
        _cache_schreiben(schluessel, elemente)  # nur eine brauchbare Antwort

    return tuple(parse_kandidaten(elemente, lat, lon))
