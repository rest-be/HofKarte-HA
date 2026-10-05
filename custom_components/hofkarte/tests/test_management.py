"""Tests für die WebSocket-Verwaltungs-API des HofKarte-Panels (management.py)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import (
    CONF_LISTEN_SORT_RICHTUNG,
    CONF_LISTEN_SORT_SPALTE,
    CONF_OSM_RADIUS_METER,
    DEFAULT_LISTEN_SORT_RICHTUNG,
    DEFAULT_LISTEN_SORT_SPALTE,
    DEFAULT_OSM_RADIUS_METER,
    DOMAIN,
)
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import (
    DuplicateHofladenIdError,
    HofladenDataProvider,
    HofladenNotFoundError,
)
from custom_components.hofkarte.management import (
    _finde_duplikat,
    _get_coordinator,
    _normalisiert,
    _serialize_hofladen,
    async_register_websocket_commands,
    ws_delete,
    ws_import_commit,
    ws_import_preview,
    ws_list,
    ws_osm_info,
    ws_save,
    ws_settings,
    ws_webseite_info,
)
from custom_components.hofkarte.models import Hofladen, Oeffnungszeit
from custom_components.hofkarte.osm_info import (
    OsmKeineOrteGefundenError,
    OsmNichtErreichbarError,
    OsmOrt,
    OsmUngueltigeKoordinatenError,
)
from custom_components.hofkarte.webseite_info import (
    WebseiteInfo,
    WebseiteInformationenNichtGefundenError,
    WebseiteNichtErreichbarError,
    WebseiteUngueltigeUrlError,
)


class _FakeConnection:
    """Leichtgewichtige Ersatz-Verbindung für WebSocket-Handler-Tests.

    Bildet nur das nach, was ``management.py`` tatsächlich verwendet:
    einen admin-berechtigten Benutzer sowie ``send_result``/``send_error``.
    """

    def __init__(self) -> None:
        self.user = SimpleNamespace(is_admin=True)
        self.results: list[tuple[Any, Any]] = []
        self.errors: list[tuple[Any, str, str]] = []

    def send_result(self, msg_id: Any, data: Any = None) -> None:
        self.results.append((msg_id, data))

    def send_error(self, msg_id: Any, code: str, message: str) -> None:
        self.errors.append((msg_id, code, message))


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def _setup_mit_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


class _ReadOnlyFakeProvider(HofladenDataProvider):
    """Rein lesender Provider zum Testen des 'nicht unterstützt'-Pfads."""

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        return [{"id": "hof-1", "name": "Hofladen Eins"}]


# ---------------------------------------------------------------------------
# _serialize_hofladen / _json_value
# ---------------------------------------------------------------------------


def test_serialize_hofladen_wandelt_verschachtelte_werte_in_json_typen_um() -> None:
    """Zeiten, Tupel und verschachtelte Dataclasses müssen JSON-serialisierbar
    werden (str/list/dict), nicht als Python-Objekte übrig bleiben."""
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-1",
        name="Hofladen Eins",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["id"] == "hof-1"
    assert isinstance(serialisiert["oeffnungszeiten"], list)
    erste_zeit = serialisiert["oeffnungszeiten"][0]
    assert erste_zeit["beginn"] == "08:00"
    assert erste_zeit["ende"] == "12:00"
    assert erste_zeit["wochentag"] == 1


def test_serialize_hofladen_zeiten_ohne_sekunden() -> None:
    """Regressionstest für den behobenen Sekunden-Bug: time.isoformat()
    liefert standardmässig 'hh:mm:ss' - die Detailansicht darf aber nur
    'hh:mm' anzeigen, da Öffnungszeiten ausschliesslich minutengenau
    erfasst werden."""
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-2",
        name="Hofladen Zwei",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=3, beginn=time(7, 30), ende=time(18, 45)),
        ),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    zeit = serialisiert["oeffnungszeiten"][0]

    assert zeit["beginn"] == "07:30"
    assert zeit["ende"] == "18:45"
    assert ":" not in zeit["beginn"][5:]  # kein zweiter Doppelpunkt -> keine Sekunden


# ---------------------------------------------------------------------------
# geoeffnet (serverseitig berechneter Öffnungsstatus für die
# Kacheln-/Listenansicht, siehe Issue #1 - keine Duplikation der
# Berechnungslogik in JavaScript)
# ---------------------------------------------------------------------------


def test_serialize_hofladen_enthaelt_geoeffnet_true() -> None:
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-3",
        name="Hofladen Drei",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    # Montag, 10 Uhr -> innerhalb des Intervalls.
    montag_10_uhr = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)

    serialisiert = _serialize_hofladen(hofladen, now=montag_10_uhr)

    assert serialisiert["geoeffnet"] is True


def test_serialize_hofladen_enthaelt_geoeffnet_false() -> None:
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-4",
        name="Hofladen Vier",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    # Montag, 14 Uhr -> ausserhalb des Intervalls.
    montag_14_uhr = datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)

    serialisiert = _serialize_hofladen(hofladen, now=montag_14_uhr)

    assert serialisiert["geoeffnet"] is False


def test_serialize_hofladen_geoeffnet_none_ohne_oeffnungszeiten() -> None:
    """Ohne hinterlegte Öffnungszeiten muss 'geoeffnet' None ('unbekannt')
    sein, nicht fälschlich False ('geschlossen')."""
    from datetime import datetime, timezone

    hofladen = Hofladen(id="hof-5", name="Hofladen Fünf")

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    )

    assert serialisiert["geoeffnet"] is None


def test_serialize_hofladen_enthaelt_hauptbild_url() -> None:
    from datetime import datetime, timezone

    from custom_components.hofkarte.models import Bild

    hofladen = Hofladen(
        id="hof-6",
        name="Hofladen Sechs",
        bilder=(Bild(url="https://example.com/logo.png"),),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["hauptbild_url"] == "https://example.com/logo.png"


def test_serialize_hofladen_hauptbild_url_none_ohne_bilder() -> None:
    from datetime import datetime, timezone

    hofladen = Hofladen(id="hof-7", name="Hofladen Sieben")

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["hauptbild_url"] is None


async def test_ws_list_liefert_geoeffnet_fuer_jeden_hofladen(
    hass: HomeAssistant,
) -> None:
    """End-zu-Ende: Der WebSocket-Befehl 'list' muss 'geoeffnet' für jeden
    Hofladen mitliefern, konsistent mit dem tatsächlichen Zustand des
    Binary Sensors 'Geöffnet'."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-a", "name": "Hofladen A"})

    connection = _FakeConnection()
    ws_list(hass, connection, {"id": 1, "type": "hofkarte/management/list"})

    _, ergebnis = connection.results[0]
    hoflaeden = ergebnis["hoflaeden"]
    assert len(hoflaeden) == 1
    # Ohne hinterlegte Öffnungszeiten ist der Status unbekannt.
    assert hoflaeden[0]["geoeffnet"] is None


async def test_ws_save_liefert_geoeffnet_im_rueckgabe_hofladen(
    hass: HomeAssistant,
) -> None:
    """Auch die Rückgabe von 'save' muss 'geoeffnet' enthalten, damit die
    Oberfläche eine einzelne Änderung ohne vollständigen Re-List
    aktualisieren kann."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 1,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-b", "name": "Hofladen B"},
        },
    )
    await hass.async_block_till_done()

    _, ergebnis = connection.results[0]
    assert "geoeffnet" in ergebnis["hofladen"]


# ---------------------------------------------------------------------------
# _get_coordinator
# ---------------------------------------------------------------------------


def test_get_coordinator_wirft_fehler_wenn_nicht_eingerichtet(
    hass: HomeAssistant,
) -> None:
    """Ohne eingerichtete Config Entry muss ein klarer Fehler geworfen werden."""
    with pytest.raises(ValueError):
        _get_coordinator(hass)


# ---------------------------------------------------------------------------
# ws_list
# ---------------------------------------------------------------------------


async def test_ws_list_liefert_aktuelle_hoflaeden(hass: HomeAssistant) -> None:
    """ws_list muss alle aktuellen Hofläden serialisiert zurückgeben."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    connection = _FakeConnection()
    ws_list(hass, connection, {"id": 1, "type": "hofkarte/management/list"})

    assert len(connection.results) == 1
    msg_id, data = connection.results[0]
    assert msg_id == 1
    namen = [eintrag["name"] for eintrag in data["hoflaeden"]]
    assert "Hofladen Eins" in namen


# ---------------------------------------------------------------------------
# ws_save
# ---------------------------------------------------------------------------


async def test_ws_save_erstellt_neuen_hofladen_mit_generierter_id(
    hass: HomeAssistant,
) -> None:
    """Ohne 'id' im Rohdatensatz muss ws_save automatisch eine ID vergeben."""
    coordinator = await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 2,
            "type": "hofkarte/management/save",
            "hofladen": {"name": "Neuer Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 1
    msg_id, data = connection.results[0]
    assert msg_id == 2
    neue_id = data["hofladen"]["id"]
    assert neue_id.startswith("hofladen-")
    assert neue_id in coordinator.data
    assert coordinator.data[neue_id].name == "Neuer Hofladen"


async def test_ws_save_aktualisiert_bestehenden_hofladen(
    hass: HomeAssistant,
) -> None:
    """Mit bereits existierender 'id' muss ws_save den Hofladen aktualisieren
    statt einen Duplikat-Fehler zu erzeugen."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Alter Name"})

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 3,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-1", "name": "Neuer Name"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    assert coordinator.data["hof-1"].name == "Neuer Name"


async def test_ws_save_erfolg_enthaelt_konflikt_false_und_neue_version(
    hass: HomeAssistant,
) -> None:
    """Eine erfolgreiche Aktualisierung muss 'konflikt': false sowie die neue,
    serverseitig erhöhte Version im Ergebnis liefern (Phase 8b)."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Alter Name"})

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 3,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-1", "name": "Neuer Name", "version": 1},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    msg_id, data = connection.results[0]
    assert data["konflikt"] is False
    assert data["hofladen"]["version"] == 2


async def test_ws_save_versionskonflikt_liefert_aktuellen_serverstand(
    hass: HomeAssistant,
) -> None:
    """Eine veraltete 'version' darf keinen Fehler auslösen, sondern muss als
    Ergebnis mit 'konflikt': true und dem aktuellen Serverstand zurückkommen,
    damit die aufrufende Oberfläche eine Konflikt-Ansicht zeigen kann."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Serverstand"})
    # Ein zweites Gerät hat zwischenzeitlich bereits gespeichert.
    await coordinator.async_save_hofladen(
        {"id": "hof-1", "name": "Serverstand (aktualisiert)", "version": 1}
    )

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 3,
            "type": "hofkarte/management/save",
            # Noch auf Version 1 - der Server ist inzwischen bei Version 2.
            "hofladen": {"id": "hof-1", "name": "Veralteter Stand", "version": 1},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    msg_id, data = connection.results[0]
    assert data["konflikt"] is True
    assert data["aktueller_hofladen"]["name"] == "Serverstand (aktualisiert)"
    assert data["aktueller_hofladen"]["version"] == 2
    # Der gespeicherte Stand darf durch den abgelehnten Versuch nicht
    # verändert worden sein.
    assert coordinator.data["hof-1"].name == "Serverstand (aktualisiert)"


async def test_ws_save_ungueltige_daten_sendet_fehler(hass: HomeAssistant) -> None:
    """Ungültige Rohdaten (z. B. leerer Name) müssen als Fehler zurückgemeldet
    werden, ohne den Store zu verändern."""
    coordinator = await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 4,
            "type": "hofkarte/management/save",
            "hofladen": {"name": ""},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 4
    assert code == "invalid_data"
    assert coordinator.data == {}


# ---------------------------------------------------------------------------
# ws_delete
# ---------------------------------------------------------------------------


async def test_ws_delete_entfernt_hofladen(hass: HomeAssistant) -> None:
    """ws_delete muss einen bestehenden Hofladen dauerhaft entfernen."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 5,
            "type": "hofkarte/management/delete",
            "hofladen_id": "hof-1",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    assert len(connection.results) == 1
    assert "hof-1" not in coordinator.data


async def test_ws_delete_unbekannte_id_sendet_not_found_fehler(
    hass: HomeAssistant,
) -> None:
    """Eine nicht existierende ID muss einen 'not_found'-Fehler ergeben."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 6,
            "type": "hofkarte/management/delete",
            "hofladen_id": "unbekannt",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 6
    assert code == "not_found"


async def test_ws_delete_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen 'not_supported'-Fehler ergeben."""
    provider = _ReadOnlyFakeProvider()
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["fake-entry"] = coordinator

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 7,
            "type": "hofkarte/management/delete",
            "hofladen_id": "hof-1",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 7
    assert code == "not_supported"


# ---------------------------------------------------------------------------
# async_register_websocket_commands
# ---------------------------------------------------------------------------


async def test_async_register_websocket_commands_registriert_alle_drei(
    hass: HomeAssistant,
) -> None:
    """Alle drei WebSocket-Befehle müssen registriert werden."""
    async_register_websocket_commands(hass)

    ws_handlers = hass.data.get("websocket_api", {})
    assert "hofkarte/management/list" in ws_handlers
    assert "hofkarte/management/save" in ws_handlers
    assert "hofkarte/management/delete" in ws_handlers
    assert "hofkarte/management/settings" in ws_handlers


# ---------------------------------------------------------------------------
# Fehlerbehandlung: HofKarte nicht (mehr) eingerichtet
# ---------------------------------------------------------------------------


def test_ws_list_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    """Ohne eingerichtetes HofKarte darf keine unbehandelte ValueError aus
    dem WebSocket-Handler entkommen – ein sauberer Fehler muss zurückkommen."""
    connection = _FakeConnection()

    ws_list(hass, connection, {"id": 10, "type": "hofkarte/management/list"})

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 10
    assert code == "not_ready"


async def test_ws_save_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_save(
        hass,
        connection,
        {
            "id": 11,
            "type": "hofkarte/management/save",
            "hofladen": {"name": "Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 11
    assert code == "not_ready"


async def test_ws_delete_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_delete(
        hass,
        connection,
        {"id": 12, "type": "hofkarte/management/delete", "hofladen_id": "hof-1"},
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 12
    assert code == "not_ready"


async def test_ws_save_nicht_unterstuetzt_ergibt_eigenen_fehlercode(
    hass: HomeAssistant,
) -> None:
    """Ein nicht schreibfähiger Provider muss als 'not_supported' gemeldet
    werden, nicht als 'invalid_data' (Fehlerarten klar unterscheiden)."""
    provider = _ReadOnlyFakeProvider()
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["fake-entry"] = coordinator

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 13,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-neu", "name": "Neuer Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 13
    assert code == "not_supported"


async def test_management_greift_nicht_mehr_direkt_auf_provider_zu() -> None:
    """Qualitätssicherung: management.py darf nicht mehr über
    ``coordinator._provider`` auf den Data Provider zugreifen (Kapselung
    über die öffentliche Coordinator-API)."""
    import inspect

    from custom_components.hofkarte import management

    quelltext = inspect.getsource(management)
    assert "coordinator._provider" not in quelltext
    assert "._provider" not in quelltext


# ---------------------------------------------------------------------------
# _normalisiert / _finde_duplikat (Issue #5: Duplikaterkennung beim Import)
# ---------------------------------------------------------------------------


def test_normalisiert_ignoriert_gross_kleinschreibung_und_leerzeichen() -> None:
    assert _normalisiert("  Hofladen Müller ") == _normalisiert("hofladen müller")


def test_normalisiert_none_ergibt_leeren_string() -> None:
    assert _normalisiert(None) == ""


def test_finde_duplikat_erkennt_uebereinstimmenden_namen_und_adresse() -> None:
    bestehend = Hofladen(id="hof-1", name="Hofladen Müller", adresse="Dorfstrasse 1")
    importiert = Hofladen(id="fremd-1", name=" hofladen müller ", adresse="dorfstrasse 1")

    treffer = _finde_duplikat(importiert, [bestehend])

    assert treffer is not None
    assert treffer.id == "hof-1"


def test_finde_duplikat_unterschiedliche_adresse_kein_duplikat() -> None:
    bestehend = Hofladen(id="hof-1", name="Hofladen Müller", adresse="Dorfstrasse 1")
    importiert = Hofladen(id="fremd-1", name="Hofladen Müller", adresse="Bergweg 9")

    assert _finde_duplikat(importiert, [bestehend]) is None


def test_finde_duplikat_ohne_adresse_auf_einer_seite_entscheidet_nur_der_name() -> None:
    """Besitzt einer der beiden Datensätze keine Adresse, darf die
    fehlende Adresse kein Duplikat verhindern (siehe Issue #5)."""
    bestehend = Hofladen(id="hof-1", name="Hofladen Müller", adresse=None)
    importiert = Hofladen(id="fremd-1", name="Hofladen Müller", adresse="Dorfstrasse 1")

    treffer = _finde_duplikat(importiert, [bestehend])

    assert treffer is not None
    assert treffer.id == "hof-1"


def test_finde_duplikat_liefert_none_ohne_uebereinstimmenden_namen() -> None:
    bestehend = Hofladen(id="hof-1", name="Hofladen Müller")
    importiert = Hofladen(id="fremd-1", name="Ganz anderer Hofladen")

    assert _finde_duplikat(importiert, [bestehend]) is None


# ---------------------------------------------------------------------------
# ws_import_preview
# ---------------------------------------------------------------------------


def test_ws_import_preview_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_import_preview(
        hass,
        connection,
        {
            "id": 20,
            "type": "hofkarte/management/import_preview",
            "hoflaeden": [{"id": "hof-1", "name": "Hofladen Eins"}],
        },
    )

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 20
    assert code == "not_ready"


async def test_ws_import_preview_leere_liste_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_preview(
        hass,
        connection,
        {"id": 21, "type": "hofkarte/management/import_preview", "hoflaeden": []},
    )

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 21
    assert code == "invalid_data"


async def test_ws_import_preview_ungueltiger_datensatz_sendet_fehler_ohne_teilresultat(
    hass: HomeAssistant,
) -> None:
    """Fail-Fast: Ist auch nur ein Datensatz ungültig, darf keine
    (Teil-)Vorschau zurückkommen."""
    await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_preview(
        hass,
        connection,
        {
            "id": 22,
            "type": "hofkarte/management/import_preview",
            "hoflaeden": [
                {"id": "hof-1", "name": "Gültiger Hofladen"},
                {"id": "hof-2", "name": ""},
            ],
        },
    )

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, message = connection.errors[0]
    assert msg_id == 22
    assert code == "invalid_data"
    assert "#2" in message


async def test_ws_import_preview_kennzeichnet_duplikat(hass: HomeAssistant) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen(
        {"id": "hof-1", "name": "Hofladen Müller", "adresse": "Dorfstrasse 1"}
    )

    connection = _FakeConnection()
    ws_import_preview(
        hass,
        connection,
        {
            "id": 23,
            "type": "hofkarte/management/import_preview",
            "hoflaeden": [
                {
                    "id": "fremde-id",
                    "name": "hofladen müller",
                    "adresse": "dorfstrasse 1",
                }
            ],
        },
    )

    _, ergebnis = connection.results[0]
    eintrag = ergebnis["eintraege"][0]
    assert eintrag["duplikat_von"] == "hof-1"
    assert eintrag["bestehend"]["id"] == "hof-1"


async def test_ws_import_preview_kennzeichnet_neuen_hofladen_ohne_duplikat(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    connection = _FakeConnection()
    ws_import_preview(
        hass,
        connection,
        {
            "id": 24,
            "type": "hofkarte/management/import_preview",
            "hoflaeden": [{"id": "fremde-id", "name": "Ganz anderer Hofladen"}],
        },
    )

    _, ergebnis = connection.results[0]
    eintrag = ergebnis["eintraege"][0]
    assert eintrag["duplikat_von"] is None
    assert eintrag["bestehend"] is None


# ---------------------------------------------------------------------------
# ws_import_commit
# ---------------------------------------------------------------------------


async def test_ws_import_commit_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_import_commit(
        hass,
        connection,
        {
            "id": 30,
            "type": "hofkarte/management/import_commit",
            "eintraege": [{"hofladen": {"name": "X"}, "aktion": "neu"}],
        },
    )

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 30
    assert code == "not_ready"


async def test_ws_import_commit_ohne_eintraege_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_commit(
        hass,
        connection,
        {"id": 31, "type": "hofkarte/management/import_commit", "eintraege": []},
    )

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 31
    assert code == "invalid_data"


async def test_ws_import_commit_neu_erzeugt_hofladen_mit_frischer_id(
    hass: HomeAssistant,
) -> None:
    """Eine im Importdatensatz enthaltene fremde 'id' muss verworfen und
    durch eine frische, lokal vergebene ID ersetzt werden."""
    coordinator = await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_commit(
        hass,
        connection,
        {
            "id": 32,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {
                    "hofladen": {"id": "fremde-id-von-anderer-instanz", "name": "Neuer Hofladen"},
                    "aktion": "neu",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    _, ergebnis = connection.results[0]
    assert ergebnis == {"importiert": 1, "aktualisiert": 0, "uebersprungen": 0}
    assert "fremde-id-von-anderer-instanz" not in coordinator.data
    namen = [h.name for h in coordinator.data.values()]
    assert "Neuer Hofladen" in namen


async def test_ws_import_commit_aktualisieren_ueberschreibt_bestehenden_hofladen(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Alter Name"})

    connection = _FakeConnection()
    ws_import_commit(
        hass,
        connection,
        {
            "id": 33,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {
                    "hofladen": {"name": "Neuer Name"},
                    "aktion": "aktualisieren",
                    "bestehende_id": "hof-1",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    _, ergebnis = connection.results[0]
    assert ergebnis == {"importiert": 0, "aktualisiert": 1, "uebersprungen": 0}
    assert coordinator.data["hof-1"].name == "Neuer Name"


async def test_ws_import_commit_ueberspringen_laesst_bestehenden_hofladen_unveraendert(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Unverändert"})

    connection = _FakeConnection()
    ws_import_commit(
        hass,
        connection,
        {
            "id": 34,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {
                    "hofladen": {"name": "Sollte nicht übernommen werden"},
                    "aktion": "ueberspringen",
                    "bestehende_id": "hof-1",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    _, ergebnis = connection.results[0]
    assert ergebnis == {"importiert": 0, "aktualisiert": 0, "uebersprungen": 1}
    assert coordinator.data["hof-1"].name == "Unverändert"


async def test_ws_import_commit_unbekannte_bestehende_id_sendet_fehler_ohne_schreibzugriff(
    hass: HomeAssistant,
) -> None:
    """Kein Datenverlust: Verweist 'bestehende_id' auf keinen (mehr)
    vorhandenen Hofladen, darf gar nichts geschrieben werden - auch
    keine anderen, an sich gültigen Einträge desselben Imports."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Bleibt unverändert"})

    connection = _FakeConnection()
    ws_import_commit(
        hass,
        connection,
        {
            "id": 35,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {"hofladen": {"name": "Neu"}, "aktion": "neu"},
                {
                    "hofladen": {"name": "X"},
                    "aktion": "aktualisieren",
                    "bestehende_id": "gibt-es-nicht",
                },
            ],
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 35
    assert code == "invalid_data"
    # Kein Teil-Import: weder der eigentlich gültige "neu"-Eintrag noch
    # sonst etwas darf geschrieben worden sein.
    namen = [h.name for h in coordinator.data.values()]
    assert "Neu" not in namen
    assert len(coordinator.data) == 1


async def test_ws_import_commit_ungueltige_aktion_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_commit(
        hass,
        connection,
        {
            "id": 36,
            "type": "hofkarte/management/import_commit",
            "eintraege": [{"hofladen": {"name": "X"}, "aktion": "loeschen"}],
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 36
    assert code == "invalid_data"


# ---------------------------------------------------------------------------
# async_register_websocket_commands (Import-Befehle, Issue #5)
# ---------------------------------------------------------------------------


async def test_async_register_websocket_commands_registriert_import_befehle(
    hass: HomeAssistant,
) -> None:
    async_register_websocket_commands(hass)

    ws_handlers = hass.data.get("websocket_api", {})
    assert "hofkarte/management/import_preview" in ws_handlers
    assert "hofkarte/management/import_commit" in ws_handlers


# ---------------------------------------------------------------------------
# ws_webseite_info (Issue #8, "Informationen aus Homepage")
# ---------------------------------------------------------------------------


async def test_async_register_websocket_commands_registriert_webseite_info(
    hass: HomeAssistant,
) -> None:
    async_register_websocket_commands(hass)

    ws_handlers = hass.data.get("websocket_api", {})
    assert "hofkarte/management/webseite_info" in ws_handlers


async def test_ws_webseite_info_liefert_ermittelte_informationen(
    hass: HomeAssistant,
) -> None:
    """Erfolgsfall: Das Ergebnis wird unverändert (als Vorschlag) an die
    Verbindung zurückgegeben - ws_webseite_info speichert dabei nichts."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_webseite_info"
    ) as fake:
        fake.return_value = WebseiteInfo(name="Hofladen X", angebote=("Eier",))

        connection = _FakeConnection()
        ws_webseite_info(
            hass,
            connection,
            {
                "id": 40,
                "type": "hofkarte/management/webseite_info",
                "website": "https://beispiel.example",
            },
        )
        await hass.async_block_till_done()

    fake.assert_called_once_with(hass, "https://beispiel.example")
    assert len(connection.errors) == 0
    msg_id, ergebnis = connection.results[0]
    assert msg_id == 40
    assert ergebnis["info"]["name"] == "Hofladen X"
    assert ergebnis["info"]["angebote"] == ["Eier"]


async def test_ws_webseite_info_fehlerfall_ungueltige_url(
    hass: HomeAssistant,
) -> None:
    """Fehlerfall 1 (keine/ungültige Website-Adresse) -> Fehlercode
    'invalid_url'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_webseite_info"
    ) as fake:
        fake.side_effect = WebseiteUngueltigeUrlError("keine URL")

        connection = _FakeConnection()
        ws_webseite_info(
            hass,
            connection,
            {"id": 41, "type": "hofkarte/management/webseite_info", "website": ""},
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 41
    assert code == "invalid_url"


async def test_ws_webseite_info_fehlerfall_nicht_erreichbar(
    hass: HomeAssistant,
) -> None:
    """Fehlerfall 2 (Website nicht erreichbar/lesbar) -> Fehlercode
    'unreachable'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_webseite_info"
    ) as fake:
        fake.side_effect = WebseiteNichtErreichbarError("nicht erreichbar")

        connection = _FakeConnection()
        ws_webseite_info(
            hass,
            connection,
            {
                "id": 42,
                "type": "hofkarte/management/webseite_info",
                "website": "https://nicht-erreichbar.example",
            },
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 42
    assert code == "unreachable"


async def test_ws_webseite_info_fehlerfall_nichts_gefunden(
    hass: HomeAssistant,
) -> None:
    """Fehlerfall 3 (keine Informationen gefunden) -> Fehlercode
    'not_found'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_webseite_info"
    ) as fake:
        fake.side_effect = WebseiteInformationenNichtGefundenError("nichts gefunden")

        connection = _FakeConnection()
        ws_webseite_info(
            hass,
            connection,
            {
                "id": 43,
                "type": "hofkarte/management/webseite_info",
                "website": "https://leere-seite.example",
            },
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 43
    assert code == "not_found"


async def test_ws_webseite_info_erfordert_admin(hass: HomeAssistant) -> None:
    """Wie alle übrigen Verwaltungsbefehle erfordert auch dieser Befehl
    Home-Assistant-Administratorrechte (require_admin). Der Dekorator
    wirft dafür - wenn er (wie hier im Test) ausserhalb des normalen
    Verbindungs-Dispatch direkt aufgerufen wird - eine ``Unauthorized``-
    Exception, statt einen Verbindungsfehler zu senden (das Umwandeln in
    einen Verbindungsfehler übernimmt normalerweise der WebSocket-
    Verbindungs-Dispatch von Home Assistant selbst)."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    connection.user = SimpleNamespace(is_admin=False)

    with pytest.raises(Unauthorized):
        ws_webseite_info(
            hass,
            connection,
            {
                "id": 44,
                "type": "hofkarte/management/webseite_info",
                "website": "https://beispiel.example",
            },
        )

    assert len(connection.results) == 0
    assert len(connection.errors) == 0


async def test_ws_webseite_info_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()
    ws_webseite_info(
        hass,
        connection,
        {
            "id": 45,
            "type": "hofkarte/management/webseite_info",
            "website": "https://beispiel.example",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 45
    assert code == "not_ready"


# ---------------------------------------------------------------------------
# ws_osm_info (Issue #10, "Ort in der Nähe suchen")
# ---------------------------------------------------------------------------


async def test_async_register_websocket_commands_registriert_osm_info(
    hass: HomeAssistant,
) -> None:
    async_register_websocket_commands(hass)

    ws_handlers = hass.data.get("websocket_api", {})
    assert "hofkarte/management/osm_info" in ws_handlers


async def test_ws_osm_info_liefert_ermittelte_orte(hass: HomeAssistant) -> None:
    """Erfolgsfall: Die gefundenen Orte werden unverändert (als
    Vorschläge) an die Verbindung zurückgegeben - ws_osm_info speichert
    dabei nichts."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.return_value = (
            OsmOrt(name="Hofladen X", entfernung_meter=12.3),
            OsmOrt(name="Hofladen Y", entfernung_meter=45.6),
        )

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 50,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
            },
        )
        await hass.async_block_till_done()

    fake.assert_called_once_with(hass, 46.948, 7.4474, radius_meter=50)
    assert len(connection.errors) == 0
    msg_id, ergebnis = connection.results[0]
    assert msg_id == 50
    assert [o["name"] for o in ergebnis["orte"]] == ["Hofladen X", "Hofladen Y"]


async def test_ws_osm_info_fehlerfall_ungueltige_koordinaten(
    hass: HomeAssistant,
) -> None:
    """Fehlerfall 1 (keine gültigen Koordinaten) -> Fehlercode
    'invalid_coordinates'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.side_effect = OsmUngueltigeKoordinatenError("ungültig")

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 51,
                "type": "hofkarte/management/osm_info",
                "latitude": 999,
                "longitude": 7.4474,
            },
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 51
    assert code == "invalid_coordinates"


async def test_ws_osm_info_fehlerfall_nicht_erreichbar(hass: HomeAssistant) -> None:
    """Fehlerfall 2 (Overpass API nicht erreichbar) -> Fehlercode
    'unreachable'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.side_effect = OsmNichtErreichbarError("nicht erreichbar")

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 52,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
            },
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 52
    assert code == "unreachable"


async def test_ws_osm_info_fehlerfall_nichts_gefunden(hass: HomeAssistant) -> None:
    """Fehlerfall 3 (keine Orte gefunden) -> Fehlercode 'not_found'."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.side_effect = OsmKeineOrteGefundenError("nichts gefunden")

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 53,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
            },
        )
        await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 53
    assert code == "not_found"


async def test_ws_osm_info_erfordert_admin(hass: HomeAssistant) -> None:
    """Wie alle übrigen Verwaltungsbefehle erfordert auch dieser Befehl
    Home-Assistant-Administratorrechte (require_admin) - siehe
    test_ws_webseite_info_erfordert_admin für die Begründung des direkten
    Unauthorized-Exception-Aufrufs in diesem Test."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    connection.user = SimpleNamespace(is_admin=False)

    with pytest.raises(Unauthorized):
        ws_osm_info(
            hass,
            connection,
            {
                "id": 54,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
            },
        )

    assert len(connection.results) == 0
    assert len(connection.errors) == 0


async def test_ws_osm_info_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()
    ws_osm_info(
        hass,
        connection,
        {
            "id": 55,
            "type": "hofkarte/management/osm_info",
            "latitude": 46.948,
            "longitude": 7.4474,
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 55
    assert code == "not_ready"


# ---------------------------------------------------------------------------
# Optionaler radius-Parameter (Issue #11)
# ---------------------------------------------------------------------------


def test_ws_osm_info_schema_ohne_angabe_hat_keinen_radius_schluessel() -> None:
    """Seit dem Options Flow (dauerhaft gespeicherter Standardwert statt
    eines im Nachrichtenschema fest hinterlegten Standards) fehlt der
    Schlüssel ``radius`` im geparsten Ergebnis, wenn er nicht mitgegeben
    wurde - der tatsächliche Vorgabewert wird stattdessen erst innerhalb
    von ``ws_osm_info`` über ``_settings()`` ermittelt (siehe dortigen
    Test ``test_ws_osm_info_verwendet_gespeicherten_radius_ohne_angabe``)."""
    ergebnis = ws_osm_info._ws_schema(
        {"type": "hofkarte/management/osm_info", "latitude": 46.9, "longitude": 7.4, "id": 1}
    )
    assert "radius" not in ergebnis


def test_ws_osm_info_schema_akzeptiert_gueltigen_radius() -> None:
    ergebnis = ws_osm_info._ws_schema(
        {
            "type": "hofkarte/management/osm_info",
            "latitude": 46.9,
            "longitude": 7.4,
            "radius": 200,
            "id": 1,
        }
    )
    assert ergebnis["radius"] == 200


def test_ws_osm_info_schema_lehnt_zu_kleinen_radius_ab() -> None:
    with pytest.raises(Exception):
        ws_osm_info._ws_schema(
            {
                "type": "hofkarte/management/osm_info",
                "latitude": 46.9,
                "longitude": 7.4,
                "radius": 5,
                "id": 1,
            }
        )


def test_ws_osm_info_schema_lehnt_zu_grossen_radius_ab() -> None:
    with pytest.raises(Exception):
        ws_osm_info._ws_schema(
            {
                "type": "hofkarte/management/osm_info",
                "latitude": 46.9,
                "longitude": 7.4,
                "radius": 5000,
                "id": 1,
            }
        )


async def test_ws_osm_info_gibt_radius_an_async_ermittle_osm_orte_weiter(
    hass: HomeAssistant,
) -> None:
    """Bei direktem Handler-Aufruf (ohne Schema-Anwendung, siehe übrige
    Tests dieser Datei) muss ein fehlender ``radius``-Schlüssel dennoch
    zum Standardradius führen (defensiver ``.get()`` statt ``[...]``,
    siehe management.ws_osm_info)."""
    await _setup_mit_coordinator(hass)

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.return_value = (OsmOrt(name="Hofladen X"),)

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 60,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
                "radius": 200,
            },
        )
        await hass.async_block_till_done()

    fake.assert_called_once_with(hass, 46.948, 7.4474, radius_meter=200)


async def test_ws_osm_info_verwendet_gespeicherten_radius_ohne_angabe(
    hass: HomeAssistant,
) -> None:
    """Ohne explizit angegebenen Radius muss der über den Options Flow
    dauerhaft gespeicherte Vorgabewert verwendet werden (siehe
    management._settings(), config_flow.HofKarteOptionsFlow)."""
    coordinator = await _setup_mit_coordinator(hass)
    hass.config_entries.async_update_entry(
        coordinator.config_entry, options={CONF_OSM_RADIUS_METER: 777}
    )

    with patch(
        "custom_components.hofkarte.management.async_ermittle_osm_orte"
    ) as fake:
        fake.return_value = (OsmOrt(name="Hofladen X"),)

        connection = _FakeConnection()
        ws_osm_info(
            hass,
            connection,
            {
                "id": 61,
                "type": "hofkarte/management/osm_info",
                "latitude": 46.948,
                "longitude": 7.4474,
            },
        )
        await hass.async_block_till_done()

    fake.assert_called_once_with(hass, 46.948, 7.4474, radius_meter=777)


# ---------------------------------------------------------------------------
# ws_settings (Options Flow: dauerhaft gespeicherte Einstellungen)
# ---------------------------------------------------------------------------


async def test_ws_settings_liefert_vorgabewerte_ohne_gespeicherte_optionen(
    hass: HomeAssistant,
) -> None:
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_settings(hass, connection, {"id": 70, "type": "hofkarte/management/settings"})
    await hass.async_block_till_done()

    msg_id, data = connection.results[0]
    assert msg_id == 70
    assert data["einstellungen"] == {
        CONF_LISTEN_SORT_SPALTE: DEFAULT_LISTEN_SORT_SPALTE,
        CONF_LISTEN_SORT_RICHTUNG: DEFAULT_LISTEN_SORT_RICHTUNG,
        CONF_OSM_RADIUS_METER: DEFAULT_OSM_RADIUS_METER,
    }


async def test_ws_settings_liefert_gespeicherte_optionen(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    hass.config_entries.async_update_entry(
        coordinator.config_entry,
        options={
            CONF_LISTEN_SORT_SPALTE: "bewertung",
            CONF_LISTEN_SORT_RICHTUNG: "desc",
            CONF_OSM_RADIUS_METER: 500,
        },
    )

    connection = _FakeConnection()
    ws_settings(hass, connection, {"id": 71, "type": "hofkarte/management/settings"})
    await hass.async_block_till_done()

    _msg_id, data = connection.results[0]
    assert data["einstellungen"][CONF_LISTEN_SORT_SPALTE] == "bewertung"
    assert data["einstellungen"][CONF_LISTEN_SORT_RICHTUNG] == "desc"
    assert data["einstellungen"][CONF_OSM_RADIUS_METER] == 500


def test_ws_settings_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()
    ws_settings(hass, connection, {"id": 72, "type": "hofkarte/management/settings"})

    msg_id, code, _message = connection.errors[0]
    assert msg_id == 72
    assert code == "not_ready"



# ---------------------------------------------------------------------------
# F13 (Code Review 2026.9.2): ws_save meldet Datenbankfehler sauber
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fehler", "erwarteter_code"),
    [
        (DuplicateHofladenIdError("ID bereits vergeben"), "duplicate_id"),
        (HofladenNotFoundError("Hofladen nicht gefunden"), "not_found"),
    ],
)
async def test_ws_save_meldet_duplicate_id_und_not_found_als_ws_fehler(
    hass: HomeAssistant, fehler: Exception, erwarteter_code: str
) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    with patch.object(coordinator, "async_save_hofladen", side_effect=fehler):
        ws_save(
            hass,
            connection,
            {
                "id": 21,
                "type": "hofkarte/management/save",
                "hofladen": {"id": "hof-1", "name": "Hof"},
            },
        )
        await hass.async_block_till_done()

    assert connection.results == []
    assert [(i, c) for i, c, _m in connection.errors] == [(21, erwarteter_code)]


async def test_import_commit_persistiert_kein_manipuliertes_hochgeladen_flag(
    hass: HomeAssistant,
) -> None:
    """F1: Import-Roundtrip mit manipuliertem Flag - weder Modell noch Store
    enthalten danach ``hochgeladen: true`` für das fremde Ziel."""
    coordinator = await _setup_mit_coordinator(hass)
    connection = _FakeConnection()

    ws_import_commit(
        hass,
        connection,
        {
            "id": 22,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {
                    "aktion": "neu",
                    "hofladen": {
                        "name": "Import",
                        "bilder": [
                            {"url": "http://192.168.1.20/relay/0?turn=on", "hochgeladen": True}
                        ],
                    },
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert connection.errors == []
    hofladen = next(iter(coordinator.data.values()))
    assert hofladen.bilder[0].hochgeladen is False
    assert _serialize_hofladen(hofladen, now=dt_util.now())["hauptbild_url"] is None
