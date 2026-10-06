"""Tests für das Parsing und die Validierung roher Hofladen-Daten."""

from datetime import date, time

import pytest

from custom_components.hofkarte.parsing import (
    HofladenValidationError,
    parse_hofladen,
)

VOLLSTAENDIGER_ROHDATENSATZ = {
    "id": "hof-1",
    "name": "Hofladen Müller",
    "beschreibung": "Frisches Gemüse direkt ab Hof.",
    "adresse": "Dorfstrasse 12",
    "plz": "3000",
    "ort": "Bern",
    "land": "Schweiz",
    "latitude": 46.948,
    "longitude": 7.4474,
    "oeffnungszeiten": [
        {"wochentag": 1, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 1, "beginn": "14:00", "ende": "18:00"},
    ],
    "sonderoeffnungszeiten": [
        {
            "datum_von": "2026-12-24",
            "datum_bis": "2026-12-26",
            "geschlossen": True,
        },
        {
            "datum_von": "2026-12-31",
            "datum_bis": "2026-12-31",
            "geschlossen": False,
            "beginn": "09:00",
            "ende": "13:00",
        },
    ],
    "produkte": [
        {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]},
    ],
    "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
    "zahlungsarten": [{"id": "bar", "name": "Bar"}],
    "bemerkung": "Nur nach telefonischer Anmeldung.",
    "bilder": [{"url": "https://example.com/hof.jpg", "beschreibung": "Hofeingang"}],
}


def test_parse_vollstaendiger_datensatz() -> None:
    """Ein vollständiger Rohdatensatz muss korrekt in alle Felder überführt
    werden. Verwendet bewusst noch das alte Format (getrennte
    'kategorien'/'produkte') für 'Angebote', um implizit auch die
    Migration alter Daten (siehe test_migration_kategorien_produkte_zu_angebote.py)
    über den regulären Parsing-Pfad abzudecken."""
    hofladen = parse_hofladen(VOLLSTAENDIGER_ROHDATENSATZ)

    assert hofladen.id == "hof-1"
    assert hofladen.name == "Hofladen Müller"
    assert hofladen.beschreibung == "Frisches Gemüse direkt ab Hof."
    assert hofladen.bemerkung == "Nur nach telefonischer Anmeldung."
    assert hofladen.plz == "3000"
    assert hofladen.latitude == pytest.approx(46.948)
    assert hofladen.longitude == pytest.approx(7.4474)

    assert len(hofladen.oeffnungszeiten) == 2
    erste = hofladen.oeffnungszeiten[0]
    assert erste.wochentag == 1
    assert erste.beginn == time(8, 0)
    assert erste.ende == time(12, 0)

    assert len(hofladen.sonderoeffnungszeiten) == 2
    weihnachten = hofladen.sonderoeffnungszeiten[0]
    assert weihnachten.geschlossen is True
    assert weihnachten.datum_von == date(2026, 12, 24)
    assert weihnachten.beginn is None

    silvester = hofladen.sonderoeffnungszeiten[1]
    assert silvester.geschlossen is False
    assert silvester.beginn == time(9, 0)

    # Kategorien und Produkte werden seit der Vereinfachung gleichermassen
    # zu schlichten, flachen Angeboten (siehe test_migration_*.py).
    angebot_namen = {angebot.name for angebot in hofladen.angebote}
    assert angebot_namen == {"Kartoffeln", "Gemüse"}
    assert hofladen.zahlungsarten[0].name == "Bar"
    assert hofladen.bilder[0].url == "https://example.com/hof.jpg"


def test_parse_unvollstaendiger_datensatz_nur_pflichtfelder() -> None:
    """Nur id/name gesetzt: alle optionalen Felder müssen sauber defaulten."""
    hofladen = parse_hofladen({"id": "hof-2", "name": "Kleiner Hofladen"})

    assert hofladen.id == "hof-2"
    assert hofladen.name == "Kleiner Hofladen"
    assert hofladen.beschreibung is None
    assert hofladen.bemerkung is None
    assert hofladen.adresse is None
    assert hofladen.plz is None
    assert hofladen.latitude is None
    assert hofladen.longitude is None
    assert hofladen.oeffnungszeiten == ()
    assert hofladen.sonderoeffnungszeiten == ()
    assert hofladen.angebote == ()
    assert hofladen.bilder == ()


def test_parse_leere_optionale_strings_werden_zu_none() -> None:
    """Leere bzw. nur aus Leerzeichen bestehende optionale Strings -> None."""
    hofladen = parse_hofladen(
        {"id": "hof-3", "name": "Hofladen", "beschreibung": "   "}
    )

    assert hofladen.beschreibung is None


@pytest.mark.parametrize("missing_field", ["id", "name"])
def test_parse_fehlt_pflichtfeld(missing_field: str) -> None:
    """Fehlt id oder name, muss ein HofladenValidationError geworfen werden."""
    raw = {"id": "hof-4", "name": "Hofladen"}
    del raw[missing_field]

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


@pytest.mark.parametrize("leerer_wert", ["", "   "])
def test_parse_leerer_name_ist_ungueltig(leerer_wert: str) -> None:
    """Ein leerer Name (auch nur Leerzeichen) ist kein gültiger Pflichtwert."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-5", "name": leerer_wert})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("longitude", -181),
    ],
)
def test_parse_koordinaten_ausserhalb_gueltiger_bereich(
    field_name: str, value: float
) -> None:
    """Koordinaten ausserhalb der gültigen Wertebereiche müssen abgelehnt werden."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-6", "name": "Hofladen", field_name: value})


def test_parse_koordinate_kein_zahlwert() -> None:
    """Ein nicht-numerischer Wert für Koordinaten ist ungültig."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-7", "name": "Hofladen", "latitude": "nord"})


def test_parse_oeffnungszeit_mitternachtsueberschreitung_ist_gueltig() -> None:
    """Ein Ende vor dem Beginn ist gültig und bedeutet Mitternachtsüberschreitung.

    Regel (siehe opening_hours.py): zuvor wurde
    'ende' vor 'beginn' abgelehnt; jetzt wird dies als Intervall über
    Mitternacht hinweg interpretiert (z. B. 22:00–02:00), siehe
    ``opening_hours.py``.
    """
    raw = {
        "id": "hof-8",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "18:00", "ende": "08:00"}],
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.oeffnungszeiten[0].beginn == time(18, 0)
    assert hofladen.oeffnungszeiten[0].ende == time(8, 0)


def test_parse_oeffnungszeit_ende_gleich_beginn_ist_ungueltig() -> None:
    """Ein Ende gleich dem Beginn ist weiterhin ungültig (keine Dauer definierbar)."""
    raw = {
        "id": "hof-8b",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "08:00", "ende": "08:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_oeffnungszeit_ungueltiger_wochentag() -> None:
    """Ein Wochentag ausserhalb 1-7 muss abgelehnt werden."""
    raw = {
        "id": "hof-9",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 8, "beginn": "08:00", "ende": "12:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_oeffnungszeit_ungueltiges_zeitformat() -> None:
    """Ein nicht ISO-8601-konformes Zeitformat muss abgelehnt werden."""
    raw = {
        "id": "hof-10",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "8 Uhr", "ende": "12:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_bis_vor_von() -> None:
    """'datum_bis' vor 'datum_von' muss abgelehnt werden."""
    raw = {
        "id": "hof-11",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-10",
                "datum_bis": "2026-06-01",
                "geschlossen": True,
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_nicht_geschlossen_ohne_uhrzeiten() -> None:
    """Ist die Sonderöffnungszeit nicht geschlossen, sind Uhrzeiten Pflicht."""
    raw = {
        "id": "hof-12",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-01",
                "datum_bis": "2026-06-01",
                "geschlossen": False,
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_mitternachtsueberschreitung_ist_gueltig() -> None:
    """Auch Sonderöffnungszeiten dürfen die Mitternacht überschreiten (z. B.
    Silvester-Sonderöffnung 20:00–02:00)."""
    raw = {
        "id": "hof-12b",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-12-31",
                "datum_bis": "2026-12-31",
                "geschlossen": False,
                "beginn": "20:00",
                "ende": "02:00",
            }
        ],
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.sonderoeffnungszeiten[0].beginn == time(20, 0)
    assert hofladen.sonderoeffnungszeiten[0].ende == time(2, 0)


def test_parse_sonderoeffnungszeit_ende_gleich_beginn_ist_ungueltig() -> None:
    """Ende gleich Beginn ist auch bei Sonderöffnungszeiten ungültig."""
    raw = {
        "id": "hof-12c",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-01",
                "datum_bis": "2026-06-01",
                "geschlossen": False,
                "beginn": "09:00",
                "ende": "09:00",
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_altes_format_produkt_fehlende_id() -> None:
    """Ein Produkt (altes Format) ohne id muss über die Migration hinweg
    weiterhin abgelehnt werden (Fail-Fast bleibt erhalten)."""
    raw = {
        "id": "hof-13",
        "name": "Hofladen",
        "produkte": [{"name": "Kartoffeln"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_altes_format_kategorie_fehlender_name() -> None:
    """Eine Kategorie (altes Format) ohne name muss über die Migration
    hinweg weiterhin abgelehnt werden."""
    raw = {
        "id": "hof-14",
        "name": "Hofladen",
        "kategorien": [{"id": "gemuese"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_rohdaten_kein_mapping() -> None:
    """Rohdaten, die kein Mapping sind, müssen abgelehnt werden."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen("kein-dict")  # type: ignore[arg-type]


def test_parse_bild_ohne_url() -> None:
    """Ein Bild ohne url muss abgelehnt werden."""
    raw = {
        "id": "hof-15",
        "name": "Hofladen",
        "bilder": [{"beschreibung": "Ohne URL"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_bild_hochgeladen_flag_default_false() -> None:
    """Fehlt 'hochgeladen' in den Rohdaten (bestehende, vor dieser
    Funktion gespeicherte Bilder), muss es als False interpretiert
    werden – unverändertes Verhalten für bestehende Daten."""
    raw = {
        "id": "hof-16",
        "name": "Hofladen",
        "bilder": [{"url": "https://example.com/bild.jpg"}],
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.bilder[0].hochgeladen is False


_EIGENE_ORIGIN = "http://192.168.1.50:8123"
_UPLOAD_ID = "0123456789abcdef0123456789abcdef"


def _bild_raw(url: str, **extra: object) -> dict:
    return {"id": "hof-17", "name": "Hofladen", "bilder": [{"url": url, **extra}]}


def test_parse_bild_hochgeladen_wird_fuer_eigenen_upload_abgeleitet() -> None:
    """F1: Das Flag entsteht serverseitig aus Pfadmuster + Origin der
    eigenen Instanz - unabhängig davon, was die Rohdaten behaupten."""
    url = f"{_EIGENE_ORIGIN}/api/image/serve/{_UPLOAD_ID}/original"

    mit_flag = parse_hofladen(
        _bild_raw(url, hochgeladen=True), eigene_origins=[_EIGENE_ORIGIN]
    )
    ohne_flag = parse_hofladen(_bild_raw(url), eigene_origins=[_EIGENE_ORIGIN])

    assert mit_flag.bilder[0].hochgeladen is True
    assert ohne_flag.bilder[0].hochgeladen is True


def test_parse_bild_hochgeladen_wird_nicht_aus_rohdaten_uebernommen() -> None:
    """F1 (Regression): ``http://192.168.1.20/relay/0?turn=on`` mit
    ``hochgeladen: true`` hätte vor der Korrektur die private-IP-Prüfung
    umgangen (SSRF)."""
    hofladen = parse_hofladen(
        _bild_raw("http://192.168.1.20/relay/0?turn=on", hochgeladen=True),
        eigene_origins=[_EIGENE_ORIGIN],
    )

    assert hofladen.bilder[0].hochgeladen is False


def test_parse_bild_hochgeladen_falscher_host_oder_ohne_origins_ist_false() -> None:
    url = f"http://192.168.1.20/api/image/serve/{_UPLOAD_ID}/original"

    assert parse_hofladen(
        _bild_raw(url, hochgeladen=True), eigene_origins=[_EIGENE_ORIGIN]
    ).bilder[0].hochgeladen is False
    # Ohne bekannte Origins: fail-closed.
    eigene = f"{_EIGENE_ORIGIN}/api/image/serve/{_UPLOAD_ID}/original"
    assert parse_hofladen(_bild_raw(eigene, hochgeladen=True)).bilder[0].hochgeladen is False


def test_parse_bild_hochgeladen_muss_bool_sein() -> None:
    raw = {
        "id": "hof-18",
        "name": "Hofladen",
        "bilder": [{"url": "https://example.com/bild.jpg", "hochgeladen": "ja"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_mobilnummer_und_email() -> None:
    """Mobilnummer und E-Mail müssen wie die übrigen optionalen
    Textfelder eingelesen werden."""
    raw = {
        "id": "hof-19",
        "name": "Hofladen",
        "mobilnummer": "+41 79 123 45 67",
        "email": "info@beispiel.ch",
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.mobilnummer == "+41 79 123 45 67"
    assert hofladen.email == "info@beispiel.ch"


def test_parse_mobilnummer_und_email_default_none() -> None:
    hofladen = parse_hofladen({"id": "hof-20", "name": "Hofladen"})

    assert hofladen.mobilnummer is None
    assert hofladen.email is None


def test_parse_bewertung_default_ist_null() -> None:
    hofladen = parse_hofladen({"id": "hof-21", "name": "Hofladen"})

    assert hofladen.bewertung == 0


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        (0, 0),
        (3, 3),
        (5, 5),
        (5.7, 5),  # float wird auf int begrenzt, nicht gerundet
        (-2, 0),  # unterhalb des Bereichs -> auf 0 begrenzt
        (7, 5),  # oberhalb des Bereichs -> auf 5 begrenzt
    ],
)
def test_parse_bewertung_wird_auf_gueltigen_bereich_begrenzt(
    eingabe: float, erwartet: int
) -> None:
    hofladen = parse_hofladen(
        {"id": "hof-22", "name": "Hofladen", "bewertung": eingabe}
    )

    assert hofladen.bewertung == erwartet


def test_parse_bewertung_muss_zahl_sein() -> None:
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-23", "name": "Hofladen", "bewertung": "viele"})


def test_parse_version_default_ist_eins() -> None:
    hofladen = parse_hofladen({"id": "hof-24", "name": "Hofladen"})

    assert hofladen.version == 1


def test_parse_version_wird_uebernommen() -> None:
    hofladen = parse_hofladen({"id": "hof-25", "name": "Hofladen", "version": 7})

    assert hofladen.version == 7


def test_parse_version_muss_ganze_zahl_sein() -> None:
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-26", "name": "Hofladen", "version": "drei"})


def test_parse_version_muss_ganze_zahl_sein_kein_float() -> None:
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-27", "name": "Hofladen", "version": 1.5})


def test_parse_version_muss_mindestens_eins_sein() -> None:
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-28", "name": "Hofladen", "version": 0})


# ---------------------------------------------------------------------------
# F11 (Code Review 2026.9.2): Längen-/Mengenlimits, ID, E-Mail, Telefon
# ---------------------------------------------------------------------------

from custom_components.hofkarte import const as _const  # noqa: E402


def _basis(**felder: object) -> dict:
    return {"id": "hof-1", "name": "Hofladen", **felder}


@pytest.mark.parametrize(
    ("feld", "maximum"),
    [
        ("name", _const.MAX_LAENGE_NAME),
        ("beschreibung", _const.MAX_LAENGE_TEXT),
        ("bemerkung", _const.MAX_LAENGE_TEXT),
        ("adresse", _const.MAX_LAENGE_ADRESSFELD),
        ("plz", _const.MAX_LAENGE_ADRESSFELD),
        ("ort", _const.MAX_LAENGE_ADRESSFELD),
        ("land", _const.MAX_LAENGE_ADRESSFELD),
        ("website", _const.MAX_LAENGE_URL),
    ],
)
def test_textfeld_grenzwert_gueltig_und_grenzwert_plus_eins_ungueltig(
    feld: str, maximum: int
) -> None:
    parse_hofladen(_basis(**{feld: "x" * maximum}))

    with pytest.raises(HofladenValidationError, match=feld):
        parse_hofladen(_basis(**{feld: "x" * (maximum + 1)}))


def test_email_laenge_grenzwert() -> None:
    lokal = "a" * (_const.MAX_LAENGE_EMAIL - len("@b.ch"))
    parse_hofladen(_basis(email=f"{lokal}@b.ch"))

    with pytest.raises(HofladenValidationError, match="email"):
        parse_hofladen(_basis(email=f"{lokal}a@b.ch"))


def test_telefon_laenge_grenzwert() -> None:
    parse_hofladen(_basis(mobilnummer="1" * _const.MAX_LAENGE_TELEFON))

    with pytest.raises(HofladenValidationError, match="mobilnummer"):
        parse_hofladen(_basis(mobilnummer="1" * (_const.MAX_LAENGE_TELEFON + 1)))


def test_bild_url_laenge_grenzwert() -> None:
    praefix = "https://example.com/"
    ok = praefix + "a" * (_const.MAX_LAENGE_URL - len(praefix))
    parse_hofladen(_basis(bilder=[{"url": ok}]))

    with pytest.raises(HofladenValidationError, match="url"):
        parse_hofladen(_basis(bilder=[{"url": ok + "a"}]))


@pytest.mark.parametrize(
    ("feld", "maximum", "eintrag"),
    [
        ("bilder", _const.MAX_ANZAHL_BILDER, {"url": "https://example.com/a.jpg"}),
        (
            "oeffnungszeiten",
            _const.MAX_ANZAHL_OEFFNUNGSZEITEN,
            {"wochentag": 1, "beginn": "08:00", "ende": "12:00"},
        ),
        (
            "sonderoeffnungszeiten",
            _const.MAX_ANZAHL_SONDEROEFFNUNGSZEITEN,
            {"datum_von": "2026-12-24", "datum_bis": "2026-12-24", "beginn": "08:00", "ende": "12:00"},
        ),
    ],
)
def test_mengenlimit_grenzwert_gueltig_und_plus_eins_ungueltig(
    feld: str, maximum: int, eintrag: dict
) -> None:
    parse_hofladen(_basis(**{feld: [dict(eintrag) for _ in range(maximum)]}))

    with pytest.raises(HofladenValidationError, match=f"'{feld}' darf höchstens"):
        parse_hofladen(_basis(**{feld: [dict(eintrag) for _ in range(maximum + 1)]}))


def test_mengenlimit_angebote_und_zahlungsarten() -> None:
    angebote = [{"id": f"a{i}", "name": f"Angebot {i}"} for i in range(_const.MAX_ANZAHL_ANGEBOTE)]
    parse_hofladen(_basis(angebote=angebote))
    with pytest.raises(HofladenValidationError, match="'angebote' darf höchstens"):
        parse_hofladen(
            _basis(angebote=angebote + [{"id": "zu-viel", "name": "Zu viel"}])
        )

    zahlungsarten = [{"id": f"z{i}", "name": f"Zahlart {i}"} for i in range(_const.MAX_ANZAHL_ZAHLUNGSARTEN)]
    parse_hofladen(_basis(zahlungsarten=zahlungsarten))
    with pytest.raises(HofladenValidationError, match="'zahlungsarten' darf höchstens"):
        parse_hofladen(
            _basis(zahlungsarten=zahlungsarten + [{"id": "zu-viel", "name": "Zu viel"}])
        )


@pytest.mark.parametrize(
    "gueltige_id",
    ["hof-1", "hofladen-0123456789abcdef0123456789abcdef", "A_b-9", "x" * 64],
)
def test_gueltige_ids(gueltige_id: str) -> None:
    assert parse_hofladen({"id": gueltige_id, "name": "H"}).id == gueltige_id


@pytest.mark.parametrize(
    "ungueltige_id",
    ["x" * 65, "mit leerzeichen", 'a"b', "a<b>", "a'b", "a/b", "a.b", "ä", "a\nb"],
)
def test_ungueltige_ids_werden_abgelehnt(ungueltige_id: str) -> None:
    with pytest.raises(HofladenValidationError, match="'id'"):
        parse_hofladen({"id": ungueltige_id, "name": "H"})


@pytest.mark.parametrize(
    "email",
    ["hof@beispiel.ch", "a.b+c@sub.beispiel.ch", "x@y"],
)
def test_gueltige_emails(email: str) -> None:
    assert parse_hofladen(_basis(email=email)).email == email


@pytest.mark.parametrize(
    "email",
    [
        "keine-mail",
        "a@@b.ch",
        "a@b@c.ch",
        "@b.ch",
        "a@",
        "a b@c.ch",
        "a@b.ch?subject=x",
        "a@b.ch&cc=x@y.ch",
        "a%40b.ch@c.ch",
        "a@b.ch#x",
        "a@b.ch,c@d.ch",
        "<a@b.ch>",
    ],
)
def test_ungueltige_emails_werden_abgelehnt(email: str) -> None:
    with pytest.raises(HofladenValidationError, match="email"):
        parse_hofladen(_basis(email=email))


@pytest.mark.parametrize("nummer", ["+41 79 123 45 67", "079/123.45-67", "(044) 123 45 67"])
def test_gueltige_telefonnummern(nummer: str) -> None:
    assert parse_hofladen(_basis(mobilnummer=nummer)).mobilnummer == nummer


@pytest.mark.parametrize("nummer", ["079 123 45 67 ext 5", "tel:0791234567", "079;123", "<script>"])
def test_ungueltige_telefonnummern_werden_abgelehnt(nummer: str) -> None:
    with pytest.raises(HofladenValidationError, match="mobilnummer"):
        parse_hofladen(_basis(mobilnummer=nummer))
