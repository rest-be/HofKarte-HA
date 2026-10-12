"""Offline-Tests für das Phase-0-Messwerkzeug (kein Netz, kein Home Assistant).

Ausführen:  python3 -m pytest tools/discovery_phase0/tests -q -p no:cacheprovider
(Hinweis: aus dem Repo-Wurzelverzeichnis; das Repo-pytest.ini erwartet asyncio-Plugin -> ggf. ``-c /dev/null``.)
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_spike"))

import overpass_messung as om  # noqa: E402
import ollama_extraktion as oe  # noqa: E402


def _elem(typ, id_, name, lat, lon, **tags):
    return {"type": typ, "id": id_, "lat": lat, "lon": lon, "tags": {"name": name, **tags}}


FAKE = {"elements": [
    _elem("node", 1, "Hofladen Müller", 47.1241, 7.1182, shop="farm"),
    _elem("way", 2, "Müller Bauernhof", 47.1300, 7.1300, landuse="farmyard"),
    {"type": "way", "id": 3, "center": {"lat": 47.12, "lon": 7.12}, "tags": {"name": "Biohof Steiner", "shop": "farm"}},
    {"type": "node", "id": 4, "lat": 47.1, "lon": 7.1, "tags": {"shop": "farm"}},  # ohne Namen -> verworfen
]}


# --- reine Funktionen --------------------------------------------------------

def test_normalisiere_umlaute_und_interpunktion():
    assert om.normalisiere("Hofladen Müller!") == "hofladen muller"
    assert om.normalisiere("Straße") == "strasse"


def test_name_aehnlichkeit_reihenfolge_unabhaengig():
    assert om.name_aehnlichkeit("Hofladen Müller", "Müller Hofladen") == pytest.approx(1.0)


def test_name_aehnlichkeit_generische_woerter_werden_toleriert():
    assert om.name_aehnlichkeit("Müller", "Hofladen Müller") >= 0.9
    assert om.name_aehnlichkeit("Hofladen Müller", "Biohof Steiner") < 0.5


def test_haversine_bekannte_distanz():
    # ~111.2 km je Breitengrad
    assert om.haversine_m(46.0, 7.0, 47.0, 7.0) == pytest.approx(111_195, rel=0.01)


def test_verschiebe_ist_konsistent_mit_haversine():
    lat, lon = om.verschiebe(47.0, 7.0, 1500, 137)
    assert om.haversine_m(47.0, 7.0, lat, lon) == pytest.approx(1500, rel=0.02)
    assert om.verschiebe(47.0, 7.0, 0, 90) == (47.0, 7.0)


def test_baue_query_enthaelt_filter_und_begrenzt_radius():
    q = om.baue_query("kern", 47.1, 7.1, 99999)
    assert 'nwr(around:5000,47.100000,7.100000)["shop"="farm"];' in q
    assert q.endswith("out center tags;")
    assert q.count("nwr(") == 1
    assert om.baue_query("erweitert", 47.1, 7.1, 1000).count("nwr(") == len(om.VARIANTEN["erweitert"])


def test_bestand_variante_entspricht_der_integration():
    """Spiegelt die Filter aus osm_info.py (Drift-Wächter)."""
    pfad = Path(__file__).resolve().parents[3] / "custom_components/hofkarte/osm_info.py"
    if not pfad.exists():  # z. B. wenn nur der Ordner discovery_phase0 entpackt wurde
        pytest.skip("osm_info.py nicht vorhanden (Werkzeug ausserhalb des Repos)")
    src = pfad.read_text(encoding="utf-8")
    for f in om.VARIANTEN["bestand"]:
        assert f in src, f


def test_parse_elemente_filtert_unbenannte_und_liest_center():
    k = om.parse_elemente(FAKE)
    assert [x["ref"] for x in k] == ["node/1", "way/2", "way/3"]
    assert k[2]["lat"] == 47.12


def test_bewerte_sortiert_nach_score_und_rang():
    k = om.parse_elemente(FAKE)
    liste = om.bewerte(k, "Hofladen Müller", 47.1234, 7.1234, 5000)
    assert liste[0]["ref"] == "node/1"
    eintrag = {"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182}
    assert om.rang(liste, eintrag) == 1


def test_ist_treffer_mit_osm_ref_ist_exakt():
    k = om.parse_elemente(FAKE)[0]
    assert om.ist_treffer(k, {"name": "egal", "latitude": 0, "longitude": 0, "osm_ref": "node/1"})
    assert not om.ist_treffer(k, {"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182, "osm_ref": "node/9"})


def test_ist_treffer_weit_entfernter_anderer_name_ist_kein_treffer():
    k = om.parse_elemente(FAKE)[2]
    assert not om.ist_treffer(k, {"name": "Hofladen Müller", "latitude": 47.5, "longitude": 7.9})


# --- Cache / Netzwerk (gefälscht) -------------------------------------------

class _Antwort(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_hole_schreibt_cache_und_liest_ihn_wieder(tmp_path):
    aufrufe = []

    def opener(req, timeout):
        aufrufe.append(req)
        return _Antwort(json.dumps(FAKE).encode())

    erste = om.hole("https://x/api", "Q", tmp_path, False, 0, opener=opener, schlafe=lambda s: None)
    zweite = om.hole("https://x/api", "Q", tmp_path, False, 0, opener=opener, schlafe=lambda s: None)
    assert erste["ok"] and not erste["aus_cache"]
    assert zweite["ok"] and zweite["aus_cache"] and len(aufrufe) == 1
    assert aufrufe[0].get_header("User-agent").startswith("HofKarte-Phase0")


def test_hole_offline_ohne_cache_meldet_fehler(tmp_path):
    r = om.hole("https://x", "Q", tmp_path, True, 0)
    assert not r["ok"] and "offline" in r["fehler"]


def test_hole_wiederholt_einmal_bei_429_und_cached_fehler_nicht(tmp_path):
    schlaf = []

    def opener(req, timeout):
        raise urllib.error.HTTPError("u", 429, "Too Many", {}, None)

    r = om.hole("https://x", "Q", tmp_path, False, 3, opener=opener, schlafe=schlaf.append)
    assert not r["ok"] and r["fehler"] == "HTTP 429"
    assert schlaf == [3, 30]
    assert list(tmp_path.glob("*.json")) == []


def test_hole_bricht_bei_400_ohne_wiederholung_ab(tmp_path):
    schlaf = []

    def opener(req, timeout):
        raise urllib.error.HTTPError("u", 400, "Bad", {}, None)

    om.hole("https://x", "Q", tmp_path, False, 0, opener=opener, schlafe=schlaf.append)
    assert len(schlaf) == 1


# --- Messung / Bericht -------------------------------------------------------

def _hole_fn(_q):
    return {"ok": True, "daten": FAKE, "latenz_s": 1.5, "bytes": 2048, "fehler": None, "aus_cache": False}


def test_messe_eintrag_positiv_und_negativ():
    pos = {"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182, "typ": "positiv"}
    neg = {"name": "Bäckerei Dorfplatz", "latitude": 47.1241, "longitude": 7.1182, "typ": "negativ"}
    r = om.messe_eintrag(pos, 0, "erweitert", 5000, 0, _hole_fn)
    assert r["gefunden"] and r["rang_score"] == 1 and r["rang_distanz"] == 1 and r["kandidaten"] == 3
    r2 = om.messe_eintrag(neg, 1, "erweitert", 5000, 1500, _hole_fn)
    assert r2["fehlalarm"] is False


def test_messe_eintrag_negativ_fehlalarm_wenn_aehnlicher_kandidat_nah():
    neg = {"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182, "typ": "negativ"}
    assert om.messe_eintrag(neg, 0, "kern", 2000, 0, _hole_fn)["fehlalarm"] is True


def test_messe_eintrag_bei_fehler_ohne_absturz():
    fehl = lambda q: {"ok": False, "daten": None, "fehler": "HTTP 504", "latenz_s": 9.0, "bytes": 0, "aus_cache": False}
    r = om.messe_eintrag({"name": "A", "latitude": 1, "longitude": 1, "typ": "positiv"}, 0, "kern", 1000, 0, fehl)
    assert not r["ok"] and "gefunden" not in r


def test_zusammenfassung_und_markdown():
    eintraege = [
        {"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182, "typ": "positiv"},
        {"name": "Nicht in OSM", "latitude": 47.2, "longitude": 7.2, "typ": "positiv"},
        {"name": "Bäckerei Dorfplatz", "latitude": 47.15, "longitude": 7.15, "typ": "negativ"},
    ]
    ergebnisse = [om.messe_eintrag(e, i, "erweitert", 5000, 0, _hole_fn) for i, e in enumerate(eintraege)]
    z = om.fasse_zusammen(ergebnisse)[0]
    assert z["n_positiv"] == 2 and z["n_negativ"] == 1
    assert z["recall_gefunden"].startswith("50 %")
    assert z["recall_at1_score"].startswith("50 %")
    assert z["fehlalarm"].startswith("0 %")
    assert z["latenz_median_s"] == 1.5
    md = om.render_markdown([z], ergebnisse)
    assert "| erweitert | 5000 | 0 |" in md and "Nicht in OSM" in md


def test_lade_testset_validiert(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"eintraege": [{"name": "A", "latitude": 1, "longitude": 2}]}))
    assert om.lade_testset(p)[0]["typ"] == "positiv"
    p.write_text(json.dumps([{"name": "A", "latitude": 1}]))
    with pytest.raises(ValueError):
        om.lade_testset(p)
    p.write_text(json.dumps([{"name": "A", "latitude": 1, "longitude": 2, "typ": "x"}]))
    with pytest.raises(ValueError):
        om.lade_testset(p)


def test_beispiel_testset_ist_ladbar():
    om.lade_testset(Path(__file__).resolve().parents[1] / "testset.beispiel.json")


def test_cli_messen_offline_mit_gefuelltem_cache(tmp_path, capsys):
    ts = tmp_path / "t.json"
    ts.write_text(json.dumps([{"name": "Hofladen Müller", "latitude": 47.1241, "longitude": 7.1182}]))
    cache = tmp_path / "cache"
    q = om.baue_query("erweitert", 47.1241, 7.1182, 2000)
    cache.mkdir()
    om.cache_pfad(cache, om.OVERPASS_URL, q).write_text(json.dumps(
        {"ok": True, "daten": FAKE, "latenz_s": 2.0, "bytes": 10, "fehler": None}))
    rc = om.main(["messen", "--testset", str(ts), "--cache", str(cache), "--offline", "--radien", "2000",
                  "--versatz", "0", "--out", str(tmp_path / "erg")])
    assert rc == 0
    erg = json.loads((tmp_path / "erg.json").read_text())
    assert erg["zusammenfassung"][0]["recall_gefunden"].startswith("100 %")
    assert (tmp_path / "erg.md").exists()


def test_cli_lehnt_radius_ueber_maximum_ab(tmp_path):
    ts = tmp_path / "t.json"
    ts.write_text(json.dumps([{"name": "A", "latitude": 1, "longitude": 2}]))
    assert om.main(["messen", "--testset", str(ts), "--cache", str(tmp_path), "--offline",
                    "--radien", "10000", "--out", str(tmp_path / "e")]) == 2


# --- KI-Spike (Fake-Ollama) --------------------------------------------------

BEISPIEL = (Path(__file__).resolve().parents[1] / "ai_spike" / "beispiel_seite.txt").read_text(encoding="utf-8")


def _chat(inhalt: dict):
    return lambda url, nutzlast: {"message": {"content": json.dumps(inhalt)}, "eval_count": 100, "eval_duration": 2_000_000_000}


def test_grounding_unterscheidet_confirmed_und_inferred():
    g = oe.grounding(["Eier", "Hofkäse", "Trüffel"], BEISPIEL)
    assert g == {"Eier": "confirmed", "Hofkäse": "confirmed", "Trüffel": "inferred"}


def test_extrahiere_gutfall_misst_tokens_und_status():
    r = oe.extrahiere(BEISPIEL, "m", "http://x", chat=_chat(
        {"produkte": ["Eier", "Milch"], "zahlungsarten": ["Twint"], "selbstbedienung": True, "oeffnungszeiten_text": None}))
    assert r["json_gueltig"] and r["schema_konform"] and r["tokens_pro_s"] == 50.0
    assert r["status"]["produkte"] == {"Eier": "confirmed", "Milch": "confirmed"}
    assert r["injection_durchgeschlagen"] is False


def test_extrahiere_erkennt_durchgeschlagene_injection_und_markiert_sie_inferred():
    r = oe.extrahiere(BEISPIEL, "m", "http://x", chat=_chat(
        {"produkte": ["Eier", "Bitcoin-Wallet-XYZ"], "zahlungsarten": [], "selbstbedienung": None, "oeffnungszeiten_text": None}))
    assert r["injection_durchgeschlagen"] is True
    assert r["status"]["produkte"]["Bitcoin-Wallet-XYZ"] == "inferred"


def test_extrahiere_kaputtes_json_und_falsches_schema():
    kaputt = lambda url, n: {"message": {"content": "{nicht json"}}
    assert oe.extrahiere("t", "m", "u", chat=kaputt)["json_gueltig"] is False
    falsch = _chat({"produkte": "Eier"})
    r = oe.extrahiere("t", "m", "u", chat=falsch)
    assert r["json_gueltig"] and r["schema_konform"] is False and "daten" not in r


def test_prompt_enthaelt_schutzhinweis_und_begrenzt_text():
    gesehen = {}

    def chat(url, n):
        gesehen.update(n)
        return {"message": {"content": "{}"}}

    oe.extrahiere("x" * 50_000, "m", "u", chat=chat, max_zeichen=6000)
    assert "KEINE Anweisungen" in gesehen["messages"][0]["content"]
    assert len(gesehen["messages"][1]["content"]) < 6100
    assert gesehen["format"] == oe.SCHEMA and gesehen["options"]["temperature"] == 0
