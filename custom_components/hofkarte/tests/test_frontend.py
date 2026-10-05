"""Tests für das HofKarte-Sidebar-Panel (frontend.py)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.hofkarte.frontend import (
    _MANIFEST_PATH,
    _PANEL_URL,
    _integration_version,
    async_register_frontend,
    async_remove_frontend,
    async_setup_frontend_assets,
)

_AKTUELLE_VERSION = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))["version"]


async def test_setup_frontend_assets_registers_static_path(
    hass: HomeAssistant,
) -> None:
    """Die statischen Panel-Assets müssen unter der erwarteten URL
    registriert werden."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    await async_setup_frontend_assets(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    (registrierte_pfade,), _kwargs = hass.http.async_register_static_paths.call_args
    assert len(registrierte_pfade) == 1
    pfad_config = registrierte_pfade[0]
    assert pfad_config.url_path == "/api/hofkarte/static"
    assert pfad_config.path.endswith("static")
    assert pfad_config.cache_headers is True, "Befund F14: langes Caching, URL trägt ?v=<Version>"


async def test_register_frontend_adds_panel(hass: HomeAssistant) -> None:
    """Das Panel muss unter dem erwarteten URL-Pfad registriert werden."""
    await async_register_frontend(hass)

    panels = hass.data.get("frontend_panels", {})
    assert _PANEL_URL in panels

    panel = panels[_PANEL_URL]
    assert panel.sidebar_title == "HofKarte"
    assert panel.require_admin is True
    assert panel.config["_panel_custom"]["name"] == "hofkarte-panel"
    assert panel.config["_panel_custom"]["js_url"] == (
        f"/api/hofkarte/static/hofkarte-panel.js?v={_AKTUELLE_VERSION}"
    )


def test_integration_version_liest_manifest_version() -> None:
    """_integration_version() muss exakt die in manifest.json hinterlegte
    Version liefern (Grundlage des Cache-Busting-Query-Parameters)."""
    assert _integration_version() == _AKTUELLE_VERSION


async def test_register_frontend_js_url_enthaelt_versions_query_parameter(
    hass: HomeAssistant,
) -> None:
    """Behobener Bug: Ohne einen sich pro Version ändernden Query-
    Parameter liefert der Browser nach einem Update weiterhin die
    zwischengespeicherte alte Fassung von hofkarte-panel.js aus, auch
    wenn die Datei auf der Festplatte bereits aktualisiert wurde – neue
    Funktionen (z. B. Kacheln/Liste/Karte) blieben dadurch unsichtbar."""
    await async_register_frontend(hass)

    js_url = hass.data["frontend_panels"][_PANEL_URL].config["_panel_custom"]["js_url"]
    assert js_url.startswith("/api/hofkarte/static/hofkarte-panel.js?v=")
    assert js_url.endswith(f"?v={_AKTUELLE_VERSION}")


async def test_register_frontend_is_idempotent(hass: HomeAssistant) -> None:
    """Ein zweiter Aufruf darf nicht mit 'Overwriting panel' abstürzen
    (Guard-Klausel gegen Doppelregistrierung)."""
    await async_register_frontend(hass)
    await async_register_frontend(hass)  # darf keine Exception werfen

    panels = hass.data.get("frontend_panels", {})
    assert _PANEL_URL in panels


async def test_remove_frontend_removes_registered_panel(
    hass: HomeAssistant,
) -> None:
    """Ein registriertes Panel muss beim Entladen entfernt werden."""
    await async_register_frontend(hass)
    assert _PANEL_URL in hass.data.get("frontend_panels", {})

    async_remove_frontend(hass)

    assert _PANEL_URL not in hass.data.get("frontend_panels", {})


async def test_remove_frontend_noop_if_not_registered(
    hass: HomeAssistant,
) -> None:
    """Ohne registriertes Panel darf das Entfernen keine Exception werfen."""
    async_remove_frontend(hass)  # darf keine Exception werfen

    assert _PANEL_URL not in hass.data.get("frontend_panels", {})
