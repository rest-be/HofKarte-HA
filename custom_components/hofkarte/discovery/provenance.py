"""Herkunft je Feld und Zusammenführung der Quellen zu einem Vorschlag.

Das Ergebnis liegt im **bestehenden** Hofladen-Format (``name``, ``adresse``,
``plz``, ``ort``, ``website``, ``mobilnummer``, ``email``,
``oeffnungszeiten``, ``angebote``, ``zahlungsarten``, ``latitude``,
``longitude``) plus ``quellen`` je Feld. Es ist ein reiner Vorschlag zur
Prüfung; gespeichert wird weiterhin nur über den bestehenden Speicherbefehl.

Quellenpriorität je Feld (Begründung: strukturierte, bewusst gepflegte
Angaben vor Textheuristiken; die Seite des Betriebs vor der Community-
Karte, wo es um veränderliche Angaben geht):

- ``name``: OpenStreetMap, sonst Website (Seitentitel ist nur Notlösung).
- Adresse (``adresse``/``plz``/``ort`` als Einheit): OSM, sonst Website.
- ``website``: OSM, sonst die angegebene Adresse.
- ``mobilnummer``/``email``: OSM, sonst Website.
- ``oeffnungszeiten``: Website, sonst OSM.
- ``angebote``/``zahlungsarten``: nur Website (über alle Seiten vereinigt).
- ``latitude``/``longitude``: OSM.

Bewusst **nicht** übernommen: Beschreibungstexte (kein automatischer
Beschreibungstext) und Bilder.

Weichen zwei Quellen für dasselbe Feld voneinander ab, wird der Wert der
Prioritätsquelle vorgeschlagen und die andere Quelle in ``abweichungen``
genannt, damit die Oberfläche warnen kann.

Quellenangabe (ODbL): OSM-Werte tragen ``quelle = "openstreetmap"`` und
``lizenz = "© OpenStreetMap-Mitwirkende (ODbL)"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .overpass import Kandidat
from .website import WebsiteErgebnis

OSM = "openstreetmap"
WEBSITE = "website"
OSM_LIZENZ = "© OpenStreetMap-Mitwirkende (ODbL)"
BESTAETIGT = "confirmed"  # steht ausdrücklich in der Quelle (kein Schluss/keine KI)
VERMUTET = "inferred"  # KI-Vermutung ohne wörtlichen Beleg im Text
WEBSITE_KI = "website_ki"  # Text stammt von der Website, ein Teil wurde per KI gefunden
KI = "ki"


@dataclass(frozen=True)
class Herkunft:
    quelle: str
    status: str = BESTAETIGT
    url: str | None = None
    lizenz: str | None = None

    def als_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"quelle": self.quelle, "status": self.status}
        if self.url:
            d["url"] = self.url
        if self.lizenz:
            d["lizenz"] = self.lizenz
        return d


@dataclass
class Vorschlag:
    daten: dict[str, Any] = field(default_factory=dict)
    quellen: dict[str, Herkunft] = field(default_factory=dict)
    abweichungen: dict[str, str] = field(default_factory=dict)  # Feld -> abweichende Quelle
    # Nur bei aktivierter KI: Werte, die die KI nannte, die aber im Text der
    # Website nicht wörtlich stehen. Nie in ``daten``; die Oberfläche zeigt sie
    # getrennt und nicht vorausgewählt (Status ``inferred``).
    vermutungen: dict[str, list[str]] = field(default_factory=dict)

    def als_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "daten": self.daten,
            "quellen": {k: v.als_dict() for k, v in self.quellen.items()},
            "abweichungen": self.abweichungen,
        }
        if self.vermutungen:
            d["vermutungen"] = self.vermutungen
        return d


def _osm_herkunft(kandidat: Kandidat) -> Herkunft:
    ref = kandidat.refs[0] if kandidat.refs else None
    url = f"https://www.openstreetmap.org/{ref}" if ref else None
    return Herkunft(OSM, url=url, lizenz=OSM_LIZENZ)


def _setze(v: Vorschlag, feld: str, wert: Any, herkunft: Herkunft) -> None:
    v.daten[feld] = wert
    v.quellen[feld] = herkunft


def _vereinige(listen: list[tuple[str, tuple[str, ...]]]) -> tuple[list[str], str | None]:
    """Vereinigt Textlisten (ohne Gross-/Kleinschreibung-Duplikate); liefert
    zusätzlich die URL der ersten Seite, die etwas beigetragen hat."""
    gesehen: set[str] = set()
    ergebnis: list[str] = []
    erste_url: str | None = None
    for url, werte in listen:
        for w in werte:
            key = w.strip().casefold()
            if key and key not in gesehen:
                gesehen.add(key)
                ergebnis.append(w.strip())
                erste_url = erste_url or url
    return ergebnis, erste_url


def _erster_wert(infos: list[tuple[str, Any]], attr: str) -> tuple[str | None, str | None]:
    for url, info in infos:
        wert = getattr(info, attr, None)
        if wert:
            return wert, url
    return None, None


def baue_vorschlag(
    kandidat: Kandidat | None,
    website: WebsiteErgebnis | None,
    angegebene_website: str | None = None,
) -> Vorschlag:
    """Führt OSM-Kandidat und Website-Ergebnis zu einem Vorschlag zusammen."""
    # Importe hier: osm_info benötigt Home Assistant (siehe overpass.async_suche).
    from ..osm_info import _extrahiere_oeffnungszeiten_osm

    v = Vorschlag()
    infos = website.infos if website else []
    osm_h = _osm_herkunft(kandidat) if kandidat else None

    def web_h(url: str | None) -> Herkunft:
        return Herkunft(WEBSITE, url=url)

    # name
    web_name, web_name_url = _erster_wert(infos, "name")
    if kandidat and kandidat.name:
        _setze(v, "name", kandidat.name, osm_h)  # type: ignore[arg-type]
        if web_name and web_name != kandidat.name:
            v.abweichungen["name"] = WEBSITE
    elif web_name:
        _setze(v, "name", web_name, web_h(web_name_url))

    # Adresse als Einheit
    if kandidat is not None and (kandidat.adresse or kandidat.plz or kandidat.ort):
        for feld in ("adresse", "plz", "ort"):
            wert = getattr(kandidat, feld)
            if wert:
                _setze(v, feld, wert, osm_h)  # type: ignore[arg-type]
        web_adr = _erster_wert(infos, "adresse")[0]
        if web_adr and kandidat.adresse and web_adr != kandidat.adresse:
            v.abweichungen["adresse"] = WEBSITE
    else:
        for url, info in infos:
            if info.adresse or info.plz or info.ort:
                for feld in ("adresse", "plz", "ort"):
                    wert = getattr(info, feld)
                    if wert:
                        _setze(v, feld, wert, web_h(url))
                break
    land, land_url = _erster_wert(infos, "land")
    if land:
        _setze(v, "land", land, web_h(land_url))

    # website
    if kandidat and kandidat.website:
        _setze(v, "website", kandidat.website, osm_h)  # type: ignore[arg-type]
    elif angegebene_website:
        _setze(v, "website", angegebene_website, Herkunft("angabe"))

    # Kontakt
    for feld_hof, feld_osm in (("mobilnummer", "telefon"), ("email", "email")):
        osm_wert = getattr(kandidat, feld_osm, None) if kandidat else None
        web_wert, web_url = _erster_wert(infos, feld_hof)
        if osm_wert:
            _setze(v, feld_hof, osm_wert, osm_h)  # type: ignore[arg-type]
            if web_wert and web_wert.replace(" ", "") != osm_wert.replace(" ", ""):
                v.abweichungen[feld_hof] = WEBSITE
        elif web_wert:
            _setze(v, feld_hof, web_wert, web_h(web_url))

    # Öffnungszeiten: Website vor OSM
    web_zeiten = next(((u, i.oeffnungszeiten) for u, i in infos if i.oeffnungszeiten), None)
    osm_zeiten = (
        _extrahiere_oeffnungszeiten_osm(kandidat.oeffnungszeiten)
        if kandidat and kandidat.oeffnungszeiten
        else ()
    )
    if web_zeiten:
        _setze(v, "oeffnungszeiten", list(web_zeiten[1]), web_h(web_zeiten[0]))
        if osm_zeiten and tuple(osm_zeiten) != tuple(web_zeiten[1]):
            v.abweichungen["oeffnungszeiten"] = OSM
    elif osm_zeiten:
        _setze(v, "oeffnungszeiten", list(osm_zeiten), osm_h)  # type: ignore[arg-type]

    # Listen: nur Website
    for feld in ("angebote", "zahlungsarten"):
        werte, liste_url = _vereinige([(u, getattr(i, feld)) for u, i in infos])
        if werte:
            _setze(v, feld, werte, web_h(liste_url))

    # Koordinate
    if kandidat:
        _setze(v, "latitude", kandidat.latitude, osm_h)  # type: ignore[arg-type]
        _setze(v, "longitude", kandidat.longitude, osm_h)  # type: ignore[arg-type]
    return v


def ergaenze_mit_ki(v: Vorschlag, ki: Any) -> None:
    """Ergänzt ``v`` um das Ergebnis der optionalen KI-Extraktion
    (``llm.KiErgebnis``). Die deterministischen Werte bleiben unverändert
    vorn; die KI ergänzt nur.

    - Belegte Listenwerte (wörtlich im Text) kommen zu ``angebote``/
      ``zahlungsarten``; war die Liste schon aus der Website, bleibt deren
      Quelle, sonst ``website_ki``.
    - Unbelegte Werte landen ausschliesslich in ``vermutungen``.
    - Öffnungszeiten (belegt und vom Parser verstanden) ersetzen die der
      OSM, nie die bereits von der Website gelesenen.
    """
    for feld in ("angebote", "zahlungsarten"):
        vorhanden = list(v.daten.get(feld) or [])
        bekannt = {str(x).casefold() for x in vorhanden}
        belegt = [w.text for w in getattr(ki, feld) if w.belegt and w.text.casefold() not in bekannt]
        unbelegt = [w.text for w in getattr(ki, feld) if not w.belegt and w.text.casefold() not in bekannt]
        if belegt:
            v.daten[feld] = vorhanden + belegt
            if feld not in v.quellen:
                v.quellen[feld] = Herkunft(WEBSITE_KI, BESTAETIGT, url=ki.url)
        if unbelegt:
            v.vermutungen[feld] = unbelegt
    if ki.oeffnungszeiten:
        bisher = v.quellen.get("oeffnungszeiten")
        if bisher is None or bisher.quelle == OSM:
            if bisher is not None:
                v.abweichungen["oeffnungszeiten"] = OSM
            v.daten["oeffnungszeiten"] = list(ki.oeffnungszeiten)
            v.quellen["oeffnungszeiten"] = Herkunft(WEBSITE_KI, BESTAETIGT, url=ki.url)
