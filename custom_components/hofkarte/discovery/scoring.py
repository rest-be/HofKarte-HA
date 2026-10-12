"""Bewertung (Scoring) der Hofladen-Kandidaten.

Reine Funktionen ohne Home Assistant, ohne Netzwerk.

## Befunde aus der Messung (Phase 0), die das Verfahren bestimmen

- Der Name in OSM weicht oft vom Namen ab, den der Betrieb selbst
  verwendet (Inhaber, Marke, Firma: "Boucherie de Campagne" steht in OSM
  als "Famille Martin"). Der Name ist deshalb **nur ein Signal**, kein
  Muss.
- Bei sehr kleinem Abstand (<= ``NAH_METER``) ist es fast immer der
  richtige Laden - auch bei völlig anderem Namen.
- Die Website-Domain ist ein starkes, namensunabhängiges Signal.
- Mit wachsendem Versatz der Koordinate gewinnt der Name an Gewicht,
  weil Entfernung dann weniger aussagt.

## Verfahren

``score`` liegt in 0..1:

1. Entfernungs-Signal ``s_d``: 1.0 bis ``NAH_METER``, danach glatter
   Abfall ``1 / (1 + ((d - NAH) / ABFALL_METER)^2)``.
2. Ohne Namensangabe: ``base = s_d``. Mit Namensangabe:
   ``base = 0.6 * s_d + 0.4 * name`` (``name`` = beste Ähnlichkeit über
   alle Namensvarianten des Kandidaten).
3. Nähe-Untergrenze: ``d <= NAH_METER`` -> ``base >= 0.85``.
4. Website-Domain gleich -> ``base + 0.3`` (höchstens 1.0).
5. Benannt und ohne Namensübereinstimmung weit weg bleibt automatisch
   niedrig; unbenannte Kandidaten werden nicht bestraft (der Name fehlt,
   er widerspricht nicht).

Die Konfidenz ("hoch"/"mittel"/"niedrig") ist eine Einordnung des
Scores für die Oberfläche. Alle Schwellen sind Konstanten und per Test
gegen die Messdaten abgesichert; sie sind ein Startwert, keine Wahrheit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .overpass import Kandidat, _domain
from .text import name_aehnlichkeit

NAH_METER = 25.0
ABFALL_METER = 150.0
GEWICHT_DISTANZ = 0.6
GEWICHT_NAME = 0.4
NAH_UNTERGRENZE = 0.85
DOMAIN_BONUS = 0.3

KONFIDENZ_HOCH = 0.75
KONFIDENZ_MITTEL = 0.45


@dataclass(frozen=True)
class Anfrage:
    """Was über den gesuchten Hofladen bekannt ist (alles ausser der
    Koordinate optional)."""

    name: str | None = None
    website: str | None = None


@dataclass(frozen=True)
class Bewertung:
    kandidat: Kandidat
    score: float
    konfidenz: str
    distanz_signal: float
    name_signal: float | None  # None: kein Name angefragt
    domain_gleich: bool

    def als_dict(self) -> dict:
        d = self.kandidat.als_dict()
        d.update(
            {
                "score": self.score,
                "konfidenz": self.konfidenz,
                "signale": {
                    "distanz": round(self.distanz_signal, 3),
                    "name": None if self.name_signal is None else round(self.name_signal, 3),
                    "website": self.domain_gleich,
                },
            }
        )
        return d


def distanz_signal(distanz_meter: float) -> float:
    if distanz_meter <= NAH_METER:
        return 1.0
    return 1.0 / (1.0 + ((distanz_meter - NAH_METER) / ABFALL_METER) ** 2)


def berechne_score(
    distanz_meter: float, name_sim: float | None, domain_gleich: bool
) -> float:
    """Score 0..1 aus den drei Signalen (siehe Moduldoc)."""
    s_d = distanz_signal(distanz_meter)
    if name_sim is None:
        base = s_d
    else:
        base = GEWICHT_DISTANZ * s_d + GEWICHT_NAME * name_sim
    if distanz_meter <= NAH_METER:
        base = max(base, NAH_UNTERGRENZE)
    if domain_gleich:
        base = base + DOMAIN_BONUS
    return round(min(1.0, base), 4)


def konfidenz(score: float) -> str:
    if score >= KONFIDENZ_HOCH:
        return "hoch"
    if score >= KONFIDENZ_MITTEL:
        return "mittel"
    return "niedrig"


def bewerte(kandidaten: list[Kandidat] | tuple[Kandidat, ...], anfrage: Anfrage) -> list[Bewertung]:
    """Bewertet ``kandidaten`` und sortiert absteigend nach Score (bei
    Gleichstand der Nähere zuerst)."""
    ziel_domain = _domain(anfrage.website)
    ergebnis: list[Bewertung] = []
    for k in kandidaten:
        name_sim: float | None = None
        if anfrage.name and k.alle_namen:  # unbenannt: kein Widerspruch, kein Signal
            name_sim = max(name_aehnlichkeit(anfrage.name, n) for n in k.alle_namen)
        domain_gleich = bool(ziel_domain) and _domain(k.website) == ziel_domain
        s = berechne_score(k.entfernung_meter, name_sim, domain_gleich)
        ergebnis.append(
            Bewertung(
                kandidat=k,
                score=s,
                konfidenz=konfidenz(s),
                distanz_signal=distanz_signal(k.entfernung_meter),
                name_signal=name_sim,
                domain_gleich=domain_gleich,
            )
        )
    return sorted(ergebnis, key=lambda b: (-b.score, b.kandidat.entfernung_meter, b.kandidat.refs))
