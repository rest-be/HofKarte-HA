"""Tests für Bereich und Label „HofKarte“ (Anforderung A2)."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import (
    CONF_BEREICH_NAME,
    CONF_LABEL_NAME,
    CONF_ZUORDNUNG_AKTIV,
    DOMAIN,
)
from custom_components.hofkarte.zuordnung import normalisiere_registername


def _entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HofKarte",
        data={CONF_NAME: "HofKarte"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def _einrichten(hass: HomeAssistant, entry: MockConfigEntry, *ids: str):
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for hof_id in ids:
        await coordinator.async_add_hofladen({"id": hof_id, "name": f"Hof {hof_id}"})
    await hass.async_block_till_done()
    return coordinator


def _geraet(hass: HomeAssistant, hof_id: str) -> dr.DeviceEntry:
    geraet = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, hof_id)})
    assert geraet is not None
    return geraet


def _entitaeten(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


def test_registername_wird_bereinigt() -> None:
    assert normalisiere_registername("  Hof   Karte ", "X") == "Hof Karte"
    assert normalisiere_registername("", "HofKarte") == "HofKarte"
    assert normalisiere_registername(None, "HofKarte") == "HofKarte"
    assert len(normalisiere_registername("a" * 500, "X")) == 100


async def test_neuer_hofladen_erhaelt_bereich_und_label(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    await _einrichten(hass, entry, "hof-1")

    bereich = ar.async_get(hass).async_get_area_by_name("HofKarte")
    label = lr.async_get(hass).async_get_label_by_name("HofKarte")
    assert bereich is not None and label is not None

    geraet = _geraet(hass, "hof-1")
    assert geraet.area_id == bereich.id
    assert label.label_id in geraet.labels

    entitaeten = _entitaeten(hass, entry)
    assert entitaeten, "es müssen Entities existieren"
    for eintrag in entitaeten:
        assert label.label_id in eintrag.labels


async def test_spaeter_hinzugekommener_hofladen_wird_zugeordnet(
    hass: HomeAssistant,
) -> None:
    entry = _entry(hass)
    coordinator = await _einrichten(hass, entry, "hof-1")
    await coordinator.async_add_hofladen({"id": "hof-2", "name": "Hof zwei"})
    await hass.async_block_till_done()

    label = lr.async_get(hass).async_get_label_by_name("HofKarte")
    bereich = ar.async_get(hass).async_get_area_by_name("HofKarte")
    geraet = _geraet(hass, "hof-2")
    assert geraet.area_id == bereich.id
    assert label.label_id in geraet.labels
    # Es entsteht nur ein Bereich und ein Label.
    assert len([a for a in ar.async_get(hass).async_list_areas() if a.name == "HofKarte"]) == 1
    assert len([x for x in lr.async_get(hass).async_list_labels() if x.name == "HofKarte"]) == 1


async def test_vorhandener_bereich_und_label_werden_wiederverwendet(
    hass: HomeAssistant,
) -> None:
    bereich = ar.async_get(hass).async_create("HofKarte")
    label = lr.async_get(hass).async_create("HofKarte")
    entry = _entry(hass)
    await _einrichten(hass, entry, "hof-1")

    assert _geraet(hass, "hof-1").area_id == bereich.id
    assert label.label_id in _geraet(hass, "hof-1").labels
    assert len(ar.async_get(hass).async_list_areas()) == 1
    assert len(lr.async_get(hass).async_list_labels()) == 1


async def test_bereits_gesetzter_bereich_wird_nicht_ueberschrieben(
    hass: HomeAssistant,
) -> None:
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    eigener = ar.async_get(hass).async_create("Hofladen am Dorfrand")
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "hof-x")},
        name="Hof x",
    )
    geraet = _geraet(hass, "hof-x")
    dr.async_get(hass).async_update_device(geraet.id, area_id=eigener.id)
    # Neu zuordnen: bereits behandelte Objekte werden nicht erneut angefasst;
    # ein frisches Gerät mit eigenem Bereich behält ihn.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "hof-y")},
        name="Hof y",
    )
    gy = _geraet(hass, "hof-y")
    dr.async_get(hass).async_update_device(gy.id, area_id=eigener.id)
    await hass.async_block_till_done()

    assert _geraet(hass, "hof-y").area_id == eigener.id


async def test_entferntes_label_kommt_nicht_ungefragt_zurueck(
    hass: HomeAssistant,
) -> None:
    entry = _entry(hass)
    await _einrichten(hass, entry, "hof-1")
    label = lr.async_get(hass).async_get_label_by_name("HofKarte")
    geraet = _geraet(hass, "hof-1")
    dr.async_get(hass).async_update_device(geraet.id, labels=set())
    eintrag = _entitaeten(hass, entry)[0]
    er.async_get(hass).async_update_entity(eintrag.entity_id, labels=set())

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert label.label_id not in _geraet(hass, "hof-1").labels
    assert label.label_id not in er.async_get(hass).async_get(eintrag.entity_id).labels


async def test_abgeschaltet_ordnet_nichts_zu(hass: HomeAssistant) -> None:
    entry = _entry(hass, {CONF_ZUORDNUNG_AKTIV: False})
    await _einrichten(hass, entry, "hof-1")

    assert ar.async_get(hass).async_get_area_by_name("HofKarte") is None
    assert lr.async_get(hass).async_get_label_by_name("HofKarte") is None
    geraet = _geraet(hass, "hof-1")
    assert geraet.area_id is None and not geraet.labels


async def test_einschalten_zieht_bestehende_hoefe_nach(hass: HomeAssistant) -> None:
    """Gilt auch für Hofläden, die schon vor dem Update existierten: sie
    stehen nicht im Zuordnungs-Store und werden daher einmalig nachgezogen."""
    entry = _entry(hass, {CONF_ZUORDNUNG_AKTIV: False})
    await _einrichten(hass, entry, "hof-1", "hof-2")
    assert _geraet(hass, "hof-1").area_id is None

    hass.config_entries.async_update_entry(
        entry, options={CONF_ZUORDNUNG_AKTIV: True}
    )
    await hass.async_block_till_done()

    bereich = ar.async_get(hass).async_get_area_by_name("HofKarte")
    label = lr.async_get(hass).async_get_label_by_name("HofKarte")
    for hof_id in ("hof-1", "hof-2"):
        geraet = _geraet(hass, hof_id)
        assert geraet.area_id == bereich.id
        assert label.label_id in geraet.labels
    for eintrag in _entitaeten(hass, entry):
        assert label.label_id in eintrag.labels


async def test_umbenennung_zieht_bestehende_zuordnung_mit(
    hass: HomeAssistant,
) -> None:
    entry = _entry(hass)
    await _einrichten(hass, entry, "hof-1")
    bereich_vorher = ar.async_get(hass).async_get_area_by_name("HofKarte")
    label_vorher = lr.async_get(hass).async_get_label_by_name("HofKarte")

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_BEREICH_NAME: "Hofläden", CONF_LABEL_NAME: "Bauernhof"},
    )
    await hass.async_block_till_done()

    bereich = ar.async_get(hass).async_get_area_by_name("Hofläden")
    label = lr.async_get(hass).async_get_label_by_name("Bauernhof")
    assert bereich is not None and bereich.id == bereich_vorher.id
    assert label is not None and label.label_id == label_vorher.label_id
    assert ar.async_get(hass).async_get_area_by_name("HofKarte") is None
    assert _geraet(hass, "hof-1").area_id == bereich.id
    assert label.label_id in _geraet(hass, "hof-1").labels


async def test_von_hand_umbenannter_bereich_bleibt_unangetastet(
    hass: HomeAssistant,
) -> None:
    entry = _entry(hass)
    await _einrichten(hass, entry, "hof-1")
    bereich = ar.async_get(hass).async_get_area_by_name("HofKarte")
    ar.async_get(hass).async_update(bereich.id, name="Mein Bereich")

    hass.config_entries.async_update_entry(
        entry, options={CONF_BEREICH_NAME: "Hofläden"}
    )
    await hass.async_block_till_done()

    # Der von Hand umbenannte Bereich bleibt, es entsteht ein neuer.
    assert ar.async_get(hass).async_get_area(bereich.id).name == "Mein Bereich"
    neu = ar.async_get(hass).async_get_area_by_name("Hofläden")
    assert neu is not None and neu.id != bereich.id


async def test_leere_namen_fallen_auf_standard_zurueck(hass: HomeAssistant) -> None:
    entry = _entry(hass, {CONF_BEREICH_NAME: "   ", CONF_LABEL_NAME: ""})
    await _einrichten(hass, entry, "hof-1")
    assert ar.async_get(hass).async_get_area_by_name("HofKarte") is not None
    assert lr.async_get(hass).async_get_label_by_name("HofKarte") is not None
