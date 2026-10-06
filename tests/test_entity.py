"""Tests für die gemeinsame HofKarte-Entity-Basis und den Setup-Helper."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import (
    HofladenDataProvider,
    StaticTestDataProvider,
)
from custom_components.hofkarte.entity import (
    HofKarteEntity,
    async_setup_hofladen_entities,
)


class _FakeProvider(HofladenDataProvider):
    def __init__(self, raw_hoflaeden: list[dict[str, Any]]) -> None:
        self.raw_hoflaeden = raw_hoflaeden

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        return self.raw_hoflaeden


async def test_hofladen_property_returns_current_data(hass: HomeAssistant) -> None:
    """`hofladen` muss den aktuellen Datensatz aus dem Coordinator liefern."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "hof-1")

    assert entity.hofladen is not None
    assert entity.hofladen.name == "Hofladen Eins"


async def test_hofladen_property_none_when_missing(hass: HomeAssistant) -> None:
    """`hofladen` muss None liefern, wenn die ID nicht (mehr) existiert."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "unbekannt")

    assert entity.hofladen is None


async def test_available_false_when_hofladen_missing(hass: HomeAssistant) -> None:
    """Verfügbarkeit muss False sein, wenn der Hofladen nicht existiert."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "hof-1")

    assert entity.available is False


async def test_available_true_when_hofladen_present(hass: HomeAssistant) -> None:
    """Verfügbarkeit muss True sein, wenn Abruf ok und Hofladen vorhanden ist."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "hof-1")

    assert entity.available is True


async def test_device_info_none_when_hofladen_missing(hass: HomeAssistant) -> None:
    """Ohne Hofladen darf kein Device referenziert werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "hof-1")

    assert entity.device_info is None


async def test_device_info_matches_hofladen(hass: HomeAssistant) -> None:
    """Das Device Info muss auf denselben Identifier wie device.py verweisen."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteEntity(coordinator, "hof-1")
    device_info = entity.device_info

    assert device_info is not None
    assert device_info["name"] == "Hofladen Eins"


async def test_setup_hofladen_entities_creates_for_existing(
    hass: HomeAssistant,
) -> None:
    """Für bereits bekannte Hofläden müssen sofort Entities erzeugt werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    created: list[HofKarteEntity] = []

    def factory(coord: HofKarteUpdateCoordinator, hofladen_id: str) -> HofKarteEntity:
        return HofKarteEntity(coord, hofladen_id)

    unsub = async_setup_hofladen_entities(
        coordinator, lambda entities: created.extend(entities), [factory]
    )
    try:
        assert len(created) == 1
        assert created[0]._hofladen_id == "hof-1"
    finally:
        unsub()


async def test_setup_hofladen_entities_creates_for_newly_added(
    hass: HomeAssistant,
) -> None:
    """Ein später hinzugefügter Hofladen muss automatisch eine Entity erhalten."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    created: list[HofKarteEntity] = []

    def factory(coord: HofKarteUpdateCoordinator, hofladen_id: str) -> HofKarteEntity:
        return HofKarteEntity(coord, hofladen_id)

    unsub = async_setup_hofladen_entities(
        coordinator, lambda entities: created.extend(entities), [factory]
    )
    try:
        assert created == []

        await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neu"})

        assert len(created) == 1
        assert created[0]._hofladen_id == "hof-neu"
    finally:
        unsub()
