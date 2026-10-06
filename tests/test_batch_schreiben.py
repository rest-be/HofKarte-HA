"""F5 (Code Review 2026.9.2): Batch-Schreiben, inkrementelles Update,
Duplikat-Index."""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import (
    HofKarteUpdateCoordinator,
    HofladenVersionConflictError,
)
from custom_components.hofkarte.data_provider import (
    HofladenNotFoundError,
    StaticTestDataProvider,
    StorageHofladenDataProvider,
    _wende_aenderungen_an,
)
from custom_components.hofkarte.management import (
    _DuplikatIndex,
    _normalisiert,
    ws_import_commit,
    ws_import_preview,
)
from custom_components.hofkarte.models import Hofladen
from custom_components.hofkarte.parsing import HofladenValidationError


class _Verbindung:
    def __init__(self) -> None:
        self.user = SimpleNamespace(is_admin=True)
        self.results: list[Any] = []
        self.errors: list[Any] = []

    def send_result(self, msg_id: Any, data: Any = None) -> None:
        self.results.append(data)

    def send_error(self, msg_id: Any, code: str, message: str) -> None:
        self.errors.append((code, message))


async def _einrichten(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


def _roh(i: int) -> dict[str, Any]:
    return {"id": f"hof-{i}", "name": f"Hofladen {i}", "adresse": f"Weg {i}"}


# --- reine Änderungsfunktion ---------------------------------------------------


def test_aenderungen_mischen_haengen_an_und_loeschen_ohne_das_original_zu_aendern() -> None:
    original = [{"id": "a", "name": "A", "ort": "X"}, {"id": "b", "name": "B"}]
    kopie = [dict(r) for r in original]
    neu = _wende_aenderungen_an(
        original, [{"id": "a", "name": "A2"}, {"id": "c", "name": "C"}], ["b"]
    )
    assert neu == [{"id": "a", "name": "A2", "ort": "X"}, {"id": "c", "name": "C"}]
    assert original == kopie, "Original darf nicht verändert werden"


def test_aenderungen_unbekannte_loeschung_wirft_ohne_teilergebnis() -> None:
    original = [{"id": "a", "name": "A"}]
    with pytest.raises(HofladenNotFoundError):
        _wende_aenderungen_an(original, [{"id": "n", "name": "N"}], ["gibt-es-nicht"])
    assert original == [{"id": "a", "name": "A"}]


async def test_static_provider_apply_changes_ist_atomar() -> None:
    provider = StaticTestDataProvider([{"id": "a", "name": "A"}])
    with pytest.raises(HofladenNotFoundError):
        await provider.async_apply_changes([{"id": "b", "name": "B"}], ["x"])
    assert await provider.async_fetch_raw_hoflaeden() == [{"id": "a", "name": "A"}]
    await provider.async_apply_changes([{"id": "b", "name": "B"}], ["a"])
    assert await provider.async_fetch_raw_hoflaeden() == [{"id": "b", "name": "B"}]


async def test_storage_provider_speichert_batch_genau_einmal(hass: HomeAssistant) -> None:
    provider = StorageHofladenDataProvider(hass)
    gespeichert: list[int] = []
    original_save = provider._store.async_save

    async def zaehlend(daten: Any) -> None:
        gespeichert.append(len(daten))
        await original_save(daten)

    provider._store.async_save = zaehlend  # type: ignore[method-assign]
    await provider.async_apply_changes([_roh(i) for i in range(500)])
    assert gespeichert == [500]
    assert len(await provider.async_fetch_raw_hoflaeden()) == 500


async def test_storage_provider_bei_speicherfehler_bleibt_speicherstand_unveraendert(
    hass: HomeAssistant,
) -> None:
    provider = StorageHofladenDataProvider(hass)
    await provider.async_add_raw_hofladen(_roh(1))

    async def fehler(daten: Any) -> None:
        raise OSError("Platte voll")

    provider._store.async_save = fehler  # type: ignore[method-assign]
    with pytest.raises(OSError):
        await provider.async_apply_changes([_roh(2)])
    assert [r["id"] for r in await provider.async_fetch_raw_hoflaeden()] == ["hof-1"]


# --- Coordinator: Import = ein Schreibvorgang, ein Update ----------------------


async def test_import_von_500_datensaetzen_ein_store_schreibvorgang_ein_update(
    hass: HomeAssistant,
) -> None:
    coordinator = await _einrichten(hass)
    provider = coordinator._provider
    schreibvorgaenge: list[int] = []
    original_save = provider._store.async_save

    async def zaehlend(daten: Any) -> None:
        schreibvorgaenge.append(len(daten))
        await original_save(daten)

    provider._store.async_save = zaehlend  # type: ignore[method-assign]

    updates: list[int] = []
    coordinator.async_add_listener(lambda: updates.append(1))
    abrufe: list[int] = []
    original_fetch = provider.async_fetch_raw_hoflaeden

    async def fetch_zaehlend() -> Any:
        abrufe.append(1)
        return await original_fetch()

    provider.async_fetch_raw_hoflaeden = fetch_zaehlend  # type: ignore[method-assign]
    parse_aufrufe: list[int] = []
    original_parse = coordinator.parse_roh

    def parse_zaehlend(*args: Any, **kwargs: Any) -> Any:
        parse_aufrufe.append(1)
        return original_parse(*args, **kwargs)

    coordinator.parse_roh = parse_zaehlend  # type: ignore[method-assign]

    verbindung = _Verbindung()
    ws_import_commit(
        hass,
        verbindung,
        {
            "id": 1,
            "type": "hofkarte/management/import_commit",
            "eintraege": [
                {"hofladen": {"name": f"Import {i}", "adresse": f"Weg {i}"}, "aktion": "neu"}
                for i in range(500)
            ],
        },
    )
    await hass.async_block_till_done()

    assert verbindung.errors == []
    assert verbindung.results == [{"importiert": 500, "aktualisiert": 0, "uebersprungen": 0}]
    assert schreibvorgaenge == [500], "genau ein Store-Schreibvorgang"
    assert updates == [1], "genau ein Coordinator-Update"
    assert abrufe == [], "kein Neu-Lesen/Neu-Parsen aller Datensätze (kein async_refresh)"
    assert len(parse_aufrufe) == 500, "jeder Datensatz wird genau einmal geparst"
    assert len(coordinator.data) == 500


async def test_batch_ergebnis_identisch_zu_sequentiellem_speichern(hass: HomeAssistant) -> None:
    rohe = [_roh(i) for i in range(30)] + [{"id": "hof-3", "name": "Neu benannt"}]

    batch = HofKarteUpdateCoordinator(hass, StaticTestDataProvider([]), update_interval=None)
    await batch.async_refresh()
    await batch.async_save_many([dict(r) for r in rohe])

    einzeln = HofKarteUpdateCoordinator(hass, StaticTestDataProvider([]), update_interval=None)
    await einzeln.async_refresh()
    for r in rohe:
        await einzeln.async_save_hofladen(dict(r))

    assert batch.data == einzeln.data
    assert list(batch.data) == list(einzeln.data)
    assert batch.data["hof-3"].version == 2, "zweiter Eintrag derselben ID baut auf dem ersten auf"
    assert await batch._provider.async_fetch_raw_hoflaeden() == await einzeln._provider.async_fetch_raw_hoflaeden()


async def test_batch_ist_fail_fast_ein_ungueltiger_datensatz_schreibt_nichts(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider, update_interval=None)
    await coordinator.async_refresh()
    with pytest.raises(HofladenValidationError):
        await coordinator.async_save_many([_roh(1), {"id": "kaputt", "name": ""}])
    assert await provider.async_fetch_raw_hoflaeden() == []
    assert coordinator.data == {}


async def test_batch_versionskonflikt_schreibt_nichts(hass: HomeAssistant) -> None:
    provider = StaticTestDataProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider, update_interval=None)
    await coordinator.async_refresh()
    await coordinator.async_save_hofladen(_roh(1))
    with pytest.raises(HofladenVersionConflictError):
        await coordinator.async_save_many([_roh(2), {**_roh(1), "version": 99}])
    assert [r["id"] for r in await provider.async_fetch_raw_hoflaeden()] == ["hof-1"]


async def test_einzelschreibzugriffe_nutzen_inkrementelles_update_ohne_refresh(
    hass: HomeAssistant,
) -> None:
    provider = StaticTestDataProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider, update_interval=None)
    await coordinator.async_refresh()
    abrufe: list[int] = []
    original_fetch = provider.async_fetch_raw_hoflaeden

    async def fetch_zaehlend() -> Any:
        abrufe.append(1)
        return await original_fetch()

    provider.async_fetch_raw_hoflaeden = fetch_zaehlend  # type: ignore[method-assign]
    updates: list[int] = []
    coordinator.async_add_listener(lambda: updates.append(1))

    await coordinator.async_save_hofladen(_roh(1))
    await coordinator.async_save_hofladen({**_roh(1), "name": "Umbenannt"})
    await coordinator.async_add_hofladen(_roh(2))
    await coordinator.async_update_hofladen_sortiment("hof-2", angebote=[])
    await coordinator.async_delete_hofladen("hof-1")

    assert abrufe == [1], "nur der Lesezugriff von async_update_hofladen_sortiment"
    assert updates == [1] * 5
    assert list(coordinator.data) == ["hof-2"]
    # Stand identisch zu einem vollständigen Neu-Parsen
    daten_vorher = dict(coordinator.data)
    await coordinator.async_refresh()
    assert coordinator.data == daten_vorher


# --- Duplikat-Index ------------------------------------------------------------


def _alt_finde_duplikat(hofladen: Hofladen, bestehende: list[Hofladen]) -> Hofladen | None:
    """Unveränderte Kopie der früheren linearen Implementierung."""
    ziel_name = _normalisiert(hofladen.name)
    for kandidat in bestehende:
        if _normalisiert(kandidat.name) != ziel_name:
            continue
        if hofladen.adresse and kandidat.adresse:
            if _normalisiert(hofladen.adresse) != _normalisiert(kandidat.adresse):
                continue
        return kandidat
    return None


def test_duplikat_index_liefert_dasselbe_wie_der_lineare_durchlauf() -> None:
    from custom_components.hofkarte.parsing import parse_hofladen

    zufall = random.Random(42)
    namen = ["Hof A", "hof a ", "Hof B", "Käserei", "KÄSEREI"]
    adressen = ["", "Weg 1", "weg 1 ", "Weg 2"]

    def neu(i: int) -> Hofladen:
        roh = {"id": f"h{i}", "name": zufall.choice(namen), "adresse": zufall.choice(adressen)}
        return parse_hofladen(roh)

    bestand = [neu(i) for i in range(60)]
    index = _DuplikatIndex(bestand)
    for i in range(200):
        kandidat = neu(1000 + i)
        assert index.finde(kandidat) is _alt_finde_duplikat(kandidat, bestand)


async def test_import_vorschau_nutzt_den_index_und_meldet_duplikate(hass: HomeAssistant) -> None:
    coordinator = await _einrichten(hass)
    await coordinator.async_save_many([_roh(i) for i in range(300)])
    verbindung = _Verbindung()
    ws_import_preview(
        hass,
        verbindung,
        {
            "id": 1,
            "type": "hofkarte/management/import_preview",
            "hoflaeden": [{"id": "x1", "name": "Hofladen 7", "adresse": "Weg 7"}, {"id": "x2", "name": "Unbekannt"}],
        },
    )
    assert verbindung.errors == []
    eintraege = verbindung.results[0]["eintraege"]
    assert eintraege[0]["duplikat_von"] == "hof-7"
    assert eintraege[1]["duplikat_von"] is None
