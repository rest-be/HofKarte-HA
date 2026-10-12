"""Tests für das Paket ``discovery`` (Hofladen-Discovery, Phase 1).

Kein Netzwerk: der Overpass-Abruf wird ersetzt, die Antworten sind
nachgebildete, an echte Messbefunde (Phase 0) angelehnte Daten."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hofkarte.discovery import overpass
from custom_components.hofkarte.discovery.geo import haversine_m
from custom_components.hofkarte.discovery.profile import FARMSHOP, PROFILE
from custom_components.hofkarte.discovery.text import name_aehnlichkeit, normalisiere
from custom_components.hofkarte.management import ws_discover
from custom_components.hofkarte.osm_info import OsmNichtErreichbarError

from .test_management import _FakeConnection, _setup_mit_coordinator

LAT, LON = 46.9480, 7.4474


def _node(id_: int, dlat: float, dlon: float, **tags: str) -> dict[str, Any]:
    return {"type": "node", "id": id_, "lat": LAT + dlat, "lon": LON + dlon, "tags": tags}


def _way(id_: int, dlat: float, dlon: float, **tags: str) -> dict[str, Any]:
    return {
        "type": "way",
        "id": id_,
        "center": {"lat": LAT + dlat, "lon": LON + dlon},
        "tags": tags,
    }


@pytest.fixture(autouse=True)
def _cache_leer():
    overpass._cache_leeren()
    yield
    overpass._cache_leeren()


# --- Profil / Query -----------------------------------------------------------


def test_profil_kern_ist_nur_shop_farm() -> None:
    assert FARMSHOP.filter(False) == ('["shop"="farm"]',)
    assert PROFILE["farmshop"] is FARMSHOP


def test_profil_erweitert_enthaelt_kern_ohne_duplikate() -> None:
    f = FARMSHOP.filter(True)
    assert f[0] == '["shop"="farm"]'
    assert len(f) == len(set(f)) and len(f) > 1


def test_query_enthaelt_umkreis_filter_und_timeout() -> None:
    q = overpass.baue_query(LAT, LON, 2000)
    assert "[out:json][timeout:20];" in q
    assert f'nwr(around:2000,{LAT:.6f},{LON:.6f})["shop"="farm"];' in q
    assert q.rstrip().endswith("out center tags;")


def test_query_erweitert_hat_mehr_zeilen() -> None:
    assert overpass.baue_query(LAT, LON, 500, erweitert=True).count("nwr(") > 1


def test_query_begrenzt_radius() -> None:
    assert "around:5000," in overpass.baue_query(LAT, LON, 99999)
    assert "around:50," in overpass.baue_query(LAT, LON, 1)


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [(None, 2000), ("abc", 2000), (0, 50), (-5, 50), (2000, 2000), (9999, 5000), ("750", 750)],
)
def test_begrenze_radius(eingabe: Any, erwartet: int) -> None:
    assert overpass.begrenze_radius(eingabe) == erwartet


# --- Antwortprüfung ------------------------------------------------------------


def test_pruefe_antwort_gueltig_leer_ist_kein_fehler() -> None:
    assert overpass.pruefe_antwort({"elements": []}) == []


def test_pruefe_antwort_timeout_remark_ist_fehler() -> None:
    daten = {"elements": [], "remark": "runtime error: Query timed out in \"query\" at line 3"}
    with pytest.raises(overpass.DiscoveryNichtErreichbarError):
        overpass.pruefe_antwort(daten)


def test_pruefe_antwort_remark_mit_treffern_wird_akzeptiert() -> None:
    daten = {"elements": [_node(1, 0, 0, shop="farm")], "remark": "runtime error: x"}
    assert len(overpass.pruefe_antwort(daten)) == 1


@pytest.mark.parametrize("daten", [None, [], "x", {}, {"elements": "x"}])
def test_pruefe_antwort_falsches_format(daten: Any) -> None:
    with pytest.raises(overpass.DiscoveryNichtErreichbarError):
        overpass.pruefe_antwort(daten)


# --- Kandidaten ----------------------------------------------------------------


def test_unbenannter_kandidat_bleibt_erhalten() -> None:
    k = overpass.parse_kandidaten([_way(1, 0.0001, 0, shop="farm")], LAT, LON)
    assert len(k) == 1
    assert k[0].unbenannt and k[0].name is None and k[0].refs == ("way/1",)


def test_namensvarianten_werden_genutzt() -> None:
    tags = {"shop": "farm", "brand": "Stähli Produits Fermiers", "operator": "Stähli SA"}
    k = overpass.parse_kandidaten([_node(1, 0, 0, **tags)], LAT, LON)[0]
    assert k.name == "Stähli Produits Fermiers"
    assert k.weitere_namen == ("Stähli SA",)
    assert not k.unbenannt


def test_felder_aus_tags() -> None:
    k = overpass.parse_kandidaten(
        [
            _node(
                1, 0, 0, shop="farm", name="Hof Müller", **{
                    "addr:street": "Dorfstrasse", "addr:housenumber": "5",
                    "addr:postcode": "3000", "addr:city": "Bern",
                    "contact:website": "https://mueller.example", "phone": "+41 31 000 00 00",
                    "contact:email": "a@mueller.example", "opening_hours": "Mo-Fr 08:00-12:00",
                }
            )
        ],
        LAT,
        LON,
    )[0]
    assert (k.adresse, k.plz, k.ort) == ("Dorfstrasse 5", "3000", "Bern")
    assert k.website == "https://mueller.example"
    assert k.telefon == "+41 31 000 00 00" and k.email == "a@mueller.example"
    assert k.oeffnungszeiten == "Mo-Fr 08:00-12:00"
    assert k.typ == ("shop=farm",)


def test_untrusted_text_wird_bereinigt_und_begrenzt() -> None:
    k = overpass.parse_kandidaten(
        [_node(1, 0, 0, shop="farm", name="Hof\x00\x07 X\n" + "y" * 1000)], LAT, LON
    )[0]
    assert "\x00" not in k.name and "\x07" not in k.name and "\n" not in k.name
    assert len(k.name) <= 300


def test_element_ohne_koordinate_oder_kein_dict_wird_uebersprungen() -> None:
    elemente = [
        {"type": "way", "id": 1, "tags": {"shop": "farm"}},  # kein center
        "kaputt",
        {"type": "node", "id": 2, "lat": "x", "lon": 1, "tags": {}},
        _node(3, 0, 0, shop="farm", name="Ok"),
    ]
    k = overpass.parse_kandidaten(elemente, LAT, LON)
    assert [x.refs for x in k] == [("node/3",)]


def test_sortierung_nach_entfernung() -> None:
    k = overpass.parse_kandidaten(
        [_node(1, 0.01, 0, shop="farm", name="Fern"), _node(2, 0.0005, 0, shop="farm", name="Nah")],
        LAT,
        LON,
    )
    assert [x.name for x in k] == ["Nah", "Fern"]
    assert k[0].entfernung_meter < k[1].entfernung_meter


# --- Zusammenführung -------------------------------------------------------------


def test_gebaeude_und_punkt_gleichen_namens_werden_ein_kandidat() -> None:
    """Befund Phase 0 (Rohrer): Gebäude + Punkt, ~16 m auseinander."""
    elemente = [
        _way(10, 0.0, 0.0, shop="farm", name="Hofladen Rohrer"),
        _node(11, 0.00015, 0.0, shop="farm", name="Hofladen Rohrer", website="https://rohrer.example",
              **{"addr:street": "Weg", "addr:housenumber": "1"}),
    ]
    k = overpass.parse_kandidaten(elemente, LAT, LON)
    assert len(k) == 1
    assert set(k[0].refs) == {"way/10", "node/11"}
    assert k[0].refs[0] == "node/11"  # reicheres Objekt ist das Hauptobjekt
    assert k[0].website == "https://rohrer.example" and k[0].adresse == "Weg 1"


def test_unbenanntes_und_benanntes_objekt_nebeneinander_werden_zusammengefuehrt() -> None:
    elemente = [
        _way(1, 0.0, 0.0, shop="farm"),
        _node(2, 0.0001, 0.0, shop="farm", name="La Ferme des Tourbières"),
    ]
    k = overpass.parse_kandidaten(elemente, LAT, LON)
    assert len(k) == 1 and k[0].name == "La Ferme des Tourbières"


def test_verschieden_benannte_laeden_im_selben_hof_bleiben_getrennt() -> None:
    elemente = [
        _node(1, 0, 0, shop="farm", name="Käserei Gerber"),
        _node(2, 0.0001, 0, shop="farm", name="Beeren Zbinden"),
    ]
    assert len(overpass.parse_kandidaten(elemente, LAT, LON)) == 2


def test_gleiche_website_domain_fuehrt_trotz_anderem_namen_zusammen() -> None:
    elemente = [
        _node(1, 0, 0, shop="farm", name="Famille Martin", website="https://www.martin.example/"),
        _node(2, 0.0001, 0, shop="farm", name="Boucherie de Campagne", website="http://martin.example"),
    ]
    k = overpass.parse_kandidaten(elemente, LAT, LON)
    assert len(k) == 1
    assert set(k[0].alle_namen) == {"Famille Martin", "Boucherie de Campagne"}


def test_gleicher_name_aber_weit_entfernt_bleibt_getrennt() -> None:
    elemente = [
        _node(1, 0, 0, shop="farm", name="Hofladen Rohrer"),
        _node(2, 0.01, 0, shop="farm", name="Hofladen Rohrer"),
    ]
    assert len(overpass.parse_kandidaten(elemente, LAT, LON)) == 2


def test_zusammenfuehrung_ist_unabhaengig_von_der_reihenfolge() -> None:
    a = _way(10, 0, 0, shop="farm", name="Hofladen Rohrer")
    b = _node(11, 0.00015, 0, shop="farm", name="Hofladen Rohrer", website="https://r.example")
    r1 = overpass.parse_kandidaten([a, b], LAT, LON)
    r2 = overpass.parse_kandidaten([b, a], LAT, LON)
    assert [k.refs for k in r1] == [k.refs for k in r2]


# --- Text / Geo --------------------------------------------------------------------


def test_normalisiere_und_aehnlichkeit() -> None:
    assert normalisiere("Müller-Hof ß") == "muller hof ss"
    assert name_aehnlichkeit("Müller Hofladen", "Hofladen Müller") == 1.0
    assert name_aehnlichkeit("Hofladen Müller", "Müller") > 0.9
    assert name_aehnlichkeit("Hofladen Müller", "Käserei Gerber") < 0.5
    assert name_aehnlichkeit(None, "x") == 0.0 and name_aehnlichkeit("x", "") == 0.0


def test_haversine_bekannter_wert() -> None:
    # 0,001° Breitengrad ~ 111,2 m
    assert haversine_m(46.0, 7.0, 46.001, 7.0) == pytest.approx(111.2, abs=0.5)
    assert haversine_m(1, 2, 1, 2) == 0


# --- async_suche (Abruf ersetzt) --------------------------------------------------------


async def test_async_suche_liefert_kandidaten_und_cached(hass: HomeAssistant) -> None:
    antwort = {"elements": [_node(1, 0.0005, 0, shop="farm", name="Hof A")]}
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab", AsyncMock(return_value=antwort)
    ) as fake:
        e1 = await overpass.async_suche(hass, LAT, LON, 1000)
        e2 = await overpass.async_suche(hass, LAT, LON, 1000)
    assert [k.name for k in e1] == ["Hof A"] and e1 == e2
    assert fake.await_count == 1  # zweiter Aufruf aus dem Cache
    query = fake.await_args.args[1]
    assert 'nwr(around:1000,' in query


async def test_async_suche_leeres_ergebnis_ist_kein_fehler(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab",
        AsyncMock(return_value={"elements": []}),
    ):
        assert await overpass.async_suche(hass, LAT, LON) == ()


async def test_async_suche_timeout_remark_wird_nicht_gecacht(hass: HomeAssistant) -> None:
    schlecht = {"elements": [], "remark": "runtime error: Query timed out"}
    gut = {"elements": [_node(1, 0, 0, shop="farm", name="Hof A")]}
    fake = AsyncMock(side_effect=[schlecht, gut])
    with patch("custom_components.hofkarte.osm_info._rufe_overpass_ab", fake):
        with pytest.raises(overpass.DiscoveryNichtErreichbarError):
            await overpass.async_suche(hass, LAT, LON)
        assert len(await overpass.async_suche(hass, LAT, LON)) == 1
    assert fake.await_count == 2


async def test_async_suche_mappt_instanzfehler(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab",
        AsyncMock(side_effect=OsmNichtErreichbarError("alle weg")),
    ):
        with pytest.raises(overpass.DiscoveryNichtErreichbarError, match="alle weg"):
            await overpass.async_suche(hass, LAT, LON)


@pytest.mark.parametrize(("lat", "lon"), [(None, 7), (999, 7), (46, 181), ("x", "y"), (float("nan"), 7)])
async def test_async_suche_ungueltige_koordinaten(hass: HomeAssistant, lat: Any, lon: Any) -> None:
    with pytest.raises(overpass.DiscoveryUngueltigeKoordinatenError):
        await overpass.async_suche(hass, lat, lon)


async def test_async_suche_unbekanntes_profil(hass: HomeAssistant) -> None:
    with pytest.raises(ValueError):
        await overpass.async_suche(hass, LAT, LON, profil="gibt-es-nicht")


async def test_async_suche_cache_ist_begrenzt(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab",
        AsyncMock(return_value={"elements": []}),
    ):
        for i in range(overpass.CACHE_MAX_EINTRAEGE + 5):
            await overpass.async_suche(hass, 40 + i * 0.01, 7.0)
    assert len(overpass._cache) == overpass.CACHE_MAX_EINTRAEGE


async def test_async_suche_cache_laeuft_ab(hass: HomeAssistant) -> None:
    fake = AsyncMock(return_value={"elements": []})
    with patch("custom_components.hofkarte.osm_info._rufe_overpass_ab", fake):
        await overpass.async_suche(hass, LAT, LON)
        with patch.object(overpass.time, "monotonic", return_value=1e9):
            await overpass.async_suche(hass, LAT, LON)
    assert fake.await_count == 2


# --- WebSocket ----------------------------------------------------------------------------


def _msg(**extra: Any) -> dict[str, Any]:
    return {
        "id": 90,
        "type": "hofkarte/management/discover",
        "latitude": LAT,
        "longitude": LON,
        "radius": 2000,
        "erweitert": False,
        **extra,
    }


async def _discover(hass: HomeAssistant, msg: dict[str, Any]) -> _FakeConnection:
    connection = _FakeConnection()
    ws_discover(hass, connection, msg)
    await hass.async_block_till_done()
    return connection


async def test_ws_discover_ist_registriert(hass: HomeAssistant) -> None:
    from custom_components.hofkarte.management import async_register_websocket_commands

    async_register_websocket_commands(hass)
    assert "hofkarte/management/discover" in hass.data.get("websocket_api", {})


async def test_ws_discover_liefert_kandidaten(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    antwort = {"elements": [_node(1, 0.0003, 0, shop="farm", name="Hof A"), _way(2, 0.002, 0, shop="farm")]}
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab", AsyncMock(return_value=antwort)
    ):
        connection = await _discover(hass, _msg())
    assert not connection.errors
    msg_id, ergebnis = connection.results[0]
    assert msg_id == 90 and ergebnis["radius"] == 2000
    assert [k["name"] for k in ergebnis["kandidaten"]] == ["Hof A", None]
    assert set(ergebnis["kandidaten"][0]) >= {"refs", "name", "entfernung_meter", "website", "typ"}
    assert not any(key.startswith("_") for key in ergebnis["kandidaten"][0])


async def test_ws_discover_keine_treffer_ist_leeres_ergebnis(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab",
        AsyncMock(return_value={"elements": []}),
    ):
        connection = await _discover(hass, _msg())
    assert connection.results[0][1]["kandidaten"] == []
    assert not connection.errors


async def test_ws_discover_unreachable(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab",
        AsyncMock(side_effect=OsmNichtErreichbarError("weg")),
    ):
        connection = await _discover(hass, _msg())
    assert connection.errors[0][:2] == (90, "unreachable")


async def test_ws_discover_invalid_coordinates(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    connection = await _discover(hass, _msg(latitude=999))
    assert connection.errors[0][:2] == (90, "invalid_coordinates")


async def test_ws_discover_not_ready_ohne_einrichtung(hass: HomeAssistant) -> None:
    connection = await _discover(hass, _msg())
    assert connection.errors[0][:2] == (90, "not_ready")


async def test_ws_discover_reicht_erweitert_durch(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    fake = AsyncMock(return_value={"elements": []})
    with patch("custom_components.hofkarte.osm_info._rufe_overpass_ab", fake):
        await _discover(hass, _msg(erweitert=True))
    assert fake.await_args.args[1].count("nwr(") > 1


async def test_ws_discover_bewertet_und_sortiert_nach_score(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    antwort = {
        "elements": [
            _node(1, 0.0049, 0, shop="farm", name="Wochenmarkt Belp"),  # ~545 m
            _node(2, 0.0135, 0, shop="farm", name="Rohrer"),  # ~1500 m
        ]
    }
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab", AsyncMock(return_value=antwort)
    ):
        c = await _discover(hass, _msg(name="Hofladen Rohrer Gemüse"))
    ks = c.results[0][1]["kandidaten"]
    assert [k["name"] for k in ks] == ["Rohrer", "Wochenmarkt Belp"]
    assert ks[0]["score"] > ks[1]["score"] and ks[0]["konfidenz"] in {"hoch", "mittel", "niedrig"}
    assert ks[0]["signale"]["name"] is not None


async def test_ws_discover_ohne_name_signal_ist_none(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    antwort = {"elements": [_node(1, 0.0001, 0, shop="farm", name="Hof A")]}
    with patch(
        "custom_components.hofkarte.osm_info._rufe_overpass_ab", AsyncMock(return_value=antwort)
    ):
        c = await _discover(hass, _msg())
    assert c.results[0][1]["kandidaten"][0]["signale"]["name"] is None
