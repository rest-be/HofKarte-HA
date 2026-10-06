"""End-zu-End-Test eines vollständigen, realistischen Nutzungsszenarios.

Bildet den kompletten, im Umsetzungsplan beschriebenen Ablauf nach
(soweit innerhalb einer Testsuite ohne echten HACS-/Browser-Kontext
möglich):

    Integration hinzufügen → Config Flow abschliessen → Daten abrufen
    → Hofladen als Device sehen → geöffnet/geschlossen sehen
    → Öffnungszeiten prüfen → Produkte/Eigenschaften sehen
    → Entfernung prüfen → Automation/Action testen
    → Integration reloaden (Ersatz für einen echten HA-Neustart,
      siehe Begründung unten) → Daten erneut prüfen

Mit **mehreren** Hofläden gleichzeitig, um Verwechslungen zwischen
Devices/Entities auszuschliessen.

Hinweis zu „Home Assistant neu starten“: Ein echter Prozess-Neustart ist
innerhalb einer einzelnen pytest-Session nicht sinnvoll simulierbar (die
Testbibliothek stellt dafür keinen unterstützten Mechanismus bereit). Der
nächstbeste, tatsächlich aussagekräftige Ersatz ist ein vollständiger
Config-Entry-Reload: Dabei wird – wie bei einem echten Neustart – eine
komplett neue Coordinator- und Provider-Instanz erzeugt, die ihre Daten
ausschliesslich aus dem persistenten Home-Assistant-Storage laden muss
(kein In-Memory-Zustand wird wiederverwendet). Das prüft exakt die
Eigenschaft, die ein Neustart-Test prüfen soll: Persistenz über das Ende
der Prozesslaufzeit einer Coordinator-Instanz hinaus.
"""

from __future__ import annotations

from datetime import time

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def test_vollstaendiges_end_zu_end_szenario_mit_mehreren_hoflaeden(
    hass: HomeAssistant,
) -> None:
    """Kompletter Ablauf mit zwei unterscheidbaren Hofläden."""
    # --- Integration hinzufügen / Config Flow abschliessen -----------------
    entry = _make_entry(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert result is True

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # --- Daten abrufen: zwei unterscheidbare Hofläden anlegen ---------------
    # Hofladen A: Montag 08:00-20:00 geöffnet, mit Sortiment, in Bern.
    montag = 1
    await coordinator.async_add_hofladen(
        {
            "id": "hof-a",
            "name": "Hofladen Alpha",
            "ort": "Bern",
            "latitude": 46.9480,
            "longitude": 7.4474,
            "oeffnungszeiten": [
                {"wochentag": tag, "beginn": "08:00", "ende": "20:00"}
                for tag in range(1, 8)
            ],
            "angebote": [
                {
                    "id": "kartoffeln",
                    "name": "Kartoffeln",
                }
            ],
            "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
        }
    )
    # Hofladen B: keine Öffnungszeiten hinterlegt (Status "unbekannt"),
    # andere Koordinaten, anderes Sortiment.
    await coordinator.async_add_hofladen(
        {
            "id": "hof-b",
            "name": "Hofladen Beta",
            "ort": "Thun",
            "latitude": 46.7580,
            "longitude": 7.6280,
            "zahlungsarten": [{"id": "twint", "name": "TWINT"}],
        }
    )
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert set(coordinator.data.keys()) == {"hof-a", "hof-b"}

    # --- Hofladen als Device sehen: zwei getrennte Devices ------------------
    device_registry = dr.async_get(hass)
    device_a = device_registry.async_get_device(identifiers={(DOMAIN, "hof-a")})
    device_b = device_registry.async_get_device(identifiers={(DOMAIN, "hof-b")})
    assert device_a is not None
    assert device_b is not None
    assert device_a.id != device_b.id
    assert device_a.name == "Hofladen Alpha"
    assert device_b.name == "Hofladen Beta"

    entity_registry = er.async_get(hass)

    def _entity_id(domain: str, hofladen_id: str, suffix: str) -> str | None:
        return entity_registry.async_get_entity_id(
            domain, DOMAIN, f"{DOMAIN}_{hofladen_id}_{suffix}"
        )

    # --- geöffnet/geschlossen sehen ------------------------------------------
    geoeffnet_a = _entity_id("binary_sensor", "hof-a", "geoeffnet")
    geoeffnet_b = _entity_id("binary_sensor", "hof-b", "geoeffnet")
    assert geoeffnet_a is not None
    assert geoeffnet_b is not None
    assert geoeffnet_a != geoeffnet_b  # stabil unterschiedliche Entity-IDs

    state_a = hass.states.get(geoeffnet_a)
    state_b = hass.states.get(geoeffnet_b)
    assert state_a is not None
    assert state_b is not None
    # Hofladen A ist an jedem Wochentag 08:00-20:00 geöffnet -> muss "on"
    # oder "off" sein (niemals "unknown", da Öffnungszeiten hinterlegt sind).
    assert state_a.state in ("on", "off")
    # Hofladen B hat keine Öffnungszeiten -> bewusst "unknown".
    assert state_b.state == "unknown"

    # --- Öffnungszeiten prüfen (Fachlogik direkt, unabhängig von der Uhrzeit
    # des Testlaufs) ----------------------------------------------------------
    from datetime import datetime, timezone

    from custom_components.hofkarte.opening_hours import is_open

    hofladen_a = coordinator.data["hof-a"]
    mittags_montag = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)  # Montag
    assert hofladen_a.oeffnungszeiten[0].wochentag == montag
    assert hofladen_a.oeffnungszeiten[0].beginn == time(8, 0)
    assert is_open(hofladen_a, mittags_montag) is True

    # --- Angebote/Eigenschaften sehen (Sortiment-Attribute) ------------------
    attribute_a = hass.states.get(geoeffnet_a).attributes
    assert attribute_a["angebote"] == ["Kartoffeln"]
    assert attribute_a["zahlungsarten"] == ["Bargeld"]

    # --- Entfernung prüfen -----------------------------------------------------
    hass.config.latitude = 46.9480  # Zuhause = exakt bei Hofladen A
    hass.config.longitude = 7.4474
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entfernung_a = _entity_id("sensor", "hof-a", "entfernung")
    entfernung_b = _entity_id("sensor", "hof-b", "entfernung")
    assert entfernung_a is not None
    assert entfernung_b is not None
    state_entfernung_a = hass.states.get(entfernung_a)
    state_entfernung_b = hass.states.get(entfernung_b)
    assert float(state_entfernung_a.state) == 0.0  # identische Koordinaten
    assert float(state_entfernung_b.state) > 0.0  # Thun liegt entfernt

    # --- Automation/Action testen (hofkarte.hoflaeden_suchen) ----------------
    treffer = await hass.services.async_call(
        DOMAIN,
        "hoflaeden_suchen",
        {"angebot": "Kartoffeln"},
        blocking=True,
        return_response=True,
    )
    assert treffer["anzahl_treffer"] == 1
    assert treffer["hoflaeden"][0]["id"] == "hof-a"

    # --- "Home Assistant neu starten" (Ersatz: vollständiger Reload, siehe
    # Modul-Docstring) + Integration reloaden -----------------------------
    # Zwei aufeinanderfolgende Reloads, um sicherzustellen, dass auch ein
    # zweiter Zyklus stabil bleibt (keine Duplikate, keine verlorenen Daten).
    for _ in range(2):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    # --- Daten erneut prüfen ----------------------------------------------
    coordinator_nach_reload = hass.data[DOMAIN][entry.entry_id]
    assert coordinator_nach_reload is not coordinator  # neue Instanz
    assert set(coordinator_nach_reload.data.keys()) == {"hof-a", "hof-b"}
    assert coordinator_nach_reload.data["hof-a"].name == "Hofladen Alpha"
    assert coordinator_nach_reload.data["hof-b"].name == "Hofladen Beta"

    # Entity-IDs und unique_ids müssen über den Reload hinweg stabil
    # bleiben (keine neuen/anderen IDs für dieselben Hofläden).
    assert _entity_id("binary_sensor", "hof-a", "geoeffnet") == geoeffnet_a
    assert _entity_id("binary_sensor", "hof-b", "geoeffnet") == geoeffnet_b

    # Devices weiterhin exakt zwei, keine Duplikate durch die Reloads.
    devices_nach_reload = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )
    assert len(devices_nach_reload) == 2
