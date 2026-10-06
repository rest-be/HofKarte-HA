"""Sortiment und Eigenschaften als Entity-Attribute.

Angebote und Zahlungsarten eines Hofladens sind fachlich keine Messwerte
und rechtfertigen keine eigenen Entities (Grundsatz: „Keine
künstlichen Messwerte“, „Keine unnötigen Entities“). Stattdessen werden
sie als ``extra_state_attributes`` einer einzigen bestehenden Entity
bereitgestellt (Binary Sensor „Geöffnet“, siehe ``binary_sensor.py``)
statt auf mehrere Entities dupliziert zu werden.

Dieses Modul ist die alleinige Stelle, die diese Rohdaten aus
``models.Hofladen`` in eine einfache, JSON-serialisierbare und stabile
Attributstruktur überführt (nur ``str``/``list``/``dict`` – keine
dataclass-Instanzen direkt als State-Attribut).

„Angebote“ ersetzt die früher getrennten Attribute ``kategorien`` und
``produkte`` (siehe CHANGELOG, Zusammenlegung zu „Angebote“) und ist
bewusst eine schlichte Liste von Namen ohne Gruppierung: ein zuvor
eingeführtes ``gruppen``-Feld je Angebot wurde nach Rückmeldung wieder
entfernt, da der Mehrwert der Gruppierung den zusätzlichen
Pflegeaufwand nicht rechtfertigte (siehe CHANGELOG). Die Fachbereiche
„Verkaufsarten“ und „Merkmale“ wurden aus demselben Grund ersatzlos
entfernt; nur „Zahlungsarten“ bleibt neben „Angebote“ bestehen.
"""

from __future__ import annotations

from typing import Any

from .models import Hofladen


def _sortierte_namen(namen: list[str]) -> list[str]:
    """Für eine stabile, deterministische Darstellung sortieren.

    Verwendet ``str.casefold`` für eine gross-/kleinschreibungsunabhängige
    Sortierung nach Unicode-Codepoint. Dies ist bewusst *keine*
    lokalisierte (z. B. deutsche) alphabetische Kollation – dafür wäre
    eine Locale-Abhängigkeit nötig, die auf unterschiedlichen Systemen
    unterschiedliche und damit nicht deterministische Ergebnisse liefern
    könnte. Effekt: Umlaute (Ä, Ö, Ü) werden nach "Z" einsortiert statt
    wie im deutschen Alphabet neben A/O/U.
    """
    return sorted(namen, key=str.casefold)


def build_sortiment_attributes(hofladen: Hofladen) -> dict[str, Any]:
    """Sortiment und Eigenschaften als stabile Attributstruktur.

    Fehlen einzelne Sammlungen (z. B. keine Zahlungsarten hinterlegt),
    liefert das jeweilige Feld stets eine leere Liste statt eines
    fehlenden Schlüssels oder ``None`` – für eine vorhersagbare,
    stabile Struktur unabhängig vom Vollständigkeitsgrad der Daten.
    """
    return {
        "angebote": _sortierte_namen(
            [angebot.name for angebot in hofladen.angebote]
        ),
        "zahlungsarten": _sortierte_namen(
            [zahlungsart.name for zahlungsart in hofladen.zahlungsarten]
        ),
    }
