"""Die HofKarte-Integration für Home Assistant.

Die Einrichtung erfolgt ausschliesslich über den Config Flow (siehe
``config_flow.py``). Eine YAML-Konfiguration ist nicht vorgesehen.

Dieses Modul richtet zusätzlich zu den Devices (siehe ``device.py``) die
Hofladen-Entities (Binary Sensor „Geöffnet“, Sensoren „Nächste
Öffnung“/„Nächste Schliessung“) über die Plattformen ``binary_sensor``
und ``sensor`` ein.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .data_provider import StorageHofladenDataProvider
from .device import async_sync_devices
from .frontend import async_register_frontend, async_remove_frontend, async_setup_frontend_assets
from .management import async_register_websocket_commands
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.IMAGE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register global HofKarte frontend/WebSocket/Action functionality.

    Home Assistant calls integration ``async_setup`` with both ``hass`` and
    the processed YAML configuration. HofKarte does not use YAML
    configuration, but the second argument is part of the Home Assistant
    integration setup contract.
    """
    async_register_websocket_commands(hass)
    await async_setup_frontend_assets(hass)
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HofKarte from a config entry.

    Erstellt den zentralen Coordinator, führt den initialen Datenabruf
    durch, registriert je Hofladen ein Device in der Device Registry und
    hält diese bei jedem weiteren Coordinator-Update synchron.

    Schlägt der initiale Abruf fehl, hebt
    ``async_config_entry_first_refresh`` automatisch ``ConfigEntryNotReady``
    aus; Home Assistant versucht die Einrichtung dann später erneut.
    """
    # Architekturentscheid: Home Assistant ist sowohl Laufzeit- als auch
    # Verwaltungsoberfläche für HofKarte. Die vom Benutzer gepflegten
    # Hofläden werden in einem integrationsinternen, persistenten Store
    # gehalten (siehe data_provider.StorageHofladenDataProvider). Der
    # Coordinator kennt ausschliesslich die abstrakte
    # HofladenDataProvider-Schnittstelle, nicht die konkrete Speicherform.
    provider = StorageHofladenDataProvider(hass)
    coordinator = HofKarteUpdateCoordinator(hass, provider, config_entry=entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async_sync_devices(hass, entry, coordinator.data)
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: async_sync_devices(hass, entry, coordinator.data)
        )
    )

    if not hass.is_running:
        # Befund F1: ``hochgeladen`` wird aus der Origin dieser Instanz
        # abgeleitet. Vor dem Start von Home Assistant ist die automatisch
        # erkannte lokale Adresse (``get_url``) evtl. noch nicht bekannt -
        # nach dem Start werden die Daten daher einmal neu eingelesen.
        async def _nach_start(_hass: HomeAssistant) -> None:
            await coordinator.async_request_refresh()

        entry.async_on_unload(async_at_started(hass, _nach_start))

    await async_register_frontend(hass)
    entry.async_on_unload(lambda: async_remove_frontend(hass))

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("HofKarte-Config-Entry eingerichtet: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a HofKarte config entry."""
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        )

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
