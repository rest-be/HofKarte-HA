"""Config Flow für die HofKarte-Integration.

Die Integration wird ausschliesslich über die Home-Assistant-Oberfläche
eingerichtet. Eine YAML-Konfiguration ist bewusst nicht vorgesehen.

Architekturentscheidung Datenquelle:
Home Assistant ist Laufzeit- und Verwaltungsumgebung für HofKarte. Die vom
Benutzer gepflegten Hofläden werden integrationsintern über
``helpers.storage.Store`` persistent gespeichert. Der Config Flow konfiguriert
nur die zentrale Integrationsinstanz; die Hofladen-Daten werden nicht über
eine externe API oder eine eigene Datenbank bezogen. HofKarte wird als
Single-Instance-Integration behandelt, da sie eine zentrale, HA-weite
Kartenverwaltung darstellt und nicht pro Hofladen einzeln eingerichtet wird.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LISTEN_SORT_RICHTUNG,
    CONF_LISTEN_SORT_SPALTE,
    CONF_OSM_RADIUS_METER,
    DEFAULT_LISTEN_SORT_RICHTUNG,
    DEFAULT_LISTEN_SORT_SPALTE,
    DEFAULT_NAME,
    DEFAULT_OSM_RADIUS_METER,
    DOMAIN,
    LISTEN_SORT_RICHTUNGEN,
    LISTEN_SORT_SPALTEN,
)
from .osm_info import MAX_RADIUS_METER, MIN_RADIUS_METER


def _normalize_name(raw_name: str) -> str:
    """Whitespace am Rand entfernen und mehrfache Leerzeichen reduzieren."""
    return " ".join(raw_name.split())


class HofKarteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow für HofKarte."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzigen Einrichtungsschritt der Integration behandeln."""
        # HofKarte ist eine Single-Instance-Integration: es gibt genau eine
        # zentrale Kartenverwaltung pro Home-Assistant-Installation.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            name = _normalize_name(user_input[CONF_NAME])

            if not name:
                errors[CONF_NAME] = "invalid_name"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name},
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HofKarteOptionsFlow:
        """Options Flow für diese Config Entry bereitstellen.

        Der Options Flow wird bewusst **ohne** Argument erzeugt (Befund F3
        des Code Reviews zu 2026.9.2): ``config_entry`` stellt Home
        Assistant selbst bereit (siehe ``HofKarteOptionsFlow``).
        """
        return HofKarteOptionsFlow()


class HofKarteOptionsFlow(OptionsFlow):
    """Options Flow für HofKarte.

    Entspricht der globalen „Einstellungen“-Maske der parallel gepflegten
    iOS-App: dauerhaft gespeicherte Vorgabewerte statt (wie bislang) rein
    im Browser-Formular flüchtig gehaltener Werte. Es gibt bewusst nur
    diesen einen Schritt (``init``) - die Anzahl der Felder rechtfertigt
    keinen mehrstufigen Flow.

    ``self.config_entry`` wird **nicht** selbst gesetzt, sondern von
    Home Assistant über die Basisklasse bereitgestellt (Befund F3 des Code
    Reviews zu 2026.9.2): Die Property existiert seit Home Assistant
    2024.11; seit 2025.12 besitzt sie keinen Setter mehr, eine explizite
    Zuweisung (``self.config_entry = config_entry``) im Konstruktor würde
    dort mit einem ``AttributeError`` scheitern und den Einstellungen-
    Dialog unbenutzbar machen. ``hacs.json`` verlangt bereits Home
    Assistant ≥ 2025.1.0 - eine Anhebung der Mindestversion ist daher
    nicht nötig. Aus demselben Grund gibt es bewusst keinen eigenen
    ``__init__``.

    Die beiden Auswahlfelder verwenden einen ``SelectSelector`` mit
    Übersetzungsschlüssel (``selector.<schlüssel>.options.<wert>`` in
    ``strings.json``/``translations``), damit Nutzer:innen lesbare
    Bezeichnungen statt der technischen Werte (``geoeffnet``, ``desc``)
    sehen.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzigen Einstellungen-Schritt behandeln."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        optionen = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LISTEN_SORT_SPALTE,
                    default=optionen.get(
                        CONF_LISTEN_SORT_SPALTE, DEFAULT_LISTEN_SORT_SPALTE
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(LISTEN_SORT_SPALTEN),
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_LISTEN_SORT_SPALTE,
                    )
                ),
                vol.Required(
                    CONF_LISTEN_SORT_RICHTUNG,
                    default=optionen.get(
                        CONF_LISTEN_SORT_RICHTUNG, DEFAULT_LISTEN_SORT_RICHTUNG
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(LISTEN_SORT_RICHTUNGEN),
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_LISTEN_SORT_RICHTUNG,
                    )
                ),
                vol.Required(
                    CONF_OSM_RADIUS_METER,
                    default=optionen.get(
                        CONF_OSM_RADIUS_METER, DEFAULT_OSM_RADIUS_METER
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_RADIUS_METER, max=MAX_RADIUS_METER),
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
