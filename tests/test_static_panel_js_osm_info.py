"""Strukturelle Regressionstests für die OSM-Quelle des "🔍 Angaben
automatisch ermitteln"-Workflows (ursprünglich Issue #10, "Erweiterung
OpenStreetMap zu #8"; seit Issue #11 mit der Website-Quelle zu einer
einzigen Aktion zusammengelegt - siehe
``test_static_panel_js_auto_ermittlung.py`` für die Tests der
Zusammenlegung selbst sowie ``holeOsmOrte()``/``ermittleAutomatisch()``).

Wie schon für frühere Frontend-Änderungen (siehe insbesondere
``test_static_panel_js_webseite_info.py``, dessen Bestätigungs-Popup
dieser Workflow wiederverwendet) wird ``hofkarte-panel.js`` als reines,
buildlos ausgeliefertes Frontend-JavaScript nicht über eine
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


def test_hole_osm_orte_ruft_erwarteten_websocket_befehl_auf() -> None:
    """Issue #11: holeOsmOrte() ersetzt das frühere ermittleOsmInfo() als
    reine Abruffunktion - Status/Popup/Trefferauswahl werden seither
    ausschliesslich von ermittleAutomatisch()/zeigeAutoErgebnis()
    gesteuert (siehe test_static_panel_js_auto_ermittlung.py)."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"async holeOsmOrte\(latitude, longitude, radius\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "holeOsmOrte(latitude, longitude, radius) nicht gefunden."
    body = match.group(1)
    assert '"hofkarte/management/osm_info"' in body
    assert "{ ok: true, orte: result.orte || [] }" in body


def test_hole_osm_orte_liefert_einheitliches_fehlerergebnis() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"async holeOsmOrte\(latitude, longitude, radius\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match
    body = match.group(1)
    assert "return { ok: false, meldung };" in body
    assert "HofkartePanel.OSM_INFO_FEHLERMELDUNGEN[err?.code]" in body


def test_alle_drei_fehlercodes_aus_issue_10_werden_behandelt() -> None:
    quelltext = _lade_panel_js()
    assert "invalid_coordinates" in quelltext
    assert "unreachable" in quelltext
    assert "not_found" in quelltext


def test_ein_treffer_wird_direkt_zu_einem_vorschlag_uebersetzt() -> None:
    """Anforderung 5.2: Bei genau einem Treffer wird die Trefferauswahl
    übersprungen - der Treffer landet direkt als Vorschlag im
    (wiederverwendeten) Bestätigungs-Popup (siehe zeigeAutoErgebnis())."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "ermittleAutomatisch() nicht gefunden."
    body = match.group(1)
    assert "osmErgebnis.orte.length === 1" in body
    assert "this.osmOrtZuVorschlag(osmErgebnis.orte[0])" in body


def test_mehrere_treffer_zeigen_auswahlliste() -> None:
    """Anforderung 5.2: Bei mehr als einem Treffer wird zunächst die
    Trefferauswahl gezeigt (this.osmOrteAuswahl), nicht direkt das
    Bestätigungs-Popup."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleAutomatisch\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "osmErgebnis.orte.length > 1" in body
    assert "this.osmOrteAuswahl = osmErgebnis.orte;" in body


def test_trefferauswahl_wird_nur_bei_vorhandenen_treffern_gerendert() -> None:
    quelltext = _lade_panel_js()
    assert (
        '${this.osmOrteAuswahl ? this.osmOrteAuswahlPopup(this.osmOrteAuswahl) : ""}'
        in quelltext
    )


def test_trefferauswahl_eintraege_sind_mit_waehleosmort_verkabelt() -> None:
    quelltext = _lade_panel_js()
    assert "data-osm-orte-auswahl" in quelltext
    treffer = re.search(
        r'\[data-osm-orte-auswahl\]"\)\.forEach\(b =>\s*'
        r"b\.addEventListener\(\"click\", \(\) => this\.waehleOsmOrt\(",
        quelltext,
    )
    assert treffer, "Die Trefferauswahl-Einträge sind nicht mit waehleOsmOrt() verkabelt."


def test_waehle_osm_ort_oeffnet_gemeinsames_bestaetigungs_popup() -> None:
    """Anforderung 5.3: die Auswahl eines Treffers aus der Liste darf
    NICHT sofort in this.editing schreiben - sie muss stattdessen (wie
    beim einzelnen Treffer) über zeigeAutoErgebnis() das gemeinsame
    Bestätigungs-Popup öffnen, damit der Treffer weiterhin vor der
    Übernahme geprüft werden kann (Issue #11: dabei wird ein ggf. bereits
    vorliegendes Website-Ergebnis nicht verworfen, siehe
    this._wartendesWebseiteErgebnis)."""
    quelltext = _lade_panel_js()
    match = re.search(r"waehleOsmOrt\(index\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "waehleOsmOrt(index) nicht gefunden."
    body = match.group(1)
    assert "this.zeigeAutoErgebnis(" in body
    assert "this.uebernehmeWebseiteInfo(" not in body
    assert "hofkarte/management/save" not in body


def test_abbrechen_der_trefferauswahl_verwirft_ohne_editing_zu_aendern() -> None:
    quelltext = _lade_panel_js()
    assert "data-osm-orte-abbrechen" in quelltext
    treffer = re.search(
        r'\[data-osm-orte-abbrechen\]"\)\?\.addEventListener\("click", '
        r"\(\) => this\.abbrechenOsmAuswahl\(\)\);",
        quelltext,
    )
    assert treffer, "'Abbrechen'-Button der Trefferauswahl ist nicht mit abbrechenOsmAuswahl() verkabelt."

    match = re.search(r"abbrechenOsmAuswahl\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "abbrechenOsmAuswahl() nicht gefunden."
    body = match.group(1)
    assert "this.osmOrteAuswahl = null;" in body
    assert "this.editing" not in body


def test_trefferauswahl_unterstuetzt_schliessen_per_escape_taste() -> None:
    """Barrierefreiheit (analog zum wiederverwendeten Bestätigungs-Popup,
    Issue #9, Anforderung 5.2): Escape muss die Trefferauswahl wie
    'Abbrechen' schliessen."""
    quelltext = _lade_panel_js()
    match = re.search(
        r'\[data-osm-orte-overlay\]"\)\?\.addEventListener\("keydown", \(e\) => \{(.*?)\}\);',
        quelltext,
        re.DOTALL,
    )
    assert match, "Kein Escape-Handler auf dem Trefferauswahl-Overlay gefunden."
    assert 'e.key === "Escape"' in match.group(1)
    assert "this.abbrechenOsmAuswahl();" in match.group(1)


def test_trefferauswahl_popup_hat_dialog_barrierefreiheits_attribute() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"osmOrteAuswahlPopup\(orte\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "osmOrteAuswahlPopup(orte) nicht gefunden."
    body = match.group(1)
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert "aria-labelledby=" in body


def test_render_fokussiert_trefferauswahl_dialog_beim_oeffnen() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"if \(this\.osmOrteAuswahl\) \{\s*"
        r'this\.shadowRoot\.querySelector\("\[data-osm-orte-dialog\]"\)\?\.focus\(\);',
        quelltext,
    )
    assert match, "render() fokussiert den Trefferauswahl-Dialog beim Öffnen nicht."


def test_osm_zustand_wird_beim_start_und_abbrechen_zurueckgesetzt() -> None:
    """Regressionsschutz: start()/cancel() müssen den OSM-Zustand
    (Trefferauswahl) wie den übrigen automatisch-ermittelten Zustand
    zurücksetzen, sonst könnte eine alte Trefferauswahl beim nächsten
    Bearbeiten eines (ggf. anderen) Hofladens wieder auftauchen."""
    quelltext = _lade_panel_js()
    start_match = re.search(r"start\(item = null\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    cancel_match = re.search(r"  cancel\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert start_match, "start(item) nicht gefunden."
    assert cancel_match, "cancel() nicht gefunden."
    for body in (start_match.group(1), cancel_match.group(1)):
        assert "this.osmOrteAuswahl = null;" in body


def test_uebernehme_webseite_info_verarbeitet_auch_website_feld() -> None:
    """Damit ein von der Overpass API gefundener Website-Vorschlag
    (osmOrtZuVorschlag()) beim Übernehmen nicht stillschweigend verloren
    geht, muss uebernehmeWebseiteInfo() auch das Feld 'website'
    berücksichtigen - nicht nur die von webseite_info.py bereits
    gelieferten Felder."""
    quelltext = _lade_panel_js()
    match = re.search(r"uebernehmeWebseiteInfo\(info\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "uebernehmeWebseiteInfo(info) nicht gefunden."
    body = match.group(1)
    assert '"website"' in body


def test_popup_zeigt_webseite_vorschlag_an() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"webseiteInfoPopup\(info\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "webseiteInfoPopup(info) nicht gefunden."
    body = match.group(1)
    assert 'zeile("Webseite", info.website, "website")' in body


def test_osm_ort_zu_vorschlag_liefert_gemeinsame_feldnamen() -> None:
    """osmOrtZuVorschlag() muss dieselben Feldnamen liefern wie die
    Website-Quelle (name/adresse/plz/ort/website/oeffnungszeiten), damit
    mischeAutoVorschlaege() (Issue #11) beide Quellen ohne Umbenennung
    zusammenführen kann."""
    quelltext = _lade_panel_js()
    match = re.search(r"osmOrtZuVorschlag\(ort\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "osmOrtZuVorschlag(ort) nicht gefunden."
    body = match.group(1)
    for feld in ("name:", "adresse:", "plz:", "ort:", "website:", "oeffnungszeiten:"):
        assert feld in body


def test_via_namen_heuristik_treffer_werden_in_trefferauswahl_gekennzeichnet() -> None:
    """Issue #11, 5.2: Treffer, die nur über die Namens-Heuristik
    (osm_info.py, OsmOrt.via_namen_heuristik) gefunden wurden, müssen in
    der Trefferauswahl erkennbar von echten Tag-Treffern unterschieden
    werden - kein stillschweigendes Gleichbehandeln."""
    quelltext = _lade_panel_js()
    match = re.search(r"osmOrteAuswahlPopup\(orte\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "osmOrteAuswahlPopup(orte) nicht gefunden."
    body = match.group(1)
    assert "ort.via_namen_heuristik" in body
    assert "anhand des Namens gefunden" in body
