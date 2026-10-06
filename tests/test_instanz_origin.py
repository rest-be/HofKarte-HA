"""Tests für ``instanz_origin.ermittle_eigene_origins`` (Befund F1)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.hofkarte.instanz_origin import ermittle_eigene_origins


async def test_interne_und_externe_url_werden_als_origins_geliefert(
    hass: HomeAssistant,
) -> None:
    hass.config.internal_url = "http://192.168.1.50:8123"
    hass.config.external_url = "https://ha.beispiel.ch"

    origins = ermittle_eigene_origins(hass)

    assert "http://192.168.1.50:8123" in origins
    assert "https://ha.beispiel.ch" in origins


async def test_ohne_konfigurierte_urls_gibt_es_keine_ausnahme(
    hass: HomeAssistant,
) -> None:
    hass.config.internal_url = None
    hass.config.external_url = None

    origins = ermittle_eigene_origins(hass)

    assert isinstance(origins, frozenset)
