"""Entfernungsberechnung (Haversine, WGS84-Kugelnäherung)."""

from __future__ import annotations

import math

_ERDRADIUS_METER = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreisentfernung in Metern."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _ERDRADIUS_METER * math.asin(math.sqrt(h))
