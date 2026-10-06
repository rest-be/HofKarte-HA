"""Tests für den HofKarte-Config-Flow."""

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers.selector import SelectSelector

from custom_components.hofkarte.const import (
    CONF_LISTEN_SORT_RICHTUNG,
    CONF_LISTEN_SORT_SPALTE,
    CONF_OSM_RADIUS_METER,
    DEFAULT_LISTEN_SORT_RICHTUNG,
    DEFAULT_LISTEN_SORT_SPALTE,
    DEFAULT_NAME,
    DEFAULT_OSM_RADIUS_METER,
    DOMAIN,
)


async def test_form_shown(hass: HomeAssistant) -> None:
    """Der erste Aufruf muss das Eingabeformular anzeigen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Eine gültige Eingabe muss eine Config Entry erzeugen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Mein Hofladen-Netzwerk"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mein Hofladen-Netzwerk"
    assert result["data"] == {CONF_NAME: "Mein Hofladen-Netzwerk"}


async def test_user_flow_default_name(hass: HomeAssistant) -> None:
    """Das Formular muss den Standardnamen als Vorschlag enthalten."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    schema = result["data_schema"].schema
    name_key = next(key for key in schema if key == CONF_NAME)
    assert name_key.default() == DEFAULT_NAME


async def test_user_flow_invalid_empty_name(hass: HomeAssistant) -> None:
    """Ein leerer bzw. nur aus Leerzeichen bestehender Name muss abgelehnt werden."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "   "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_NAME: "invalid_name"}


async def test_user_flow_duplicate_setup_aborts(hass: HomeAssistant) -> None:
    """Eine zweite Einrichtung muss abgebrochen werden (Single Instance)."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_shows_defaults(hass: HomeAssistant) -> None:
    """Ohne zuvor gespeicherte Optionen müssen die Vorgabewerte erscheinen."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, data={CONF_NAME: DEFAULT_NAME}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    werte = {key: key.default() for key in schema}
    assert werte[CONF_LISTEN_SORT_SPALTE] == DEFAULT_LISTEN_SORT_SPALTE
    assert werte[CONF_LISTEN_SORT_RICHTUNG] == DEFAULT_LISTEN_SORT_RICHTUNG
    assert werte[CONF_OSM_RADIUS_METER] == DEFAULT_OSM_RADIUS_METER


async def test_options_flow_saves_values(hass: HomeAssistant) -> None:
    """Eine gültige Eingabe muss als Optionen der Config Entry gespeichert werden."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, data={CONF_NAME: DEFAULT_NAME}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LISTEN_SORT_SPALTE: "bewertung",
            CONF_LISTEN_SORT_RICHTUNG: "desc",
            CONF_OSM_RADIUS_METER: 500,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_LISTEN_SORT_SPALTE] == "bewertung"
    assert entry.options[CONF_LISTEN_SORT_RICHTUNG] == "desc"
    assert entry.options[CONF_OSM_RADIUS_METER] == 500


async def test_options_flow_rejects_radius_out_of_range(hass: HomeAssistant) -> None:
    """Ein Suchradius ausserhalb 20-2000 m muss abgelehnt werden."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, data={CONF_NAME: DEFAULT_NAME}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with pytest.raises(vol.MultipleInvalid):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_LISTEN_SORT_SPALTE: "name",
                CONF_LISTEN_SORT_RICHTUNG: "asc",
                CONF_OSM_RADIUS_METER: 5,
            },
        )


# --- F3 (Code Review 2026.9.2): Options Flow ohne eigenen Konstruktor ---------


def test_options_flow_hat_keinen_eigenen_konstruktor() -> None:
    """``config_entry`` hat ab Home Assistant 2025.12 keinen Setter mehr.

    Eine Zuweisung im Konstruktor würde dort mit ``AttributeError``
    scheitern. Statischer Test, damit der Fehler nicht versehentlich
    wieder eingeführt wird (auch ohne passende Home-Assistant-Version).
    """
    import ast
    import inspect
    import textwrap

    from custom_components.hofkarte.config_flow import HofKarteOptionsFlow

    assert "__init__" not in vars(HofKarteOptionsFlow)
    # Per AST (nicht per Textsuche): Docstrings dürfen die Zuweisung erwähnen.
    baum = ast.parse(textwrap.dedent(inspect.getsource(HofKarteOptionsFlow)))
    zuweisungen = [
        knoten
        for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Attribute)
        and knoten.attr == "config_entry"
        and isinstance(knoten.ctx, ast.Store)
    ]
    assert zuweisungen == []


def test_async_get_options_flow_liefert_flow_ohne_argument() -> None:
    from custom_components.hofkarte.config_flow import (
        HofKarteConfigFlow,
        HofKarteOptionsFlow,
    )

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: DEFAULT_NAME})

    flow = HofKarteConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, HofKarteOptionsFlow)


async def test_options_flow_nutzt_select_selector_mit_uebersetzungsschluessel(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, data={CONF_NAME: DEFAULT_NAME}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    schema = result["data_schema"].schema
    selektoren = {str(key): wert for key, wert in schema.items()}
    for feld in (CONF_LISTEN_SORT_SPALTE, CONF_LISTEN_SORT_RICHTUNG):
        assert isinstance(selektoren[feld], SelectSelector)
        assert selektoren[feld].config["translation_key"] == feld
