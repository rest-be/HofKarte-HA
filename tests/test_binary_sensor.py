"""Tests für den Binary Sensor „Geöffnet“."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.binary_sensor import HofKarteGeoeffnetBinarySensor
from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import HofladenDataProvider


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


async def test_binary_sensor_created_for_default_test_data(
    hass: HomeAssistant,
) -> None:
    """Für einen hinzugefügten Hofladen muss ein Binary Sensor entstehen.

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
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_geoeffnet"
    )

    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    # Der Testhofladen hat keine Öffnungszeiten hinterlegt, daher ist der
    # Status bewusst "unbekannt" statt erfunden "geschlossen".
    assert state.state == "unknown"


async def test_binary_sensor_has_no_device_class(hass: HomeAssistant) -> None:
    """Es darf keine unpassende Device Class erfunden werden."""
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {"id": "platzhalter-hofladen", "name": "Platzhalter-Hofladen"}
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_geoeffnet"
    )
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.attributes.get("device_class") is None


async def test_binary_sensor_is_assigned_to_correct_device(
    hass: HomeAssistant,
) -> None:
    """Die Entity muss demselben Device zugeordnet sein wie der Hofladen."""
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
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_geoeffnet"
    )
    entity_entry = entity_registry.async_get(entity_id)

    assert device is not None
    assert entity_entry is not None
    assert entity_entry.device_id == device.id


async def test_unique_id_follows_expected_pattern(hass: HomeAssistant) -> None:
    """Die unique_id muss stabil und eindeutig aus der Hofladen-ID gebildet werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "hof-1")

    assert entity.unique_id == f"{DOMAIN}_hof-1_geoeffnet"


async def test_is_on_returns_none_when_hofladen_present(hass: HomeAssistant) -> None:
    """Ohne hinterlegte Öffnungszeiten ist der Status bewusst unbekannt."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "hof-1")

    assert entity.is_on is None


async def test_is_on_returns_none_when_hofladen_missing(hass: HomeAssistant) -> None:
    """Ohne Hofladen darf kein Status erfunden werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "unbekannt")

    assert entity.is_on is None
    assert entity.available is False


async def test_availability_toggles_with_coordinator_success(
    hass: HomeAssistant,
) -> None:
    """Availability muss sich nach Erfolg des letzten Coordinator-Abrufs richten."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "hof-1")
    assert entity.available is True

    provider.raw_hoflaeden = []
    provider.async_fetch_raw_hoflaeden = _make_failing_fetch()
    await coordinator.async_refresh()

    assert entity.available is False


def _make_failing_fetch():
    async def _fetch():
        raise RuntimeError("Datenquelle nicht erreichbar")

    return _fetch


async def test_newly_added_hofladen_gets_binary_sensor(hass: HomeAssistant) -> None:
    """Ein über den Coordinator hinzugefügter Hofladen erhält automatisch
    einen Binary Sensor, ohne dass ein Reload nötig ist."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_hof-neu_geoeffnet"
    )

    assert entity_id is not None
    assert hass.states.get(entity_id) is not None


async def test_extra_state_attributes_none_when_hofladen_missing(
    hass: HomeAssistant,
) -> None:
    """Ohne Hofladen dürfen keine Sortiment-Attribute erfunden werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "unbekannt")

    assert entity.extra_state_attributes is None


async def test_extra_state_attributes_contains_sortiment(hass: HomeAssistant) -> None:
    """Die Entity muss Sortiment und Eigenschaften als Attribute tragen."""
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "angebote": [{"id": "kartoffeln", "name": "Kartoffeln"}],
                "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteGeoeffnetBinarySensor(coordinator, "hof-1")
    attribute = entity.extra_state_attributes

    assert attribute is not None
    assert attribute["angebote"] == ["Kartoffeln"]
    assert attribute["zahlungsarten"] == ["Bargeld"]


async def test_extra_state_attributes_visible_in_hass_state(
    hass: HomeAssistant,
) -> None:
    """End-zu-End: Die Attribute müssen im tatsächlichen HA-State ankommen."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-neu",
            "name": "Neuer Hofladen",
            "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
        }
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_hof-neu_geoeffnet"
    )
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.attributes.get("zahlungsarten") == ["Bargeld"]
    assert state.attributes.get("angebote") == []


async def test_update_sortiment_wirkt_sich_ohne_reload_auf_attribute_aus(
    hass: HomeAssistant,
) -> None:
    """Eine über den Coordinator vorgenommene Sortiment-Änderung muss sich
    ohne Reload in den State-Attributen niederschlagen."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-edit",
            "name": "Editierbarer Hofladen",
            "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
        }
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DOMAIN}_hof-edit_geoeffnet"
    )
    assert hass.states.get(entity_id).attributes.get("zahlungsarten") == ["Bargeld"]

    await coordinator.async_update_hofladen_sortiment(
        "hof-edit",
        zahlungsarten=[
            {"id": "bar", "name": "Bargeld"},
            {"id": "twint", "name": "TWINT"},
        ],
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get("zahlungsarten") == ["Bargeld", "TWINT"]
