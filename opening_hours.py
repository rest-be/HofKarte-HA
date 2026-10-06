"""Berechnung des Öffnungsstatus von Hofläden.

Dies ist die alleinig vorgesehene Stelle für die
Öffnungszeiten-Berechnungslogik (Grundsatz: „Keine neue
Berechnungslogik außerhalb des dafür vorgesehenen Moduls“). Sensoren und
der Binary Sensor rufen ausschliesslich die Funktionen dieses Moduls auf
und enthalten selbst keine Berechnungslogik.

## Funktionsweise

Statt Wochentage modular zu vergleichen ("ist heute Montag?"), werden für
ein Zeitfenster rund um ``now`` (ein Tag zurück, zwei Wochen voraus)
konkrete, zeitzonenbewusste Datum-Uhrzeit-Intervalle erzeugt. Das
vermeidet Sonderfälle bei Wochenwechseln und macht Mitternachts- sowie
Wochenüberschreitungen zu einem Spezialfall der allgemeinen Logik statt
zu eigenem Code.

Für jedes Datum im Fenster gilt:

- Existiert eine Sonderöffnungszeit, deren Datumsbereich das Datum
  abdeckt, überschreibt sie die regulären Öffnungszeiten für dieses
  Datum vollständig (auch wenn sie "geschlossen" bedeutet).
- Andernfalls gelten die regulären wöchentlichen Öffnungszeiten
  (``Hofladen.oeffnungszeiten``) für den entsprechenden Wochentag.

Ein Intervall, dessen Ende nicht nach dem Beginn liegt (``ende < beginn``,
von ``parsing.py`` als gültig zugelassen), überschreitet die Mitternacht:
Das Ende wird auf den Folgetag gelegt.

## Zeitzone / keine naive Datetime-Arithmetik

``now`` muss zeitzonenbewusst sein (z. B. ``homeassistant.util.dt.now()``,
das die konfigurierte Zeitzone des Home-Assistant-Systems liefert).
Konkrete Intervalle werden über ``datetime.combine(datum, uhrzeit,
tzinfo=now.tzinfo)`` gebildet statt über Addition von ``timedelta`` auf
Uhrzeiten. Das lässt Python (bei einer echten ``ZoneInfo``-Zeitzone) für
jedes Datum den korrekten UTC-Offset auflösen, inklusive
Sommer-/Winterzeit-Umstellungen, statt Stunden naiv zu addieren.

## Bekannte Grenzen

Bei Zeiten, die exakt in eine Sommerzeit-Umstellungslücke fallen (z. B.
eine Öffnungszeit, die um 02:30 beginnt, während die Uhr in dieser Nacht
von 02:00 auf 03:00 vorgestellt wird) oder in den doppelt vorkommenden
Bereich beim Zurückstellen fallen, wird die von Python/``zoneinfo``
standardmässig gewählte Auflösung (erstes Vorkommen, ``fold=0``)
verwendet. Eine explizite Disambiguierung für diese seltenen Grenzfälle
ist bewusst nicht umgesetzt (siehe README, „Bekannte Einschränkungen“).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo as TzInfo

from .models import Hofladen, Sonderoeffnungszeit

# Suchfenster für die Intervall-Generierung: ein Tag zurück (damit ein
# gestern begonnenes, die Mitternacht überschreitendes Intervall erfasst
# wird) und zwei Wochen voraus (deckt wöchentliche Muster inklusive
# Wochenwechsel sowie die meisten Sonderöffnungszeiträume ab).
_DAYS_BACK = 1
_DAYS_FORWARD = 14


def _hat_keine_oeffnungsdaten(hofladen: Hofladen) -> bool:
    """Ob für den Hofladen überhaupt keine Öffnungszeiten hinterlegt sind."""
    return not hofladen.oeffnungszeiten and not hofladen.sonderoeffnungszeiten


def _finde_sonderoeffnungszeit(
    hofladen: Hofladen, datum: date
) -> Sonderoeffnungszeit | None:
    """Erste zum Datum passende Sonderöffnungszeit, falls vorhanden.

    Überlappen sich mehrere Sonderöffnungszeiten für dasselbe Datum (vom
    Datenmodell nicht ausgeschlossen), gewinnt die zuerst definierte.
    """
    for sonder in hofladen.sonderoeffnungszeiten:
        if sonder.datum_von <= datum <= sonder.datum_bis:
            return sonder
    return None


def _baue_intervall(
    datum: date, beginn: time, ende: time, tzinfo: TzInfo | None
) -> tuple[datetime, datetime]:
    """Ein konkretes, zeitzonenbewusstes Intervall für ein Datum bilden.

    ``ende <= beginn`` bedeutet Mitternachtsüberschreitung: Das Ende liegt
    dann am Folgetag (siehe ``parsing.py``: ``ende == beginn`` ist bereits
    dort ausgeschlossen, hier bleibt nur ``ende < beginn`` möglich).
    """
    start = datetime.combine(datum, beginn, tzinfo=tzinfo)
    if ende <= beginn:
        end = datetime.combine(datum + timedelta(days=1), ende, tzinfo=tzinfo)
    else:
        end = datetime.combine(datum, ende, tzinfo=tzinfo)
    return (start, end)


def _intervalle_fuer_datum(
    hofladen: Hofladen, datum: date, tzinfo: TzInfo | None
) -> list[tuple[datetime, datetime]]:
    """Effektive Öffnungsintervalle für ein einzelnes Datum.

    Sonderöffnungszeiten überschreiben die regulären Öffnungszeiten
    vollständig (siehe ``models.Sonderoeffnungszeit``).
    """
    sonder = _finde_sonderoeffnungszeit(hofladen, datum)
    if sonder is not None:
        if sonder.geschlossen:
            return []
        # Validiert durch parsing.py: bei geschlossen=False sind beginn
        # und ende immer gesetzt.
        assert sonder.beginn is not None
        assert sonder.ende is not None
        return [_baue_intervall(datum, sonder.beginn, sonder.ende, tzinfo)]

    wochentag = datum.isoweekday()  # 1 = Montag ... 7 = Sonntag
    return [
        _baue_intervall(datum, oeffnungszeit.beginn, oeffnungszeit.ende, tzinfo)
        for oeffnungszeit in hofladen.oeffnungszeiten
        if oeffnungszeit.wochentag == wochentag
    ]


def _alle_intervalle(
    hofladen: Hofladen, now: datetime
) -> list[tuple[datetime, datetime]]:
    """Alle Öffnungsintervalle im Suchfenster rund um ``now``, sortiert."""
    if now.tzinfo is None:
        raise ValueError(
            "'now' muss zeitzonenbewusst sein (z. B. homeassistant.util.dt.now())."
        )

    start_datum = now.date() - timedelta(days=_DAYS_BACK)
    intervalle: list[tuple[datetime, datetime]] = []
    for offset in range(_DAYS_BACK + _DAYS_FORWARD + 1):
        datum = start_datum + timedelta(days=offset)
        intervalle.extend(_intervalle_fuer_datum(hofladen, datum, now.tzinfo))

    intervalle.sort(key=lambda intervall: intervall[0])
    return intervalle


def is_open(hofladen: Hofladen, now: datetime) -> bool | None:
    """Ob der Hofladen zum Zeitpunkt ``now`` geöffnet ist.

    Liefert ``None`` (Zustand „unbekannt“), wenn für den Hofladen
    überhaupt keine Öffnungszeiten hinterlegt sind – es wird dann
    bewusst nicht "geschlossen" behauptet, ohne dafür Daten zu haben.
    """
    if _hat_keine_oeffnungsdaten(hofladen):
        return None

    return any(
        start <= now < ende for start, ende in _alle_intervalle(hofladen, now)
    )


def get_next_opening(hofladen: Hofladen, now: datetime) -> datetime | None:
    """Zeitpunkt der nächsten Öffnung nach ``now``.

    Ist der Hofladen aktuell geöffnet, ist dies der Beginn der
    darauffolgenden Öffnungsphase (nicht die laufende). Liefert ``None``,
    wenn keine Öffnungszeiten hinterlegt sind oder im Suchfenster keine
    künftige Öffnung gefunden wird.
    """
    if _hat_keine_oeffnungsdaten(hofladen):
        return None

    kuenftige_beginne = [
        start for start, _ende in _alle_intervalle(hofladen, now) if start > now
    ]
    return min(kuenftige_beginne) if kuenftige_beginne else None


def get_next_closing(hofladen: Hofladen, now: datetime) -> datetime | None:
    """Zeitpunkt der nächsten Schliessung nach ``now``.

    Ist der Hofladen aktuell geöffnet, ist dies das Ende der laufenden
    Öffnungsphase. Ist er aktuell geschlossen, ist es das Ende der
    nächsten künftigen Öffnungsphase (also: wann schliesst er, nachdem er
    als Nächstes öffnet). Liefert ``None``, wenn keine Öffnungszeiten
    hinterlegt sind oder im Suchfenster keine relevante Phase gefunden
    wird.
    """
    if _hat_keine_oeffnungsdaten(hofladen):
        return None

    intervalle = _alle_intervalle(hofladen, now)

    laufendes_ende = next(
        (ende for start, ende in intervalle if start <= now < ende), None
    )
    if laufendes_ende is not None:
        return laufendes_ende

    kuenftige = sorted(
        (intervall for intervall in intervalle if intervall[0] > now),
        key=lambda intervall: intervall[0],
    )
    return kuenftige[0][1] if kuenftige else None


def naechster_statuswechsel(hofladen: Hofladen, now: datetime) -> datetime | None:
    """Frühester Zeitpunkt nach ``now``, ab dem sich ein zeitabhängiger
    Zustand des Hofladens ändern kann (Befund F6).

    Reine, Home-Assistant-freie Planungsfunktion für die zeitgenaue
    Aktualisierung der Entities „Geöffnet“, „Nächste Öffnung“ und
    „Nächste Schliessung“: das Minimum aus

    - dem nächsten Beginn **und** dem nächsten Ende eines Öffnungsintervalls
      (jeweils strikt nach ``now``) und
    - dem nächsten lokalen Mitternacht - dann verschiebt sich das
      Suchfenster (Sonderöffnungszeiten, wöchentliche Muster), sodass sich
      ``get_next_opening``/``get_next_closing`` ändern können, ohne dass ein
      Intervall begonnen oder geendet hat.

    Ohne hinterlegte Öffnungszeiten ist der Zustand dauerhaft „unbekannt“;
    es gibt dann nichts zu planen (``None``). Die Intervalle stammen aus
    :func:`_alle_intervalle` - die zeitzonenbewusste Logik inklusive
    Sommer-/Winterzeit wird nicht dupliziert; auch die Mitternacht wird über
    ``datetime.combine(..., tzinfo=now.tzinfo)`` gebildet, nicht per
    Addition von 24 Stunden.
    """
    if _hat_keine_oeffnungsdaten(hofladen):
        return None

    kandidaten = [
        grenze
        for intervall in _alle_intervalle(hofladen, now)
        for grenze in intervall
        if grenze > now
    ]
    mitternacht = datetime.combine(
        now.date() + timedelta(days=1), time.min, tzinfo=now.tzinfo
    )
    kandidaten.append(mitternacht)
    return min(kandidaten)
