"""Suchprofile als reine Daten.

Ein Profil beschreibt, *was* gesucht wird (Overpass-Filter) - nicht *wie*.
Weitere Profile (z. B. Hofkäserei, Marktstand) lassen sich später als Daten
ergänzen, ohne den Abruf-Code anzufassen.

Messbefund (Phase 0, echte Testdaten): ``["shop"="farm"]`` allein ist
günstig (Median ~0,2 s, <= 6 KB Antwort) und findet alle in OSM
vorhandenen Hofläden; der Filter ``leicht`` brachte keine zusätzlichen
Treffer bei ~6-facher Laufzeit. ``erweitert`` ist **nicht gemessen** und
daher nur auf ausdrücklichen Wunsch (``erweitert=True``) aktiv.
"""

from __future__ import annotations

from dataclasses import dataclass

# Namensbestandteile, die auf Hofstellen hindeuten (nur für ``erweitert``).
_HOFNAMEN_REGEX = "hof|laden|ferme|bauer|bure|käse|milch"
_AUTOMATEN_REGEX = "milk|eggs|potatoes|honey|cheese|vegetables|fruit"


@dataclass(frozen=True)
class Profil:
    """Ein Suchprofil: Name plus Overpass-Filter (``nwr(around...)<filter>``)."""

    name: str
    kern: tuple[str, ...]
    erweitert: tuple[str, ...] = ()

    def filter(self, erweitert: bool) -> tuple[str, ...]:
        """Kernfilter; mit ``erweitert`` zusätzlich die ungemessenen Varianten."""
        if not erweitert:
            return self.kern
        return tuple(dict.fromkeys(self.kern + self.erweitert))


FARMSHOP = Profil(
    name="farmshop",
    kern=('["shop"="farm"]',),
    erweitert=(
        '["craft"="agricultural"]',
        '["amenity"="marketplace"]',
        '["farm_shop"]',
        '["produce"]',
        f'["amenity"="vending_machine"]["vending"~"{_AUTOMATEN_REGEX}",i]',
        f'["landuse"="farmyard"]["name"~"{_HOFNAMEN_REGEX}",i]',
        f'["building"="farm"]["name"~"{_HOFNAMEN_REGEX}",i]',
    ),
)

PROFILE: dict[str, Profil] = {FARMSHOP.name: FARMSHOP}
