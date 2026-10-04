"""Tests für search.py – Suche und Filter über Hofladen-Daten."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from custom_components.hofkarte.models import (
    Angebot,
    Hofladen,
    Oeffnungszeit,
    Zahlungsart,
)
from custom_components.hofkarte.search import find_hoflaeden, find_hoflaeden_in_naehe

_MONTAG = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)  # innerhalb 08-12 Uhr


def _hofladen(**kwargs) -> Hofladen:
    defaults = {"id": "hof", "name": "Hofladen"}
    defaults.update(kwargs)
    return Hofladen(**defaults)


_MUELLER = _hofladen(
    id="hof-mueller",
    name="Hofladen Müller",
    beschreibung="Frisches Gemüse direkt ab Hof.",
    ort="Bern",
    angebote=(Angebot(id="kartoffeln", name="Kartoffeln"),),
    zahlungsarten=(Zahlungsart(id="bar", name="Bargeld"),),
    oeffnungszeiten=(
        Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
    ),
)
_SCHMID = _hofladen(
    id="hof-schmid",
    name="Hofladen Schmid",
    beschreibung="Käse und Milchprodukte.",
    ort="Thun",
    angebote=(Angebot(id="kaese", name="Käse"),),
    zahlungsarten=(Zahlungsart(id="twint", name="TWINT"),),
    oeffnungszeiten=(),  # keine Öffnungszeiten -> is_open liefert None
)

_ALLE = [_MUELLER, _SCHMID]


# ---------------------------------------------------------------------------
# Ohne Filter
# ---------------------------------------------------------------------------


def test_ohne_filter_liefert_alle_hoflaeden() -> None:
    """Ohne gesetzte Kriterien müssen alle übergebenen Hofläden zurückkommen."""
    ergebnis = find_hoflaeden(_ALLE)

    assert ergebnis == _ALLE


def test_leere_eingabe_liefert_leeres_ergebnis() -> None:
    """Eine leere Liste muss ein leeres Ergebnis liefern, kein Fehler."""
    assert find_hoflaeden([]) == []


# ---------------------------------------------------------------------------
# Freitextsuche
# ---------------------------------------------------------------------------


def test_suchbegriff_findet_treffer_im_namen() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="müller")

    assert ergebnis == [_MUELLER]


def test_suchbegriff_findet_treffer_in_beschreibung() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="käse")

    assert ergebnis == [_SCHMID]


def test_suchbegriff_findet_treffer_im_ort() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="thun")

    assert ergebnis == [_SCHMID]


def test_suchbegriff_ist_case_insensitiv() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="MÜLLER")

    assert ergebnis == [_MUELLER]


def test_suchbegriff_ohne_treffer_liefert_leere_liste() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="nicht-vorhanden")

    assert ergebnis == []


def test_suchbegriff_ignoriert_hofladen_ohne_beschreibung() -> None:
    """Ein Hofladen ohne Beschreibung darf beim Durchsuchen nicht zum
    Absturz führen (None-Feld)."""
    hofladen_ohne_beschreibung = _hofladen(id="hof-x", name="Testhof")

    ergebnis = find_hoflaeden([hofladen_ohne_beschreibung], suchbegriff="testhof")

    assert ergebnis == [hofladen_ohne_beschreibung]


# ---------------------------------------------------------------------------
# Filter nach Angebot / Zahlungsart
# ---------------------------------------------------------------------------


def test_filter_nach_angebot_name() -> None:
    assert find_hoflaeden(_ALLE, angebot="Käse") == [_SCHMID]


def test_filter_nach_angebot_case_insensitiv() -> None:
    assert find_hoflaeden(_ALLE, angebot="käse") == [_SCHMID]


def test_filter_nach_zahlungsart() -> None:
    assert find_hoflaeden(_ALLE, zahlungsart="Bargeld") == [_MUELLER]


def test_filter_ist_exakter_abgleich_kein_teilstring() -> None:
    """Filterkriterien (im Unterschied zum Suchbegriff) müssen exakt
    übereinstimmen, kein Teilstring-Treffer."""
    assert find_hoflaeden(_ALLE, angebot="Kart") == []


def test_filter_ohne_treffer_liefert_leere_liste() -> None:
    assert find_hoflaeden(_ALLE, angebot="Honig") == []


# ---------------------------------------------------------------------------
# Kombinierte Filter (logisches UND)
# ---------------------------------------------------------------------------


def test_kombinierte_filter_werden_und_verknuepft() -> None:
    """Beide Kriterien zusammen dürfen nur Hofläden liefern, die beide
    erfüllen."""
    ergebnis = find_hoflaeden(_ALLE, angebot="Kartoffeln", zahlungsart="Bargeld")

    assert ergebnis == [_MUELLER]


def test_kombinierte_filter_ohne_gemeinsamen_treffer() -> None:
    """Erfüllt kein Hofladen alle Kriterien gemeinsam, ist das Ergebnis leer."""
    ergebnis = find_hoflaeden(_ALLE, angebot="Kartoffeln", zahlungsart="TWINT")

    assert ergebnis == []


# ---------------------------------------------------------------------------
# nur_geoeffnet
# ---------------------------------------------------------------------------


def test_nur_geoeffnet_filtert_auf_offene_hoflaeden() -> None:
    """Nur der Hofladen mit passender Öffnungszeit darf zurückkommen."""
    ergebnis = find_hoflaeden(_ALLE, nur_geoeffnet=True, now=_MONTAG)

    assert ergebnis == [_MUELLER]


def test_nur_geoeffnet_schliesst_unbekannten_status_aus() -> None:
    """Ein Hofladen ohne hinterlegte Öffnungszeiten (Status unbekannt) darf
    bei nur_geoeffnet=True nicht als Treffer gelten."""
    ergebnis = find_hoflaeden([_SCHMID], nur_geoeffnet=True, now=_MONTAG)

    assert ergebnis == []


def test_nur_geoeffnet_false_wirkt_nicht_als_filter() -> None:
    """``nur_geoeffnet=False`` bedeutet 'kein Filter', nicht 'nur geschlossene'."""
    ergebnis = find_hoflaeden(_ALLE, nur_geoeffnet=False, now=_MONTAG)

    assert ergebnis == _ALLE


def test_nur_geoeffnet_ohne_now_wirft_fehler() -> None:
    """Ohne 'now' kann der Öffnungsstatus nicht berechnet werden."""
    with pytest.raises(ValueError):
        find_hoflaeden(_ALLE, nur_geoeffnet=True)


# ---------------------------------------------------------------------------
# Reihenfolge / Unveränderlichkeit
# ---------------------------------------------------------------------------


def test_eingabereihenfolge_bleibt_erhalten() -> None:
    ergebnis = find_hoflaeden([_SCHMID, _MUELLER])

    assert ergebnis == [_SCHMID, _MUELLER]


def test_eingabe_wird_nicht_veraendert() -> None:
    eingabe = [_MUELLER, _SCHMID]
    find_hoflaeden(eingabe, angebot="Kartoffeln")

    assert eingabe == [_MUELLER, _SCHMID]


# ---------------------------------------------------------------------------
# find_hoflaeden_in_naehe
# ---------------------------------------------------------------------------

# Bern, Bahnhof
_BERN_LAT, _BERN_LON = 46.9480, 7.4474
# Zürich HB - ca. 95.5 km von Bern entfernt
_ZUERICH_LAT, _ZUERICH_LON = 47.3769, 8.5417

_NAHE_BERN = _hofladen(
    id="hof-nahe-bern", name="Hofladen nahe Bern", latitude=46.95, longitude=7.45
)
_WEIT_WEG = _hofladen(
    id="hof-weit-weg",
    name="Hofladen weit weg",
    latitude=_ZUERICH_LAT,
    longitude=_ZUERICH_LON,
)
_OHNE_KOORDINATEN = _hofladen(id="hof-ohne-koordinaten", name="Ohne Koordinaten")


def test_in_naehe_findet_hofladen_im_radius() -> None:
    treffer = find_hoflaeden_in_naehe(
        [_NAHE_BERN, _WEIT_WEG],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=2000,
    )

    assert [hofladen.id for hofladen, _ in treffer] == ["hof-nahe-bern"]


def test_in_naehe_schliesst_hofladen_ausserhalb_radius_aus() -> None:
    treffer = find_hoflaeden_in_naehe(
        [_WEIT_WEG],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=500,
    )

    assert treffer == []


def test_in_naehe_ignoriert_hoflaeden_ohne_koordinaten() -> None:
    treffer = find_hoflaeden_in_naehe(
        [_OHNE_KOORDINATEN],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=100_000,
    )

    assert treffer == []


def test_in_naehe_sortiert_nach_entfernung_aufsteigend() -> None:
    naeher = _hofladen(id="hof-naeher", latitude=46.95, longitude=7.45)
    weiter = _hofladen(id="hof-weiter", latitude=47.0, longitude=7.5)

    treffer = find_hoflaeden_in_naehe(
        [weiter, naeher],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=100_000,
    )

    assert [hofladen.id for hofladen, _ in treffer] == ["hof-naeher", "hof-weiter"]


def test_in_naehe_liefert_entfernung_in_km() -> None:
    treffer = find_hoflaeden_in_naehe(
        [_WEIT_WEG],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=200_000,
    )

    [(hofladen, entfernung_km)] = treffer
    assert hofladen.id == "hof-weit-weg"
    assert entfernung_km == pytest.approx(95.49, abs=0.1)


def test_in_naehe_nur_geoeffnet_filtert() -> None:
    geoeffnet = _hofladen(
        id="hof-offen",
        latitude=46.95,
        longitude=7.45,
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    geschlossen = _hofladen(
        id="hof-ohne-zeiten", latitude=46.95, longitude=7.45, oeffnungszeiten=()
    )

    treffer = find_hoflaeden_in_naehe(
        [geoeffnet, geschlossen],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=2000,
        nur_geoeffnet=True,
        now=_MONTAG,
    )

    assert [hofladen.id for hofladen, _ in treffer] == ["hof-offen"]


def test_in_naehe_nur_geoeffnet_ohne_now_wirft_fehler() -> None:
    with pytest.raises(ValueError):
        find_hoflaeden_in_naehe(
            [_NAHE_BERN],
            latitude=_BERN_LAT,
            longitude=_BERN_LON,
            radius_meter=2000,
            nur_geoeffnet=True,
        )


def test_in_naehe_negativer_radius_wirft_fehler() -> None:
    with pytest.raises(ValueError):
        find_hoflaeden_in_naehe(
            [_NAHE_BERN],
            latitude=_BERN_LAT,
            longitude=_BERN_LON,
            radius_meter=-1,
        )


def test_in_naehe_min_bewertung_filtert() -> None:
    liebling = _hofladen(
        id="hof-liebling", latitude=46.95, longitude=7.45, bewertung=5
    )
    unbewertet = _hofladen(
        id="hof-unbewertet", latitude=46.95, longitude=7.45, bewertung=0
    )
    mittel = _hofladen(id="hof-mittel", latitude=46.95, longitude=7.45, bewertung=3)

    treffer = find_hoflaeden_in_naehe(
        [liebling, unbewertet, mittel],
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=2000,
        min_bewertung=4,
    )

    assert [hofladen.id for hofladen, _ in treffer] == ["hof-liebling"]


def test_in_naehe_min_bewertung_null_schliesst_nichts_aus() -> None:
    treffer = find_hoflaeden_in_naehe(
        [_NAHE_BERN],  # Standard-Bewertung 0 (siehe models.Hofladen)
        latitude=_BERN_LAT,
        longitude=_BERN_LON,
        radius_meter=2000,
        min_bewertung=0,
    )

    assert [hofladen.id for hofladen, _ in treffer] == ["hof-nahe-bern"]


def test_in_naehe_min_bewertung_ausserhalb_bereich_wirft_fehler() -> None:
    with pytest.raises(ValueError):
        find_hoflaeden_in_naehe(
            [_NAHE_BERN],
            latitude=_BERN_LAT,
            longitude=_BERN_LON,
            radius_meter=2000,
            min_bewertung=6,
        )
