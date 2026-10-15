"""24h-Automat im Verwaltungs-Panel (ab 2026.10.2): statische Prüfungen.

Das Verhalten (Speichern, Anzeige) ist über ``hofkarte-panel.js`` verdrahtet;
diese Tests stellen sicher, dass die Verdrahtung vollständig vorhanden ist,
auch wenn die jsdom-Tests in einer Umgebung übersprungen werden.
"""

from __future__ import annotations

from pathlib import Path

_PANEL = (Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js").read_text(
    encoding="utf-8"
)


def test_panel_hat_checkbox_im_zeiten_editor() -> None:
    assert "name=automat_24h" in _PANEL
    assert "24h-Automat (rund um die Uhr zugänglich)" in _PANEL


def test_panel_sendet_automat_24h_beim_speichern() -> None:
    assert "data.automat_24h = !!f.elements.automat_24h?.checked;" in _PANEL


def test_panel_leerer_hofladen_hat_automat_24h_falsch() -> None:
    assert "automat_24h: false" in _PANEL


def test_panel_zeigt_automat_im_detail_und_in_der_kurzinfo() -> None:
    assert "24h-Automat</strong> – rund um die Uhr zugänglich" in _PANEL
    assert 'd.automat_24h ? "24h-Automat (rund um die Uhr)"' in _PANEL


def test_panel_wertet_automat_als_vorhandene_oeffnungszeiten() -> None:
    assert 'd.automat_24h === true || liste(d.oeffnungszeiten)' in _PANEL
