"""Strukturelle Regressionstests für Issue #11 ("Vereinfachung der
automatischen Ermittlung") - die Zusammenlegung der bisher getrennten
"🔎 Infos ermitteln"- und "📍 Ort in der Nähe suchen"-Buttons zu einer
einzigen Aktion ("🔍 Angaben automatisch ermitteln", ``ermittleAutomatisch()``),
den einstellbaren Overpass-Suchradius sowie die Quellen-Kennzeichnung im
gemeinsamen Bestätigungs-Popup.

Für die quellenspezifischen Abruffunktionen (``holeWebseiteVorschlag()``/
``holeOsmOrte()``) und deren jeweilige Fehlercodes siehe weiterhin
``test_static_panel_js_webseite_info.py``/``test_static_panel_js_osm_info.py``.

Wie schon für frühere Frontend-Änderungen wird ``hofkarte-panel.js`` als
reines, buildlos ausgeliefertes Frontend-JavaScript nicht über eine
JS-Testumgebung, sondern über gezielte strukturelle Prüfungen des
Quelltexts abgesichert.
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 5.1: Ein Button statt zwei
# ---------------------------------------------------------------------------


def test_formular_enthaelt_nur_noch_einen_automatisch_ermitteln_button() -> None:
    quelltext = _lade_panel_js()
    assert "data-auto-info-btn" in quelltext
    assert "Angaben automatisch ermitteln" in quelltext
    # Regressionsschutz: die beiden früheren, getrennten Buttons dürfen
    # nicht mehr existieren (Issue #11, 5.1).
    assert "data-webseite-info-btn" not in quelltext
    assert "data-osm-info-btn" not in quelltext


def test_button_ist_mit_ermittle_automatisch_verkabelt() -> None:
    quelltext = _lade_panel_js()
    treffer = re.search(
        r'\[data-auto-info-btn\]"\)\?\.addEventListener\("click", \(\) => \{\s*'
        r"this\.ermittleAutomatisch\(\);",
        quelltext,
    )
    assert treffer, "Der 'Angaben automatisch ermitteln'-Button ist nicht mit ermittleAutomatisch() verkabelt."


def test_ermittleautomatisch_fragt_website_nur_bei_eingetragener_adresse_ab() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "ermittleAutomatisch() nicht gefunden."
    body = match.group(1)
    assert "website ? this.holeWebseiteVorschlag(website) : Promise.resolve(null)" in body
    assert "hatKoordinaten ? this.holeOsmOrte(latitude, longitude, this.osmRadius) : Promise.resolve(null)" in body


def test_kein_backend_aufruf_ohne_website_und_ohne_gueltige_koordinaten() -> None:
    """Fehlerfall (Issue #11): Weder Website noch gültige Koordinaten
    vorhanden -> kein Backend-Aufruf, die Prüfung muss vor Promise.all(...)
    liegen und dabei aus der Funktion zurückkehren."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    pruefung_index = body.index("if (!website && !hatKoordinaten)")
    promise_index = body.index("Promise.all([")
    assert pruefung_index < promise_index

    pruef_block = body[pruefung_index : body.index("}", pruefung_index) + 1]
    assert "return" in pruef_block


def test_ermittleautomatisch_erfasst_formularzustand_vor_jedem_render() -> None:
    """Kern des in Issue #9 behobenen Datenverlust-Bugs, hier als
    Anti-Regressionsanforderung für die zusammengelegte Aktion (Issue
    #11): ermittleAutomatisch() muss den vollständigen Formularzustand
    VOR dem ersten this.render()-Aufruf sichern (siehe
    erfasseFormularZustand())."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    erfassen_index = body.index("this.erfasseFormularZustand()")
    assert "this.render()" not in body[:erfassen_index]


def test_beide_quellen_werden_parallel_statt_nacheinander_abgefragt() -> None:
    """Issue #11: Promise.all statt zweier sequenzieller Aufrufe, damit
    ein Klick auf den einen Button nicht länger dauert als bei getrennten
    Buttons nötig."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "await Promise.all([" in body


# ---------------------------------------------------------------------------
# 5.1: Zusammenführung der Ergebnisse (mischeAutoVorschlaege/zeigeAutoErgebnis)
# ---------------------------------------------------------------------------


def test_mischeautovorschlaege_bevorzugt_website_bei_konflikt_ohne_osm_wert_zu_verwerfen() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"mischeAutoVorschlaege\(websiteVorschlag, osmVorschlag\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "mischeAutoVorschlaege(websiteVorschlag, osmVorschlag) nicht gefunden."
    body = match.group(1)
    # Website hat Vorrang ...
    assert 'quellen[feld] = (o && o !== w) ? "website+osm" : "website";' in body
    # ... der abweichende OSM-Wert wird aber nicht stillschweigend
    # verworfen, sondern bleibt über "website+osm" nachvollziehbar.
    assert '"website+osm"' in body


def test_zeigeautoergebnis_meldet_kombinierten_fehler_wenn_beide_quellen_fehlschlagen() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"zeigeAutoErgebnis\(websiteErgebnis, osmErgebnis, osmVorschlag\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "zeigeAutoErgebnis(...) nicht gefunden."
    body = match.group(1)
    assert "if (!websiteVorschlag && !osmVorschlag) {" in body
    assert "teile.push(`Website: ${websiteErgebnis.meldung}`)" in body
    assert "teile.push(`OpenStreetMap: ${osmErgebnis.meldung}`)" in body


def test_zeigeautoergebnis_oeffnet_popup_wenn_mindestens_eine_quelle_liefert() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"zeigeAutoErgebnis\(websiteErgebnis, osmErgebnis, osmVorschlag\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match
    body = match.group(1)
    assert "this.mischeAutoVorschlaege(websiteVorschlag, osmVorschlag)" in body
    assert "this.webseiteInfoVorschlag = vorschlag;" in body
    assert "this.render();" in body


def test_mehrere_osm_treffer_verwerfen_bereits_vorliegendes_website_ergebnis_nicht() -> None:
    """Issue #11: Liefert die OSM-Quelle mehrere Treffer, muss ein bereits
    erfolgreich ermitteltes Website-Ergebnis bis zur Auswahl
    zwischengespeichert werden, statt verworfen zu werden."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "this._wartendesWebseiteErgebnis = websiteErgebnis;" in body


# ---------------------------------------------------------------------------
# 5.1: Quellen-Kennzeichnung im gemeinsamen Bestätigungs-Popup
# ---------------------------------------------------------------------------


def test_popup_kennzeichnet_felder_mit_ihrer_quelle() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"webseiteInfoPopup\(info\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "webseiteInfoPopup(info) nicht gefunden."
    body = match.group(1)
    assert "this.autoErmittlungQuellen" in body
    assert "quelle-badge" in body


# ---------------------------------------------------------------------------
# 5.2: Einstellbarer Suchradius
# ---------------------------------------------------------------------------


def test_formular_enthaelt_einstellbares_radius_feld() -> None:
    quelltext = _lade_panel_js()
    assert 'name="osm_radius"' in quelltext
    assert "OSM_MIN_RADIUS_METER" in quelltext
    assert "OSM_MAX_RADIUS_METER" in quelltext


def test_radius_wird_wie_uebrige_formularfelder_vor_render_gesichert() -> None:
    """Derselbe Datenverlust-Mechanismus wie in Issue #9 - ein bereits
    geänderter Radius-Wert darf beim nächsten Re-Render nicht verloren
    gehen."""
    quelltext = _lade_panel_js()
    match = re.search(r"erfasseFormularZustand\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert 'f.elements["osm_radius"]' in body
    assert "this.osmRadius = radiusEingabe;" in body


def test_ermittleautomatisch_gibt_radius_an_holeosmorte_weiter() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "this.holeOsmOrte(latitude, longitude, this.osmRadius)" in body


# ---------------------------------------------------------------------------
# 5.3: Formularbereich visuell vereinfacht
# ---------------------------------------------------------------------------


def test_automatisch_ausfuellen_abschnitt_existiert() -> None:
    quelltext = _lade_panel_js()
    assert "Automatisch ausfüllen" in quelltext


def test_zustand_wird_beim_start_und_abbrechen_zurueckgesetzt() -> None:
    """Regressionsschutz: start()/cancel() müssen den zusammengelegten
    Ermittlungs-Zustand (Vorschlag, Quellen, Status, Radius, wartendes
    Website-Ergebnis) zurücksetzen."""
    quelltext = _lade_panel_js()
    start_match = re.search(r"start\(item = null\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    cancel_match = re.search(r"  cancel\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert start_match, "start(item) nicht gefunden."
    assert cancel_match, "cancel() nicht gefunden."
    for body in (start_match.group(1), cancel_match.group(1)):
        assert "this.webseiteInfoVorschlag = null;" in body
        assert "this.autoErmittlungQuellen = null;" in body
        assert "this._wartendesWebseiteErgebnis = null;" in body
