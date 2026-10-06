"""Strukturelle Regressionstests für Issue #6 (Bug: Öffnungszeiten-
Intervall verdoppelt sich, doppelte Hofladen-Einträge beim Speichern).

Wie bereits für Issue #4/#5 (siehe ``test_static_panel_js.py``,
``test_static_panel_js_export_import.py``) wird ``hofkarte-panel.js``
als reines, buildlos ausgeliefertes Frontend-JavaScript nicht über eine
JS-Testumgebung, sondern über gezielte strukturelle Prüfungen des
Quelltexts abgesichert.

Ursache des behobenen Bugs: ``bind()`` registriert Event-Listener ohne
zuvor bestehende zu entfernen. Solange ``bind()`` nur einmalig nach
einem vollständigen ``innerHTML``-Ersatz in ``render()`` aufgerufen
wird, ist das unproblematisch. Die Handler für "+ weiteres Intervall"
und "+ Sonderzeit hinzufügen" fügten eine neue Zeile jedoch gezielt per
DOM-Insert ein (ohne vollständigen Re-Render, um den restlichen
Formularzustand/Fokus zu erhalten) und riefen danach erneut
``this.bind()`` auf demselben, unverändert bestehenden DOM auf - dabei
erhielten bereits vorhandene Elemente (u. a. der Button selbst sowie
der Formular-``submit``-Handler) bei jedem Klick einen weiteren,
zusätzlichen Listener obendrauf. Der Fix verkabelt stattdessen gezielt
nur den "entfernen"-Button der jeweils neu eingefügten Zeile, ohne
``bind()`` erneut aufzurufen.
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


def _handler_koerper(marker: str, quelltext: str) -> str:
    """Den Code-Block eines mit ``marker`` beginnenden Klick-Handlers
    (bis zur nächsten schliessenden ``}));`` oder ``});`` auf oberster
    Einrückungsebene) grob extrahieren - ausreichend für die hier
    geprüften einfachen, nicht weiter verschachtelten Handler."""
    start = quelltext.index(marker)
    kandidaten = [
        quelltext.index(muster, start)
        for muster in ("\n    }));", "\n    });")
        if muster in quelltext[start:]
    ]
    assert kandidaten, f"Kein Handler-Ende nach '{marker}' gefunden."
    return quelltext[start : min(kandidaten)]


def test_bind_wird_ausschliesslich_in_render_aufgerufen() -> None:
    """Regressionstest für die eigentliche Ursache: ``this.bind()`` darf
    nur noch an genau einer Stelle im gesamten Quelltext aufgerufen
    werden - innerhalb von ``render()``, direkt nach dem vollständigen
    ``innerHTML``-Ersatz. Jeder weitere Aufruf auf einem nicht frisch
    erzeugten DOM würde erneut zur berichteten Listener-Akkumulation
    führen."""
    quelltext = _lade_panel_js()
    aufrufe = re.findall(r"this\.bind\(\)", quelltext)
    assert len(aufrufe) == 1, (
        f"Erwartet genau einen this.bind()-Aufruf (in render()), "
        f"gefunden: {len(aufrufe)}."
    )


def test_add_interval_handler_ruft_bind_nicht_mehr_auf() -> None:
    quelltext = _lade_panel_js()
    koerper = _handler_koerper('this.shadowRoot.querySelectorAll("[data-add-interval]")', quelltext)
    assert "this.bind()" not in koerper


def test_add_special_handler_ruft_bind_nicht_mehr_auf() -> None:
    quelltext = _lade_panel_js()
    koerper = _handler_koerper('this.shadowRoot.querySelector("[data-add-special]")', quelltext)
    assert "this.bind()" not in koerper


def test_neue_intervall_zeile_erhaelt_gezielt_eigenen_entfernen_handler() -> None:
    """Kein Datenverlust an anderer Stelle: Der "−"-Button einer neu
    hinzugefügten Intervall-Zeile muss trotz des Verzichts auf
    this.bind() weiterhin funktionieren - direkt auf das neue Element
    gebunden."""
    quelltext = _lade_panel_js()
    koerper = _handler_koerper('this.shadowRoot.querySelectorAll("[data-add-interval]")', quelltext)
    assert 'querySelector("[data-remove-interval]")' in koerper
    assert "addEventListener(\"click\"" in koerper
    assert ".remove()" in koerper


def test_neue_sonderzeit_zeile_erhaelt_gezielt_eigenen_entfernen_handler() -> None:
    quelltext = _lade_panel_js()
    koerper = _handler_koerper('this.shadowRoot.querySelector("[data-add-special]")', quelltext)
    assert 'querySelector("[data-remove-special]")' in koerper
    assert "addEventListener(\"click\"" in koerper
    assert ".remove()" in koerper
