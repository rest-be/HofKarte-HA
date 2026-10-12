"""Tests für ``discovery.scoring`` - Fälle aus der echten Messung (Phase 0)."""

from __future__ import annotations

import pytest

from custom_components.hofkarte.discovery import overpass
from custom_components.hofkarte.discovery.scoring import (
    Anfrage,
    berechne_score,
    bewerte,
    distanz_signal,
    konfidenz,
)

LAT, LON = 46.9480, 7.4474
_M = 1 / 111_195  # Grad je Meter (Breitengrad)


def _k(id_: int, dist: float, name: str | None = None, **tags: str) -> overpass.Kandidat:
    t = {"shop": "farm", **tags}
    if name:
        t["name"] = name
    el = {"type": "node", "id": id_, "lat": LAT + dist * _M, "lon": LON, "tags": t}
    return overpass.parse_kandidaten([el], LAT, LON)[0]


def test_distanzsignal_verlauf() -> None:
    assert distanz_signal(0) == distanz_signal(25) == 1.0
    assert distanz_signal(100) > distanz_signal(500) > distanz_signal(2000) > 0
    assert distanz_signal(175) == pytest.approx(0.5)


def test_score_ist_begrenzt_und_monoton() -> None:
    for d in (0, 10, 50, 300, 1500):
        for n in (None, 0.0, 0.5, 1.0):
            for dom in (False, True):
                assert 0.0 <= berechne_score(d, n, dom) <= 1.0
    assert berechne_score(30, 0.5, False) > berechne_score(300, 0.5, False)
    assert berechne_score(300, 0.9, False) > berechne_score(300, 0.1, False)
    assert berechne_score(300, 0.3, True) > berechne_score(300, 0.3, False)


def test_konfidenzstufen() -> None:
    assert (konfidenz(0.9), konfidenz(0.5), konfidenz(0.1)) == ("hoch", "mittel", "niedrig")


def test_nah_aber_anderer_name_ist_hoch() -> None:
    """Befund: 'Boucherie de Campagne' steht in OSM als 'Famille Martin' (8 m)."""
    b = bewerte([_k(1, 8, "Famille Martin")], Anfrage(name="Boucherie de Campagne"))[0]
    assert b.konfidenz == "hoch"


def test_le_petit_buffle_staehli_4m() -> None:
    b = bewerte([_k(1, 4, "Stähli Produits Fermiers SA")], Anfrage(name="Le Petit Buffle"))[0]
    assert b.konfidenz == "hoch"


def test_naeherer_falscher_laden_schlaegt_nicht_den_nahen() -> None:
    ks = [_k(1, 8, "Famille Martin"), _k(2, 886, "Self des Amoureux"), _k(3, 1611, "Ferme de Primapraz")]
    r = bewerte(ks, Anfrage(name="Boucherie de Campagne"))
    assert r[0].kandidat.name == "Famille Martin"


def test_name_hilft_bei_grossem_versatz_gegen_reine_distanz() -> None:
    """Befund (Versatz 1500 m): reine Distanz bevorzugt den falschen Markt."""
    ks = [_k(1, 538, "Wochenmarkt Belp"), _k(2, 1502, "Rohrer")]
    nach_distanz = sorted(ks, key=lambda k: k.entfernung_meter)[0]
    assert nach_distanz.name == "Wochenmarkt Belp"
    assert bewerte(ks, Anfrage(name="Hofladen Rohrer Gemüse"))[0].kandidat.name == "Rohrer"


def test_ohne_name_entscheidet_die_distanz() -> None:
    ks = [_k(1, 400, "Fern"), _k(2, 20, "Nah")]
    r = bewerte(ks, Anfrage())
    assert [b.kandidat.name for b in r] == ["Nah", "Fern"]
    assert all(b.name_signal is None for b in r)


def test_unbenannter_kandidat_wird_nicht_bestraft() -> None:
    unbenannt, benannt = _k(1, 100), _k(2, 100, "Völlig Anders")
    r = {b.kandidat.refs[0]: b for b in bewerte([unbenannt, benannt], Anfrage(name="Hof Müller"))}
    assert r["node/1"].name_signal is None
    assert r["node/1"].score > r["node/2"].score


def test_website_domain_hebt_kandidaten() -> None:
    ks = [_k(1, 200, "A", website="https://www.hof-a.example/"), _k(2, 180, "B", website="https://b.example")]
    r = bewerte(ks, Anfrage(website="http://hof-a.example"))
    assert r[0].kandidat.name == "A" and r[0].domain_gleich and not r[1].domain_gleich


def test_gleichstand_der_naehere_zuerst() -> None:
    r = bewerte([_k(2, 10, "X"), _k(1, 5, "Y")], Anfrage())
    assert [b.kandidat.refs[0] for b in r] == ["node/1", "node/2"]  # beide 1.0 -> nähere zuerst


def test_als_dict_enthaelt_signale() -> None:
    d = bewerte([_k(1, 10, "X")], Anfrage(name="X"))[0].als_dict()
    assert d["score"] == pytest.approx(1.0) and d["konfidenz"] == "hoch"
    assert set(d["signale"]) == {"distanz", "name", "website"}
