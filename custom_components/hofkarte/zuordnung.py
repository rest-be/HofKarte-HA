"""Bereich und Label „HofKarte“ für Hofladen-Devices und -Entities (A2).

Jeder Hofladen wird automatisch dem Home-Assistant-Bereich „HofKarte“
zugeordnet (am Device; die Entities erben den Bereich vom Device) und
erhält das Label „HofKarte“ (am Device und an allen zugehörigen Entities).
Beides lässt sich in den Optionen der Integration abschalten und
umbenennen.

Regeln (entsprechen den Grundsätzen von HofKarte „nichts ohne Wahl
überschreiben“):

- Bereich und Label werden beim ersten Bedarf angelegt, falls sie fehlen;
  gibt es bereits einen Bereich/ein Label mit diesem Namen, wird es
  wiederverwendet.
- Ein Device mit bereits gesetztem Bereich behält diesen Bereich.
- Jedes Device und jede Entity wird nur **einmal** behandelt (die
  behandelten Kennungen liegen in einem eigenen Store). Wer das Label
  oder den Bereich später von Hand entfernt, bekommt ihn nicht ungefragt
  zurück.
- Bestehende Hofläden werden beim ersten Start nach dem Update
  nachgezogen; ebenso, wenn die Zuordnung später wieder eingeschaltet wird.
- Eine Umbenennung in den Optionen benennt den von HofKarte verwalteten
  Bereich bzw. das Label um (alle Zuordnungen ziehen so mit) - ausser,
  der Name wurde zwischenzeitlich von Hand geändert; dann bleibt er
  unangetastet und es wird ein Bereich/Label mit dem neuen Namen
  verwendet bzw. angelegt.
- Das Abschalten entfernt nichts; es werden lediglich keine weiteren
  Hofläden mehr zugeordnet.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BEREICH_NAME,
    CONF_LABEL_NAME,
    CONF_ZUORDNUNG_AKTIV,
    DEFAULT_BEREICH_NAME,
    DEFAULT_LABEL_NAME,
    DEFAULT_ZUORDNUNG_AKTIV,
    DOMAIN,
    MAX_LAENGE_REGISTERNAME,
)

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}.zuordnung"


def normalisiere_registername(roh: Any, standard: str) -> str:
    """Namen bereinigen (Leerraum, Länge); leer -> Standardname."""
    text = " ".join(str(roh or "").split())[:MAX_LAENGE_REGISTERNAME]
    return text or standard


class ZuordnungsManager:
    """Verwaltet Bereich und Label „HofKarte“ für eine Config Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._daten: dict[str, Any] = {}
        self._geladen = False

    # -- Konfiguration ---------------------------------------------------

    @property
    def aktiv(self) -> bool:
        return bool(
            self._entry.options.get(CONF_ZUORDNUNG_AKTIV, DEFAULT_ZUORDNUNG_AKTIV)
        )

    @property
    def bereich_name(self) -> str:
        return normalisiere_registername(
            self._entry.options.get(CONF_BEREICH_NAME), DEFAULT_BEREICH_NAME
        )

    @property
    def label_name(self) -> str:
        return normalisiere_registername(
            self._entry.options.get(CONF_LABEL_NAME), DEFAULT_LABEL_NAME
        )

    # -- Store -----------------------------------------------------------

    async def async_laden(self) -> None:
        gespeichert = await self._store.async_load()
        self._daten = dict(gespeichert) if isinstance(gespeichert, dict) else {}
        self._daten.setdefault("behandelt", [])
        self._geladen = True

    def _speichern(self) -> None:
        """Zuordnungsstand sofort sichern (selten, kleine Datenmenge)."""
        stand = {**self._daten, "behandelt": list(self._daten["behandelt"])}
        self._hass.async_create_task(self._store.async_save(stand))

    # -- Bereich und Label -----------------------------------------------

    @callback
    def _bereich_id(self) -> str:
        """ID des Bereichs „HofKarte“ (anlegen/umbenennen/wiederverwenden)."""
        registry = ar.async_get(self._hass)
        name = self.bereich_name
        gespeicherte_id = self._daten.get("bereich_id")
        gespeicherter_name = self._daten.get("bereich_name")
        bereich = registry.async_get_area(gespeicherte_id) if gespeicherte_id else None

        if bereich is not None and bereich.name == name:
            return bereich.id
        vorhanden = registry.async_get_area_by_name(name)
        if vorhanden is not None:
            bereich = vorhanden
        elif bereich is not None and bereich.name == gespeicherter_name:
            # Von HofKarte verwaltet und nicht von Hand umbenannt: umbenennen.
            bereich = registry.async_update(bereich.id, name=name)
        else:
            bereich = registry.async_create(name)
        self._daten["bereich_id"] = bereich.id
        self._daten["bereich_name"] = bereich.name
        self._speichern()
        return bereich.id

    @callback
    def _label_id(self) -> str:
        """ID des Labels „HofKarte“ (anlegen/umbenennen/wiederverwenden)."""
        registry = lr.async_get(self._hass)
        name = self.label_name
        gespeicherte_id = self._daten.get("label_id")
        gespeicherter_name = self._daten.get("label_name")
        label = registry.async_get_label(gespeicherte_id) if gespeicherte_id else None

        if label is not None and label.name == name:
            return label.label_id
        vorhanden = registry.async_get_label_by_name(name)
        if vorhanden is not None:
            label = vorhanden
        elif label is not None and label.name == gespeicherter_name:
            label = registry.async_update(label.label_id, name=name)
        else:
            label = registry.async_create(name)
        self._daten["label_id"] = label.label_id
        self._daten["label_name"] = label.name
        self._speichern()
        return label.label_id

    # -- Zuordnung -------------------------------------------------------

    @callback
    def anwenden(self) -> None:
        """Namen abgleichen und alle noch nicht behandelten Objekte zuordnen."""
        if not self._geladen or not self.aktiv:
            return
        try:
            bereich_id = self._bereich_id()
            label_id = self._label_id()
        except ValueError as err:  # z. B. Namenskollision in der Registry
            _LOGGER.warning("Bereich/Label konnten nicht angelegt werden: %s", err)
            return

        behandelt: list[str] = self._daten["behandelt"]
        bekannt = set(behandelt)
        geaendert = False

        geraete = dr.async_get(self._hass)
        for geraet in dr.async_entries_for_config_entry(geraete, self._entry.entry_id):
            schluessel = f"device:{geraet.id}"
            if schluessel in bekannt:
                continue
            aenderungen: dict[str, Any] = {"labels": geraet.labels | {label_id}}
            if geraet.area_id is None:
                aenderungen["area_id"] = bereich_id
            geraete.async_update_device(geraet.id, **aenderungen)
            behandelt.append(schluessel)
            geaendert = True

        entitaeten = er.async_get(self._hass)
        for eintrag in er.async_entries_for_config_entry(
            entitaeten, self._entry.entry_id
        ):
            schluessel = f"entity:{eintrag.id}"
            if schluessel in bekannt:
                continue
            entitaeten.async_update_entity(
                eintrag.entity_id, labels=eintrag.labels | {label_id}
            )
            behandelt.append(schluessel)
            geaendert = True

        if geaendert:
            self._speichern()

    # -- Einrichtung -----------------------------------------------------

    async def async_start(self) -> Callable[[], None]:
        """Laden, einmal anwenden und auf neue Devices/Entities reagieren."""
        await self.async_laden()
        self.anwenden()

        @callback
        def _bei_neuem_objekt(ereignis: Event) -> None:
            if ereignis.data.get("action") == "create":
                self.anwenden()

        async def _bei_optionen(_hass: HomeAssistant, _entry: ConfigEntry) -> None:
            self.anwenden()

        abmeldungen = [
            self._hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, _bei_neuem_objekt
            ),
            self._hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, _bei_neuem_objekt
            ),
            self._entry.add_update_listener(_bei_optionen),
        ]

        @callback
        def _abmelden() -> None:
            for abmelden in abmeldungen:
                abmelden()

        return _abmelden


async def async_zuordnung_einrichten(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Zuordnungs-Manager starten; Abmeldung beim Entladen der Entry."""
    manager = ZuordnungsManager(hass, entry)
    abmelden = await manager.async_start()
    entry.async_on_unload(abmelden)
