"""Tests für osm_info.py (Issue #10, "Erweiterung OpenStreetMap zu #8").

Wie schon test_webseite_info.py deckt dieses Modul zwei Ebenen ab: die
reine ``opening_hours``-Parsing-/Adress-/Entfernungslogik (ohne Netzwerk)
sowie den asynchronen Overpass-API-Abruf inkl. Grössen-/Timeout-Limits und
der drei geforderten Fehlerfälle. Der HTTP-Abruf wird über eine
leichtgewichtige Fake-Session nachgebildet (kein echtes Netzwerk, kein
zusätzliches Test-Framework) - derselbe Ansatz wie in
test_webseite_info.py, hier für session.post() statt session.get().
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp
import pytest

from custom_components.hofkarte.osm_info import (
    MAX_ANTWORT_BYTES,
    MAX_RADIUS_METER,
    MIN_RADIUS_METER,
    OVERPASS_URLS,
    STANDARD_RADIUS_METER,
    OsmKeineOrteGefundenError,
    OsmNichtErreichbarError,
    OsmOrt,
    OsmUngueltigeKoordinatenError,
    _adresse_aus_tags,
    _baue_overpass_query,
    _entfernung_meter,
    _extrahiere_oeffnungszeiten_osm,
    _klassifiziere_herkunft,
    _sind_gueltige_koordinaten,
    async_ermittle_osm_orte,
)


# ---------------------------------------------------------------------------
# _extrahiere_oeffnungszeiten_osm: reine Parsing-Logik (kein Netzwerk)
# ---------------------------------------------------------------------------


def test_einfache_regel_ueber_werktage() -> None:
    assert _extrahiere_oeffnungszeiten_osm("Mo-Fr 08:00-18:00") == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_mehrere_regeln_durch_semikolon_getrennt() -> None:
    assert _extrahiere_oeffnungszeiten_osm("Mo-Fr 08:00-18:00; Sa 08:00-12:00") == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 6, "beginn": "08:00", "ende": "12:00"},
    )


def test_mehrere_zeitintervalle_desselben_tages_lunch_break() -> None:
    """Regressionstest für den während der Implementierung gefundenen Bug:
    zwei Zeitintervalle EINER Regel für denselben Tag (z. B. eine
    Mittagspause) sind kein Widerspruch und müssen beide übernommen
    werden."""
    ergebnis = _extrahiere_oeffnungszeiten_osm("Mo-Fr 08:00-12:00,14:00-18:00")
    assert ergebnis == (
        {"wochentag": 1, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 1, "beginn": "14:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 2, "beginn": "14:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 3, "beginn": "14:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 4, "beginn": "14:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 5, "beginn": "14:00", "ende": "18:00"},
    )


def test_widerspruechliche_regeln_fuer_denselben_tag_werden_verworfen() -> None:
    """Liefern zwei unterschiedliche Regeln unterschiedliche Zeiten für
    denselben Tag (hier: Montag), gibt es für diesen Tag keinen
    Vorschlag - die übrigen, eindeutigen Tage bleiben davon unberührt."""
    ergebnis = _extrahiere_oeffnungszeiten_osm("Mo-Fr 08:00-18:00; Mo 09:00-17:00")
    assert ergebnis == (
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_24_7_liefert_alle_wochentage_durchgehend() -> None:
    ergebnis = _extrahiere_oeffnungszeiten_osm("24/7")
    assert len(ergebnis) == 7
    assert all(e["beginn"] == "00:00" and e["ende"] == "23:59" for e in ergebnis)
    assert {e["wochentag"] for e in ergebnis} == set(range(1, 8))


def test_24_00_wird_zu_23_59_normalisiert() -> None:
    assert _extrahiere_oeffnungszeiten_osm("Mo 08:00-24:00") == (
        {"wochentag": 1, "beginn": "08:00", "ende": "23:59"},
    )


def test_ph_off_regel_wird_ignoriert_andere_regel_bleibt() -> None:
    """Feiertagsregeln (PH) und 'off'-Ausnahmen gehören nicht zur
    unterstützten Teilmenge (siehe Moduldoc) - die Regel wird komplett
    übersprungen, nicht teilweise interpretiert; andere Regeln in
    derselben Zeichenkette bleiben davon unberührt."""
    ergebnis = _extrahiere_oeffnungszeiten_osm("PH off; Mo-Fr 08:00-18:00")
    assert ergebnis == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_wochenendueberschreitender_tagbereich() -> None:
    ergebnis = _extrahiere_oeffnungszeiten_osm("Sa-Mo 09:00-12:00")
    assert {e["wochentag"] for e in ergebnis} == {6, 7, 1}


@pytest.mark.parametrize(
    "wert",
    [
        None,
        "",
        "   ",
        123,
        "völlig unverständlicher Text",
        "Mo 25:00-26:00",  # ungültige Uhrzeit
        "Xx-Yy 08:00-18:00",  # ungültige Tageskürzel
    ],
)
def test_nicht_unterstuetzte_oder_leere_werte_liefern_leeres_ergebnis(wert: Any) -> None:
    assert _extrahiere_oeffnungszeiten_osm(wert) == ()


def test_leere_zeitangabe_beginn_gleich_ende_wird_verworfen() -> None:
    assert _extrahiere_oeffnungszeiten_osm("Mo 08:00-08:00") == ()


# ---------------------------------------------------------------------------
# Weitere reine Hilfsfunktionen (kein Netzwerk)
# ---------------------------------------------------------------------------


def test_adresse_aus_tags_strasse_und_hausnummer() -> None:
    assert _adresse_aus_tags({"addr:street": "Musterweg", "addr:housenumber": "1"}) == "Musterweg 1"


def test_adresse_aus_tags_nur_strasse() -> None:
    assert _adresse_aus_tags({"addr:street": "Musterweg"}) == "Musterweg"


def test_adresse_aus_tags_leer_ohne_angaben() -> None:
    assert _adresse_aus_tags({}) is None


def test_entfernung_meter_gleiche_koordinate_ist_null() -> None:
    assert _entfernung_meter(46.948, 7.4474, 46.948, 7.4474) == pytest.approx(0.0, abs=0.01)


def test_entfernung_meter_plausibler_wert() -> None:
    # Bern -> Zürich: rund 95 km Luftlinie.
    entfernung = _entfernung_meter(46.948, 7.4474, 47.3769, 8.5417)
    assert 90_000 < entfernung < 100_000


def test_sind_gueltige_koordinaten() -> None:
    assert _sind_gueltige_koordinaten(46.948, 7.4474) is True
    assert _sind_gueltige_koordinaten(90, 180) is True
    assert _sind_gueltige_koordinaten(-90, -180) is True


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (None, 7.4474),
        (46.948, None),
        ("keine-zahl", 7.4474),
        (91, 7.4474),
        (46.948, 181),
        (-91, 7.4474),
        (46.948, -181),
    ],
)
def test_sind_gueltige_koordinaten_lehnt_ungueltige_werte_ab(lat: Any, lon: Any) -> None:
    assert _sind_gueltige_koordinaten(lat, lon) is False


# ---------------------------------------------------------------------------
# async_ermittle_osm_orte: Koordinaten-Validierung (Fehlerfall 1)
# ---------------------------------------------------------------------------


async def test_ungueltige_koordinaten_wirft_error(hass: Any) -> None:
    with pytest.raises(OsmUngueltigeKoordinatenError):
        await async_ermittle_osm_orte(hass, 999, 7.4474)


async def test_fehlende_koordinaten_wirft_error(hass: Any) -> None:
    with pytest.raises(OsmUngueltigeKoordinatenError):
        await async_ermittle_osm_orte(hass, None, None)


# ---------------------------------------------------------------------------
# async_ermittle_osm_orte: Overpass-Abruf (Fake-Session, kein echtes Netzwerk)
# ---------------------------------------------------------------------------


class _FakeContent:
    def __init__(self, data: bytes, chunk_size: int = 4096) -> None:
        self._data = data
        self._chunk_size = chunk_size

    def iter_chunked(self, _n: int):
        data = self._data
        chunk_size = self._chunk_size

        async def _generator():
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        return _generator()


class _FakeResponse:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status = status
        self.content = _FakeContent(body)
        self._body = body

    async def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _RaisingPost:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __call__(self, *args: Any, **kwargs: Any):
        raise self._exc


class _FakeSession:
    """Bildet, wie viele Overpass-Instanzen (``OVERPASS_URLS``) tatsächlich
    versucht werden, über eine Liste von Antworten nach - eine pro
    erwartetem Aufruf, in Reihenfolge. Ein Test, der ALLE Instanzen
    fehlschlagen lassen will, muss also ``len(OVERPASS_URLS)`` Antworten
    liefern (siehe ``_alle_instanzen_fehlschlagen``); ein Test, der nur den
    ersten (erfolgreichen) Versuch braucht, genügt mit einer einzigen."""

    def __init__(self, antworten: list[_FakeResponse]) -> None:
        self._antworten = list(antworten)
        self.aufrufe: list[dict[str, Any]] = []

    def post(
        self, url: str, *, data: Any = None, timeout: Any = None, headers: Any = None
    ):
        self.aufrufe.append({"url": url, "data": data, "headers": headers})
        return self._antworten.pop(0)


def _alle_instanzen_fehlschlagen(fabrik) -> "_FakeSession":
    """Baut eine _FakeSession, bei der JEDE konfigurierte Overpass-Instanz
    (``OVERPASS_URLS``) mit derselben, über ``fabrik()`` erzeugten Antwort
    fehlschlägt - für Tests, die das endgültige Scheitern aller Instanzen
    prüfen wollen (siehe Moduldoc, "Zuverlässigkeit")."""
    return _FakeSession([fabrik() for _ in OVERPASS_URLS])


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    monkeypatch.setattr(
        "custom_components.hofkarte.osm_info.async_get_clientsession",
        lambda hass: session,
    )


def _overpass_antwort(elemente: list[dict[str, Any]]) -> bytes:
    return json.dumps({"elements": elemente}).encode("utf-8")


async def test_erfolgreicher_abruf_liefert_sortierte_orte(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    nah = {
        "type": "node", "lat": 46.9481, "lon": 7.4475,
        "tags": {"name": "Naher Hofladen", "shop": "farm"},
    }
    fern = {
        "type": "node", "lat": 47.3769, "lon": 8.5417,
        "tags": {"name": "Ferner Hofladen", "shop": "farm"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([fern, nah]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    assert len(orte) == 2
    assert all(isinstance(o, OsmOrt) for o in orte)
    # Näherer Treffer muss zuerst kommen.
    assert orte[0].name == "Naher Hofladen"
    assert orte[1].name == "Ferner Hofladen"
    assert orte[0].entfernung_meter < orte[1].entfernung_meter


async def test_anfrage_sendet_identifizierenden_user_agent_header(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Von den Overpass-Nutzungsrichtlinien ausdrücklich verlangt: ein
    erkennbarer User-Agent- oder Referer-Header (siehe Moduldoc,
    "Zuverlässigkeit")."""
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "Hofladen", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    headers = session.aufrufe[0]["headers"]
    assert headers is not None
    assert "User-Agent" in headers
    assert "HofKarte" in headers["User-Agent"]


async def test_anfrage_nutzt_ersten_konfigurierten_endpunkt_zuerst(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "Hofladen", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    assert session.aufrufe[0]["url"] == OVERPASS_URLS[0]


def test_baue_overpass_query_nutzt_nwr_selektor_und_beide_filter() -> None:
    """Der kombinierte nwr-Selektor (statt separater node-/way-Anweisungen,
    siehe Moduldoc, "Tag-Auswahl") deckt zusätzlich als Relation gemappte
    Läden ab."""
    query = _baue_overpass_query(46.948, 7.4474, 50)
    assert "nwr(around:50,46.948,7.4474)[\"shop\"];" in query
    assert 'nwr(around:50,46.948,7.4474)["craft"="agricultural"];' in query
    assert "node(" not in query
    assert "way(" not in query
    assert query.startswith("[out:json][timeout:")
    assert query.rstrip().endswith("out center tags;")


def test_baue_overpass_query_enthaelt_marketplace_und_namens_heuristik_filter() -> None:
    """Issue #11: amenity=marketplace sowie die beiden Filter für die
    Namens-Heuristik (landuse=farmyard/building=farm) gehören zur selben
    Anfrage wie die bestehenden Tag-Filter (siehe Moduldoc, "Erweiterung
    (Issue #11)")."""
    query = _baue_overpass_query(46.948, 7.4474, 50)
    assert 'nwr(around:50,46.948,7.4474)["amenity"="marketplace"];' in query
    assert 'nwr(around:50,46.948,7.4474)["landuse"="farmyard"];' in query
    assert 'nwr(around:50,46.948,7.4474)["building"="farm"];' in query


async def test_way_element_nutzt_center_koordinate(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    way = {
        "type": "way",
        "center": {"lat": 46.9481, "lon": 7.4475},
        "tags": {"name": "Hofladen als Way", "shop": "farm"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([way]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    assert len(orte) == 1
    assert orte[0].name == "Hofladen als Way"
    assert orte[0].entfernung_meter is not None


async def test_vollstaendiges_element_liefert_alle_felder(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {
            "name": "Hofladen Muster",
            "shop": "farm",
            "addr:street": "Musterweg",
            "addr:housenumber": "1",
            "addr:postcode": "3000",
            "addr:city": "Bern",
            "website": "https://hofladen-muster.example",
            "phone": "+41 79 123 45 67",
            "email": "info@hofladen-muster.example",
            "opening_hours": "Mo-Fr 08:00-18:00",
        },
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    assert len(orte) == 1
    ort = orte[0]
    assert ort.name == "Hofladen Muster"
    assert ort.adresse == "Musterweg 1"
    assert ort.plz == "3000"
    assert ort.ort == "Bern"
    assert ort.website == "https://hofladen-muster.example"
    assert ort.mobilnummer == "+41 79 123 45 67"
    assert ort.email == "info@hofladen-muster.example"
    assert ort.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


async def test_contact_website_fallback(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {"name": "Hofladen", "shop": "farm", "contact:website": "https://beispiel.example"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert orte[0].website == "https://beispiel.example"


async def test_contact_phone_und_email_fallback(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {
            "name": "Hofladen", "shop": "farm",
            "contact:phone": "+41 79 123 45 67",
            "contact:email": "info@beispiel.example",
        },
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert orte[0].mobilnummer == "+41 79 123 45 67"
    assert orte[0].email == "info@beispiel.example"


async def test_elemente_ohne_namen_werden_verworfen(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    unbenannt = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([unbenannt]))])
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmKeineOrteGefundenError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


# ---------------------------------------------------------------------------
# async_ermittle_osm_orte: Fehlerfall 2 (nicht erreichbar) & Fehlerfall 3
# ---------------------------------------------------------------------------


async def test_keine_treffer_wirft_not_found(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([]))])
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmKeineOrteGefundenError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_http_fehlerstatus_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Fehlerstatus auf EINER Instanz führt zum Versuch der nächsten
    (siehe Moduldoc, "Zuverlässigkeit") - erst wenn ALLE konfigurierten
    Instanzen fehlschlagen, wird 'nicht erreichbar' geworfen."""
    session = _alle_instanzen_fehlschlagen(lambda: _FakeResponse(status=500))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert len(session.aufrufe) == len(OVERPASS_URLS)


async def test_429_drosselung_fuehrt_ebenfalls_zur_naechsten_instanz(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP 429 (von den Overpass-Nutzungsrichtlinien als Drosselungs-
    Antwort dokumentiert) wird wie ein sonstiger Fehlerstatus behandelt -
    ebenfalls ein Grund, die nächste Instanz zu versuchen."""
    session = _alle_instanzen_fehlschlagen(lambda: _FakeResponse(status=429))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert len(session.aufrufe) == len(OVERPASS_URLS)


async def test_erste_instanz_schlaegt_fehl_zweite_liefert_ergebnis(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kernverhalten des Fallbacks: Schlägt die erste konfigurierte
    Instanz fehl, wird automatisch die zweite versucht - der Aufruf
    liefert trotzdem ein Ergebnis, kein Fehler."""
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "Hofladen", "shop": "farm"}}
    session = _FakeSession(
        [_FakeResponse(status=503), _FakeResponse(body=_overpass_antwort([element]))]
    )
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    assert len(orte) == 1
    assert orte[0].name == "Hofladen"
    assert len(session.aufrufe) == 2
    assert session.aufrufe[0]["url"] == OVERPASS_URLS[0]
    assert session.aufrufe[1]["url"] == OVERPASS_URLS[1]


async def test_zu_grosse_antwort_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    zu_gross = b'{"elements": []}' + b" " * (MAX_ANTWORT_BYTES + 1)
    session = _alle_instanzen_fehlschlagen(lambda: _FakeResponse(body=zu_gross))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_ungueltiges_json_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _alle_instanzen_fehlschlagen(lambda: _FakeResponse(body=b"das ist kein JSON"))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_unerwartetes_antwortformat_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(body=json.dumps({"kein_elements_feld": True}).encode())])
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_verbindungsfehler_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.post = _RaisingPost(aiohttp.ClientConnectionError("kaputt"))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_timeout_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.post = _RaisingPost(TimeoutError("zu langsam"))
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


# ---------------------------------------------------------------------------
# _klassifiziere_herkunft / Namens-Heuristik / amenity=marketplace (Issue #11)
# ---------------------------------------------------------------------------


def test_klassifiziere_herkunft_shop_tag_ist_tag_treffer() -> None:
    assert _klassifiziere_herkunft({"shop": "farm", "name": "X"}, "X") == "tag"


def test_klassifiziere_herkunft_craft_agricultural_ist_tag_treffer() -> None:
    assert _klassifiziere_herkunft({"craft": "agricultural", "name": "X"}, "X") == "tag"


def test_klassifiziere_herkunft_marketplace_ist_tag_treffer() -> None:
    assert _klassifiziere_herkunft({"amenity": "marketplace", "name": "X"}, "X") == "tag"


def test_klassifiziere_herkunft_anderer_amenity_wert_ist_kein_treffer() -> None:
    # amenity=cafe o. Ä. darf NICHT als Tag-Treffer durchgehen - nur der
    # explizit dokumentierte Wert "marketplace" (siehe Moduldoc).
    assert _klassifiziere_herkunft({"amenity": "cafe", "name": "X"}, "X") is None


def test_klassifiziere_herkunft_farmyard_mit_passendem_namen_ist_namens_treffer() -> None:
    assert (
        _klassifiziere_herkunft({"landuse": "farmyard", "name": "Bauernhof Muster"}, "Bauernhof Muster")
        == "name"
    )


def test_klassifiziere_herkunft_building_farm_mit_passendem_namen_ist_namens_treffer() -> None:
    assert (
        _klassifiziere_herkunft({"building": "farm", "name": "Hofladen Muster"}, "Hofladen Muster")
        == "name"
    )


def test_klassifiziere_herkunft_farmyard_ohne_passenden_namen_ist_kein_treffer() -> None:
    # Eine Hofstelle allein (ohne Hinweis im Namen) ist noch kein
    # erkennbarer Laden - "lieber nichts als falsch" (siehe Moduldoc).
    assert _klassifiziere_herkunft({"landuse": "farmyard", "name": "Familie Muster"}, "Familie Muster") is None


def test_klassifiziere_herkunft_namensheuristik_ist_gross_kleinschreibungsunabhaengig() -> None:
    assert (
        _klassifiziere_herkunft({"building": "farm", "name": "HOFLADEN MUSTER"}, "HOFLADEN MUSTER")
        == "name"
    )


def test_klassifiziere_herkunft_weder_tag_noch_hofstelle_ist_kein_treffer() -> None:
    assert _klassifiziere_herkunft({"amenity": "bench", "name": "X"}, "X") is None


async def test_marketplace_treffer_wird_vorgeschlagen(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {"name": "Wochenmarkt", "amenity": "marketplace"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert orte[0].name == "Wochenmarkt"
    assert orte[0].via_namen_heuristik is False


async def test_namensheuristik_treffer_wird_als_solcher_gekennzeichnet(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {"name": "Hofladen Bergmatte", "landuse": "farmyard"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert len(orte) == 1
    assert orte[0].name == "Hofladen Bergmatte"
    assert orte[0].via_namen_heuristik is True


async def test_hofstelle_ohne_namenstreffer_wird_nicht_vorgeschlagen(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {"name": "Familie Muster", "building": "farm"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    with pytest.raises(OsmKeineOrteGefundenError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474)


async def test_echter_tag_treffer_hat_via_namen_heuristik_false(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {
        "type": "node", "lat": 46.949, "lon": 7.448,
        "tags": {"name": "Hofladen X", "shop": "farm"},
    }
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    orte = await async_ermittle_osm_orte(hass, 46.948, 7.4474)
    assert orte[0].via_namen_heuristik is False


# ---------------------------------------------------------------------------
# Suchradius (Issue #11): Clamping in async_ermittle_osm_orte
# ---------------------------------------------------------------------------


async def test_radius_wird_in_die_anfrage_uebernommen(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "X", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474, radius_meter=123)

    gesendete_query = session.aufrufe[0]["data"]["data"]
    assert "around:123," in gesendete_query


async def test_radius_zu_klein_wird_auf_minimum_begrenzt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "X", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474, radius_meter=1)

    gesendete_query = session.aufrufe[0]["data"]["data"]
    assert f"around:{MIN_RADIUS_METER}," in gesendete_query


async def test_radius_zu_gross_wird_auf_maximum_begrenzt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "X", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474, radius_meter=10_000)

    gesendete_query = session.aufrufe[0]["data"]["data"]
    assert f"around:{MAX_RADIUS_METER}," in gesendete_query


async def test_radius_default_ist_standard_radius(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "X", "shop": "farm"}}
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([element]))])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474)

    gesendete_query = session.aufrufe[0]["data"]["data"]
    assert f"around:{STANDARD_RADIUS_METER}," in gesendete_query


# ---------------------------------------------------------------------------
# F14: Gesamtbudget und kurzer In-Memory-Cache
# ---------------------------------------------------------------------------


def _ein_element() -> dict[str, Any]:
    return {"type": "node", "lat": 46.949, "lon": 7.448, "tags": {"name": "Hofladen", "shop": "farm"}}


async def test_identische_anfrage_wird_aus_dem_cache_bedient(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([_ein_element()]))])
    _patch_session(monkeypatch, session)

    erste = await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    zweite = await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    # auf 4 Nachkommastellen gerundet: praktisch gleicher Punkt -> ebenfalls Cache
    dritte = await async_ermittle_osm_orte(hass, 46.94803, 7.44741, 100)

    assert len(session.aufrufe) == 1
    assert erste == zweite and len(dritte) == 1


async def test_cache_schluessel_beruecksichtigt_radius_und_ort(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([_ein_element()])) for _ in range(3)])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    await async_ermittle_osm_orte(hass, 46.948, 7.4474, 200)
    await async_ermittle_osm_orte(hass, 47.5, 8.0, 100)
    assert len(session.aufrufe) == 3


async def test_cache_eintrag_laeuft_nach_der_ttl_ab(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custom_components.hofkarte import osm_info

    uhr = {"t": 1000.0}
    monkeypatch.setattr(osm_info.time, "monotonic", lambda: uhr["t"])
    session = _FakeSession([_FakeResponse(body=_overpass_antwort([_ein_element()])) for _ in range(2)])
    _patch_session(monkeypatch, session)

    await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    uhr["t"] += osm_info.CACHE_TTL_SEKUNDEN - 1
    await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    assert len(session.aufrufe) == 1
    uhr["t"] += 2
    await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    assert len(session.aufrufe) == 2


async def test_cache_ist_auf_32_eintraege_begrenzt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custom_components.hofkarte import osm_info

    session = _FakeSession([_FakeResponse(body=_overpass_antwort([_ein_element()])) for _ in range(40)])
    _patch_session(monkeypatch, session)
    for i in range(40):
        await async_ermittle_osm_orte(hass, 46.0 + i * 0.01, 7.0, 100)
    assert len(osm_info._cache) == osm_info.CACHE_MAX_EINTRAEGE == 32


async def test_fehler_und_unbrauchbare_antworten_werden_nicht_gecacht(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custom_components.hofkarte import osm_info

    session = _alle_instanzen_fehlschlagen(lambda: _FakeResponse(status=503, body=b"busy"))
    _patch_session(monkeypatch, session)
    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    assert osm_info._cache == {}

    session2 = _FakeSession([_FakeResponse(body=json.dumps({"elements": "kaputt"}).encode())])
    _patch_session(monkeypatch, session2)
    with pytest.raises(OsmNichtErreichbarError):
        await async_ermittle_osm_orte(hass, 46.948, 7.4474, 100)
    assert osm_info._cache == {}


async def test_gesamtbudget_bricht_haengende_instanzen_ab(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    from custom_components.hofkarte import osm_info

    class _Haengt:
        async def __aenter__(self) -> Any:
            await asyncio.sleep(30)

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    class _HaengendeSession:
        aufrufe = 0

        def post(self, *args: Any, **kwargs: Any) -> Any:
            type(self).aufrufe += 1
            return _Haengt()

    monkeypatch.setattr(osm_info, "GESAMT_BUDGET_SEKUNDEN", 0.1)
    _patch_session(monkeypatch, _HaengendeSession())
    with pytest.raises(OsmNichtErreichbarError, match="Sekunden"):
        await asyncio.wait_for(async_ermittle_osm_orte(hass, 46.948, 7.4474, 100), 5)
    assert _HaengendeSession.aufrufe == 1, "Budget gilt für alle Instanzen zusammen"
    assert osm_info.GESAMT_BUDGET_SEKUNDEN == 0.1


def test_gesamtbudget_ist_kleiner_als_die_summe_der_einzel_timeouts() -> None:
    from custom_components.hofkarte import osm_info

    assert osm_info.GESAMT_BUDGET_SEKUNDEN == 40
    assert osm_info.GESAMT_BUDGET_SEKUNDEN < osm_info.ABRUF_TIMEOUT_SEKUNDEN * len(osm_info.OVERPASS_URLS)
