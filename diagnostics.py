"""Diagnostics-Unterstützung für HofKarte.

Liefert eine kompakte technische Übersicht für die Fehlersuche (Home
Assistant → Einstellungen → Geräte & Dienste → HofKarte → Diagnose
herunterladen).

Enthält bewusst **keine** Hofladen-Inhalte (Namen, Adressen,
Beschreibungen, Koordinaten, Bild-URLs) und keine
Home-Assistant-Standortdaten (``hass.config.latitude``/``longitude``):
Auch wenn diese Daten fachlich nicht "geheim" sind (öffentliche
Hofladen-Informationen), sind es nutzerspezifische Daten, die in einer
zur Fehlersuche geteilten und damit potenziell öffentlich einsehbaren
Diagnosedatei nichts verloren haben (Grundsatz: „Keine
vertraulichen Konfigurationswerte in Logs oder Diagnostics“). Es werden
ausschliesslich anonymisierte Zähler und technische Statusinformationen
ausgegeben.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnosedaten für eine HofKarte-Config-Entry zusammenstellen."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": {
            "version": entry.version,
            "state": str(entry.state),
        },
        "datenquelle": {
            "typ": coordinator.provider_type_name,
            "unterstuetzt_schreibzugriffe": (
                coordinator.provider_unterstuetzt_schreibzugriffe
            ),
        },
        "coordinator": {
            "letzter_abruf_erfolgreich": coordinator.last_update_success,
            "letzte_erfolgreiche_aktualisierung_utc": (
                coordinator.letzte_erfolgreiche_aktualisierung.isoformat()
                if coordinator.letzte_erfolgreiche_aktualisierung
                else None
            ),
            "update_intervall_sekunden": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "letzter_fehler_typ": (
                type(coordinator.last_exception).__name__
                if coordinator.last_exception
                else None
            ),
        },
        "hoflaeden": {
            "anzahl": len(coordinator.data) if coordinator.data else 0,
        },
    }
