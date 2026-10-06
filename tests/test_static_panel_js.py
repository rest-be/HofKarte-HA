"""Strukturelle Regressionstests für das statische Panel-Skript.

``hofkarte-panel.js`` ist reines Frontend-JavaScript ohne Build-Schritt
(siehe README, Abschnitt „Keine npm-/Build-Abhängigkeiten“) und wird
daher nicht über eine JS-Testumgebung, sondern - wie schon
``test_manifest_und_hacs.py`` es für JSON-Dateien tut - über gezielte
strukturelle Prüfungen des Quelltexts abgesichert. Dieses Modul deckt
den in Issue #4 behobenen Bug ab: Das Kartenmarker-Icon zeigte in Home
Assistant ein defektes Bild ("?") an, weil Leaflets eigene, bild-
basierte Standard-Icon-Erkennung (``Icon.Default._detectIconPath``) die
in den Shadow DOM des Panels eingebundene ``leaflet.css`` nicht finden
kann (Shadow-DOM-Grenze). Der Fix ersetzt das bild-basierte
Standard-Icon durch ein eigenes, reines Inline-SVG-Icon
(``L.divIcon()``), das keine externe Bildressource und keine auf
``document.body``/``document.querySelector`` beruhende Pfaderkennung
benötigt.
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


def test_panel_js_definiert_eigene_marker_icon_funktion() -> None:
    """Regressionstest für Issue #4: Es muss eine eigene Icon-Erzeugung
    existieren, statt sich auf Leaflets defekte Standard-Icon-Erkennung
    zu verlassen."""
    quelltext = _lade_panel_js()
    assert "function erzeugeKarteMarkerIcon(L, geoeffnet)" in quelltext
    assert "L.divIcon(" in quelltext


def test_panel_js_verlaesst_sich_nicht_mehr_auf_icon_default() -> None:
    """Leaflets bild-basiertes Standard-Icon (``L.Icon.Default``) ist die
    in Issue #4 identifizierte Ursache des „?“-Icons (funktioniert nicht
    innerhalb eines Shadow DOM) und darf daher nicht mehr aktiv verwendet
    werden (ein erklärender Kommentar, der die Ursache dokumentiert, ist
    davon ausgenommen)."""
    quelltext = _lade_panel_js()
    assert "L.Icon.Default" not in quelltext
    assert "mergeOptions" not in quelltext
    assert "new L.Icon(" not in quelltext


def test_panel_js_marker_erzeugung_uebergibt_icon_option() -> None:
    """``L.marker(...)`` muss die selbst erzeugte Icon-Option erhalten,
    statt Leaflet ohne ``icon:``-Option das (defekte) Standardbild
    wählen zu lassen. Seit der Marker-Einfärbung nach Öffnungsstatus wird
    das Icon pro Marker über ``markerIconFuer(item.geoeffnet)`` ermittelt
    statt eines einzigen, für alle Marker gleichen ``markerIcon``."""
    quelltext = _lade_panel_js()
    treffer = re.search(
        r"const m = L\.marker\(\[item\.latitude, item\.longitude\],\s*"
        r"\{\s*icon:\s*iconFuer\(item\.geoeffnet\)\s*\}\);",
        quelltext,
    )
    assert treffer, (
        "L.marker(...) übergibt keine passende 'icon: markerIconFuer(...)'-"
        "Option - Marker würden weiterhin Leaflets defektes Standardbild "
        "verwenden bzw. nicht mehr nach Status eingefärbt."
    )


def test_panel_js_marker_icon_html_enthaelt_kein_img_und_keine_url() -> None:
    """Das per divIcon() erzeugte Markup muss ein reines Inline-SVG ohne
    zusätzliche Bildressource oder Netzwerk-Adresse sein (kein neuer
    externer Abhängigkeitspunkt, siehe Datenschutz-Hinweise im
    Handbuch)."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"function erzeugeKarteMarkerIcon\(L, geoeffnet\) \{(.*?)\n\}",
        quelltext,
        re.DOTALL,
    )
    assert match, "erzeugeKarteMarkerIcon() nicht gefunden."
    funktionskoerper = match.group(1)

    assert "<img" not in funktionskoerper
    assert "<svg" in funktionskoerper
    # Die SVG-Namensraum-Deklaration (xmlns="http://www.w3.org/2000/svg")
    # ist kein Netzwerk-Request; wohl aber jede tatsächliche Bild-/CDN-URL.
    assert "cdn." not in funktionskoerper
    assert ".png" not in funktionskoerper
    assert ".jpg" not in funktionskoerper
    assert "src=" not in funktionskoerper


def test_panel_js_definiert_css_regeln_fuer_marker_icon() -> None:
    """Die eigene Icon-Darstellung braucht eigene CSS-Regeln (Farbe,
    Hintergrund transparent statt Leaflets Standard-Icon-Hintergrund)."""
    quelltext = _lade_panel_js()
    assert ".karte-marker-icon{" in quelltext
    assert ".karte-marker-pin{" in quelltext
    assert ".karte-marker-glyph{" in quelltext


def test_panel_js_laedt_leaflet_css_weiterhin_im_shadow_dom() -> None:
    """Der Icon-Fix darf die bestehende CSS-Einbindung für Kacheln/
    Steuerelemente (Zoom-Buttons etc.) nicht entfernen - nur die
    Marker-Icon-Darstellung wird durch das eigene SVG ersetzt."""
    quelltext = _lade_panel_js()
    # Seit Block C (F10) steht das <link> dauerhaft im Shadow Root
    # (sorgeFuerKarteCss()) statt in jedem Render der Kartenansicht.
    assert 'link.rel = "stylesheet";' in quelltext
    assert "this.shadowRoot.append(link)" in quelltext
    assert "[LEAFLET_CSS_URL," in quelltext
