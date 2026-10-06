"""Tests für ``attributes.py`` – Sortiment und Eigenschaften als Attribute."""

from __future__ import annotations

from custom_components.hofkarte.attributes import build_sortiment_attributes
from custom_components.hofkarte.models import Angebot, Hofladen, Zahlungsart


def test_vollstaendiges_mapping() -> None:
    """Beide verbleibenden Fachbereiche müssen korrekt in die
    Attributstruktur überführt werden."""
    hofladen = Hofladen(
        id="hof-1",
        name="Hofladen Müller",
        angebote=(
            Angebot(id="kartoffeln", name="Kartoffeln"),
            Angebot(id="milch-1", name="Vollmilch"),
        ),
        zahlungsarten=(
            Zahlungsart(id="bar", name="Bargeld"),
            Zahlungsart(id="twint", name="TWINT"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["angebote"] == ["Kartoffeln", "Vollmilch"]
    assert attribute["zahlungsarten"] == ["Bargeld", "TWINT"]


def test_fehlende_werte_ergeben_leere_listen() -> None:
    """Ohne hinterlegte Daten müssen alle Felder leere Listen sein, nicht None."""
    hofladen = Hofladen(id="hof-2", name="Kleiner Hofladen")

    attribute = build_sortiment_attributes(hofladen)

    assert attribute == {"angebote": [], "zahlungsarten": []}


def test_angebote_werden_alphabetisch_und_case_insensitiv_sortiert() -> None:
    """Die Sortierung muss gross-/kleinschreibungsunabhängig erfolgen."""
    hofladen = Hofladen(
        id="hof-3",
        name="Hofladen",
        angebote=(
            Angebot(id="z", name="Zucchetti"),
            Angebot(id="a", name="Äpfel"),
            Angebot(id="k", name="karotten"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    # Codepoint-basierte Sortierung (str.casefold): "Zucchetti" und
    # "karotten" vor "Äpfel", da 'k'/'z' (ASCII) < 'ä' (U+00E4).
    assert attribute["angebote"] == ["karotten", "Zucchetti", "Äpfel"]
