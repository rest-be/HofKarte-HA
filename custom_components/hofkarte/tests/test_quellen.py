"""Tests für das optionale Feld ``quellen`` (Herkunft der Angaben, Discovery)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hofkarte.management import ws_list, ws_save
from custom_components.hofkarte.models import Quelle
from custom_components.hofkarte.parsing import HofladenValidationError, parse_hofladen

from .test_management import _FakeConnection, _setup_mit_coordinator

BASIS = {"id": "hof-1", "name": "Hof"}


def _q(**kw):
    return {"feld": "name", "quelle": "openstreetmap", **kw}


def test_ohne_quellen_ist_leer_abwaertskompatibel() -> None:
    assert parse_hofladen(BASIS).quellen == ()


def test_gueltige_quellen_werden_geparst() -> None:
    h = parse_hofladen(
        {
            **BASIS,
            "quellen": [
                _q(url="https://www.openstreetmap.org/node/1", lizenz="© OpenStreetMap-Mitwirkende (ODbL)"),
                {"feld": "email", "quelle": "website", "status": "inferred", "url": "http://x.example/k"},
            ],
        }
    )
    assert h.quellen[0] == Quelle("name", "openstreetmap", "confirmed", "https://www.openstreetmap.org/node/1", "© OpenStreetMap-Mitwirkende (ODbL)")
    assert h.quellen[1].status == "inferred" and h.quellen[1].lizenz is None


@pytest.mark.parametrize(
    "quellen",
    [
        "kein-liste",
        ["kein-dict"],
        [{"quelle": "website"}],  # Feld fehlt
        [_q(feld="id")],  # unbekanntes Feld
        [_q(quelle="")],
        [_q(quelle=None)],
        [_q(status="egal")],
        [_q(url="javascript:alert(1)")],
        [_q(url="ftp://x.example")],
        [_q(url=5)],
        [_q(quelle="x" * 41)],
        [_q(), _q(quelle="website")],  # doppeltes Feld
        [{"feld": f, "quelle": "w"} for f in ("name", "adresse", "plz", "ort", "land", "website", "mobilnummer", "email", "latitude", "longitude", "oeffnungszeiten", "angebote", "zahlungsarten", "beschreibung")] * 2,
    ],
)
def test_ungueltige_quellen_werden_abgelehnt(quellen) -> None:
    with pytest.raises(HofladenValidationError):
        parse_hofladen({**BASIS, "quellen": quellen})


async def test_quellen_ueberleben_speichern_und_liste(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    c = _FakeConnection()
    ws_save(hass, c, {"id": 1, "type": "hofkarte/management/save", "hofladen": {"name": "Hof A", "quellen": [_q(url="https://www.openstreetmap.org/node/7")]}})
    await hass.async_block_till_done()
    import asyncio

    for _ in range(200):
        if c.results or c.errors:
            break
        await asyncio.sleep(0.01)
    assert not c.errors
    assert c.results[0][1]["hofladen"]["quellen"][0]["url"].endswith("/node/7")

    c2 = _FakeConnection()
    ws_list(hass, c2, {"id": 2, "type": "hofkarte/management/list"})
    await hass.async_block_till_done()
    for _ in range(200):
        if c2.results or c2.errors:
            break
        await asyncio.sleep(0.01)
    liste = c2.results[0][1]["hoflaeden"]
    assert liste[0]["quellen"] == [
        {"feld": "name", "quelle": "openstreetmap", "status": "confirmed", "url": "https://www.openstreetmap.org/node/7", "lizenz": None}
    ]


async def test_ungueltige_quellen_beim_speichern_invalid_data(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    c = _FakeConnection()
    ws_save(hass, c, {"id": 3, "type": "hofkarte/management/save", "hofladen": {"name": "Hof", "quellen": [_q(url="javascript:x")]}})
    await hass.async_block_till_done()
    import asyncio

    for _ in range(200):
        if c.errors:
            break
        await asyncio.sleep(0.01)
    assert c.errors[0][1] == "invalid_data"


def test_panel_build_entspricht_manifest_version():
    """Die im Panel angezeigte Build-Kennung muss zur Manifest-Version passen."""
    import json
    import re
    from pathlib import Path

    basis = Path(__file__).resolve().parent.parent
    version = json.loads((basis / "manifest.json").read_text())["version"]
    js = (basis / "static" / "hofkarte-panel.js").read_text()
    treffer = re.search(r'const PANEL_BUILD = "([^"]+)"', js)
    assert treffer and treffer.group(1) == version


def test_finden_dialog_auswahlelemente_nicht_volle_breite():
    """Regression: globale ``input{width:100%}`` zog Radio/Checkbox über die
    ganze Zeile und drückte den Text an den rechten Rand (Schritt 2/3)."""
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js").read_text()
    regel = ".finden-kandidat input[type=radio],.finden-zeile input[type=checkbox]"
    assert regel in js
    zeile = next(z for z in js.splitlines() if regel in z)
    assert "width:auto" in zeile and "flex:0 0 auto" in zeile
