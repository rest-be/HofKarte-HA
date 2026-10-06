"""Strukturelle Regressionstests für das statische Panel-Skript.

``hofkarte-panel.js`` ist reines Frontend-JavaScript ohne Build-Schritt
und wird daher - wie in Issue #4/#5/#6 etabliert - nicht über eine
JS-Testumgebung, sondern über gezielte strukturelle Prüfungen des
Quelltexts abgesichert. Dieses Modul deckt Issue #3 ab: Der bisherige
einzelne Kartenlink ("Auf Google Maps anzeigen", zeigt nur einen
Standort-Pin, keine Route) wird in Kacheln-, Listen- und Detailansicht
durch eine kompakte Routing-Auswahl (Google Maps / Apple Maps, mit
echter Wegbeschreibung) ersetzt; das Bearbeitungsformular behält seinen
bisherigen einzelnen Kartenlink zur Koordinatenkontrolle unverändert.
Ausserdem deckt es die vollständige Entfernung der clientseitigen
Funktion "Entfernung von diesem Gerät berechnen" ab (nicht zu
verwechseln mit dem unveränderten, serverseitigen
``HofKarteEntfernungSensor`` in ``distance.py``/``sensor.py``).
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


def _funktionskoerper(quelltext: str, funktionskopf: str) -> str:
    """Extrahiert den Körper einer Top-Level-Funktion anhand ihres exakten
    Funktionskopfs (z. B. ``"function ermittleRoutingZiel(item) {"``) durch
    einfaches Klammer-Zählen - robust genug für die hier verwendeten,
    unverschachtelten Template-Strings ohne geschweifte Klammern."""
    start = quelltext.index(funktionskopf)
    start_koerper = quelltext.index("{", start) + 1
    tiefe = 1
    i = start_koerper
    while tiefe > 0:
        if quelltext[i] == "{":
            tiefe += 1
        elif quelltext[i] == "}":
            tiefe -= 1
        i += 1
    return quelltext[start_koerper : i - 1]


# --- Routing-URLs (Google Maps / Apple Maps) -------------------------------


def test_panel_js_verwendet_google_maps_routen_url_schema() -> None:
    """Regressionstest für Issue #3: Google Maps muss über das offizielle
    Routen-/Wegbeschreibungs-URL-Schema angesteuert werden (nicht mehr nur
    den Pin-/Suchlink), inklusive Fahrmodus."""
    quelltext = _lade_panel_js()
    assert "https://www.google.com/maps/dir/?api=1&destination=" in quelltext
    assert "travelmode=driving" in quelltext


def test_panel_js_verwendet_apple_maps_routen_url_schema() -> None:
    """Regressionstest für Issue #3: Apple Maps muss über das offizielle
    Routen-URL-Schema (``daddr``) mit Fahrmodus (``dirflg=d``) angesteuert
    werden."""
    quelltext = _lade_panel_js()
    assert "https://maps.apple.com/?daddr=" in quelltext
    assert "dirflg=d" in quelltext


def test_panel_js_alter_google_maps_pin_link_bleibt_fuer_editor_erhalten() -> None:
    """Der bisherige, reine Standort-Pin-Link (``/maps/search/?api=1``)
    muss weiterhin existieren - er wird jetzt ausschliesslich noch von
    ``mapButton()`` im Bearbeitungsformular verwendet."""
    quelltext = _lade_panel_js()
    assert "https://www.google.com/maps/search/?api=1&query=" in quelltext
    assert "function googleMapsUrl(lat, lon)" in quelltext


def test_panel_js_routing_ziel_bevorzugt_adresse_vor_koordinaten() -> None:
    """Regressionstest für Issue #3: ``ermittleRoutingZiel()`` muss zuerst
    die zusammengesetzte Adresse prüfen und erst danach (nur als
    Rückfallebene) gültige Koordinaten - nicht umgekehrt."""
    quelltext = _lade_panel_js()
    koerper = _funktionskoerper(quelltext, "function ermittleRoutingZiel(item) {")

    adress_index = koerper.index("zusammengesetzteAdresse(item)")
    koordinaten_index = koerper.index("isValidWgs84(item.latitude, item.longitude)")
    assert adress_index < koordinaten_index, (
        "Die Adress-Prüfung muss vor der Koordinaten-Prüfung erfolgen, "
        "damit die Adresse beim Routing Vorrang hat."
    )
    # Adress-Zweig muss zurückgegeben werden, bevor die Koordinaten-Prüfung
    # überhaupt erreicht wird (kein Fallthrough, der die Priorität aufhebt).
    rueckgabe_vor_koordinaten = koerper[:koordinaten_index]
    assert re.search(r"return\s+adresse\s*;", rueckgabe_vor_koordinaten)


def test_panel_js_routing_ziel_ohne_adresse_und_koordinaten_ist_null() -> None:
    """Ohne Adresse und ohne gültige Koordinaten darf kein Routing-Ziel
    entstehen (kein funktionsloser Link ins Leere)."""
    quelltext = _lade_panel_js()
    koerper = _funktionskoerper(quelltext, "function ermittleRoutingZiel(item) {")
    assert re.search(r"return\s+null\s*;\s*$", koerper.strip())


def test_panel_js_routing_urls_kodieren_das_ziel() -> None:
    """Adresse/Koordinaten müssen als URL-Parameter kodiert werden
    (``encodeURIComponent``), damit z. B. Kommas/Leerzeichen in Adressen
    keine ungültige URL erzeugen."""
    quelltext = _lade_panel_js()
    google_koerper = _funktionskoerper(quelltext, "function googleMapsRoutenUrl(ziel) {")
    apple_koerper = _funktionskoerper(quelltext, "function appleMapsRoutenUrl(ziel) {")
    assert "encodeURIComponent(ziel)" in google_koerper
    assert "encodeURIComponent(ziel)" in apple_koerper


# --- Verwendungsstellen (Kacheln/Liste/Detail vs. Bearbeitungsformular) ----


def test_panel_js_routing_auswahl_ersetzt_kartenbutton_in_drei_ansichten() -> None:
    """Regressionstest für Issue #3: ``routingAuswahl()`` muss die neue,
    einzige Kartenlogik in Kacheln- (``listCard``), Listen-
    (``listTable``) und Detailansicht (``detail``) sein - nicht mehr
    ``mapButton()`` an diesen drei Stellen."""
    quelltext = _lade_panel_js()
    treffer = re.findall(r"this\.routingAuswahl\(", quelltext)
    assert len(treffer) == 3, (
        f"Erwartet genau 3 Aufrufstellen (Kacheln/Liste/Detail), "
        f"gefunden: {len(treffer)}."
    )


def test_panel_js_editor_behaelt_unveraenderten_mapbutton() -> None:
    """Regressionstest für Issue #3: Das Bearbeitungsformular (``editor()``)
    muss weiterhin ausschliesslich ``mapButton()`` zur Koordinatenkontrolle
    verwenden - dort ist kein Adress-Routing sinnvoll (ggf. noch keine
    gespeicherte, konsistente Adresse/Koordinate)."""
    quelltext = _lade_panel_js()
    treffer = re.findall(r"this\.mapButton\(", quelltext)
    assert len(treffer) == 1, (
        f"Erwartet genau 1 verbleibende Aufrufstelle (editor()), "
        f"gefunden: {len(treffer)}."
    )


def test_panel_js_routing_auswahl_definiert_eigene_css_regeln() -> None:
    """Die kompakte, icon-only Routing-Auswahl braucht eigene, schmalere
    CSS-Regeln als der bisherige Textbutton (``.map-btn``)."""
    quelltext = _lade_panel_js()
    assert ".route-actions{" in quelltext
    assert ".route-btn{" in quelltext


# --- Vollständige Entfernung der Geräte-Entfernungs-Funktion ---------------


def test_panel_js_geraete_entfernung_ist_vollstaendig_entfernt() -> None:
    """Regressionstest für Issue #3: Die clientseitige Funktion "Entfernung
    von diesem Gerät berechnen" (Funktionen, Zustandsfelder, Event-Binding)
    muss vollständig aus dem Quelltext entfernt sein."""
    quelltext = _lade_panel_js()
    fuer_geraete_entfernung_spezifische_bezeichner = [
        "ermittleGeraeteEntfernung",
        "deviceDistanceBlock",
        "haversineDistanceKm",
        "deviceDistance",
        "deviceDistanceStatus",
        "data-geraete-entfernung",
    ]
    for bezeichner in fuer_geraete_entfernung_spezifische_bezeichner:
        assert bezeichner not in quelltext, (
            f"'{bezeichner}' wurde in Issue #3 entfernt, taucht aber noch "
            "im Quelltext auf."
        )


def test_panel_js_verwendet_keine_geolocation_api_mehr() -> None:
    """Ohne die Geräte-Entfernungs-Funktion gibt es keinen verbleibenden
    Grund mehr, die Browser-Geolocation-API zu verwenden."""
    quelltext = _lade_panel_js()
    assert "navigator.geolocation" not in quelltext
    assert "isSecureContext" not in quelltext
