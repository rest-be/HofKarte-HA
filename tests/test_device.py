"""Tests für die Device-Repräsentation und Device-Registry-Synchronisation."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.device import (
    async_sync_devices,
    build_device_identifier,
    build_device_info,
)
from custom_components.hofkarte.models import Hofladen


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


def test_build_device_identifier_is_stable_and_domain_scoped() -> None:
    """Der Identifier muss auf der stabilen Hofladen-ID basieren."""
    hofladen = Hofladen(id="hof-1", name="Hofladen Müller")

    assert build_device_identifier(hofladen) == (DOMAIN, "hof-1")


def test_build_device_info_has_no_manufacturer_or_model() -> None:
    """Ein Hofladen ist kein physisches Gerät: keine erfundenen Angaben."""
    hofladen = Hofladen(id="hof-1", name="Hofladen Müller")

    device_info = build_device_info(hofladen)

    assert device_info["name"] == "Hofladen Müller"
    assert device_info["identifiers"] == {(DOMAIN, "hof-1")}
    assert "manufacturer" not in device_info
    assert "model" not in device_info


async def test_sync_creates_one_device_per_hofladen(hass: HomeAssistant) -> None:
    """Für jeden Hofladen muss genau ein Device angelegt werden."""
    entry = _make_entry(hass)
    hoflaeden = {
        "hof-1": Hofladen(id="hof-1", name="Hofladen Eins"),
        "hof-2": Hofladen(id="hof-2", name="Hofladen Zwei"),
    }

    async_sync_devices(hass, entry, hoflaeden)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert len(devices) == 2
    names = {device.name for device in devices}
    assert names == {"Hofladen Eins", "Hofladen Zwei"}


async def test_sync_devices_are_cleanly_separated(hass: HomeAssistant) -> None:
    """Mehrere Hofläden müssen unterschiedliche, eindeutige Identifiers haben."""
    entry = _make_entry(hass)
    hoflaeden = {
        "hof-1": Hofladen(id="hof-1", name="Hofladen Eins"),
        "hof-2": Hofladen(id="hof-2", name="Hofladen Zwei"),
    }

    async_sync_devices(hass, entry, hoflaeden)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_1 = device_registry.async_get_device(identifiers={(DOMAIN, "hof-1")})
    device_2 = device_registry.async_get_device(identifiers={(DOMAIN, "hof-2")})

    assert device_1 is not None
    assert device_2 is not None
    assert device_1.id != device_2.id


async def test_sync_is_idempotent_no_duplicates_on_reload(
    hass: HomeAssistant,
) -> None:
    """Ein erneuter Sync (z. B. Reload) darf keine Duplikate erzeugen."""
    entry = _make_entry(hass)
    hoflaeden = {"hof-1": Hofladen(id="hof-1", name="Hofladen Eins")}

    async_sync_devices(hass, entry, hoflaeden)
    await hass.async_block_till_done()
    async_sync_devices(hass, entry, hoflaeden)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert len(devices) == 1


async def test_sync_updates_device_name_on_change(hass: HomeAssistant) -> None:
    """Ändert sich der Name, muss das bestehende Device aktualisiert werden
    statt ein neues zu erzeugen (stabiler Identifier)."""
    entry = _make_entry(hass)

    async_sync_devices(
        hass, entry, {"hof-1": Hofladen(id="hof-1", name="Alter Name")}
    )
    await hass.async_block_till_done()

    async_sync_devices(
        hass, entry, {"hof-1": Hofladen(id="hof-1", name="Neuer Name")}
    )
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert len(devices) == 1
    assert devices[0].name == "Neuer Name"


async def test_sync_removes_device_for_disappeared_hofladen(
    hass: HomeAssistant,
) -> None:
    """Verschwindet ein Hofladen aus den Daten, muss sein Device entfernt werden."""
    entry = _make_entry(hass)

    async_sync_devices(
        hass,
        entry,
        {
            "hof-1": Hofladen(id="hof-1", name="Hofladen Eins"),
            "hof-2": Hofladen(id="hof-2", name="Hofladen Zwei"),
        },
    )
    await hass.async_block_till_done()

    async_sync_devices(hass, entry, {"hof-1": Hofladen(id="hof-1", name="Hofladen Eins")})
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert len(devices) == 1
    assert devices[0].name == "Hofladen Eins"


async def test_setup_entry_creates_device_for_default_test_data(
    hass: HomeAssistant,
) -> None:
    """Der End-zu-End-Setup-Pfad muss einen hinzugefügten Hofladen als
    Device anlegen.

    Seit dem Architekturentscheid (persistenter Store statt Testdaten-
    Provider in der Produktion) startet ein frisch eingerichteter Eintrag
    ohne Hofläden; der Testdatensatz wird daher explizit ergänzt.
    """
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {"id": "platzhalter-hofladen", "name": "Platzhalter-Hofladen"}
    )
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "platzhalter-hofladen")}
    )

    assert device is not None
    assert device.name == "Platzhalter-Hofladen"


async def test_adding_hofladen_via_coordinator_creates_device(
    hass: HomeAssistant,
) -> None:
    """Ein über den Coordinator hinzugefügter Hofladen muss automatisch ein
    Device erhalten (siehe Coordinator-Listener in device.py)."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "hof-neu")})

    assert device is not None
    assert device.name == "Neuer Hofladen"
