"""Ermittlung von Hofladen-Informationen anhand der im Verwaltungsformular
eingetragenen GPS-Koordinaten, über die OpenStreetMap-Overpass-API
(Issue #10, "Erweiterung OpenStreetMap zu #8").

## Architektonische Einordnung: eine zweite, bewusst begrenzte Ausnahme

HofKarte verfolgt den Grundsatz "kein externer/Cloud-/KI-Dienst" (siehe
``webseite_info.py``, Moduldoc). Dieses Modul führt dennoch eine zweite,
eigene ausgehende Netzwerkanfrage ein - diesmal an einen von HofKarte nicht
kontrollierten, aber öffentlichen, kostenlosen, kontofreien
OpenStreetMap-Community-Dienst (die Overpass API, ``overpass-api.de``).
Das wird bewusst als zweite, eng begrenzte Ausnahme behandelt, analog zur
bereits bestehenden Ausnahme für Leaflet/OpenStreetMap-Kartenkacheln
(siehe ``docs/architecture.md``, Abschnitt "Eingebettete Kartenansicht") -
kein kommerzieller Cloud-Dienst, kein LLM/KI-Dienst, kein
"Scraping-as-a-Service".

Anders als die rein clientseitig vom Browser geladenen Kartenkacheln (die
keine hofladenspezifischen Daten an OpenStreetMap übertragen, nur
generische Kachel-Indizes) sendet dieses Modul die **konkreten
Koordinaten eines bestimmten Hofladens serverseitig** an die Overpass API
- ausschliesslich auf ausdrücklichen Klick auf "📍 Ort in der Nähe
suchen" im Bearbeitungsformular, nie automatisch oder im Hintergrund
(siehe README.md, Abschnitt "Datenschutz- und Standort-Hinweise", sowie
SECURITY.md für die ausführliche Begründung dieser Ausnahme).

## Fair Use, Gesamtbudget und Cache (Befund F14)

Die Overpass-Instanzen sind öffentliche Community-Dienste mit
Fair-Use-Regeln. HofKarte begrenzt die Last deshalb mehrfach: die Suche
läuft nur auf ausdrücklichen Klick, der Radius ist auf höchstens
``MAX_RADIUS_METER`` (2 000 m) begrenzt, die gesamte Abfrage (alle
Instanzen zusammen) hat ein **Gesamtzeitbudget** von
``GESAMT_BUDGET_SEKUNDEN`` (40 s statt bis zu 3 x 25 s) und identische
Anfragen werden kurz im Arbeitsspeicher gehalten
(``CACHE_TTL_SEKUNDEN`` = 10 min, höchstens ``CACHE_MAX_EINTRAEGE`` = 32
Einträge, Schlüssel: auf 4 Nachkommastellen (~11 m) gerundete Koordinaten
plus Radius), damit wiederholte Klicks denselben Dienst nicht erneut
belasten. Gecacht wird nur die rohe, erfolgreiche Overpass-Antwort - nie
ein Fehler.

## Kein SSRF-Schutz über ``url_sicherheit.py`` nötig

Anders als bei ``webseite_info.py`` (dort bestimmt die Benutzerin/der
Benutzer die abgerufene URL selbst - klassisches SSRF-Risiko) sind die
Anfrageziele hier **fest im Code hinterlegt** (``OVERPASS_URLS``, siehe
unten) und werden nie durch Benutzereingaben beeinflusst - nur
Koordinaten und Radius fliessen (als reine Zahlenwerte, nicht als
Freitext) in den Anfragetext ein. Eine SSRF-Prüfung à la
``url_sicherheit.py`` (Schema-/Host-Prüfung einer benutzergesteuerten
Ziel-URL) ist daher nicht anwendbar. Es gelten stattdessen dieselben
allgemeinen Abwehrmassnahmen gegen eine möglicherweise übergrosse oder
fehlerhafte Antwort wie in ``webseite_info.py``: ein Antwortgrössen-Limit
(``MAX_ANTWORT_BYTES``) sowie eine Zeitüberschreitung
(``ABRUF_TIMEOUT_SEKUNDEN``).

## Zuverlässigkeit: mehrere Instanzen statt eines Einzelpunkts

Recherche in der offiziellen Dokumentation (OSM-Wiki „Overpass API“,
``overpass-api.de``, ``github.com/drolbr/Overpass-API``) ergab zwei für
die Zuverlässigkeit dieser Funktion direkt relevante, dort ausdrücklich
dokumentierte Punkte:

1. Die Haupt-Instanz ``overpass-api.de`` wird von den Betreibern selbst
   als **häufig überlastet** beschrieben („Nowadays this server is
   overloaded [...] do not expect high reliability. Use alternatives if
   possible.“) - ein einzelner, fest verdrahteter Endpunkt ist damit ein
   unnötiger Single Point of Failure für eine Funktion, die ohnehin nur
   auf ausdrücklichen Klick läuft und keine hohe Anfragefrequenz braucht.
2. Die Nutzungsrichtlinien verlangen ausdrücklich einen erkennbaren
   ``User-Agent``- oder ``Referer``-Header („Be sure to check that your
   app or website adds User-Agent or Referer headers“) - ein Client ohne
   erkennbaren Absender riskiert, von der Instanz als anonymer/
   Massen-Client eingestuft und stärker gedrosselt oder abgelehnt zu
   werden.

Dieses Modul begegnet Punkt 1 mit einer kurzen, statisch im Code
hinterlegten Liste bekannter, öffentlicher Overpass-Instanzen
(``OVERPASS_URLS``) - bei einem Verbindungsfehler, einer Zeitüberschreitung
oder einem serverseitigen Fehler-/Drosselungs-Status (u. a. HTTP 429, wie
in den Nutzungsrichtlinien als Drosselungs-Antwort dokumentiert) wird
automatisch die nächste Instanz derselben Liste versucht, bevor die
Suche endgültig als nicht erreichbar gilt; jeder einzelne Fehlversuch
wird protokolliert (siehe ``_rufe_overpass_ab``). Neben der Haupt-Instanz
enthält die Liste bewusst ``overpass.private.coffee`` (im OSM-Wiki als
Alternative genannt) sowie die für Schweizer Nutzung naheliegende
Regional-Instanz ``overpass.osm.ch`` - alle drei sind, wie die
Haupt-Instanz, freie, kostenlose, kontofreie OpenStreetMap-
Community-Dienste und fallen damit unter dieselbe, oben begründete
Ausnahme vom Grundsatz „kein externer Dienst“; es wird keine neue,
andersartige Kategorie externer Dienste eingeführt. Punkt 2 wird durch
einen expliziten, identifizierenden ``User-Agent``-Header
(``_USER_AGENT``) bei jeder Anfrage berücksichtigt.

## Tag-Auswahl

Das im Issue mitgelieferte Beispiel filtert nach dem generischen
``amenity``-Tag - dafür sind Hofläden auf OpenStreetMap in aller Regel
nicht getaggt (das ist die Tag-Familie für z. B. Cafés, Bänke, Briefkästen
u. Ä.). Läden werden auf OpenStreetMap stattdessen über ``shop=*``
getaggt; für landwirtschaftliche Hofläden ergänzend über
``craft=agricultural``. Diese Auswahl ist bewusst nicht abschliessend
(z. B. ``leisure=*``-Objekte werden nicht berücksichtigt), sondern eine
nachvollziehbare, auf den Anwendungsfall "Hofladen" zugeschnittene
Annäherung - lieber eine sinnvolle Teilmenge als eine überhastete
Rundum-Suche mit vielen irrelevanten Treffern.

Die Anfrage selbst nutzt den kombinierten ``nwr``-Selektor (Overpass-QL-
Kurzform für „nodes, ways or relations“, siehe OSM-Wiki, „Overpass
API/Overpass QL“) statt separater ``node``-/``way``-Anweisungen je Filter
- das deckt zusätzlich auch als **Relation** (z. B. Gebäude-Multipolygon)
gemappte Läden ab, die zuvor durch die auf Node/Way begrenzte Anfrage
übersehen worden wären, und hält die Anfrage kürzer.

### Erweiterung (Issue #11): ``amenity=marketplace`` und Namens-Heuristik

Eine Analyse im Rahmen von Issue #11 ergab: ``["shop"]`` ist ein reiner
**Schlüssel**-Filter (kein Wertevergleich) und matcht daher bereits **jeden**
``shop=*``-Wert, einschliesslich ``shop=farm`` (dediziertes, im OSM-Wiki
als "de facto" etabliertes Tag für Hofläden) und ``shop=greengrocer`` -
eine Erweiterung um konkrete ``shop``-Werte wäre also wirkungslos
(bereits abgedeckt). Tatsächlich fehlend war bislang ``amenity=marketplace``
(laut OSM-Wiki "a public marketplace where goods and services are traded
daily or weekly") - dafür existiert **kein** dokumentiertes Untertag wie
``marketplace=farmers`` (im OSM-Wiki ausdrücklich nicht als Untertag-System
geführt), weshalb ``amenity=marketplace`` undifferenziert nach Wert ergänzt
wurde, analog zu ``["shop"]``.

Zusätzlich deckt eine zweite, unabhängige Anfragegruppe
(``_OVERPASS_NAME_HEURISTIK_FILTER``) Hofläden ab, die auf OpenStreetMap
**kein** ``shop``-/``craft``-/``amenity``-Tag tragen, sondern nur als
Hofgebäude bzw. Hofstelle erfasst sind (``building=farm`` - "the main
building of a farm", bzw. ``landuse=farmyard`` - "an area of land with
farm buildings"; beide laut OSM-Wiki üblicherweise mit ``name=*``
versehen). Treffer aus dieser zweiten Gruppe werden nur dann
vorgeschlagen, wenn ihr Name zusätzlich einen der Begriffe
"Hof"/"Bauernhof"/"Hofladen"/"Laden" enthält (``_NAME_HEURISTIK_BEGRIFFE``,
Teilstring-Vergleich, gross-/kleinschreibungsunabhängig) - eine reine
Hofstelle ohne einen solchen Hinweis im Namen wird **nicht** vorgeschlagen,
da sie allein noch keinen Laden erkennen lässt. Diese Heuristik ist
bewusst als solche im Ergebnis gekennzeichnet (``OsmOrt.via_namen_heuristik``)
statt gleichwertig zu echten Tag-Treffern behandelt zu werden ("lieber
nichts als falsch"): Ein Teilstring-Treffer ist kein Beleg, nur ein
Hinweis zur Überprüfung durch die Benutzerin/den Benutzer.

## ``opening_hours``: begrenzter, dokumentierter Parser statt Freitext-Raten

OpenStreetMaps ``opening_hours``-Tag folgt einer eigenen, formal
spezifizierten Syntax (https://wiki.openstreetmap.org/wiki/Key:opening_hours)
- kein Fliesstext wie bei der Text-Heuristik aus Issue #9. Dieses Modul
unterstützt bewusst nur eine gängige Teilmenge dieser Syntax:
Semikolon-getrennte Regeln der Form ``<Tag(e)/-bereich(e)> <Zeit(en)>``,
mit englischen Zwei-Buchstaben-Wochentagskürzeln (``Mo,Tu,We,Th,Fr,Sa,Su``),
Wochentagbereichen (``Mo-Fr``), kommagetrennten Aufzählungen sowie
``HH:MM-HH:MM``-Zeitintervallen (auch mehrere pro Tag, kommagetrennt),
sowie den Sonderfall ``24/7``. **Nicht** unterstützt und bewusst
ignoriert (nicht interpretiert, nicht geraten): Feiertagsregeln (``PH``),
Datums-/Monatsbereiche, Kommentare in Klammern, ``off``/Ausnahmeregeln
sowie jede andere Syntax ausserhalb der genannten Teilmenge - eine Regel,
die nicht in dieses einfache Muster passt, wird komplett übersprungen,
statt eine falsche oder unvollständige Interpretation zu riskieren
("lieber nichts als falsch", siehe ``webseite_info.py``). Wie schon bei
der Text-Heuristik aus Issue #9 gilt zusätzlich: Liefern mehrere Regeln
unterschiedliche, widersprüchliche Zeiten für denselben Wochentag, wird
für diesen Wochentag kein Vorschlag geliefert.

## Review vor dem Speichern

Wie bei ``webseite_info.py`` liefert dieses Modul ausschliesslich
**Vorschlagsdaten zur Überprüfung** (siehe ``management.py``,
``ws_osm_info``) - das in Issue #9 eingeführte Bestätigungs-Popup wird
für diese zweite Datenquelle mitgenutzt (siehe
``static/hofkarte-panel.js``); es wird nichts automatisch gespeichert.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"  # Haupt-Instanz (primärer, zuerst versuchter Endpunkt)
# Bekannte, öffentliche Overpass-API-Instanzen in Versuchsreihenfolge
# (siehe Moduldoc, "Zuverlässigkeit: mehrere Instanzen statt eines
# Einzelpunkts") - schlägt eine Instanz fehl (Verbindungsfehler,
# Zeitüberschreitung, Fehler-/Drosselungs-Status), wird automatisch die
# nächste versucht, bevor die Suche als nicht erreichbar gilt.
OVERPASS_URLS: tuple[str, ...] = (
    OVERPASS_URL,
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
)
# HTTP-Statuscodes, bei denen ein Fehlversuch auf dieser Instanz nicht
# zwingend ein grundsätzliches Problem der Anfrage bedeutet (z. B. 429 -
# von den Overpass-Nutzungsrichtlinien selbst als Drosselungs-Antwort
# dokumentiert), sondern ebenfalls einen Versuch der nächsten Instanz
# rechtfertigt.
_OVERPASS_DROSSELUNGS_STATUS = {429, 502, 503, 504}
# Von den Overpass-Nutzungsrichtlinien ausdrücklich verlangt ("Be sure to
# check that your app or website adds User-Agent or Referer headers").
_USER_AGENT = "HofKarte/HomeAssistant (+https://github.com/rest-be/HofKarte)"
# Harte Absicherung, falls (z. B. in Tests oder bei fehlender Config
# Entry) kein über den Options Flow gespeicherter Vorgabewert ermittelt
# werden kann - der eigentliche, für die Verwaltungsoberfläche relevante
# Vorgabewert ist seit dessen Einführung ``const.DEFAULT_OSM_RADIUS_METER``
# (dauerhaft gespeichert statt nur pro Formularsitzung flüchtig, siehe
# ``config_flow.py``).
STANDARD_RADIUS_METER = 50
# Sinnvolle Grenzen für den seit Issue #11 im Formular einstellbaren
# Suchradius - ein zu kleiner Radius liefert praktisch nie Treffer (GPS-
# Ungenauigkeit), ein zu grosser erzeugt unnötig viele, meist irrelevante
# Treffer und eine unnötig grosse Overpass-Antwort. Werte ausserhalb dieses
# Bereichs werden von ``async_ermittle_osm_orte`` auf die jeweilige Grenze
# begrenzt (nicht als Fehler behandelt), da eine geringfügig falsche
# Eingabe hier keinen Sicherheits- oder Korrektheitsschaden anrichtet.
# An die iOS-App angeglichen (Options Flow, 20-2000 m statt der früheren
# 10-500 m).
MIN_RADIUS_METER = 20
MAX_RADIUS_METER = 2000
# Innerhalb der Overpass-Anfrage selbst gesetztes Zeitlimit (siehe
# _baue_overpass_query, "[out:json][timeout:...]"); das HTTP-Zeitlimit
# (ABRUF_TIMEOUT_SEKUNDEN) liegt bewusst etwas darüber, damit ein von der
# Overpass API selbst sauber beendetes, langsames Query noch als reguläre
# (wenn auch ggf. leere) Antwort ankommt, statt durch den HTTP-Client
# vorher abgebrochen zu werden.
_OVERPASS_QUERY_TIMEOUT_SEKUNDEN = 20
ABRUF_TIMEOUT_SEKUNDEN = 25
# Overpass-Antworten für einen kleinen Umkreis sind normalerweise winzig;
# 1 MB ist grosszügig genug für viele Treffer und begrenzt gleichzeitig
# den Ressourcenverbrauch durch eine übergrosse Antwort (siehe Moduldoc).
MAX_ANTWORT_BYTES = 1 * 1024 * 1024
_LESE_CHUNK_BYTES = 65536
# Gesamtbudget für den Overpass-Abruf über ALLE Instanzen (Befund F14);
# vorher konnten drei Instanzen nacheinander je ABRUF_TIMEOUT_SEKUNDEN
# (also bis zu 75 s) beanspruchen.
GESAMT_BUDGET_SEKUNDEN = 40
# Kurzer In-Memory-Cache identischer Anfragen (Befund F14).
CACHE_TTL_SEKUNDEN = 600
CACHE_MAX_EINTRAEGE = 32
_COORD_STELLEN = 4
_cache: dict[tuple[float, float, int], tuple[float, dict[str, Any]]] = {}


def _cache_leeren() -> None:
    """Cache leeren (Tests)."""
    _cache.clear()


def _cache_schluessel(lat: float, lon: float, radius: int) -> tuple[float, float, int]:
    return (round(lat, _COORD_STELLEN), round(lon, _COORD_STELLEN), radius)


def _cache_lesen(schluessel: tuple[float, float, int]) -> dict[str, Any] | None:
    eintrag = _cache.get(schluessel)
    if eintrag is None:
        return None
    zeit, daten = eintrag
    if time.monotonic() - zeit > CACHE_TTL_SEKUNDEN:
        del _cache[schluessel]
        return None
    return daten


def _cache_schreiben(schluessel: tuple[float, float, int], daten: dict[str, Any]) -> None:
    _cache.pop(schluessel, None)
    while len(_cache) >= CACHE_MAX_EINTRAEGE:
        del _cache[next(iter(_cache))]  # ältesten Eintrag verdrängen
    _cache[schluessel] = (time.monotonic(), daten)

_ERDRADIUS_METER = 6_371_000.0

# Für Hofläden relevante OpenStreetMap-Tags (siehe Moduldoc, "Tag-Auswahl").
_OVERPASS_FILTER = ('["shop"]', '["craft"="agricultural"]', '["amenity"="marketplace"]')

# Zusätzliche Anfragegruppe für Hofstellen ohne eigenes Laden-Tag (siehe
# Moduldoc, "Erweiterung (Issue #11)") - Treffer hieraus werden nur bei
# einem zusätzlichen Namenstreffer vorgeschlagen (_NAME_HEURISTIK_BEGRIFFE).
_OVERPASS_NAME_HEURISTIK_FILTER = ('["landuse"="farmyard"]', '["building"="farm"]')

# Begriffe der Namens-Heuristik (Issue #11) - Teilstring-Vergleich,
# gross-/kleinschreibungsunabhängig, bewusst einfach gehalten (siehe
# Moduldoc für die damit verbundene, akzeptierte Unschärfe).
_NAME_HEURISTIK_BEGRIFFE = ("hof", "bauernhof", "hofladen", "laden")

_OSM_WOCHENTAG = {
    "Mo": 1, "Tu": 2, "We": 3, "Th": 4, "Fr": 5, "Sa": 6, "Su": 7,
}
_OSM_TAG_ALTERNATIVEN = "|".join(_OSM_WOCHENTAG)
_OSM_TAG_REGEX = re.compile(
    rf"^({_OSM_TAG_ALTERNATIVEN})(-({_OSM_TAG_ALTERNATIVEN}))?$"
)
_OSM_ZEIT_REGEX = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


class OsmUngueltigeKoordinatenError(Exception):
    """Es wurden keine gültigen Latitude-/Longitude-Werte übergeben
    (Fehlerfall 1)."""


class OsmNichtErreichbarError(Exception):
    """Die Overpass API konnte nicht erreicht oder ihre Antwort nicht
    gelesen werden (Fehlerfall 2: Verbindungsfehler, Timeout,
    HTTP-Fehlerstatus, unlesbare/zu grosse Antwort)."""


class OsmKeineOrteGefundenError(Exception):
    """Die Overpass API war erreichbar, im angegebenen Umkreis wurden
    aber keine (benannten) Orte gefunden (Fehlerfall 3)."""


@dataclass(frozen=True, slots=True)
class OsmOrt:
    """Ein über die Overpass API gefundener, noch ungeprüfter
    Orts-Vorschlag (Issue #10). Reine Vorschlagsdaten zur Überprüfung
    durch die Benutzerin/den Benutzer im Verwaltungs-Panel - nichts
    hiervon wird automatisch gespeichert (siehe ``management.py``,
    ``ws_osm_info``). Optionale Felder sind ``None`` bzw. leer, wenn die
    jeweilige Information nicht vorhanden war (siehe Moduldoc, Prinzip
    "lieber nichts als falsch")."""

    name: str
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    website: str | None = None
    mobilnummer: str | None = None
    email: str | None = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    entfernung_meter: float | None = None
    # Issue #11: True, wenn dieser Treffer NICHT über ein Hofladen-Tag
    # (shop/craft/amenity), sondern nur über die Namens-Heuristik auf einer
    # Hofstelle (landuse=farmyard/building=farm) gefunden wurde - siehe
    # Moduldoc, "Erweiterung (Issue #11)". Dient der Kennzeichnung im
    # Trefferauswahl-Popup, nicht der Filterung selbst.
    via_namen_heuristik: bool = False


def _str_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _sind_gueltige_koordinaten(latitude: Any, longitude: Any) -> bool:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _entfernung_meter(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreisentfernung zweier WGS84-Koordinaten (Haversine-Formel) -
    dient nur der Sortierung/Anzeige in der Trefferauswahl bei mehreren
    Treffern, nicht der eigentlichen Umkreis-Filterung (die übernimmt die
    Overpass API selbst über ``around:``)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return _ERDRADIUS_METER * 2 * math.asin(math.sqrt(a))


def _adresse_aus_tags(tags: dict[str, Any]) -> str | None:
    strasse = _str_or_none(tags.get("addr:street"))
    hausnummer = _str_or_none(tags.get("addr:housenumber"))
    if strasse and hausnummer:
        return f"{strasse} {hausnummer}"
    return strasse or hausnummer


def _wochentag_bereich(von_tag: int, bis_tag: int | None) -> list[int]:
    """Liste der Wochentage eines Bereichs (z. B. Mo-Fr -> [1,2,3,4,5]),
    inkl. über die Wochengrenze laufender Bereiche (z. B. Sa-Mo ->
    [6,7,1]). Bewusst als eigene, kleine Kopie statt eines Imports aus
    ``webseite_info.py`` gehalten - beide Module sollen unabhängig
    voneinander lesbar/wartbar bleiben, ohne dass ein privater Helfer
    modulübergreifend geteilt wird."""
    if bis_tag is None:
        return [von_tag]
    if von_tag <= bis_tag:
        return list(range(von_tag, bis_tag + 1))
    return list(range(von_tag, 8)) + list(range(1, bis_tag + 1))


def _normalisiere_osm_uhrzeit(stunde: str, minute: str) -> str | None:
    try:
        h = int(stunde)
        m = int(minute)
    except ValueError:
        return None
    if h == 24 and m == 0:
        # OpenStreetMap erlaubt "24:00" als Tagesende. HofKarte speichert
        # "durchgehend geöffnet" als 00:00-23:59 (siehe FULL_DAY in
        # static/hofkarte-panel.js) - dieselbe Konvention wird hier
        # angewendet.
        return "23:59"
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def _parse_osm_regel(regel: str) -> dict[int, list[tuple[str, str]]] | None:
    """Parst eine einzelne, semikolon-getrennte ``opening_hours``-Regel
    (z. B. ``"Mo-Fr 08:00-18:00"`` oder ``"Sa,Su 08:00-12:00,14:00-16:00"``)
    zu einer Zuordnung Wochentag -> Liste der Zeitintervalle, die **diese
    eine Regel** für den jeweiligen Tag festlegt (mehrere Intervalle pro
    Tag, z. B. eine Mittagspause, sind hier ausdrücklich kein Widerspruch
    - erst wenn zwei **unterschiedliche Regeln** für denselben Tag
    abweichende Angaben liefern, ist das ein Widerspruch, siehe
    ``_extrahiere_oeffnungszeiten_osm``). Liefert ``None``, wenn die Regel
    nicht der unterstützten Teilmenge entspricht (siehe Moduldoc) - dann
    wird sie vom Aufrufer vollständig ignoriert, nicht teilweise
    interpretiert."""
    teile = regel.strip().split(None, 1)
    if len(teile) != 2:
        return None
    tage_teil, zeiten_teil = teile

    tage: list[int] = []
    for stueck in tage_teil.split(","):
        treffer = _OSM_TAG_REGEX.match(stueck.strip())
        if not treffer:
            return None
        von = _OSM_WOCHENTAG[treffer.group(1)]
        bis = _OSM_WOCHENTAG[treffer.group(3)] if treffer.group(3) else None
        tage.extend(_wochentag_bereich(von, bis))

    zeiten: list[tuple[str, str]] = []
    for stueck in zeiten_teil.split(","):
        treffer = _OSM_ZEIT_REGEX.match(stueck.strip())
        if not treffer:
            return None
        beginn = _normalisiere_osm_uhrzeit(treffer.group(1), treffer.group(2))
        ende = _normalisiere_osm_uhrzeit(treffer.group(3), treffer.group(4))
        if beginn is None or ende is None or beginn == ende:
            return None
        zeiten.append((beginn, ende))

    return {tag: list(zeiten) for tag in tage}


def _extrahiere_oeffnungszeiten_osm(opening_hours: Any) -> tuple[dict[str, Any], ...]:
    """Übersetzt den ``opening_hours``-Tag eines OSM-Objekts in HofKartes
    ``oeffnungszeiten``-Modell (siehe Moduldoc für die unterstützte
    Teilmenge und deren Grenzen).

    Pro Wochentag wird die Menge der von den einzelnen Regeln jeweils
    dafür festgelegten Zeit-"Signaturen" gesammelt (eine Signatur = alle
    Zeitintervalle, die EINE Regel für diesen Tag festlegt). Liefern alle
    Regeln, die sich zu einem Tag äussern, dieselbe Signatur (der übliche
    Fall: nur eine einzige Regel betrifft den Tag), werden deren
    Intervalle übernommen - auch wenn es mehrere sind (z. B.
    Mittagspause). Liefern unterschiedliche Regeln unterschiedliche
    Signaturen für denselben Tag, ist das ein echter Widerspruch - dann
    gibt es für diesen Tag keinen Vorschlag (andere, eindeutige
    Wochentage sind davon nicht betroffen)."""
    if not isinstance(opening_hours, str) or not opening_hours.strip():
        return ()

    wert = opening_hours.strip()
    if wert.lower() == "24/7":
        return tuple({"wochentag": tag, "beginn": "00:00", "ende": "23:59"} for tag in range(1, 8))

    kandidaten: dict[int, set[frozenset[tuple[str, str]]]] = {}
    for regel in wert.split(";"):
        regel = regel.strip()
        if not regel:
            continue
        geparst = _parse_osm_regel(regel)
        if geparst is None:
            continue  # nicht unterstützte Syntax - wird ignoriert, nicht geraten
        for tag, zeiten_liste in geparst.items():
            kandidaten.setdefault(tag, set()).add(frozenset(zeiten_liste))

    ergebnis: list[dict[str, Any]] = []
    for tag in sorted(kandidaten):
        signaturen = kandidaten[tag]
        if len(signaturen) != 1:
            continue  # widersprüchliche Regeln für diesen Tag -> kein Vorschlag
        for beginn, ende in sorted(next(iter(signaturen))):
            ergebnis.append({"wochentag": tag, "beginn": beginn, "ende": ende})
    return tuple(ergebnis)


def _baue_overpass_query(latitude: float, longitude: float, radius_meter: int) -> str:
    """Baut die Overpass-QL-Anfrage. Nutzt den kombinierten ``nwr``-
    Selektor (siehe Moduldoc, "Tag-Auswahl") statt separater ``node``-/
    ``way``-Anweisungen - deckt damit auch als Relation gemappte Läden ab.
    Das interne Zeitlimit (``[timeout:...]``) ist bewusst kleiner als das
    äussere HTTP-Zeitlimit (``ABRUF_TIMEOUT_SEKUNDEN``), damit die
    Overpass API selbst sauber mit einer regulären (ggf. leeren) Antwort
    abschliessen kann, statt vom HTTP-Client vorher abgebrochen zu
    werden.

    Enthält seit Issue #11 sowohl die Tag-Filter
    (``_OVERPASS_FILTER``) als auch die Filter für die Namens-Heuristik
    (``_OVERPASS_NAME_HEURISTIK_FILTER``) in derselben Anfrage (eine
    einzelne Overpass-Anfrage statt zwei separaten HTTP-Roundtrips) - die
    Unterscheidung, über welche Filtergruppe ein Treffer gefunden wurde,
    erfolgt anschliessend anhand seiner tatsächlichen Tags
    (``_klassifiziere_herkunft``), nicht anhand der Anfrage selbst."""
    umkreis = f"around:{int(radius_meter)},{latitude},{longitude}"
    alle_filter = _OVERPASS_FILTER + _OVERPASS_NAME_HEURISTIK_FILTER
    zeilen = [f"  nwr({umkreis}){filt};" for filt in alle_filter]
    return (
        f"[out:json][timeout:{_OVERPASS_QUERY_TIMEOUT_SEKUNDEN}];\n(\n"
        + "\n".join(zeilen)
        + "\n);\nout center tags;"
    )


def _klassifiziere_herkunft(tags: dict[str, Any], name: str) -> str | None:
    """Ordnet einen gefundenen Treffer seiner Herkunft zu (Issue #11):
    ``"tag"`` bei einem echten Hofladen-Tag (``shop``/``craft=agricultural``/
    ``amenity=marketplace``), ``"name"`` bei einer Hofstelle
    (``landuse=farmyard``/``building=farm``) mit zusätzlichem
    Namenstreffer (siehe Moduldoc), sonst ``None`` (Treffer wird verworfen -
    z. B. eine Hofstelle ohne passenden Namen, "lieber nichts als
    falsch")."""
    if (
        "shop" in tags
        or tags.get("craft") == "agricultural"
        or tags.get("amenity") == "marketplace"
    ):
        return "tag"

    ist_hofstelle = tags.get("landuse") == "farmyard" or tags.get("building") == "farm"
    if ist_hofstelle:
        name_klein = name.lower()
        if any(begriff in name_klein for begriff in _NAME_HEURISTIK_BEGRIFFE):
            return "name"

    return None


class _OsmInstanzFehlgeschlagen(Exception):
    """Interne Markierungs-Exception (nicht Teil der öffentlichen
    Modul-API): EINE Overpass-Instanz aus ``OVERPASS_URLS`` war nicht
    erreichbar oder lieferte keine brauchbare Antwort.
    ``_rufe_overpass_ab`` fängt sie ab und versucht die nächste
    konfigurierte Instanz, bevor endgültig ``OsmNichtErreichbarError``
    geworfen wird (siehe Moduldoc, "Zuverlässigkeit")."""


async def _rufe_overpass_instanz_ab(
    session: aiohttp.ClientSession, url: str, query: str
) -> dict[str, Any]:
    """Ruft EINE einzelne Overpass-Instanz (``url``) mit ``query`` auf und
    liefert die (begrenzt gelesene) JSON-Antwort, oder wirft
    ``_OsmInstanzFehlgeschlagen`` mit einer aussagekräftigen, für die
    Protokollierung in ``_rufe_overpass_ab`` bestimmten Fehlermeldung."""
    timeout = aiohttp.ClientTimeout(total=ABRUF_TIMEOUT_SEKUNDEN)
    headers = {"User-Agent": _USER_AGENT}
    try:
        async with session.post(
            url, data={"data": query}, timeout=timeout, headers=headers
        ) as antwort:
            if antwort.status >= 400:
                fehlertext = (await antwort.text())[:500]
                art = (
                    "Drosselung/temporärer Serverfehler"
                    if antwort.status in _OVERPASS_DROSSELUNGS_STATUS
                    else "Fehler"
                )
                raise _OsmInstanzFehlgeschlagen(
                    f"HTTP-Status {antwort.status} ({art}): {fehlertext}"
                )

            rohdaten = bytearray()
            async for chunk in antwort.content.iter_chunked(_LESE_CHUNK_BYTES):
                rohdaten.extend(chunk)
                if len(rohdaten) > MAX_ANTWORT_BYTES:
                    raise _OsmInstanzFehlgeschlagen(
                        f"Antwort überschreitet das Grössenlimit von "
                        f"{MAX_ANTWORT_BYTES} Bytes."
                    )

            try:
                return json.loads(bytes(rohdaten).decode("utf-8", errors="replace"))
            except json.JSONDecodeError as err:
                raise _OsmInstanzFehlgeschlagen(
                    f"Antwort ist kein gültiges JSON: {err}"
                ) from err
    except _OsmInstanzFehlgeschlagen:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise _OsmInstanzFehlgeschlagen(f"{type(err).__name__}: {err}") from err


async def _rufe_overpass_ab(session: aiohttp.ClientSession, query: str) -> dict[str, Any]:
    """Ruft ``query`` nacheinander gegen jede in ``OVERPASS_URLS``
    konfigurierte Instanz ab und liefert die JSON-Antwort der ersten
    erfolgreichen Instanz. Die Anfrageziele sind fest im Code hinterlegt
    (keine Weiterleitungsauflösung/SSRF-Prüfung nötig, siehe Moduldoc).

    Jeder einzelne Fehlversuch sowie das endgültige Scheitern aller
    Instanzen werden über ``_LOGGER`` protokolliert (Level ``warning``,
    sichtbar in den Home-Assistant-Protokollen auch ohne aktiviertes
    Debug-Logging) - inklusive der jeweiligen Instanz-URL, des HTTP-Status
    bzw. Exception-Typs und (bei einem Fehlerstatus) eines Ausschnitts des
    Antworttexts. Die an die Verwaltungsoberfläche zurückgegebene
    Fehlermeldung bleibt bewusst allgemein (siehe ``management.
    ws_osm_info``) - die Details lassen sich bei Bedarf nur über diese
    Protokollierung nachvollziehen."""
    letzter_fehler: Exception | None = None
    try:
        async with asyncio.timeout(GESAMT_BUDGET_SEKUNDEN):
            for url in OVERPASS_URLS:
                try:
                    return await _rufe_overpass_instanz_ab(session, url, query)
                except _OsmInstanzFehlgeschlagen as err:
                    _LOGGER.warning("Overpass-Instanz %s nicht erreichbar: %s", url, err)
                    letzter_fehler = err
    except TimeoutError as err:
        _LOGGER.warning(
            "Overpass-Abruf überschritt das Gesamtbudget von %s s.", GESAMT_BUDGET_SEKUNDEN
        )
        raise OsmNichtErreichbarError(
            "Die Overpass API (OpenStreetMap) hat innerhalb von "
            f"{GESAMT_BUDGET_SEKUNDEN} Sekunden nicht geantwortet."
        ) from err

    _LOGGER.warning(
        "Alle %s konfigurierten Overpass-Instanzen sind fehlgeschlagen: %s",
        len(OVERPASS_URLS),
        ", ".join(OVERPASS_URLS),
    )
    raise OsmNichtErreichbarError(
        "Die Overpass API (OpenStreetMap) konnte über keine der "
        f"{len(OVERPASS_URLS)} bekannten Instanzen erreicht werden."
    ) from letzter_fehler


def _koordinaten_aus_element(element: dict[str, Any]) -> tuple[float, float] | None:
    """Liefert die Koordinate eines Overpass-Elements - bei Nodes direkt
    ``lat``/``lon``, bei Ways/Relations der von ``out center`` gelieferte
    Mittelpunkt (``center``)."""
    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        zentrum = element.get("center")
        lat, lon = (zentrum or {}).get("lat"), (zentrum or {}).get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


async def async_ermittle_osm_orte(
    hass: HomeAssistant,
    latitude: Any,
    longitude: Any,
    radius_meter: int = STANDARD_RADIUS_METER,
) -> tuple[OsmOrt, ...]:
    """Sucht über die Overpass API nach Hofladen-artigen Orten im Umkreis
    von ``latitude``/``longitude`` und liefert sie nach Entfernung
    sortiert zurück.

    Wirft (siehe Moduldoc für die jeweilige Bedeutung):

    - :class:`OsmUngueltigeKoordinatenError` - keine gültigen
      Latitude-/Longitude-Werte übergeben (Fehlerfall 1).
    - :class:`OsmNichtErreichbarError` - Verbindungsfehler, Timeout,
      HTTP-Fehlerstatus oder unlesbare/zu grosse Antwort (Fehlerfall 2).
    - :class:`OsmKeineOrteGefundenError` - die Overpass API war
      erreichbar, es wurden aber keine (benannten) Orte im Umkreis
      gefunden (Fehlerfall 3).

    Das Ergebnis ist ausschliesslich eine Liste von Vorschlägen zur
    Überprüfung - siehe ``management.py``, ``ws_osm_info``.

    ``radius_meter`` wird seit Issue #11 serverseitig auf den Bereich
    ``MIN_RADIUS_METER``-``MAX_RADIUS_METER`` begrenzt (nicht als Fehler
    behandelt, siehe Moduldoc bei den Konstanten) - ein zu kleiner oder zu
    grosser Wert aus dem Formular führt so nicht zu einem Fehlerfall,
    sondern zu einer sinnvoll begrenzten Suche.
    """
    if not _sind_gueltige_koordinaten(latitude, longitude):
        raise OsmUngueltigeKoordinatenError(
            "Es sind keine gültigen Latitude-/Longitude-Werte vorhanden."
        )

    try:
        radius = int(radius_meter)
    except (TypeError, ValueError):
        radius = STANDARD_RADIUS_METER
    radius = max(MIN_RADIUS_METER, min(MAX_RADIUS_METER, radius))

    lat, lon = float(latitude), float(longitude)
    query = _baue_overpass_query(lat, lon, radius)
    schluessel = _cache_schluessel(lat, lon, radius)
    daten = _cache_lesen(schluessel)
    neu_abgerufen = False
    if daten is None:
        session = async_get_clientsession(hass)
        daten = await _rufe_overpass_ab(session, query)
        neu_abgerufen = True

    elemente = daten.get("elements")
    if not isinstance(elemente, list):
        raise OsmNichtErreichbarError(
            "Die Antwort der Overpass API hat nicht das erwartete Format."
        )
    if neu_abgerufen:
        _cache_schreiben(schluessel, daten)  # nur eine brauchbare Antwort

    orte: list[OsmOrt] = []
    for element in elemente:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue

        name = _str_or_none(tags.get("name"))
        if name is None:
            continue  # kein sinnvoller Auswahleintrag ohne Namen (siehe Moduldoc)

        herkunft = _klassifiziere_herkunft(tags, name)
        if herkunft is None:
            continue  # z. B. Hofstelle ohne passenden Namenstreffer (Issue #11)

        koordinate = _koordinaten_aus_element(element)
        entfernung = (
            _entfernung_meter(lat, lon, koordinate[0], koordinate[1])
            if koordinate is not None
            else None
        )

        orte.append(
            OsmOrt(
                name=name,
                adresse=_adresse_aus_tags(tags),
                plz=_str_or_none(tags.get("addr:postcode")),
                ort=_str_or_none(tags.get("addr:city")),
                website=(
                    _str_or_none(tags.get("website"))
                    or _str_or_none(tags.get("contact:website"))
                ),
                mobilnummer=(
                    _str_or_none(tags.get("phone"))
                    or _str_or_none(tags.get("contact:phone"))
                ),
                email=(
                    _str_or_none(tags.get("email"))
                    or _str_or_none(tags.get("contact:email"))
                ),
                oeffnungszeiten=_extrahiere_oeffnungszeiten_osm(tags.get("opening_hours")),
                entfernung_meter=round(entfernung, 1) if entfernung is not None else None,
                via_namen_heuristik=(herkunft == "name"),
            )
        )

    if not orte:
        raise OsmKeineOrteGefundenError(
            "Im angegebenen Umkreis wurden keine Orte gefunden."
        )

    orte.sort(key=lambda ort: (ort.entfernung_meter is None, ort.entfernung_meter))
    return tuple(orte)
