"""Home-Assistant-Actions (Services) für HofKarte.

Kapselt ausschliesslich die Anbindung der Fachfunktion aus ``search.py``
an eine Home-Assistant-Action: Schema-Validierung des Service-Aufrufs,
Ermittlung des (einzigen) Coordinators und Aufbau der Rückgabedaten.
Enthält selbst keine Such-/Filterlogik.

Home Assistant stellt mit der eingebauten Action
``homeassistant.update_entity`` bereits eine allgemeine Möglichkeit
bereit, coordinator-basierte Entities (wie alle HofKarte-Entities, siehe
``entity.py``) gezielt zu aktualisieren. Eine eigene
„Hofladen-Daten aktualisieren“-Action würde dies nur unnötig
duplizieren und wird daher bewusst **nicht** implementiert (Grundsatz:
„Keine Actions bauen, die ... unnötig duplizieren“).

Analog wird auf separate Actions je Filterdimension (Angebot,
Zahlungsart) verzichtet – eine einzige, klar strukturierte Such-Action
mit mehreren optionalen, UND-verknüpften Filterparametern deckt alle
genannten Fälle ab, ohne naheliegend redundanten Code zu
erzeugen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .opening_hours import is_open
from .search import find_hoflaeden, find_hoflaeden_in_naehe

SERVICE_HOFLAEDEN_SUCHEN = "hoflaeden_suchen"
SERVICE_HOFLAEDEN_IN_NAEHE = "hoflaeden_in_naehe"

_SERVICE_HOFLAEDEN_SUCHEN_SCHEMA = vol.Schema(
    {
        vol.Optional("suchbegriff"): cv.string,
        vol.Optional("angebot"): cv.string,
        vol.Optional("zahlungsart"): cv.string,
        vol.Optional("nur_geoeffnet"): cv.boolean,
    }
)

_SERVICE_HOFLAEDEN_IN_NAEHE_SCHEMA = vol.Schema(
    {
        vol.Required("latitude"): cv.latitude,
        vol.Required("longitude"): cv.longitude,
        vol.Required("radius_meter"): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
        vol.Optional("nur_geoeffnet"): cv.boolean,
        vol.Optional("min_bewertung"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=5)
        ),
    }
)


def _get_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    """Den (einzigen) HofKarte-Coordinator ermitteln.

    HofKarte ist als Single-Instance-Integration ausgelegt (siehe
    ``config_flow.py``); der Zugriff über den einzigen Eintrag ist daher
    eindeutig – analog zu ``management._get_coordinator``.
    """
    entries = list(hass.data.get(DOMAIN, {}).values())
    if len(entries) != 1:
        raise HomeAssistantError("HofKarte ist nicht (oder mehrfach) eingerichtet.")
    return entries[0]


def _hofladen_zu_ergebnis_eintrag(hofladen: Any, now) -> dict[str, Any]:
    """Ein Suchtreffer als knapper, JSON-tauglicher Datensatz.

    Bewusst keine vollständige Kopie aller Hofladen-Felder – nur eine
    kompakte, für Automationen unmittelbar nützliche Auswahl
    (Identifikation, Anzeigename, aktueller Öffnungsstatus).
    """
    return {
        "id": hofladen.id,
        "name": hofladen.name,
        "geoeffnet": is_open(hofladen, now),
    }


def _naehe_treffer_zu_ergebnis_eintrag(
    hofladen: Any, entfernung_km: float, now
) -> dict[str, Any]:
    """Ein Nähe-Treffer als knapper, JSON-tauglicher Datensatz.

    Analog zu ``_hofladen_zu_ergebnis_eintrag``, zusätzlich mit der auf
    volle Meter gerundeten Entfernung zum übergebenen Standort – der für
    diese Action namensgebenden zusätzlichen Information gegenüber
    ``hoflaeden_suchen``.
    """
    eintrag = _hofladen_zu_ergebnis_eintrag(hofladen, now)
    eintrag["entfernung_meter"] = round(entfernung_km * 1000)
    eintrag["bewertung"] = hofladen.bewertung
    return eintrag


async def _async_hoflaeden_suchen(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Service-Handler für ``hofkarte.hoflaeden_suchen``."""
    coordinator = _get_coordinator(hass)

    nur_geoeffnet = call.data.get("nur_geoeffnet")
    now = dt_util.now()

    treffer = find_hoflaeden(
        coordinator.data.values() if coordinator.data else [],
        suchbegriff=call.data.get("suchbegriff"),
        angebot=call.data.get("angebot"),
        zahlungsart=call.data.get("zahlungsart"),
        nur_geoeffnet=nur_geoeffnet,
        now=now if nur_geoeffnet is not None else None,
    )

    return {
        "anzahl_treffer": len(treffer),
        "hoflaeden": [
            _hofladen_zu_ergebnis_eintrag(hofladen, now) for hofladen in treffer
        ],
    }


async def _async_hoflaeden_in_naehe(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Service-Handler für ``hofkarte.hoflaeden_in_naehe``.

    Anders als ``hoflaeden_suchen``/der ``Entfernung``-Sensor (beide
    gegen die fixe, konfigurierte Home-Assistant-Position) prüft diese
    Action gegen einen beliebigen, bei jedem Aufruf mitgegebenen
    Standort – Grundlage für eine Nähe-Benachrichtigung anhand des
    tatsächlichen Gerätestandorts (siehe ``search.find_hoflaeden_in_naehe``).
    """
    coordinator = _get_coordinator(hass)

    nur_geoeffnet = call.data.get("nur_geoeffnet")
    now = dt_util.now()

    treffer = find_hoflaeden_in_naehe(
        coordinator.data.values() if coordinator.data else [],
        latitude=call.data["latitude"],
        longitude=call.data["longitude"],
        radius_meter=call.data["radius_meter"],
        nur_geoeffnet=nur_geoeffnet,
        min_bewertung=call.data.get("min_bewertung"),
        now=now if nur_geoeffnet is not None else None,
    )

    return {
        "anzahl_treffer": len(treffer),
        "hoflaeden": [
            _naehe_treffer_zu_ergebnis_eintrag(hofladen, entfernung_km, now)
            for hofladen, entfernung_km in treffer
        ],
    }


def async_register_services(hass: HomeAssistant) -> None:
    """HofKarte-Actions registrieren.

    Wird einmalig aus ``__init__.async_setup`` aufgerufen (Domain-Ebene,
    analog zu ``management.async_register_websocket_commands`` –
    Actions sind wie WebSocket-Befehle nicht an eine einzelne Config
    Entry gebunden).
    """

    async def _service_handler(call: ServiceCall) -> ServiceResponse:
        # Eine eigene async-Funktion (statt einer lambda, die lediglich
        # eine Coroutine zurückgibt) ist hier notwendig: Home Assistant
        # erkennt den Service-Handler nur dann korrekt als Koroutinen-
        # funktion und awaitet ihn entsprechend, wenn er selbst mit
        # ``async def`` definiert ist. Eine lambda-Hülle würde
        # stattdessen die (nicht ausgeführte) Coroutine als Rückgabewert
        # liefern.
        return await _async_hoflaeden_suchen(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        _service_handler,
        schema=_SERVICE_HOFLAEDEN_SUCHEN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    async def _naehe_service_handler(call: ServiceCall) -> ServiceResponse:
        # Siehe Kommentar bei ``_service_handler`` oben – aus demselben
        # Grund auch hier eine eigene ``async def``-Funktion statt einer
        # lambda-Hülle.
        return await _async_hoflaeden_in_naehe(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOFLAEDEN_IN_NAEHE,
        _naehe_service_handler,
        schema=_SERVICE_HOFLAEDEN_IN_NAEHE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
