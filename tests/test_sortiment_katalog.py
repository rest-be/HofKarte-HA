"""Tests für den Standardkatalog (sortiment_katalog.py)."""

from __future__ import annotations

from custom_components.hofkarte.parsing import parse_hofladen
from custom_components.hofkarte.sortiment_katalog import (
    slug,
    standard_zahlungsarten_rohdaten,
)


def test_slug_einfache_namen() -> None:
    """Einfache Namen müssen in Kleinbuchstaben mit Bindestrichen überführt werden."""
    assert slug("Bargeld") == "bargeld"
    assert slug("eigener Anbau") == "eigener-anbau"
    assert slug("Ab-Hof-Verkauf") == "ab-hof-verkauf"


def test_slug_ist_deterministisch() -> None:
    """Derselbe Name muss immer dieselbe ID ergeben."""
    assert slug("TWINT") == slug("TWINT")


def test_standard_zahlungsarten_enthalten_erwartete_werte() -> None:
    """Der Katalog muss exakt die vorgegebenen Standard-Zahlungsarten enthalten."""
    rohdaten = standard_zahlungsarten_rohdaten()

    namen = [eintrag["name"] for eintrag in rohdaten]
    assert namen == ["Bargeld", "Debitkarte", "Kreditkarte", "TWINT"]
    # IDs müssen eindeutig sein.
    ids = [eintrag["id"] for eintrag in rohdaten]
    assert len(ids) == len(set(ids))


def test_standard_rohdaten_sind_gueltige_hofladen_eingabe() -> None:
    """Die erzeugten Rohdaten müssen ohne Anpassung von parse_hofladen
    akzeptiert werden (Round-Trip-Gültigkeit)."""
    hofladen = parse_hofladen(
        {
            "id": "hof-1",
            "name": "Hofladen Eins",
            "zahlungsarten": standard_zahlungsarten_rohdaten(),
        }
    )

    assert [z.name for z in hofladen.zahlungsarten] == [
        "Bargeld",
        "Debitkarte",
        "Kreditkarte",
        "TWINT",
    ]
