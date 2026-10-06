"""Tests für den HofKarte-Data-Provider."""

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hofkarte.data_provider import (
    DuplicateHofladenIdError,
    HofladenNotFoundError,
    StaticTestDataProvider,
    StorageHofladenDataProvider,
)


async def test_static_provider_returns_default_data() -> None:
    """Ohne explizite Daten liefert der Provider einen Platzhalter-Datensatz."""
    provider = StaticTestDataProvider()

    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "platzhalter-hofladen"


async def test_static_provider_returns_custom_data() -> None:
    """Explizit übergebene Testdaten müssen unverändert zurückgegeben werden."""
    custom_data = [{"id": "hof-x", "name": "Hofladen X"}]
    provider = StaticTestDataProvider(raw_hoflaeden=custom_data)

    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert raw_hoflaeden == custom_data
    # Rückgabe muss eine Kopie sein, keine Referenz auf die interne Liste.
    assert raw_hoflaeden is not provider._raw_hoflaeden


async def test_static_provider_add_raw_hofladen() -> None:
    """Ein neuer Hofladen muss beim nächsten Abruf enthalten sein."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])

    await provider.async_add_raw_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "hof-neu"


async def test_static_provider_add_raw_hofladen_rejects_duplicate_id() -> None:
    """Eine bereits vorhandene ID darf nicht stillschweigend überschrieben werden."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Bestehender Hofladen"}]
    )

    with pytest.raises(DuplicateHofladenIdError):
        await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Anderer Name"})


async def test_static_provider_update_raw_hofladen_merges_fields() -> None:
    """Ein Update darf nur die übergebenen Felder ändern, nicht die übrigen."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "plz": "3000",
                "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
            }
        ]
    )

    await provider.async_update_raw_hofladen(
        "hof-1", {"zahlungsarten": [{"id": "twint", "name": "TWINT"}]}
    )
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    aktualisiert = raw_hoflaeden[0]
    assert aktualisiert["name"] == "Hofladen Eins"  # unverändert
    assert aktualisiert["plz"] == "3000"  # unverändert
    assert aktualisiert["zahlungsarten"] == [{"id": "twint", "name": "TWINT"}]


async def test_static_provider_update_raw_hofladen_unbekannte_id() -> None:
    """Ein Update auf eine nicht existierende ID muss abgelehnt werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])

    with pytest.raises(HofladenNotFoundError):
        await provider.async_update_raw_hofladen("unbekannt", {"name": "Neu"})


# ---------------------------------------------------------------------------
# StorageHofladenDataProvider (Architekturentscheid: integrationsinterner,
# persistenter Store statt erfundener externer Datenquelle)
# ---------------------------------------------------------------------------


async def test_storage_provider_startet_leer_ohne_erfundene_daten(
    hass: HomeAssistant,
) -> None:
    """Ein frischer Store enthält keine Datei; es dürfen keine erfundenen
    Beispieldaten zurückgegeben werden – der Store startet leer."""
    provider = StorageHofladenDataProvider(hass)

    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert raw_hoflaeden == []


async def test_storage_provider_fetch_gibt_kopie_zurueck(
    hass: HomeAssistant,
) -> None:
    """Die Rückgabe muss eine Kopie sein, keine Referenz auf den internen Cache."""
    provider = StorageHofladenDataProvider(hass)
    await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    erste_abfrage = await provider.async_fetch_raw_hoflaeden()
    erste_abfrage.append({"id": "manipuliert", "name": "Sollte nicht ankommen"})
    zweite_abfrage = await provider.async_fetch_raw_hoflaeden()

    assert len(zweite_abfrage) == 1


async def test_storage_provider_add_und_fetch(hass: HomeAssistant) -> None:
    """Ein hinzugefügter Hofladen muss beim nächsten Abruf enthalten sein."""
    provider = StorageHofladenDataProvider(hass)

    await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Hofladen Eins"})
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "hof-1"


async def test_storage_provider_add_rejects_duplicate_id(
    hass: HomeAssistant,
) -> None:
    """Eine bereits vorhandene ID darf nicht stillschweigend überschrieben werden."""
    provider = StorageHofladenDataProvider(hass)
    await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    with pytest.raises(DuplicateHofladenIdError):
        await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Anderer Name"})


async def test_storage_provider_update_merges_fields(hass: HomeAssistant) -> None:
    """Ein Update darf nur die übergebenen Felder ändern, nicht die übrigen."""
    provider = StorageHofladenDataProvider(hass)
    await provider.async_add_raw_hofladen(
        {"id": "hof-1", "name": "Hofladen Eins", "plz": "3000"}
    )

    await provider.async_update_raw_hofladen("hof-1", {"plz": "8000"})
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert raw_hoflaeden[0]["name"] == "Hofladen Eins"  # unverändert
    assert raw_hoflaeden[0]["plz"] == "8000"


async def test_storage_provider_update_unbekannte_id(hass: HomeAssistant) -> None:
    """Ein Update auf eine nicht existierende ID muss abgelehnt werden."""
    provider = StorageHofladenDataProvider(hass)

    with pytest.raises(HofladenNotFoundError):
        await provider.async_update_raw_hofladen("unbekannt", {"name": "Neu"})


async def test_storage_provider_persistiert_ueber_neue_instanz_hinweg(
    hass: HomeAssistant,
) -> None:
    """Daten müssen tatsächlich persistent sein: Eine neue Provider-Instanz
    (z. B. nach einem Reload/Neustart der Integration) mit demselben
    ``hass`` muss zuvor gespeicherte Daten wiederfinden."""
    erster_provider = StorageHofladenDataProvider(hass)
    await erster_provider.async_add_raw_hofladen(
        {"id": "hof-1", "name": "Persistenter Hofladen"}
    )

    # Simuliert einen Neustart/Reload: komplett neue Provider-Instanz,
    # die denselben zugrundeliegenden Home-Assistant-Store liest.
    zweiter_provider = StorageHofladenDataProvider(hass)
    raw_hoflaeden = await zweiter_provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "hof-1"
    assert raw_hoflaeden[0]["name"] == "Persistenter Hofladen"


async def test_storage_provider_aenderungen_ueber_instanzen_hinweg_sichtbar(
    hass: HomeAssistant,
) -> None:
    """Auch Updates müssen über eine neue Provider-Instanz hinweg sichtbar
    sein (vollständiger Schreib-/Lese-Round-Trip über den echten Store)."""
    erster_provider = StorageHofladenDataProvider(hass)
    await erster_provider.async_add_raw_hofladen(
        {"id": "hof-1", "name": "Hofladen Eins", "plz": "3000"}
    )
    await erster_provider.async_update_raw_hofladen("hof-1", {"plz": "8000"})

    zweiter_provider = StorageHofladenDataProvider(hass)
    raw_hoflaeden = await zweiter_provider.async_fetch_raw_hoflaeden()

    assert raw_hoflaeden[0]["plz"] == "8000"

async def test_storage_provider_delete_removes_hofladen(hass: HomeAssistant) -> None:
    """Ein Hofladen muss dauerhaft aus dem Store entfernt werden können."""
    provider = StorageHofladenDataProvider(hass)
    await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    await provider.async_delete_raw_hofladen("hof-1")

    assert await provider.async_fetch_raw_hoflaeden() == []


async def test_storage_provider_delete_unknown_id(hass: HomeAssistant) -> None:
    """Das Löschen einer unbekannten ID muss abgelehnt werden."""
    provider = StorageHofladenDataProvider(hass)
    with pytest.raises(HofladenNotFoundError):
        await provider.async_delete_raw_hofladen("unbekannt")
