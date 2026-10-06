"""Device-Repräsentation für Hofläden.

Jeder Hofladen wird als logisches Home-Assistant-Device abgebildet – kein
physisches Gerät. Dieses Modul kapselt
ausschliesslich die Erstellung der ``DeviceInfo``-Struktur sowie die
Synchronisation mit der Device Registry. Es enthält bewusst keine
Entity-Logik – Entities werden in eigenen Modulen implementiert (siehe
``binary_sensor.py``, ``sensor.py``, ``image.py``).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .models import Hofladen

_LOGGER = logging.getLogger(__name__)


def build_device_identifier(hofladen: Hofladen) -> tuple[str, str]:
    """Stabilen Device-Identifier für einen Hofladen erzeugen.

    Basiert ausschliesslich auf der stabilen ``Hofladen.id`` aus dem
    Datenmodell (siehe ``models.py``) und wechselt daher nie zwischen
    Neustarts, Reloads oder Coordinator-Updates.
    """
    return (DOMAIN, hofladen.id)


def build_device_info(hofladen: Hofladen) -> dr.DeviceInfo:
    """``DeviceInfo`` für einen Hofladen erzeugen.

    Es werden bewusst keine ``manufacturer``- oder ``model``-Angaben
    gesetzt: Ein Hofladen ist kein physisches Gerät mit Hersteller oder
    Modell, und das fachliche Datenmodell (``models.Hofladen``) kennt
    diese Konzepte nicht. Erfundene Werte sind daher nicht zulässig.
    """
    return dr.DeviceInfo(
        identifiers={build_device_identifier(hofladen)},
        name=hofladen.name,
    )


def async_sync_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    hoflaeden: dict[str, Hofladen],
) -> None:
    """Device Registry mit den aktuellen Hofladen-Daten abgleichen.

    - Für jeden Hofladen wird ein Device erzeugt bzw. aktualisiert.
      ``async_get_or_create`` ist idempotent: wiederholte Aufrufe mit
      identischen ``identifiers`` (z. B. bei einem Reload oder einem
      erneuten Coordinator-Update) erzeugen keine Duplikate.
    - Devices von Hofläden, die nicht mehr in ``hoflaeden`` enthalten
      sind (z. B. aus dem persistenten Storage entfernt), werden aus der
      Device Registry entfernt. Die bereits registrierten Entities bleiben
      bewusst bestehen und werden durch ``HofKarteEntity.available``
      ``unavailable``; dadurch bleiben stabile Entity-IDs erhalten.
    - Devices, die nicht zu dieser Config Entry gehören, bleiben
      unangetastet.
    """
    device_registry = dr.async_get(hass)

    current_identifiers = {
        build_device_identifier(hofladen) for hofladen in hoflaeden.values()
    }

    for hofladen in hoflaeden.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **build_device_info(hofladen),
        )

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        hofkarte_identifiers = {
            identifier
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }
        if hofkarte_identifiers and not hofkarte_identifiers & current_identifiers:
            _LOGGER.debug(
                "Entferne Device %s (Hofladen nicht mehr in den Daten enthalten): %s",
                device_entry.id,
                hofkarte_identifiers,
            )
            device_registry.async_remove_device(device_entry.id)
