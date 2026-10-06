"""Tests für die Image Entity 'Hauptbild'."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import HofladenDataProvider
from custom_components.hofkarte.image import HofKarteHauptbildImage


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


async def _setup_mit_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


# ---------------------------------------------------------------------------
# Unit-Tests an der Entity direkt
# ---------------------------------------------------------------------------


async def test_unique_id_pattern(hass: HomeAssistant) -> None:
    provider = _FakeProvider(
        [{"id": "hof-1", "name": "Hofladen Eins", "bilder": []}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")

    assert entity.unique_id == f"{DOMAIN}_hof-1_hauptbild"


async def test_image_url_ist_hauptbild(hass: HomeAssistant) -> None:
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "bilder": [
                    {"url": "https://example.com/1.jpg", "beschreibung": "Erstes"},
                    {"url": "https://example.com/2.jpg"},
                ],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")

    assert entity.image_url == "https://example.com/1.jpg"


async def test_image_url_none_ohne_bilder(hass: HomeAssistant) -> None:
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")

    assert entity.image_url is None


async def test_image_url_ueberspringt_unsichere_url(hass: HomeAssistant) -> None:
    """Ein unsicheres Bild (private IP) darf nicht als Hauptbild verwendet
    werden; das nächste sichere Bild muss stattdessen gewählt werden."""
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "bilder": [
                    {"url": "http://192.168.1.1/intern.jpg"},
                    {"url": "https://example.com/sicher.jpg"},
                ],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")

    assert entity.image_url == "https://example.com/sicher.jpg"


async def test_extra_state_attributes_enthaelt_weitere_bilder(
    hass: HomeAssistant,
) -> None:
    """Das Hauptbild selbst darf nicht nochmals in den Attributen
    auftauchen; nur die übrigen (sicheren) Bilder gehören dort hinein."""
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "bilder": [
                    {"url": "https://example.com/1.jpg", "beschreibung": "Eins"},
                    {"url": "https://example.com/2.jpg"},
                ],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")
    attribute = entity.extra_state_attributes

    assert attribute is not None
    assert entity.image_url == "https://example.com/1.jpg"
    weitere = attribute["weitere_bilder"]
    assert len(weitere) == 1
    assert weitere[0]["url"] == "https://example.com/2.jpg"


async def test_extra_state_attributes_none_ohne_hofladen(
    hass: HomeAssistant,
) -> None:
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "unbekannt")

    assert entity.extra_state_attributes is None
    assert entity.available is False


async def test_bild_cache_wird_bei_url_aenderung_invalidiert(
    hass: HomeAssistant,
) -> None:
    """Ändert sich die Hauptbild-URL, muss der interne Home-Assistant-
    Bild-Cache invalidiert und image_last_updated aktualisiert werden –
    sonst würden Nutzer weiterhin das alte Bild sehen."""
    provider = _FakeProvider(
        [
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "bilder": [{"url": "https://example.com/alt.jpg"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    entity = HofKarteHauptbildImage(hass, coordinator, "hof-1")
    entity._cached_image = object()  # simuliert bereits abgerufenes Bild
    erster_zeitstempel = entity.image_last_updated
    assert erster_zeitstempel is not None

    # Zugrunde liegende Bild-URL direkt in den Testdaten ändern und einen
    # regulären Coordinator-Refresh anstossen (der Fake-Provider ist
    # bewusst nur lesend, siehe Klassendefinition oben).
    provider.raw_hoflaeden[0]["bilder"] = [{"url": "https://example.com/neu.jpg"}]
    await coordinator.async_refresh()
    # Die Entity ist hier nicht über die Plattform hinzugefügt (kein
    # async_add_entities, kein hass-Attribut gesetzt); daher wird direkt
    # die interne Abgleich-Methode aufgerufen statt des vollen
    # _handle_coordinator_update-Callbacks (der zusätzlich
    # async_write_ha_state() aufruft und ein angehängtes hass benötigt).
    entity._sync_bild_url()

    assert entity.image_url == "https://example.com/neu.jpg"
    assert entity._cached_image is None
    assert entity.image_last_updated != erster_zeitstempel


# ---------------------------------------------------------------------------
# End-zu-End über die tatsächliche Config Entry
# ---------------------------------------------------------------------------


async def test_entity_wird_fuer_hofladen_erstellt(hass: HomeAssistant) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen(
        {
            "id": "hof-1",
            "name": "Hofladen Eins",
            "bilder": [{"url": "https://example.com/bild.jpg"}],
        }
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "image", DOMAIN, f"{DOMAIN}_hof-1_hauptbild"
    )

    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("entity_picture") is not None


async def test_entity_ist_richtigem_device_zugeordnet(hass: HomeAssistant) -> None:
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "hof-1")})
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "image", DOMAIN, f"{DOMAIN}_hof-1_hauptbild"
    )
    entity_entry = entity_registry.async_get(entity_id)

    assert device is not None
    assert entity_entry is not None
    assert entity_entry.device_id == device.id


async def test_newly_added_hofladen_gets_image_entity(hass: HomeAssistant) -> None:
    """Ein später hinzugefügter Hofladen muss automatisch eine Image
    Entity erhalten, ohne dass ein Reload nötig ist."""
    coordinator = await _setup_mit_coordinator(hass)

    await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "image", DOMAIN, f"{DOMAIN}_hof-neu_hauptbild"
    )

    assert entity_id is not None
