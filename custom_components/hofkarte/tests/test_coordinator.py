"""Tests für den HofKarteUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.hofkarte.coordinator import (
    HofKarteUpdateCoordinator,
    HofladenVersionConflictError,
)
from custom_components.hofkarte.data_provider import (
    DuplicateHofladenIdError,
    HofladenDataProvider,
    HofladenNotFoundError,
    StaticTestDataProvider,
)
from custom_components.hofkarte.parsing import HofladenValidationError


class _FakeProvider(HofladenDataProvider):
    """Test-Provider mit konfigurierbarem Verhalten (Daten, Fehler, Delay)."""

    def __init__(
        self,
        raw_hoflaeden: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.raw_hoflaeden = raw_hoflaeden if raw_hoflaeden is not None else []
        self.error = error
        self.delay = delay

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.raw_hoflaeden


async def test_successful_update(hass: HomeAssistant) -> None:
    """Ein erfolgreicher Abruf muss validierte Hofladen-Daten liefern."""
    provider = _FakeProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(
        hass, provider, update_interval=timedelta(minutes=15)
    )

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert set(coordinator.data.keys()) == {"hof-1"}
    assert coordinator.data["hof-1"].name == "Hofladen Eins"


async def test_invalid_record_is_skipped_not_fatal(hass: HomeAssistant) -> None:
    """Ein einzelner ungültiger Datensatz darf den gesamten Abruf nicht scheitern lassen."""
    provider = _FakeProvider(
        raw_hoflaeden=[
            {"id": "hof-1", "name": "Gültiger Hofladen"},
            {"name": "Ungültig, keine id"},
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert list(coordinator.data.keys()) == ["hof-1"]


async def test_timeout_results_in_update_failed(hass: HomeAssistant) -> None:
    """Eine Zeitüberschreitung beim Abruf muss sauber als Fehler behandelt werden."""
    provider = _FakeProvider(raw_hoflaeden=[], delay=1.0)
    coordinator = HofKarteUpdateCoordinator(
        hass, provider, fetch_timeout_seconds=0.01
    )

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False


async def test_provider_error_results_in_update_failed(hass: HomeAssistant) -> None:
    """Ein Fehler der Datenquelle darf Home Assistant nicht blockieren."""
    provider = _FakeProvider(error=RuntimeError("Datenquelle nicht erreichbar"))
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False


async def test_refresh_failure_after_success_keeps_previous_data(
    hass: HomeAssistant,
) -> None:
    """Ein späterer Fehlversuch darf vorhandene Daten aus dem letzten Erfolg
    nicht verwerfen (Availability über ``last_update_success`` abbildbar)."""
    provider = _FakeProvider(raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True

    provider.error = RuntimeError("Vorübergehend nicht erreichbar")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.data is not None
    assert "hof-1" in coordinator.data


async def test_empty_data_source_yields_empty_mapping(hass: HomeAssistant) -> None:
    """Eine leere Datenquelle ist kein Fehler, sondern ein leeres Mapping."""
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == {}


async def test_add_hofladen_appears_in_data_after_add(hass: HomeAssistant) -> None:
    """Ein neu hinzugefügter Hofladen muss danach in coordinator.data stehen."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.data == {}

    hofladen = await coordinator.async_add_hofladen(
        {"id": "hof-neu", "name": "Neuer Hofladen"}
    )

    assert hofladen.id == "hof-neu"
    assert "hof-neu" in coordinator.data
    assert coordinator.data["hof-neu"].name == "Neuer Hofladen"


async def test_add_hofladen_invalid_data_raises_and_does_not_add(
    hass: HomeAssistant,
) -> None:
    """Ungültige Rohdaten dürfen weder validiert noch zum Provider durchgereicht werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenValidationError):
        await coordinator.async_add_hofladen({"name": "Ohne ID"})

    assert coordinator.data == {}


async def test_add_hofladen_duplicate_id_raises(hass: HomeAssistant) -> None:
    """Ein Duplikat der ID muss durchgereicht werden, nicht überschrieben."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Bestehender Hofladen"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(DuplicateHofladenIdError):
        await coordinator.async_add_hofladen({"id": "hof-1", "name": "Anderer Name"})


async def test_add_hofladen_not_supported_by_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen klaren Fehler liefern."""
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neu"})


# ---------------------------------------------------------------------------
# async_update_hofladen_sortiment (Sortiment nutzereditierbar)
# ---------------------------------------------------------------------------


async def test_update_sortiment_aendert_gewaehltes_feld(hass: HomeAssistant) -> None:
    """Nur das übergebene Feld darf geändert werden, andere bleiben erhalten."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "angebote": [{"id": "honig", "name": "Honig"}],
                "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1",
        zahlungsarten=[
            {"id": "bar", "name": "Bargeld"},
            {"id": "twint", "name": "TWINT"},
        ],
    )

    assert [z.name for z in ergebnis.zahlungsarten] == ["Bargeld", "TWINT"]
    assert [a.name for a in ergebnis.angebote] == ["Honig"]  # unverändert

    # Auch im Coordinator (nach Refresh) muss die Änderung sichtbar sein.
    aktualisiert = coordinator.data["hof-1"]
    assert [z.name for z in aktualisiert.zahlungsarten] == ["Bargeld", "TWINT"]
    assert [a.name for a in aktualisiert.angebote] == ["Honig"]


async def test_update_sortiment_mehrere_fachbereiche_gleichzeitig(
    hass: HomeAssistant,
) -> None:
    """Mehrere Fachbereiche müssen in einem Aufruf gemeinsam änderbar sein."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1",
        angebote=[{"id": "kartoffeln", "name": "Kartoffeln"}],
        zahlungsarten=[{"id": "bar", "name": "Bargeld"}],
    )

    assert [a.name for a in ergebnis.angebote] == ["Kartoffeln"]
    assert [z.name for z in ergebnis.zahlungsarten] == ["Bargeld"]


async def test_update_sortiment_leere_liste_leert_feld(hass: HomeAssistant) -> None:
    """Eine explizit übergebene leere Liste muss das Feld leeren (kein 'unverändert')."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "angebote": [{"id": "honig", "name": "Honig"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1", angebote=[]
    )

    assert ergebnis.angebote == ()


async def test_update_sortiment_ohne_parameter_aendert_nichts(
    hass: HomeAssistant,
) -> None:
    """Werden keine Parameter gesetzt, bleibt der Hofladen unverändert."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "angebote": [{"id": "honig", "name": "Honig"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment("hof-1")

    assert [a.name for a in ergebnis.angebote] == ["Honig"]


async def test_update_sortiment_unbekannte_id_wirft_fehler(
    hass: HomeAssistant,
) -> None:
    """Eine nicht existierende Hofladen-ID muss abgelehnt werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenNotFoundError):
        await coordinator.async_update_hofladen_sortiment(
            "unbekannt", angebote=[{"id": "honig", "name": "Honig"}]
        )


async def test_update_sortiment_ungueltige_daten_wirft_fehler_und_aendert_nichts(
    hass: HomeAssistant,
) -> None:
    """Ungültige Werte müssen abgelehnt werden, ohne den Provider zu verändern
    (Fail-Fast, analog zu async_add_hofladen)."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenValidationError):
        await coordinator.async_update_hofladen_sortiment(
            "hof-1", angebote=[{"id": "honig"}]  # 'name' fehlt
        )

    # Der Datensatz darf durch den fehlgeschlagenen Versuch nicht verändert
    # worden sein.
    unveraendert = coordinator.data["hof-1"]
    assert unveraendert.angebote == ()


async def test_update_sortiment_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen klaren Fehler liefern."""
    provider = _FakeProvider(raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_update_hofladen_sortiment(
            "hof-1", angebote=[{"id": "honig", "name": "Honig"}]
        )


# ---------------------------------------------------------------------------
# async_save_hofladen (Kapselung für management.py)
# ---------------------------------------------------------------------------


async def test_save_hofladen_legt_neuen_hofladen_an(hass: HomeAssistant) -> None:
    """Eine unbekannte ID muss einen neuen Hofladen anlegen."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-neu", "name": "Neuer Hofladen"}
    )

    assert ergebnis.id == "hof-neu"
    assert "hof-neu" in coordinator.data


async def test_save_hofladen_aktualisiert_bestehenden_hofladen(
    hass: HomeAssistant,
) -> None:
    """Eine bereits vorhandene ID muss aktualisiert werden, kein Duplikatfehler."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Alter Name"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-1", "name": "Neuer Name"}
    )

    assert ergebnis.name == "Neuer Name"
    assert coordinator.data["hof-1"].name == "Neuer Name"


async def test_save_hofladen_kann_beliebige_felder_setzen(
    hass: HomeAssistant,
) -> None:
    """Im Unterschied zu async_update_hofladen_sortiment müssen auch Felder
    wie Adresse/Koordinaten setzbar sein."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {
            "id": "hof-1",
            "name": "Hofladen Eins",
            "adresse": "Dorfstrasse 1",
            "latitude": 47.0,
            "longitude": 8.0,
        }
    )

    assert ergebnis.adresse == "Dorfstrasse 1"
    assert ergebnis.latitude == 47.0


async def test_save_hofladen_ungueltige_daten_wirft_fehler(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenValidationError):
        await coordinator.async_save_hofladen({"name": ""})


async def test_save_hofladen_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_save_hofladen({"id": "hof-1", "name": "Hofladen"})


# ---------------------------------------------------------------------------
# async_save_hofladen – Versionierung/Konflikterkennung (Phase 8b)
# ---------------------------------------------------------------------------


async def test_save_hofladen_neu_erhaelt_version_eins(
    hass: HomeAssistant,
) -> None:
    """Ein neu angelegter Hofladen beginnt bei Version 1, unabhängig davon,
    ob die Aufrufer selbst eine (falsche) Version mitschicken."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-neu", "name": "Neuer Hofladen", "version": 99}
    )

    assert ergebnis.version == 1
    assert coordinator.data["hof-neu"].version == 1


async def test_save_hofladen_aktualisierung_erhoeht_version(
    hass: HomeAssistant,
) -> None:
    """Jede erfolgreiche Aktualisierung erhöht die Version um 1."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Alter Name", "version": 1}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-1", "name": "Neuer Name", "version": 1}
    )

    assert ergebnis.version == 2
    assert coordinator.data["hof-1"].version == 2


async def test_save_hofladen_ohne_version_prueft_keinen_konflikt(
    hass: HomeAssistant,
) -> None:
    """Fehlt 'version' im übergebenen Datensatz (ältere Aufrufer, Import),
    wird kein Konflikt geprüft - die Änderung wird wie bisher übernommen,
    die Version aber dennoch serverseitig weitergeführt."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Alter Name", "version": 5}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-1", "name": "Ohne Versionsangabe"}
    )

    assert ergebnis.name == "Ohne Versionsangabe"
    assert ergebnis.version == 6


async def test_save_hofladen_veraltete_version_wirft_konflikt(
    hass: HomeAssistant,
) -> None:
    """Eine veraltete erwartete Version (ein anderes Gerät hat
    zwischenzeitlich bereits gespeichert) muss abgelehnt werden, OHNE die
    aktuell gespeicherten Daten zu verändern."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Serverstand", "version": 3}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenVersionConflictError) as exc_info:
        await coordinator.async_save_hofladen(
            {"id": "hof-1", "name": "Veralteter Stand", "version": 2}
        )

    assert exc_info.value.aktueller_hofladen.name == "Serverstand"
    assert exc_info.value.aktueller_hofladen.version == 3
    # Die ursprünglichen Daten dürfen unverändert bleiben.
    assert coordinator.data["hof-1"].name == "Serverstand"
    assert coordinator.data["hof-1"].version == 3


async def test_save_hofladen_unbekannte_id_mit_version_wird_wie_neuanlage_behandelt(
    hass: HomeAssistant,
) -> None:
    """Eine mitgeschickte Version für eine (noch) nicht existierende ID löst
    keinen Konflikt aus - der Datensatz existiert serverseitig schlicht noch
    nicht, es gibt also nichts, womit die Version kollidieren könnte."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_save_hofladen(
        {"id": "hof-unbekannt", "name": "Hofladen", "version": 4}
    )

    assert ergebnis.version == 1


# ---------------------------------------------------------------------------
# async_delete_hofladen (Kapselung für management.py)
# ---------------------------------------------------------------------------


async def test_delete_hofladen_entfernt_bestehenden_hofladen(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    await coordinator.async_delete_hofladen("hof-1")

    assert "hof-1" not in coordinator.data


async def test_delete_hofladen_unbekannte_id_wirft_fehler(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenNotFoundError):
        await coordinator.async_delete_hofladen("unbekannt")


async def test_delete_hofladen_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    provider = _FakeProvider(raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_delete_hofladen("hof-1")


# ---------------------------------------------------------------------------
# Diagnostics-Unterstützung
# ---------------------------------------------------------------------------


async def test_letzte_erfolgreiche_aktualisierung_none_vor_erstem_abruf(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    assert coordinator.letzte_erfolgreiche_aktualisierung is None


async def test_letzte_erfolgreiche_aktualisierung_gesetzt_nach_erfolg(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.letzte_erfolgreiche_aktualisierung is not None


async def test_letzte_erfolgreiche_aktualisierung_bleibt_bei_fehlschlag_erhalten(
    hass: HomeAssistant,
) -> None:
    """Ein späterer Fehlversuch darf den Zeitpunkt des letzten Erfolgs nicht
    überschreiben (wichtig für Diagnostics: zeigt, seit wann es hakt)."""
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    erster_zeitpunkt = coordinator.letzte_erfolgreiche_aktualisierung
    assert erster_zeitpunkt is not None

    provider.error = RuntimeError("Vorübergehend nicht erreichbar")
    await coordinator.async_refresh()

    assert coordinator.letzte_erfolgreiche_aktualisierung == erster_zeitpunkt


async def test_provider_type_name(hass: HomeAssistant) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    assert coordinator.provider_type_name == "StaticTestDataProvider"


async def test_provider_unterstuetzt_schreibzugriffe_true_fuer_mutable(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    assert coordinator.provider_unterstuetzt_schreibzugriffe is True


async def test_provider_unterstuetzt_schreibzugriffe_false_fuer_read_only(
    hass: HomeAssistant,
) -> None:
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    assert coordinator.provider_unterstuetzt_schreibzugriffe is False
