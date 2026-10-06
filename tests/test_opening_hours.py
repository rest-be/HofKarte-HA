"""Tests für ``opening_hours.py`` – die Öffnungszeiten-Berechnung.

Deckt mindestens folgende Fälle ab: offen innerhalb
eines Intervalls, geschlossen vor Öffnung, geschlossen nach Schliessung,
zwei Intervalle am selben Tag, Mitternachtsüberschreitung, Sonderöffnung,
Sonder-Schliessung, Wochenwechsel sowie ein Zeitzonen-/DST-Grenzfall.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from custom_components.hofkarte.models import Hofladen, Oeffnungszeit, Sonderoeffnungszeit
from custom_components.hofkarte.opening_hours import (
    get_next_closing,
    get_next_opening,
    is_open,
)

_UTC = timezone.utc
_ZUERICH = ZoneInfo("Europe/Zurich")


def _hofladen(**kwargs) -> Hofladen:
    return Hofladen(id="hof-1", name="Hofladen Eins", **kwargs)


def _dt(year, month, day, hour, minute, tzinfo=_UTC) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=tzinfo)


# ---------------------------------------------------------------------------
# Keine Öffnungsdaten hinterlegt
# ---------------------------------------------------------------------------


def test_keine_oeffnungsdaten_ergibt_unbekannt() -> None:
    """Ohne jegliche Öffnungszeiten ist der Status unbekannt, nicht 'geschlossen'."""
    hofladen = _hofladen()
    now = _dt(2026, 1, 5, 12, 0)  # Montag

    assert is_open(hofladen, now) is None
    assert get_next_opening(hofladen, now) is None
    assert get_next_closing(hofladen, now) is None


# ---------------------------------------------------------------------------
# Offen innerhalb eines Intervalls
# ---------------------------------------------------------------------------


def test_offen_innerhalb_eines_intervalls() -> None:
    """Innerhalb eines Intervalls muss der Status 'offen' sein."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        )
    )
    now = _dt(2026, 1, 5, 10, 0)  # Montag, 10:00 – innerhalb 08:00-12:00

    assert is_open(hofladen, now) is True
    assert get_next_closing(hofladen, now) == _dt(2026, 1, 5, 12, 0)
    # Nächste Öffnung ist NICHT die laufende, sondern die kommende Woche.
    assert get_next_opening(hofladen, now) == _dt(2026, 1, 12, 8, 0)


# ---------------------------------------------------------------------------
# Geschlossen vor Öffnung
# ---------------------------------------------------------------------------


def test_geschlossen_vor_oeffnung() -> None:
    """Vor Beginn des Intervalls muss der Status 'geschlossen' sein."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        )
    )
    now = _dt(2026, 1, 5, 7, 0)  # Montag, 07:00 – vor Öffnung

    assert is_open(hofladen, now) is False
    assert get_next_opening(hofladen, now) == _dt(2026, 1, 5, 8, 0)
    assert get_next_closing(hofladen, now) == _dt(2026, 1, 5, 12, 0)


# ---------------------------------------------------------------------------
# Geschlossen nach Schliessung
# ---------------------------------------------------------------------------


def test_geschlossen_nach_schliessung() -> None:
    """Nach Ende des Intervalls muss der Status 'geschlossen' sein, die
    nächste Öffnung liegt erst wieder in der Folgewoche."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        )
    )
    now = _dt(2026, 1, 5, 13, 0)  # Montag, 13:00 – nach Schliessung

    assert is_open(hofladen, now) is False
    assert get_next_opening(hofladen, now) == _dt(2026, 1, 12, 8, 0)
    assert get_next_closing(hofladen, now) == _dt(2026, 1, 12, 12, 0)


# ---------------------------------------------------------------------------
# Zwei Intervalle am selben Tag
# ---------------------------------------------------------------------------


def test_zwei_intervalle_am_selben_tag() -> None:
    """Zwischen zwei Tagesintervallen muss korrekt 'geschlossen' erkannt und
    das jeweils nächstgelegene Intervall gefunden werden."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
            Oeffnungszeit(wochentag=1, beginn=time(14, 0), ende=time(18, 0)),
        )
    )

    vormittag = _dt(2026, 1, 5, 10, 0)
    assert is_open(hofladen, vormittag) is True
    assert get_next_closing(hofladen, vormittag) == _dt(2026, 1, 5, 12, 0)
    assert get_next_opening(hofladen, vormittag) == _dt(2026, 1, 5, 14, 0)

    mittagspause = _dt(2026, 1, 5, 13, 0)
    assert is_open(hofladen, mittagspause) is False
    assert get_next_opening(hofladen, mittagspause) == _dt(2026, 1, 5, 14, 0)
    assert get_next_closing(hofladen, mittagspause) == _dt(2026, 1, 5, 18, 0)

    nachmittag = _dt(2026, 1, 5, 16, 0)
    assert is_open(hofladen, nachmittag) is True
    assert get_next_closing(hofladen, nachmittag) == _dt(2026, 1, 5, 18, 0)


# ---------------------------------------------------------------------------
# Mitternachtsüberschreitung
# ---------------------------------------------------------------------------


def test_mitternachtsueberschreitung_offen_vor_mitternacht() -> None:
    """Ein Intervall 22:00-02:00 muss vor Mitternacht als offen erkannt werden."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=5, beginn=time(22, 0), ende=time(2, 0)),
        )
    )
    freitag_abend = _dt(2026, 1, 2, 23, 0)  # Freitag, 23:00

    assert is_open(hofladen, freitag_abend) is True
    assert get_next_closing(hofladen, freitag_abend) == _dt(2026, 1, 3, 2, 0)


def test_mitternachtsueberschreitung_offen_nach_mitternacht() -> None:
    """Dasselbe Intervall muss auch nach Mitternacht (Folgetag) noch als
    offen erkannt werden."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=5, beginn=time(22, 0), ende=time(2, 0)),
        )
    )
    samstag_frueh = _dt(2026, 1, 3, 1, 0)  # Samstag, 01:00

    assert is_open(hofladen, samstag_frueh) is True
    assert get_next_closing(hofladen, samstag_frueh) == _dt(2026, 1, 3, 2, 0)


def test_mitternachtsueberschreitung_geschlossen_nach_ende() -> None:
    """Nach 02:00 (Ende des Mitternachtsintervalls) muss geschlossen sein."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=5, beginn=time(22, 0), ende=time(2, 0)),
        )
    )
    samstag_morgen = _dt(2026, 1, 3, 3, 0)  # Samstag, 03:00

    assert is_open(hofladen, samstag_morgen) is False


# ---------------------------------------------------------------------------
# Sonderöffnung (überschreibt reguläre Zeiten)
# ---------------------------------------------------------------------------


def test_sonderoeffnung_ueberschreibt_normalerweise_geschlossenen_tag() -> None:
    """Ein Tag ohne reguläre Öffnungszeiten kann durch eine
    Sonderöffnungszeit trotzdem geöffnet sein."""
    hofladen = _hofladen(
        oeffnungszeiten=(),  # nie regulär geöffnet
        sonderoeffnungszeiten=(
            Sonderoeffnungszeit(
                datum_von=datetime(2026, 1, 6).date(),
                datum_bis=datetime(2026, 1, 6).date(),
                geschlossen=False,
                beginn=time(10, 0),
                ende=time(14, 0),
            ),
        ),
    )
    now = _dt(2026, 1, 6, 11, 0)  # Dienstag, innerhalb der Sonderöffnung

    assert is_open(hofladen, now) is True
    assert get_next_closing(hofladen, now) == _dt(2026, 1, 6, 14, 0)


# ---------------------------------------------------------------------------
# Sonder-Schliessung (überschreibt reguläre Zeiten)
# ---------------------------------------------------------------------------


def test_sonderschliessung_ueberschreibt_regulaere_oeffnungszeit() -> None:
    """Eine Sonder-Schliessung muss reguläre Öffnungszeiten am selben Tag
    ausser Kraft setzen (z. B. Feiertag)."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
        sonderoeffnungszeiten=(
            Sonderoeffnungszeit(
                datum_von=datetime(2026, 1, 5).date(),
                datum_bis=datetime(2026, 1, 5).date(),
                geschlossen=True,
            ),
        ),
    )
    now = _dt(2026, 1, 5, 10, 0)  # Montag, 10:00 – regulär wäre offen

    assert is_open(hofladen, now) is False
    # Nächste Öffnung erst wieder die Folgewoche (Montag ohne Sonderregel).
    assert get_next_opening(hofladen, now) == _dt(2026, 1, 12, 8, 0)


def test_sonderschliessung_ueber_datumsbereich() -> None:
    """Eine mehrtägige Sonder-Schliessung (z. B. Betriebsferien) muss über
    den gesamten Zeitraum wirken."""
    hofladen = _hofladen(
        oeffnungszeiten=tuple(
            Oeffnungszeit(wochentag=wt, beginn=time(8, 0), ende=time(12, 0))
            for wt in range(1, 8)
        ),
        sonderoeffnungszeiten=(
            Sonderoeffnungszeit(
                datum_von=datetime(2026, 1, 5).date(),
                datum_bis=datetime(2026, 1, 7).date(),
                geschlossen=True,
            ),
        ),
    )

    assert is_open(hofladen, _dt(2026, 1, 5, 10, 0)) is False
    assert is_open(hofladen, _dt(2026, 1, 6, 10, 0)) is False
    assert is_open(hofladen, _dt(2026, 1, 7, 10, 0)) is False
    # Am Tag danach gilt wieder die reguläre Öffnungszeit.
    assert is_open(hofladen, _dt(2026, 1, 8, 10, 0)) is True


# ---------------------------------------------------------------------------
# Wochenwechsel
# ---------------------------------------------------------------------------


def test_wochenwechsel_sonntag_zu_montag() -> None:
    """Ein Sonntagabend-Intervall, das über Mitternacht in den neuen Montag
    hineinreicht, darf nicht mit dem regulären Montagsintervall kollidieren
    und muss korrekt dem Sonntag zugeordnet bleiben."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=7, beginn=time(22, 0), ende=time(1, 0)),
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        )
    )
    # Sonntag, 4. Januar 2026, 23:00 -> Teil des Sonntagabend-Intervalls.
    sonntag_abend = _dt(2026, 1, 4, 23, 0)
    assert is_open(hofladen, sonntag_abend) is True
    assert get_next_closing(hofladen, sonntag_abend) == _dt(2026, 1, 5, 1, 0)

    # Montag, 5. Januar 2026, 00:30 -> weiterhin das Sonntagabend-Intervall.
    montag_frueh = _dt(2026, 1, 5, 0, 30)
    assert is_open(hofladen, montag_frueh) is True
    assert get_next_closing(hofladen, montag_frueh) == _dt(2026, 1, 5, 1, 0)

    # Montag, 5. Januar 2026, 07:00 -> geschlossen zwischen den Intervallen.
    montag_vormittag_vor_oeffnung = _dt(2026, 1, 5, 7, 0)
    assert is_open(hofladen, montag_vormittag_vor_oeffnung) is False
    assert get_next_opening(
        hofladen, montag_vormittag_vor_oeffnung
    ) == _dt(2026, 1, 5, 8, 0)

    # Montag, 5. Januar 2026, 10:00 -> das reguläre Montagsintervall.
    montag_vormittag = _dt(2026, 1, 5, 10, 0)
    assert is_open(hofladen, montag_vormittag) is True


# ---------------------------------------------------------------------------
# Zeitzone / Sommerzeit-Grenzfall
# ---------------------------------------------------------------------------


def test_zeitzone_wird_korrekt_uebernommen_kein_utc_fallback() -> None:
    """Die Berechnung muss in der Zeitzone von ``now`` erfolgen, nicht in UTC."""
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        )
    )
    # 09:00 Lokalzeit Zürich entspricht im Winter 08:00 UTC.
    now_zuerich = datetime(2026, 1, 5, 9, 0, tzinfo=_ZUERICH)

    assert is_open(hofladen, now_zuerich) is True
    naechste_schliessung = get_next_closing(hofladen, now_zuerich)
    assert naechste_schliessung is not None
    assert naechste_schliessung.tzinfo is not None
    assert naechste_schliessung.utcoffset() == now_zuerich.utcoffset()


def test_sommerzeitumstellung_fruehjahr_keine_absturz_und_plausibel() -> None:
    """An der Sommerzeitumstellung (Europe/Zurich, letzter Sonntag im März)
    darf die Berechnung nicht abstürzen und muss ein plausibles Ergebnis
    liefern, auch wenn ein Intervall die Umstellung überschreitet."""
    # 29. März 2026 ist der Umstellungstag (Sonntag) in Europe/Zurich;
    # Uhren springen von 02:00 auf 03:00.
    umstellungstag = datetime(2026, 3, 29).date()
    hofladen = _hofladen(
        oeffnungszeiten=(
            Oeffnungszeit(
                wochentag=umstellungstag.isoweekday(),
                beginn=time(1, 0),
                ende=time(4, 0),
            ),
        )
    )
    now = datetime(2026, 3, 29, 1, 30, tzinfo=_ZUERICH)

    # Darf nicht auslösen und muss ein eindeutiges True/False liefern.
    ergebnis = is_open(hofladen, now)
    assert ergebnis in (True, False)

    naechste_schliessung = get_next_closing(hofladen, now)
    assert naechste_schliessung is None or naechste_schliessung.tzinfo is not None
