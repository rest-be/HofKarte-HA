"""Strukturelle Regressionstests für Export/Import im Panel (Issue #5).

Wie ``test_static_panel_js.py`` (Issue #4) wird ``hofkarte-panel.js``
als reines, buildlos ausgeliefertes Frontend-JavaScript nicht über eine
JS-Testumgebung, sondern über gezielte strukturelle Prüfungen des
Quelltexts abgesichert. Dieses Modul deckt Issue #5 ab: Mehrfachauswahl
in Kacheln/Liste, clientseitigen JSON-Export sowie den zweistufigen
Import-Ablauf (serverseitige Vorschau/Duplikaterkennung über
``import_preview``, anschliessender Commit über ``import_commit``).
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


def test_panel_js_definiert_export_und_import_kernfunktionen() -> None:
    quelltext = _lade_panel_js()
    for funktionsname in (
        "exportAuswahl",
        "bereinigtFuerExport",
        "importDatei",
        "starteKonfliktloesung",
        "schliesseImportAb",
        "commitImport",
        "diffFelder",
    ):
        assert f"{funktionsname}(" in quelltext, f"{funktionsname}() fehlt."


def test_panel_js_checkboxen_in_kacheln_und_liste_vorhanden() -> None:
    """Regressionstest für die geforderte Mehrfachauswahl: Sowohl die
    Kachel- als auch die Tabellenzeile müssen eine Auswahl-Checkbox
    rendern (data-auswahl)."""
    quelltext = _lade_panel_js()
    treffer = re.findall(
        r'data-auswahl="\$\{this\.escAttr\(item\.id\)\}"', quelltext
    )
    assert len(treffer) >= 2, (
        "Erwartet je eine 'data-auswahl'-Checkbox in listCard() (Kacheln) "
        "und listTable() (Liste)."
    )


def test_panel_js_export_entfernt_serverseitig_berechnete_felder() -> None:
    """'geoeffnet' und 'hauptbild_url' sind serverseitig berechnete,
    nicht zum internen Datenmodell gehörende Felder (siehe
    management.py:_serialize_hofladen) und dürfen nicht Teil der
    exportierten JSON-Datei sein."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"bereinigtFuerExport\(item\) \{(.*?)\n  \}", quelltext, re.DOTALL
    )
    assert match, "bereinigtFuerExport() nicht gefunden."
    assert "geoeffnet" in match.group(1)
    assert "hauptbild_url" in match.group(1)


def test_panel_js_export_erzeugt_eine_json_datei_ueber_alle_ausgewaehlten() -> None:
    """Export mehrerer Hofläden muss als eine JSON-Datei mit einer Liste
    von Objekten erfolgen (kein ZIP, keine Einzeldateien, siehe
    Anforderung 2 des Issue-#5-Prompts)."""
    quelltext = _lade_panel_js()
    match = re.search(r"exportAuswahl\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "exportAuswahl() nicht gefunden."
    funktionskoerper = match.group(1)
    assert "JSON.stringify(" in funktionskoerper
    assert "application/json" in funktionskoerper
    assert ".zip" not in funktionskoerper


def test_panel_js_import_nutzt_zweistufigen_preview_commit_ablauf() -> None:
    """Import muss über eine serverseitige Vorschau (Duplikaterkennung/
    Validierung) laufen, bevor tatsächlich etwas übernommen wird - keine
    eigene Duplikaterkennung im Frontend (Vermeidung von Logikduplikation,
    siehe Anforderung 5 des Issue-#5-Prompts)."""
    quelltext = _lade_panel_js()
    assert '"hofkarte/management/import_preview"' in quelltext
    assert '"hofkarte/management/import_commit"' in quelltext


def test_panel_js_import_lehnt_strukturell_ungueltige_datei_clientseitig_ab() -> None:
    """Eine nicht als JSON parsbare oder nicht listenförmige Datei muss
    vor jedem Server-Aufruf abgelehnt werden (kein unnötiger
    Server-Roundtrip für einen offensichtlich fehlerhaften Datei-Inhalt)."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"async importDatei\(file\) \{(.*?)\n  \}", quelltext, re.DOTALL
    )
    assert match, "importDatei() nicht gefunden."
    funktionskoerper = match.group(1)
    assert "JSON.parse(" in funktionskoerper
    assert "Array.isArray(" in funktionskoerper


def test_panel_js_unentschiedene_duplikate_werden_beim_abschluss_beibehalten() -> None:
    """Kein Datenverlust: Ein beim Abschluss des Imports noch nicht
    entschiedenes Duplikat darf nicht überschrieben werden, sondern muss
    auf 'ueberspringen' (beibehalten) zurückfallen."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"schliesseImportAb\(\) \{(.*?)\n  \}", quelltext, re.DOTALL
    )
    assert match, "schliesseImportAb() nicht gefunden."
    assert '|| "ueberspringen"' in match.group(1)


def test_panel_js_konfliktdialog_bietet_globale_komfortoptionen() -> None:
    """Optionale Komfortfunktion (Anforderung 4): 'für alle'-Aktionen
    zusätzlich zur Einzelentscheidung je Duplikat."""
    quelltext = _lade_panel_js()
    assert "data-import-alle" in quelltext
    assert "data-import-entscheidung" in quelltext


def test_panel_js_definiert_css_regeln_fuer_diff_darstellung() -> None:
    quelltext = _lade_panel_js()
    for klasse in (".export-import-row{", ".import-diff{", ".diff-alt{", ".diff-neu{"):
        assert klasse in quelltext, f"CSS-Regel '{klasse}' fehlt."
