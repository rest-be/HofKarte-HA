"""Tests für services.py – die HofKarte-Home-Assistant-Actions."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.services import (
    SERVICE_HOFLAEDEN_IN_NAEHE,
    SERVICE_HOFLAEDEN_SUCHEN,
    _get_coordinator,
)

# Bern, Bahnhof - Referenzstandort für die hoflaeden_in_naehe-Tests
_BERN_LAT, _BERN_LON = 46.9480, 7.4474


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(hass: HomeAssistant) -> None:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------


async def test_service_wird_registriert(hass: HomeAssistant) -> None:
    """Die Action muss nach dem Setup unter der Domain verfügbar sein."""
    await _setup(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_HOFLAEDEN_SUCHEN)


# ---------------------------------------------------------------------------
# _get_coordinator
# ---------------------------------------------------------------------------


def test_get_coordinator_wirft_fehler_wenn_nicht_eingerichtet(
    hass: HomeAssistant,
) -> None:
    with pytest.raises(HomeAssistantError):
        _get_coordinator(hass)


# ---------------------------------------------------------------------------
# Aufruf mit Rückgabedaten
# ---------------------------------------------------------------------------


async def test_suche_ohne_filter_liefert_alle_hoflaeden(
    hass: HomeAssistant,
) -> None:
    """Ohne Filter müssen alle vorhandenen Hofläden zurückkommen."""
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    ergebnis = await hass.services.async_call(
        DOMAIN, SERVICE_HOFLAEDEN_SUCHEN, {}, blocking=True, return_response=True
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-1"
    assert ergebnis["hoflaeden"][0]["name"] == "Hofladen Eins"
    # Ohne Öffnungszeiten hinterlegt ist der Status bewusst unbekannt (None).
    assert ergebnis["hoflaeden"][0]["geoeffnet"] is None


async def test_suche_mit_suchbegriff_filtert_korrekt(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Müller"})
    await coordinator.async_add_hofladen({"id": "hof-2", "name": "Hofladen Schmid"})

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        {"suchbegriff": "müller"},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-1"


async def test_suche_mit_angebot_filter(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-1",
            "name": "Hofladen Eins",
            "angebote": [{"id": "kartoffeln", "name": "Kartoffeln"}],
        }
    )
    await coordinator.async_add_hofladen({"id": "hof-2", "name": "Hofladen Zwei"})

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        {"angebot": "Kartoffeln"},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-1"


async def test_suche_mit_mehreren_kombinierten_filtern(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-1",
            "name": "Hofladen Eins",
            "angebote": [{"id": "kartoffeln", "name": "Kartoffeln"}],
            "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
        }
    )
    await coordinator.async_add_hofladen(
        {
            "id": "hof-2",
            "name": "Hofladen Zwei",
            "angebote": [{"id": "kartoffeln2", "name": "Kartoffeln"}],
            "zahlungsarten": [{"id": "twint", "name": "TWINT"}],
        }
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        {"angebot": "Kartoffeln", "zahlungsart": "Bargeld"},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-1"


async def test_suche_ohne_treffer_liefert_leeres_ergebnis(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        {"suchbegriff": "existiert-nicht"},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 0
    assert ergebnis["hoflaeden"] == []


async def test_suche_nur_geoeffnet(hass: HomeAssistant) -> None:
    """Mit nur_geoeffnet=True dürfen nur aktuell geöffnete Hofläden erscheinen."""
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]

    await coordinator.async_add_hofladen(
        {
            "id": "hof-immer-offen",
            "name": "Rund-um-die-Uhr-Hofladen",
            "oeffnungszeiten": [
                {"wochentag": tag, "beginn": "00:00", "ende": "23:59"}
                for tag in range(1, 8)
            ],
        }
    )
    await coordinator.async_add_hofladen(
        {"id": "hof-ohne-zeiten", "name": "Hofladen ohne Öffnungszeiten"}
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        {"nur_geoeffnet": True},
        blocking=True,
        return_response=True,
    )

    treffer_ids = {eintrag["id"] for eintrag in ergebnis["hoflaeden"]}
    assert "hof-immer-offen" in treffer_ids
    assert "hof-ohne-zeiten" not in treffer_ids


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------


async def test_suche_mit_ungueltigem_datentyp_wird_abgelehnt(
    hass: HomeAssistant,
) -> None:
    """Ein strukturell falscher Datentyp (Liste statt Text) muss vom Schema
    abgelehnt werden, bevor der Handler überhaupt aufgerufen wird.

    Hinweis: Home Assistants ``cv.string`` konvertiert Zahlen/Bools
    grosszügig in Strings (dokumentiertes Verhalten); Listen/Dicts lehnt
    es hingegen ab – das prüft dieser Test.
    """
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_SUCHEN,
            {"angebot": ["nicht", "erlaubt"]},
            blocking=True,
            return_response=True,
        )


async def test_suche_mit_unbekanntem_feld_wird_abgelehnt(
    hass: HomeAssistant,
) -> None:
    """Unbekannte Felder müssen vom Schema abgelehnt werden (kein 'anything goes')."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_SUCHEN,
            {"unbekanntes_feld": "wert"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# hoflaeden_in_naehe – Registrierung
# ---------------------------------------------------------------------------


async def test_naehe_service_wird_registriert(hass: HomeAssistant) -> None:
    """Die Action muss nach dem Setup unter der Domain verfügbar sein."""
    await _setup(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_HOFLAEDEN_IN_NAEHE)


# ---------------------------------------------------------------------------
# hoflaeden_in_naehe – Aufruf mit Rückgabedaten
# ---------------------------------------------------------------------------


async def test_naehe_findet_hofladen_im_radius(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-nahe",
            "name": "Hofladen nahe Bern",
            "latitude": 46.95,
            "longitude": 7.45,
        }
    )
    await coordinator.async_add_hofladen(
        {
            "id": "hof-weit-weg",
            "name": "Hofladen weit weg",
            "latitude": 47.3769,
            "longitude": 8.5417,
        }
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        {"latitude": _BERN_LAT, "longitude": _BERN_LON, "radius_meter": 2000},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-nahe"
    assert ergebnis["hoflaeden"][0]["name"] == "Hofladen nahe Bern"
    assert isinstance(ergebnis["hoflaeden"][0]["entfernung_meter"], int)


async def test_naehe_ohne_treffer_liefert_leeres_ergebnis(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-weit-weg",
            "name": "Hofladen weit weg",
            "latitude": 47.3769,
            "longitude": 8.5417,
        }
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        {"latitude": _BERN_LAT, "longitude": _BERN_LON, "radius_meter": 500},
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 0
    assert ergebnis["hoflaeden"] == []


async def test_naehe_sortiert_nach_entfernung(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {"id": "hof-weiter", "name": "Weiter weg", "latitude": 47.0, "longitude": 7.5}
    )
    await coordinator.async_add_hofladen(
        {"id": "hof-naeher", "name": "Näher dran", "latitude": 46.95, "longitude": 7.45}
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        {"latitude": _BERN_LAT, "longitude": _BERN_LON, "radius_meter": 100_000},
        blocking=True,
        return_response=True,
    )

    assert [hof["id"] for hof in ergebnis["hoflaeden"]] == [
        "hof-naeher",
        "hof-weiter",
    ]


async def test_naehe_nur_geoeffnet_filtert(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-immer-offen",
            "name": "Rund-um-die-Uhr-Hofladen",
            "latitude": 46.95,
            "longitude": 7.45,
            "oeffnungszeiten": [
                {"wochentag": tag, "beginn": "00:00", "ende": "23:59"}
                for tag in range(1, 8)
            ],
        }
    )
    await coordinator.async_add_hofladen(
        {
            "id": "hof-ohne-zeiten",
            "name": "Hofladen ohne Öffnungszeiten",
            "latitude": 46.95,
            "longitude": 7.45,
        }
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        {
            "latitude": _BERN_LAT,
            "longitude": _BERN_LON,
            "radius_meter": 2000,
            "nur_geoeffnet": True,
        },
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-immer-offen"


async def test_naehe_min_bewertung_filtert(hass: HomeAssistant) -> None:
    await _setup(hass)
    coordinator = hass.data[DOMAIN][next(iter(hass.data[DOMAIN]))]
    await coordinator.async_add_hofladen(
        {
            "id": "hof-liebling",
            "name": "Lieblings-Hofladen",
            "latitude": 46.95,
            "longitude": 7.45,
            "bewertung": 5,
        }
    )
    await coordinator.async_add_hofladen(
        {
            "id": "hof-unbewertet",
            "name": "Unbewerteter Hofladen",
            "latitude": 46.95,
            "longitude": 7.45,
        }
    )

    ergebnis = await hass.services.async_call(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        {
            "latitude": _BERN_LAT,
            "longitude": _BERN_LON,
            "radius_meter": 2000,
            "min_bewertung": 4,
        },
        blocking=True,
        return_response=True,
    )

    assert ergebnis["anzahl_treffer"] == 1
    assert ergebnis["hoflaeden"][0]["id"] == "hof-liebling"
    assert ergebnis["hoflaeden"][0]["bewertung"] == 5


# ---------------------------------------------------------------------------
# hoflaeden_in_naehe – Validierung
# ---------------------------------------------------------------------------


async def test_naehe_ohne_pflichtfeld_wird_abgelehnt(hass: HomeAssistant) -> None:
    """``latitude``/``longitude``/``radius_meter`` sind Pflichtfelder."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_IN_NAEHE,
            {"latitude": _BERN_LAT, "longitude": _BERN_LON},
            blocking=True,
            return_response=True,
        )


async def test_naehe_mit_ungueltiger_latitude_wird_abgelehnt(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_IN_NAEHE,
            {"latitude": 999, "longitude": _BERN_LON, "radius_meter": 500},
            blocking=True,
            return_response=True,
        )


async def test_naehe_mit_negativem_radius_wird_abgelehnt(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_IN_NAEHE,
            {"latitude": _BERN_LAT, "longitude": _BERN_LON, "radius_meter": -1},
            blocking=True,
            return_response=True,
        )


async def test_naehe_mit_min_bewertung_ausserhalb_bereich_wird_abgelehnt(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOFLAEDEN_IN_NAEHE,
            {
                "latitude": _BERN_LAT,
                "longitude": _BERN_LON,
                "radius_meter": 500,
                "min_bewertung": 6,
            },
            blocking=True,
            return_response=True,
        )
