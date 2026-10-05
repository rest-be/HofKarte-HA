"""Gemeinsame Basis für HofKarte-Entities.

Kapselt Device-Zuordnung und Verfügbarkeit, die für alle
Hofladen-Entities identisch sind, sowie einen Helper, der pro Plattform
(``binary_sensor``, ``sensor``) Entities für alle aktuellen *und* künftig
über den Coordinator hinzukommenden Hofläden anlegt (siehe
``coordinator.async_add_hofladen``), ohne dass ein Reload nötig ist.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import HofKarteUpdateCoordinator
from .device import build_device_info
from .models import Hofladen
from .opening_hours import naechster_statuswechsel


class HofKarteEntity(CoordinatorEntity[HofKarteUpdateCoordinator]):
    """Basisklasse für alle Entities eines einzelnen Hofladens."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator)
        self._hofladen_id = hofladen_id

    @property
    def hofladen(self) -> Hofladen | None:
        """Der aktuelle Hofladen-Datensatz, falls (noch) vorhanden.

        ``None``, wenn der Hofladen zwischenzeitlich aus den
        Coordinator-Daten verschwunden ist (siehe ``available``).
        """
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._hofladen_id)

    @property
    def available(self) -> bool:
        """Nur verfügbar, solange der letzte Abruf erfolgreich war *und*
        der zugehörige Hofladen noch in den Daten enthalten ist."""
        return super().available and self.hofladen is not None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Dem Hofladen zugeordnetes Device (siehe ``device.py``)."""
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return build_device_info(hofladen)


class HofKarteZeitgesteuerteEntity(HofKarteEntity):
    """Entity, deren Zustand von der Uhrzeit abhängt (Befund F6).

    Statt auf einen periodischen Coordinator-Abruf zu warten, wird die
    Entity exakt zum nächsten Statuswechsel aktualisiert
    (``async_track_point_in_time``, Zeitpunkt aus
    ``opening_hours.naechster_statuswechsel``) und danach neu geplant.
    Bei jedem Coordinator-Update (geänderte Öffnungszeiten) wird der
    Zeitpunkt neu berechnet. Die Abmeldung des Timers erfolgt über
    ``async_on_remove``.
    """

    _zeit_abmeldung: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._zeitplan_abmelden)
        self._zeitplan_neu_berechnen()

    @callback
    def _zeitplan_abmelden(self) -> None:
        if self._zeit_abmeldung is not None:
            self._zeit_abmeldung()
            self._zeit_abmeldung = None

    @callback
    def _zeitplan_neu_berechnen(self) -> None:
        """Nächsten Statuswechsel ermitteln und genau dafür einen Timer setzen."""
        self._zeitplan_abmelden()
        hofladen = self.hofladen
        if hofladen is None:
            return
        zeitpunkt = naechster_statuswechsel(hofladen, dt_util.now())
        if zeitpunkt is None:
            return
        self._zeit_abmeldung = async_track_point_in_time(
            self.hass, self._bei_statuswechsel, zeitpunkt
        )

    @callback
    def _bei_statuswechsel(self, _jetzt: datetime) -> None:
        self._zeit_abmeldung = None
        self.async_write_ha_state()
        self._zeitplan_neu_berechnen()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._zeitplan_neu_berechnen()
        super()._handle_coordinator_update()


def async_setup_hofladen_entities(
    coordinator: HofKarteUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    entity_factories: Iterable[
        Callable[[HofKarteUpdateCoordinator, str], HofKarteEntity]
    ],
) -> Callable[[], None]:
    """Entities für alle aktuellen und künftigen Hofläden anlegen.

    Wird von jeder Plattform (``binary_sensor.py``, ``sensor.py``) mit den
    dort passenden Entity-Klassen aufgerufen. Legt zunächst Entities für
    alle bereits bekannten Hofläden an und registriert danach einen
    Coordinator-Listener, der für neu hinzukommende Hofläden automatisch
    weitere Entities erzeugt.

    Gibt die Unsubscribe-Funktion des Listeners zurück; Aufrufer müssen
    diese über ``entry.async_on_unload`` registrieren, damit der Listener
    beim Entladen der Config Entry korrekt entfernt wird.
    """
    entity_factories = list(entity_factories)
    known_ids: set[str] = set()

    def _add_new_entities() -> None:
        new_ids = set(coordinator.data) - known_ids
        if not new_ids:
            return
        known_ids.update(new_ids)
        async_add_entities(
            factory(coordinator, hofladen_id)
            for hofladen_id in new_ids
            for factory in entity_factories
        )

    _add_new_entities()
    return coordinator.async_add_listener(_add_new_entities)
