"""Entfernungsberechnung zwischen der Home-Assistant-Position und Hofläden.

Enthält ausschliesslich reine, testbare Fachfunktionen (Haversine-
Distanz, Rundung für die Anzeige). Keine Abhängigkeit von ``hass``, keine
Speicherung von Positionsdaten, keine Netzwerkkommunikation – die
Berechnung erfolgt vollständig lokal aus den übergebenen Koordinaten
(Grundsatz: „Keine Standortdaten persistieren“, „Keine
Standortübertragung an externe Dienste“).

Referenzpunkt ist stets die konfigurierte Home-Assistant-Position
(``hass.config.latitude``/``longitude``, siehe ``sensor.py``) – ein
stabiler Konfigurationswert, kein von der Integration gespeicherter oder
verfolgter Standort.
"""

from __future__ import annotations

import math

# Mittlerer Erdradius in km (IUGG-Standardwert), gebräuchlich für
# Haversine-Berechnungen.
_ERDRADIUS_KM = 6371.0088

_STANDARD_RUNDUNG_NACHKOMMASTELLEN = 1


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreisdistanz zwischen zwei Koordinaten in Kilometern (Haversine).

    Reine, deterministische Fachfunktion ohne Seiteneffekte – unabhängig
    von Home Assistant testbar. Funktioniert korrekt auch über die
    Datumsgrenze (180°/-180°) hinweg, da die Formel auf periodischen
    Winkelfunktionen (Sinus/Kosinus) beruht statt auf einer naiven
    Differenz der Längengrade.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _ERDRADIUS_KM * c


def round_distance_km(
    distance_km: float, ndigits: int = _STANDARD_RUNDUNG_NACHKOMMASTELLEN
) -> float:
    """Entfernung für die Anzeige sinnvoll runden (Standard: 1 Nachkommastelle).

    Eigenständige, testbare Funktion für Kontexte ausserhalb einer
    Sensor-Entity (z. B. künftige Suche/Sortierung). Die Sensor-Entity
    selbst nutzt zusätzlich Home Assistants eingebauten Mechanismus
    (``suggested_display_precision``), damit der volle, ungerundete Wert
    für Verlauf/Statistik erhalten bleibt (siehe ``sensor.py``).
    """
    return round(distance_km, ndigits)


def is_valid_home_position(
    latitude: float | None, longitude: float | None
) -> bool:
    """Prüfen, ob eine konfigurierte Home-Assistant-Position nutzbar ist.

    ``None`` bedeutet eine unbekannte Position. Zusätzlich wird das von
    Home Assistant bei einer frischen, noch nicht sinnvoll konfigurierten
    Installation verwendete Paar ``0.0 / 0.0`` als unbekannt behandelt,
    damit daraus keine irreführende Entfernung berechnet wird. Einzelne
    Koordinaten von ``0.0`` bleiben dagegen gültig.
    """
    if latitude is None or longitude is None:
        return False
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return False
    if not -90.0 <= latitude <= 90.0:
        return False
    if not -180.0 <= longitude <= 180.0:
        return False
    return not (latitude == 0.0 and longitude == 0.0)


def calculate_distance_km(
    home_latitude: float | None,
    home_longitude: float | None,
    hofladen_latitude: float | None,
    hofladen_longitude: float | None,
) -> float | None:
    """Entfernung eines Hofladens zur Home-Assistant-Position in Kilometern.

    Liefert ``None`` (statt eines erfundenen oder geschätzten Werts), wenn
    die Home-Assistant-Position nicht nutzbar ist oder die Koordinaten des
    Hofladens nicht bekannt sind. Das Standardpaar ``0.0 / 0.0`` einer
    frischen, unkonfigurierten Home-Assistant-Installation wird als
    unbekannte Home-Position behandelt.
    """
    if not is_valid_home_position(home_latitude, home_longitude):
        return None
    if hofladen_latitude is None or hofladen_longitude is None:
        return None

    # is_valid_home_position() bereits geprüft: beide Werte sind an dieser
    # Stelle garantiert nicht None. Die assert-Anweisung macht das auch für
    # statische Typprüfung (mypy) explizit, da TypeGuard zwei unabhängige
    # Parameter nicht gemeinsam verengen kann.
    assert home_latitude is not None
    assert home_longitude is not None

    return haversine_distance_km(
        home_latitude, home_longitude, hofladen_latitude, hofladen_longitude
    )
