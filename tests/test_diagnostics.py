"""Tests für diagnostics.py."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.diagnostics import (
    async_get_config_entry_diagnostics,
)


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def test_diagnostics_enthaelt_erwartete_struktur(hass: HomeAssistant) -> None:
    """Die Diagnosedaten müssen die erwarteten Top-Level-Schlüssel enthalten."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert set(diagnostics.keys()) == {
        "config_entry",
        "datenquelle",
        "coordinator",
        "hoflaeden",
    }


async def test_diagnostics_zeigt_erfolgreichen_abruf(hass: HomeAssistant) -> None:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"]["letzter_abruf_erfolgreich"] is True
    assert diagnostics["coordinator"]["letzte_erfolgreiche_aktualisierung_utc"] is not None
    assert diagnostics["coordinator"]["letzter_fehler_typ"] is None
    assert diagnostics["coordinator"]["update_intervall_sekunden"] is None


async def test_diagnostics_zeigt_datenquellen_typ_und_schreibfaehigkeit(
    hass: HomeAssistant,
) -> None:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["datenquelle"]["typ"] == "StorageHofladenDataProvider"
    assert diagnostics["datenquelle"]["unterstuetzt_schreibzugriffe"] is True


async def test_diagnostics_zaehlt_hoflaeden_ohne_inhalte_preiszugeben(
    hass: HomeAssistant,
) -> None:
    """Es darf nur die Anzahl, aber kein Name/keine Adresse etc. enthalten sein."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-1",
            "name": "Geheimer Hofladen Name",
            "adresse": "Geheime Adresse 1",
            "latitude": 47.123,
            "longitude": 8.456,
        }
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["hoflaeden"]["anzahl"] == 1

    # Sicherstellen, dass keine Hofladen-Inhalte irgendwo in der
    # Diagnosestruktur (auch nicht verschachtelt) auftauchen.
    diagnostics_text = str(diagnostics)
    assert "Geheimer Hofladen Name" not in diagnostics_text
    assert "Geheime Adresse 1" not in diagnostics_text
    assert "47.123" not in diagnostics_text
    assert "8.456" not in diagnostics_text


async def test_diagnostics_ohne_hoflaeden_zeigt_null(hass: HomeAssistant) -> None:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["hoflaeden"]["anzahl"] == 0
