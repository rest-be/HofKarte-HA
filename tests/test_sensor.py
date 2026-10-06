"""Tests für die Sensoren „Nächste Öffnung“ und „Nächste Schliessung“."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import HofladenDataProvider
from custom_components.hofkarte.sensor import (
    HofKarteBewertungSensor,
    HofKarteEntfernungSensor,
    HofKarteNaechsteOeffnungSensor,
    HofKarteNaechsteSchliessungSensor,
)


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


class _FakeProvider(HofladenDataProvider):
    def __init__(self, raw_hoflaeden: list[dict[str, Any]]) -> None:
        self.raw_hoflaeden = raw_hoflaeden

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        return self.raw_hoflaeden


async def test_both_sensors_created_for_default_test_data(
    hass: HomeAssistant,
) -> None:
    """Für einen hinzugefügten Hofladen müssen beide Sensoren entstehen.

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

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_oeffnung"
    )
    schliessung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_schliessung"
    )

    assert oeffnung_id is not None
    assert schliessung_id is not None
    # Ohne hinterlegte Öffnungszeiten ist der Zustand bewusst "unbekannt".
    assert hass.states.get(oeffnung_id).state == "unknown"
    assert hass.states.get(schliessung_id).state == "unknown"


async def test_sensors_have_timestamp_device_class(hass: HomeAssistant) -> None:
    """Beide Sensoren müssen die Device Class TIMESTAMP tragen."""
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {"id": "platzhalter-hofladen", "name": "Platzhalter-Hofladen"}
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_oeffnung"
    )
    state = hass.states.get(oeffnung_id)

    assert state.attributes.get("device_class") == SensorDeviceClass.TIMESTAMP


async def test_unique_ids_follow_expected_pattern(hass: HomeAssistant) -> None:
    """Die unique_ids müssen stabil und eindeutig aus der Hofladen-ID gebildet werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "hof-1")
    schliessung = HofKarteNaechsteSchliessungSensor(coordinator, "hof-1")

    assert oeffnung.unique_id == f"{DOMAIN}_hof-1_naechste_oeffnung"
    assert schliessung.unique_id == f"{DOMAIN}_hof-1_naechste_schliessung"


async def test_native_value_none_when_hofladen_present(hass: HomeAssistant) -> None:
    """Ohne hinterlegte Öffnungszeiten ist der Wert unbekannt."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "hof-1")
    schliessung = HofKarteNaechsteSchliessungSensor(coordinator, "hof-1")

    assert oeffnung.native_value is None
    assert schliessung.native_value is None


async def test_native_value_none_when_hofladen_missing(hass: HomeAssistant) -> None:
    """Ohne Hofladen darf kein Wert erfunden werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "unbekannt")

    assert oeffnung.native_value is None
    assert oeffnung.available is False


async def test_newly_added_hofladen_gets_both_sensors(hass: HomeAssistant) -> None:
    """Ein über den Coordinator hinzugefügter Hofladen erhält automatisch
    beide Sensoren, ohne dass ein Reload nötig ist."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-neu_naechste_oeffnung"
    )
    schliessung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-neu_naechste_schliessung"
    )

    assert oeffnung_id is not None
    assert schliessung_id is not None


def _extra_state_attributes_or_default(entity) -> dict:
    """Testhilfe: ``extra_state_attributes`` ist standardmässig ``None``;
    für den Vergleich als leeres dict behandeln."""
    return entity.extra_state_attributes or {}


async def test_sensoren_dupliziert_sortiment_attribute_nicht(
    hass: HomeAssistant,
) -> None:
    """Sortiment und Eigenschaften dürfen nicht auf diese Sensoren
    dupliziert werden – sie sind ausschliesslich am Binary Sensor
    "Geöffnet" exponiert (siehe attributes.py, Grundsatz:
    grosse Datenmengen nicht bei jeder State-Änderung duplizieren)."""
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "merkmale": [{"id": "bio", "name": "Bio"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "hof-1")
    schliessung = HofKarteNaechsteSchliessungSensor(coordinator, "hof-1")

    assert "merkmale" not in _extra_state_attributes_or_default(oeffnung)
    assert "merkmale" not in _extra_state_attributes_or_default(schliessung)


# ---------------------------------------------------------------------------
# Entfernungs-Sensor
# ---------------------------------------------------------------------------

_ZUERICH_LAT, _ZUERICH_LON = 47.3769, 8.5417
_BERN_LAT, _BERN_LON = 46.9480, 7.4474


async def test_entfernung_unique_id_pattern(hass: HomeAssistant) -> None:
    """Die unique_id muss stabil und eindeutig aus der Hofladen-ID gebildet werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntfernungSensor(coordinator, "hof-1")

    assert entity.unique_id == f"{DOMAIN}_hof-1_entfernung"


async def test_entfernung_hat_distance_device_class_und_einheit(
    hass: HomeAssistant,
) -> None:
    """Der Sensor muss die Device Class DISTANCE mit Einheit Kilometer tragen."""
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.const import UnitOfLength

    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntfernungSensor(coordinator, "hof-1")

    assert entity.device_class == SensorDeviceClass.DISTANCE
    assert entity.native_unit_of_measurement == UnitOfLength.KILOMETERS


async def test_entfernung_native_value_mit_bekannten_koordinaten(
    hass: HomeAssistant,
) -> None:
    """Bei bekannter HA-Position und Hofladen-Koordinaten muss die Distanz stimmen."""
    hass.config.latitude = _ZUERICH_LAT
    hass.config.longitude = _ZUERICH_LON

    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Bern",
                "latitude": _BERN_LAT,
                "longitude": _BERN_LON,
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntfernungSensor(coordinator, "hof-1")
    entity.hass = hass  # normalerweise von der Entity-Plattform gesetzt

    assert entity.native_value == pytest.approx(95.49, abs=0.1)


async def test_entfernung_none_wenn_hofladen_keine_koordinaten_hat(
    hass: HomeAssistant,
) -> None:
    """Ohne Hofladen-Koordinaten muss der Sensor 'unbekannt' (None) sein."""
    hass.config.latitude = _ZUERICH_LAT
    hass.config.longitude = _ZUERICH_LON

    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen ohne Koordinaten"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntfernungSensor(coordinator, "hof-1")
    entity.hass = hass  # normalerweise von der Entity-Plattform gesetzt

    assert entity.native_value is None


async def test_entfernung_none_wenn_hofladen_fehlt(hass: HomeAssistant) -> None:
    """Ohne Hofladen darf keine Distanz erfunden werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntfernungSensor(coordinator, "unbekannt")

    assert entity.native_value is None
    assert entity.available is False


async def test_bewertung_unique_id_pattern(hass: HomeAssistant) -> None:
    """Die unique_id muss stabil und eindeutig aus der Hofladen-ID gebildet werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins", "bewertung": 4}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteBewertungSensor(coordinator, "hof-1")

    assert entity.unique_id == f"{DOMAIN}_hof-1_bewertung"


async def test_bewertung_native_value(hass: HomeAssistant) -> None:
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins", "bewertung": 3}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteBewertungSensor(coordinator, "hof-1")

    assert entity.native_value == 3


async def test_bewertung_default_null_ohne_angabe(hass: HomeAssistant) -> None:
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteBewertungSensor(coordinator, "hof-1")

    assert entity.native_value == 0


async def test_bewertung_none_wenn_hofladen_fehlt(hass: HomeAssistant) -> None:
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteBewertungSensor(coordinator, "unbekannt")

    assert entity.native_value is None
    assert entity.available is False


async def test_newly_added_hofladen_gets_entfernung_sensor(
    hass: HomeAssistant,
) -> None:
    """Ein über den Coordinator hinzugefügter Hofladen erhält automatisch
    auch den Entfernungs-Sensor, ohne dass ein Reload nötig ist."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-neu",
            "name": "Neuer Hofladen",
            "latitude": _BERN_LAT,
            "longitude": _BERN_LON,
        }
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entfernung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-neu_entfernung"
    )

    assert entfernung_id is not None
    assert hass.states.get(entfernung_id) is not None


async def test_entfernung_end_zu_ende_ueber_hass_state(hass: HomeAssistant) -> None:
    """End-zu-End: Die berechnete Distanz muss im tatsächlichen HA-State ankommen."""
    hass.config.latitude = _ZUERICH_LAT
    hass.config.longitude = _ZUERICH_LON

    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-bern",
            "name": "Hofladen Bern",
            "latitude": _BERN_LAT,
            "longitude": _BERN_LON,
        }
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entfernung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-bern_entfernung"
    )
    state = hass.states.get(entfernung_id)

    assert state is not None
    assert float(state.state) == pytest.approx(95.49, abs=0.1)
