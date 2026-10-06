"""Tests für die Migration des alten Formats (getrennte 'kategorien'/
'produkte') zu 'angebote' (siehe parsing._migriere_kategorien_und_produkte_zu_angeboten).

Seit der Vereinfachung von "Angebote" auf eine schlichte Namensliste
ohne Gruppierung (siehe CHANGELOG) werden sowohl bestehende Kategorien
als auch bestehende Produkte gleichermassen zu flachen Angebot-
Einträgen (nur id/name) migriert - eine produkt->kategorie-Zuordnung
(``kategorie_ids``) wird dabei nicht mehr ausgewertet, da es keine
Gruppierung mehr gibt.
"""

from __future__ import annotations

from custom_components.hofkarte.parsing import (
    _migriere_kategorien_und_produkte_zu_angeboten,
    parse_hofladen,
)


def test_produkt_wird_zu_flachem_angebot() -> None:
    """Ein Produkt wird unabhängig von etwaigen kategorie_ids zu einem
    schlichten Angebot mit nur id/name."""
    raw = {
        "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert {"id": "kartoffeln", "name": "Kartoffeln"} in angebote


def test_produkt_ohne_kategorie() -> None:
    """Ein Produkt ganz ohne kategorie_ids wird unverändert zu einem
    Angebot, nicht zu einem Fehler führen."""
    raw = {
        "kategorien": [],
        "produkte": [{"id": "honig", "name": "Honig"}],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "honig", "name": "Honig"}]


def test_kategorie_ohne_produkt_wird_ebenfalls_zu_einem_angebot() -> None:
    """Eine Kategorie ohne referenzierendes Produkt darf nicht
    stillschweigend verschwinden - sie wird als eigenständiges,
    schlichtes Angebot erhalten (Kategorien und Produkte werden seit der
    Vereinfachung gleich behandelt)."""
    raw = {
        "kategorien": [{"id": "sonstiges", "name": "Sonstiges"}],
        "produkte": [],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "sonstiges", "name": "Sonstiges"}]


def test_gemischt_kategorien_und_produkte_ergeben_alle_namen() -> None:
    """Realistischer Mischfall: sowohl Kategorien als auch Produkte
    vorhanden - alle Namen müssen als Angebote erhalten bleiben, ohne
    Duplikate zu erzeugen."""
    raw = {
        "kategorien": [
            {"id": "gemuese", "name": "Gemüse"},
            {"id": "sonstiges", "name": "Sonstiges"},
        ],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert {"id": "kartoffeln", "name": "Kartoffeln"} in angebote
    assert {"id": "gemuese", "name": "Gemüse"} in angebote
    assert {"id": "sonstiges", "name": "Sonstiges"} in angebote
    assert len(angebote) == 3


def test_bereits_neues_format_ist_idempotent() -> None:
    """Ein Datensatz, der bereits 'angebote' enthält, darf durch die
    Migration nicht verändert werden - auch nicht, wenn zufällig noch
    alte Schlüssel danebenliegen (angebote hat Vorrang)."""
    raw = {
        "angebote": [{"id": "kartoffeln", "name": "Kartoffeln"}],
        "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "kartoffeln", "name": "Kartoffeln"}]


def test_weder_altes_noch_neues_format_ergibt_leere_liste() -> None:
    assert _migriere_kategorien_und_produkte_zu_angeboten({}) == []


def test_migration_ueber_den_vollen_parse_hofladen_pfad() -> None:
    """End-zu-Ende: Ein kompletter, alter Rohdatensatz muss über
    parse_hofladen() korrekt migriert und validiert werden."""
    raw = {
        "id": "hof-alt",
        "name": "Alter Hofladen",
        "kategorien": [
            {"id": "gemuese", "name": "Gemüse"},
            {"id": "verwaist", "name": "Verwaiste Kategorie"},
        ],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    hofladen = parse_hofladen(raw)

    namen = {angebot.name for angebot in hofladen.angebote}
    assert namen == {"Kartoffeln", "Gemüse", "Verwaiste Kategorie"}


def test_migration_erneutes_einlesen_bereits_migrierter_daten_ist_stabil() -> None:
    """Wird ein bereits migrierter Hofladen (neues Format) erneut
    eingelesen, dürfen keine Duplikate oder Veränderungen entstehen."""
    raw_neu = {
        "id": "hof-neu",
        "name": "Neuer Hofladen",
        "angebote": [{"id": "kartoffeln", "name": "Kartoffeln"}],
    }

    erstes_parsen = parse_hofladen(raw_neu)
    zweites_parsen = parse_hofladen(raw_neu)

    assert erstes_parsen.angebote == zweites_parsen.angebote
    assert len(erstes_parsen.angebote) == 1


def test_altes_gruppen_feld_wird_beim_einlesen_ignoriert() -> None:
    """Ein bereits im 'angebote'-Format gespeichertes, aber noch ein
    'gruppen'-Feld enthaltendes Angebot (aus der Zeit vor der
    Vereinfachung) darf beim Einlesen weder einen Fehler auslösen noch
    das Feld übernehmen - es wird schlicht ignoriert."""
    raw = {
        "id": "hof-mit-gruppen",
        "name": "Hofladen",
        "angebote": [
            {"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]}
        ],
    }

    hofladen = parse_hofladen(raw)

    assert len(hofladen.angebote) == 1
    assert hofladen.angebote[0].name == "Kartoffeln"
    assert not hasattr(hofladen.angebote[0], "gruppen")
