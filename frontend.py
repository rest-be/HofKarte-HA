"""Native Home Assistant sidebar panel for HofKarte management."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_PANEL_URL = "hofkarte"
_STATIC_URL = "/api/hofkarte/static"
_MANIFEST_PATH = Path(__file__).parent / "manifest.json"


def _integration_version() -> str:
    """Version aus manifest.json lesen – dient ausschliesslich als
    Cache-Busting-Query-Parameter für ``js_url`` (siehe
    ``async_register_frontend``), keine funktionale Bedeutung.

    Browser (und teilweise Home Assistants eigenes Frontend) cachen
    per Custom-Panel geladenes JavaScript anhand seiner URL, nicht
    anhand des Dateiinhalts. Bleibt die URL über Versions-Updates
    hinweg identisch, kann eine bereits im Browser zwischengespeicherte
    ältere Fassung von ``hofkarte-panel.js`` unbegrenzt weiterverwendet
    werden – neue Funktionen erscheinen dann trotz korrekt
    aktualisierter Dateien auf der Festplatte nicht (behobener Bug,
    siehe CHANGELOG). Fällt das Lesen der Datei aus irgendeinem Grund
    aus (z. B. bei einem stark abweichenden Installationslayout), wird
    ein fester Platzhalter verwendet – die Funktion selbst bleibt dann
    nutzbar, nur die Cache-Invalidierung entfällt für diesen Fall.
    """
    try:
        with _MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
            manifest: dict[str, Any] = json.load(manifest_file)
        version = manifest.get("version")
        if isinstance(version, str) and version:
            return version
    except (OSError, ValueError):
        pass
    return "0"


async def async_setup_frontend_assets(hass: HomeAssistant) -> None:
    """Serve the bundled frontend assets once for the integration."""
    frontend_dir = Path(__file__).parent / "static"
    await hass.http.async_register_static_paths([
        # cache_headers=True (Befund F14): Der Browser darf die Dateien
        # lange zwischenspeichern, weil alle versionierten Einstiegspunkte
        # ihre Version in der URL tragen (hofkarte-panel.js?v=<Version>,
        # Leaflet/markercluster ?v=<Bibliotheksversion>) und sich bei einem
        # Update damit die URL ändert.
        StaticPathConfig(_STATIC_URL, str(frontend_dir), True)
    ])


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the HofKarte management panel."""
    if _PANEL_URL in hass.data.get("frontend_panels", {}):
        return
    # Der Versions-Query-Parameter (?v=...) erzwingt beim Wechsel der
    # Integrationsversion eine neue, dem Browser bisher unbekannte URL
    # für hofkarte-panel.js – ohne ihn liefert der Browser nach einem
    # Update sonst weiterhin die zuvor zwischengespeicherte alte
    # Fassung aus, siehe _integration_version().
    js_url = f"{_STATIC_URL}/hofkarte-panel.js?v={_integration_version()}"
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="HofKarte",
        sidebar_icon="mdi:store-edit",
        frontend_url_path=_PANEL_URL,
        config={
            "_panel_custom": {
                "name": "hofkarte-panel",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": js_url,
            }
        },
        require_admin=True,
    )


def async_remove_frontend(hass: HomeAssistant) -> None:
    """Remove the panel during config-entry unload."""
    if _PANEL_URL in hass.data.get("frontend_panels", {}):
        async_remove_panel(hass, _PANEL_URL)
