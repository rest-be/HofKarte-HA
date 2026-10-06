"""Sensoren für Hofläden: nächster Öffnungs-/Schliesszeitpunkt und Entfernung."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .distance import calculate_distance_km
from .entity import (
    HofKarteEntity,
    HofKarteZeitgesteuerteEntity,
    async_setup_hofladen_entities,
)
from .opening_hours import get_next_closing, get_next_opening

# Alle Hofladen-Daten stammen aus einem gemeinsamen Coordinator-Abruf
# (siehe entity.py); es gibt keine pro-Entity-Netzwerkzugriffe, die
# parallel gedrosselt werden müssten.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren für alle aktuellen und künftigen Hofläden einrichten."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entry.async_on_unload(
        async_setup_hofladen_entities(
            coordinator,
            async_add_entities,
            [
                HofKarteNaechsteOeffnungSensor,
                HofKarteNaechsteSchliessungSensor,
                HofKarteEntfernungSensor,
                HofKarteBewertungSensor,
            ],
        )
    )


class _HofKarteZeitpunktSensor(HofKarteZeitgesteuerteEntity, SensorEntity):
    """Gemeinsame Basis für die beiden zeitpunktbasierten Sensoren.

    ``TIMESTAMP`` ist die einzige passende Device Class für einen
    zukünftigen Zeitpunkt (nächste Öffnung/Schliessung); ``native_value``
    muss dafür ein zeitzonenbewusstes ``datetime``-Objekt oder ``None``
    liefern – keine erfundenen bzw. naiven Werte.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP


class HofKarteNaechsteOeffnungSensor(_HofKarteZeitpunktSensor):
    """Zeitpunkt der nächsten Öffnung eines Hofladens."""

    _attr_name = "Nächste Öffnung"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_naechste_oeffnung"

    @property
    def native_value(self):
        """Nächster Öffnungszeitpunkt.

        Berechnet über ``opening_hours.get_next_opening``. Liefert
        ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht (mehr)
        existiert oder keinerlei Öffnungszeiten hinterlegt sind.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return get_next_opening(hofladen, dt_util.now())


class HofKarteNaechsteSchliessungSensor(_HofKarteZeitpunktSensor):
    """Zeitpunkt der nächsten Schliessung eines Hofladens."""

    _attr_name = "Nächste Schliessung"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_naechste_schliessung"

    @property
    def native_value(self):
        """Nächster Schliesszeitpunkt.

        Berechnet über ``opening_hours.get_next_closing``. Liefert
        ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht (mehr)
        existiert oder keinerlei Öffnungszeiten hinterlegt sind.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return get_next_closing(hofladen, dt_util.now())


class HofKarteEntfernungSensor(HofKarteEntity, SensorEntity):
    """Entfernung eines Hofladens zur Home-Assistant-Position (Luftlinie).

    Nutzt ausschliesslich ``hass.config.latitude``/``longitude`` – die
    konfigurierte Position der Home-Assistant-Installation selbst – als
    Referenzpunkt. Das ist ein stabiler Konfigurationswert, kein von der
    Integration verfolgter oder gespeicherter Standort (siehe
    ``distance.py``, Grundsatz: „Keine Standortdaten
    persistieren“, „Keine Standortübertragung an externe Dienste“).

    Ein Distance Sensor ist hier fachlich sinnvoll: Der Zweck von
    HofKarte ist das Finden von Hofläden, und Home Assistant bietet mit
    ``SensorDeviceClass.DISTANCE`` eine passende, etablierte Device
    Class dafür (u. a. genutzt von Zonen-/Geolocation-Sensoren).
    """

    _attr_name = "Entfernung"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    # HA rundet den angezeigten Wert; der volle Wert bleibt für
    # Verlauf/Statistik erhalten (siehe distance.round_distance_km für
    # eine eigenständig testbare Variante ausserhalb von Entities).
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_entfernung"

    @property
    def native_value(self) -> float | None:
        """Entfernung in Kilometern.

        Berechnet über ``distance.calculate_distance_km``. Liefert
        ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht (mehr)
        existiert, keine Koordinaten hinterlegt hat, oder die
        Home-Assistant-Position nicht bekannt ist.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return calculate_distance_km(
            self.hass.config.latitude,
            self.hass.config.longitude,
            hofladen.latitude,
            hofladen.longitude,
        )


class HofKarteBewertungSensor(HofKarteEntity, SensorEntity):
    """Bewertung eines Hofladens (0-5 Sterne).

    Kein ``SensorDeviceClass`` – Home Assistant bietet keine passende
    Device Class für eine schlichte Sterne-Bewertung (anders als z. B.
    ``DISTANCE`` für ``HofKarteEntfernungSensor``); der Zustand ist ein
    einfacher, unitless Integer zwischen 0 und 5. Macht die Bewertung für
    Dashboards, Vorlagen und Automationen verfügbar (z. B. Filtern/
    Sortieren nach Bewertung in eigenen Lovelace-Karten).
    """

    _attr_name = "Bewertung"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_bewertung"

    @property
    def native_value(self) -> int | None:
        """Aktueller Bewertungswert (0-5).

        Liefert ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht
        (mehr) existiert.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return hofladen.bewertung
