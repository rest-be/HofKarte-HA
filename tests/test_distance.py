"""Tests für ``distance.py`` – Haversine-Distanz und Entfernungsberechnung."""

from __future__ import annotations

import pytest

from custom_components.hofkarte.distance import (
    calculate_distance_km,
    haversine_distance_km,
    is_valid_home_position,
    round_distance_km,
)

# Zürich HB
_ZUERICH_LAT, _ZUERICH_LON = 47.3769, 8.5417
# Bern, Bahnhof
_BERN_LAT, _BERN_LON = 46.9480, 7.4474


# ---------------------------------------------------------------------------
# haversine_distance_km
# ---------------------------------------------------------------------------


def test_bekannte_koordinaten_zuerich_bern() -> None:
    """Die Distanz zwischen zwei bekannten Städten muss dem erwarteten
    Wert entsprechen (Luftlinie Zürich–Bern: ca. 95.5 km)."""
    distanz = haversine_distance_km(_ZUERICH_LAT, _ZUERICH_LON, _BERN_LAT, _BERN_LON)

    assert distanz == pytest.approx(95.49, abs=0.1)


def test_gleiche_koordinaten_ergeben_null() -> None:
    """Identische Koordinaten müssen eine Distanz von exakt 0 km ergeben."""
    distanz = haversine_distance_km(47.0, 8.0, 47.0, 8.0)

    assert distanz == pytest.approx(0.0, abs=1e-9)


def test_symmetrie() -> None:
    """Die Distanz muss unabhängig von der Reihenfolge der Punkte sein."""
    a_nach_b = haversine_distance_km(_ZUERICH_LAT, _ZUERICH_LON, _BERN_LAT, _BERN_LON)
    b_nach_a = haversine_distance_km(_BERN_LAT, _BERN_LON, _ZUERICH_LAT, _ZUERICH_LON)

    assert a_nach_b == pytest.approx(b_nach_a)


def test_antipoden_ergeben_halben_erdumfang() -> None:
    """Zwei diametral gegenüberliegende Punkte (Pole) müssen die maximal
    mögliche Distanz (halber Erdumfang, ca. 20'015 km) ergeben."""
    distanz = haversine_distance_km(90.0, 0.0, -90.0, 0.0)

    assert distanz == pytest.approx(20015.11, abs=0.1)


def test_datumsgrenze_wird_korrekt_behandelt() -> None:
    """Zwei nahe beieinanderliegende Punkte beidseits der Datumsgrenze
    (179°/-179°) müssen als kurze, nicht als sehr lange Distanz erkannt
    werden – ein klassischer Grenzfall für naive Longitude-Differenzen."""
    kurze_distanz = haversine_distance_km(0.0, 179.0, 0.0, -179.0)

    # Bei einer naiven Differenz (179 - (-179) = 358°) ergäbe sich
    # fälschlich fast der halbe Erdumfang. Der tatsächliche, kurze Weg
    # entspricht 2° Längengrad am Äquator (ca. 222 km).
    assert kurze_distanz == pytest.approx(222.4, abs=0.1)
    assert kurze_distanz < 20000  # deutlich kürzer als der lange Umweg


# ---------------------------------------------------------------------------
# round_distance_km
# ---------------------------------------------------------------------------


def test_round_distance_km_standardrundung() -> None:
    """Standardmässig muss auf eine Nachkommastelle gerundet werden."""
    assert round_distance_km(12.34) == 12.3
    assert round_distance_km(0.0) == 0.0
    assert round_distance_km(99.96) == 100.0


def test_round_distance_km_eigene_nachkommastellen() -> None:
    """Die Anzahl Nachkommastellen muss konfigurierbar sein."""
    assert round_distance_km(12.345, ndigits=2) == 12.35
    assert round_distance_km(12.0, ndigits=0) == 12.0


# ---------------------------------------------------------------------------
# calculate_distance_km
# ---------------------------------------------------------------------------


def test_calculate_distance_km_mit_bekannten_koordinaten() -> None:
    """Bei vollständigen Koordinaten muss die berechnete Distanz stimmen."""
    distanz = calculate_distance_km(
        _ZUERICH_LAT, _ZUERICH_LON, _BERN_LAT, _BERN_LON
    )

    assert distanz == pytest.approx(95.49, abs=0.1)


def test_is_valid_home_position() -> None:
    """Nur nutzbare Home-Assistant-Koordinaten gelten als bekannt."""
    assert is_valid_home_position(_ZUERICH_LAT, _ZUERICH_LON) is True
    assert is_valid_home_position(0.0, _ZUERICH_LON) is True
    assert is_valid_home_position(_ZUERICH_LAT, 0.0) is True
    assert is_valid_home_position(0.0, 0.0) is False
    assert is_valid_home_position(None, _ZUERICH_LON) is False
    assert is_valid_home_position(_ZUERICH_LAT, None) is False


def test_calculate_distance_km_fehlende_home_position() -> None:
    """Ohne bekannte Home-Assistant-Position muss None geliefert werden."""
    assert calculate_distance_km(None, None, _BERN_LAT, _BERN_LON) is None
    assert calculate_distance_km(_ZUERICH_LAT, None, _BERN_LAT, _BERN_LON) is None
    assert calculate_distance_km(None, _ZUERICH_LON, _BERN_LAT, _BERN_LON) is None


def test_calculate_distance_km_standardposition_0_0_gilt_als_unbekannt() -> None:
    """0.0/0.0 darf nicht als echte Home-Position verwendet werden."""
    assert calculate_distance_km(0.0, 0.0, _BERN_LAT, _BERN_LON) is None


def test_calculate_distance_km_fehlende_hofladen_koordinaten() -> None:
    """Ohne bekannte Hofladen-Koordinaten muss None geliefert werden."""
    assert (
        calculate_distance_km(_ZUERICH_LAT, _ZUERICH_LON, None, None) is None
    )
    assert (
        calculate_distance_km(_ZUERICH_LAT, _ZUERICH_LON, _BERN_LAT, None) is None
    )
    assert (
        calculate_distance_km(_ZUERICH_LAT, _ZUERICH_LON, None, _BERN_LON) is None
    )


def test_calculate_distance_km_beide_positionen_fehlen() -> None:
    """Fehlen beide Positionen, muss ebenfalls None geliefert werden."""
    assert calculate_distance_km(None, None, None, None) is None
