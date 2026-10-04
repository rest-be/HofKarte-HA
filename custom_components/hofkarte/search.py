"""Suche und Filter über Hofladen-Daten.

Reine, testbare Fachfunktion ohne Home-Assistant-Abhängigkeit – analog zu
``opening_hours.py``, ``distance.py`` und ``attributes.py``. ``services.py``
kapselt ausschliesslich die Anbindung an Home-Assistant-Actions (Parsing
des Service-Aufrufs, Validierung über das Schema, Aufbau der
Rückgabedaten) und enthält selbst keine Such-/Filterlogik.

Alle Filter werden UND-verknüpft: Ein Hofladen muss jedes gesetzte
Filterkriterium erfüllen, um in das Ergebnis aufgenommen zu werden. Nicht
gesetzte (``None``) Kriterien werden nicht angewendet.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .distance import haversine_distance_km
from .models import Hofladen
from .opening_hours import is_open


def _enthaelt_suchbegriff(hofladen: Hofladen, suchbegriff: str) -> bool:
    """Ob der Suchbegriff (case-insensitive) in Name, Beschreibung oder Ort
    vorkommt."""
    begriff = suchbegriff.casefold()
    freitext_felder = (hofladen.name, hofladen.beschreibung, hofladen.ort)
    return any(
        feld is not None and begriff in feld.casefold() for feld in freitext_felder
    )


def _hat_eintrag_mit_namen(
    eintraege: Iterable[object], gesuchter_name: str
) -> bool:
    """Ob eine der Sammlungen (Angebote, Zahlungsarten) einen Eintrag mit
    exakt diesem Namen (case-insensitive) enthält."""
    gesucht = gesuchter_name.casefold()
    return any(
        getattr(eintrag, "name", "").casefold() == gesucht for eintrag in eintraege
    )


def find_hoflaeden(
    hoflaeden: Iterable[Hofladen],
    *,
    suchbegriff: str | None = None,
    angebot: str | None = None,
    zahlungsart: str | None = None,
    nur_geoeffnet: bool | None = None,
    now: datetime | None = None,
) -> list[Hofladen]:
    """Hofläden anhand der gesetzten Kriterien filtern (logisches UND).

    - ``suchbegriff``: Freitextsuche (case-insensitive Teilstring) über
      Name, Beschreibung und Ort.
    - ``angebot``: exakter, case-insensitiver Namensabgleich gegen die
      Angebote des Hofladens (schlichte Namensliste ohne Gruppierung,
      siehe CHANGELOG).
    - ``zahlungsart``: exakter, case-insensitiver Namensabgleich gegen
      die Zahlungsarten des Hofladens (siehe ``models.Hofladen``).
    - ``nur_geoeffnet``: Wenn ``True``, werden nur aktuell geöffnete
      Hofläden geliefert (nutzt ``opening_hours.is_open`` – keine eigene
      Berechnungslogik, siehe ``opening_hours.py``). Ein Hofladen ohne bekannten
      Öffnungsstatus (``is_open`` liefert ``None``) gilt dabei als nicht
      passend, da nicht bestätigt werden kann, dass er geöffnet ist.
      ``now`` wird dafür benötigt; ist ``nur_geoeffnet`` gesetzt und
      ``now`` fehlt, wird ein ``ValueError`` ausgelöst.

    Gibt eine neue Liste zurück (Eingabereihenfolge bleibt erhalten);
    ``hoflaeden`` selbst wird nicht verändert.
    """
    if nur_geoeffnet is not None and now is None:
        raise ValueError(
            "'now' muss angegeben werden, wenn 'nur_geoeffnet' gesetzt ist."
        )

    ergebnis: list[Hofladen] = []
    for hofladen in hoflaeden:
        if suchbegriff and not _enthaelt_suchbegriff(hofladen, suchbegriff):
            continue
        if angebot and not _hat_eintrag_mit_namen(hofladen.angebote, angebot):
            continue
        if zahlungsart and not _hat_eintrag_mit_namen(
            hofladen.zahlungsarten, zahlungsart
        ):
            continue
        if nur_geoeffnet:
            assert now is not None  # durch die Prüfung oben sichergestellt
            if is_open(hofladen, now) is not True:
                continue

        ergebnis.append(hofladen)

    return ergebnis


def find_hoflaeden_in_naehe(
    hoflaeden: Iterable[Hofladen],
    *,
    latitude: float,
    longitude: float,
    radius_meter: float,
    nur_geoeffnet: bool | None = None,
    min_bewertung: int | None = None,
    now: datetime | None = None,
) -> list[tuple[Hofladen, float]]:
    """Hofläden innerhalb eines Radius um einen beliebigen Standort.

    Im Unterschied zu ``HofKarteEntfernungSensor``/``distance.py`` wird
    hier **nicht** die konfigurierte Home-Assistant-Position verwendet,
    sondern ein beliebiger, mitgegebener Standort (``latitude``/
    ``longitude``) – Grundlage für eine Nähe-Benachrichtigung anhand des
    tatsächlichen, aktuellen Gerätestandorts (z. B. aus einer
    ``person``-/``device_tracker``-Entity), der von der Integration
    selbst bewusst nicht gespeichert oder verfolgt wird (siehe
    ``distance.py``, Grundsatz „Keine Standortdaten persistieren“) –
    der Aufrufer (typischerweise eine Automation) liefert ihn bei jedem
    Aufruf frisch mit.

    Hofläden ohne bekannte Koordinaten werden übersprungen, da für sie
    keine Entfernung berechnet werden kann. ``nur_geoeffnet`` filtert
    analog zu ``find_hoflaeden`` zusätzlich auf aktuell geöffnete
    Hofläden (dafür ist ``now`` erforderlich). ``min_bewertung`` filtert
    zusätzlich auf Hofläden mit einer Bewertung (``Hofladen.bewertung``,
    ein geteilter Wert 0–5, siehe ``models.py``) von mindestens diesem
    Wert – gedacht als einfacher "nur Lieblings-Hofläden"-Filter für
    Benachrichtigungen (es gibt bewusst kein separates Favoriten-Feld,
    siehe Vorgehensplan, um die bestehende, geteilte Bewertung nicht zu
    verdoppeln). Ein Hofladen ohne Bewertung (``bewertung == 0``, der
    Default) erfüllt ein gesetztes ``min_bewertung`` nie, ausser
    ``min_bewertung`` ist selbst ``0``.

    Gibt eine Liste aus Tupeln ``(Hofladen, entfernung_km)`` zurück,
    aufsteigend nach Entfernung sortiert (nächstgelegener Hofladen
    zuerst).
    """
    if nur_geoeffnet is not None and now is None:
        raise ValueError(
            "'now' muss angegeben werden, wenn 'nur_geoeffnet' gesetzt ist."
        )
    if radius_meter < 0:
        raise ValueError("'radius_meter' darf nicht negativ sein.")
    if min_bewertung is not None and not (0 <= min_bewertung <= 5):
        raise ValueError("'min_bewertung' muss zwischen 0 und 5 liegen.")

    radius_km = radius_meter / 1000

    treffer: list[tuple[Hofladen, float]] = []
    for hofladen in hoflaeden:
        if hofladen.latitude is None or hofladen.longitude is None:
            continue

        entfernung_km = haversine_distance_km(
            latitude, longitude, hofladen.latitude, hofladen.longitude
        )
        if entfernung_km > radius_km:
            continue

        if nur_geoeffnet:
            assert now is not None  # durch die Prüfung oben sichergestellt
            if is_open(hofladen, now) is not True:
                continue

        if min_bewertung and hofladen.bewertung < min_bewertung:
            continue

        treffer.append((hofladen, entfernung_km))

    treffer.sort(key=lambda eintrag: eintrag[1])
    return treffer
