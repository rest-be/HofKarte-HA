"""F6 (Code Review 2026.9.2): zeitgenaue Statuswechsel.

Teil 1: reine Planungsfunktion ``naechster_statuswechsel`` (hass-frei).
Teil 2: Entity-/Coordinator-Verhalten (im Stil der übrigen Entity-Tests; in
der Sandbox mit der angepassten Home-Assistant-Testumgebung ausgeführt).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hofkarte.const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from custom_components.hofkarte.models import Hofladen, Oeffnungszeit, Sonderoeffnungszeit
from custom_components.hofkarte.opening_hours import (
    get_next_closing,
    get_next_opening,
    is_open,
    naechster_statuswechsel,
)

_ZH = ZoneInfo("Europe/Zurich")


def _hof(**kw: Any) -> Hofladen:
    return Hofladen(id="hof-1", name="Hof", **kw)


def _dt(y: int, m: int, d: int, h: int, mi: int = 0, tz=_ZH) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=tz)


# --- reine Funktion ------------------------------------------------------------


def test_ohne_oeffnungszeiten_nichts_zu_planen() -> None:
    assert naechster_statuswechsel(_hof(), _dt(2026, 1, 5, 12)) is None


def test_geschlossen_vor_oeffnung_naechster_wechsel_ist_der_beginn() -> None:
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),))
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 6, 30)) == _dt(2026, 1, 5, 8)


def test_offen_naechster_wechsel_ist_das_ende() -> None:
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),))
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 10)) == _dt(2026, 1, 5, 12)


def test_genau_auf_der_grenze_wird_der_naechste_wechsel_gesucht() -> None:
    """Strikt nach ``now``: sonst würde um 08:00:00 erneut 08:00:00 geplant."""
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),))
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 8)) == _dt(2026, 1, 5, 12)


def test_nach_der_letzten_schliessung_des_tages_ist_es_mitternacht() -> None:
    """Nur montags offen: Dienstag 00:00 verschiebt das Suchfenster -> Mitternacht
    ist früher als der nächste Montag."""
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),))
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 13)) == _dt(2026, 1, 6, 0)


def test_mitternachtsueberschreitung() -> None:
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=5, beginn=time(22), ende=time(2)),))
    # Freitag 2026-01-09, 23:00: offen; Ende Samstag 02:00, aber vorher Mitternacht
    assert naechster_statuswechsel(hof, _dt(2026, 1, 9, 23)) == _dt(2026, 1, 10, 0)
    # Samstag 00:30: laufendes Intervall endet 02:00
    assert naechster_statuswechsel(hof, _dt(2026, 1, 10, 0, 30)) == _dt(2026, 1, 10, 2)


def test_sonderoeffnungszeit_ueberschreibt_regulaere_zeiten() -> None:
    hof = _hof(
        oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),),
        sonderoeffnungszeiten=(
            Sonderoeffnungszeit(datum_von=date(2026, 1, 5), datum_bis=date(2026, 1, 5), geschlossen=False, beginn=time(14), ende=time(16)),
        ),
    )
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 6)) == _dt(2026, 1, 5, 14)


def test_sonder_schliessung_laesst_nur_mitternacht_uebrig() -> None:
    hof = _hof(
        oeffnungszeiten=(Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),),
        sonderoeffnungszeiten=(
            Sonderoeffnungszeit(datum_von=date(2026, 1, 5), datum_bis=date(2026, 1, 5), geschlossen=True),
        ),
    )
    assert naechster_statuswechsel(hof, _dt(2026, 1, 5, 6)) == _dt(2026, 1, 6, 0)


def test_ergebnis_ist_nie_vor_now_und_liegt_hoechstens_bis_zur_naechsten_mitternacht() -> None:
    hof = _hof(oeffnungszeiten=tuple(Oeffnungszeit(wochentag=t, beginn=time(9), ende=time(17)) for t in range(1, 8)))
    jetzt = _dt(2026, 1, 5, 0)
    for minuten in range(0, 24 * 60, 37):
        n = jetzt + timedelta(minutes=minuten)
        w = naechster_statuswechsel(hof, n)
        assert w is not None and w > n
        assert w <= datetime.combine(n.date() + timedelta(days=1), time.min, tzinfo=_ZH)


def test_wechsel_stimmt_mit_dem_tatsaechlichen_statuswechsel_ueberein() -> None:
    """Zwischen ``now`` und dem geplanten Wechsel ändern sich Status und
    Folgezeitpunkte nicht; unmittelbar danach ggf. schon."""
    hof = _hof(oeffnungszeiten=(
        Oeffnungszeit(wochentag=1, beginn=time(8), ende=time(12)),
        Oeffnungszeit(wochentag=1, beginn=time(14), ende=time(18)),
    ))
    jetzt = _dt(2026, 1, 5, 7)
    for _ in range(8):
        w = naechster_statuswechsel(hof, jetzt)
        kurz_davor = w - timedelta(seconds=1)
        assert is_open(hof, kurz_davor) == is_open(hof, jetzt)
        assert get_next_opening(hof, kurz_davor) == get_next_opening(hof, jetzt)
        assert get_next_closing(hof, kurz_davor) == get_next_closing(hof, jetzt)
        jetzt = w


def test_sommerzeitumstellung_mitternacht_und_grenzen_bleiben_korrekt() -> None:
    """Zürich: Sommerzeit beginnt So 2026-03-29 um 02:00 -> 03:00."""
    hof = _hof(oeffnungszeiten=(Oeffnungszeit(wochentag=7, beginn=time(8), ende=time(12)),))
    # Samstag 23:00 (CET): nächster Wechsel ist Mitternacht (= 23:00 UTC)
    sa = _dt(2026, 3, 28, 23)
    assert naechster_statuswechsel(hof, sa) == _dt(2026, 3, 29, 0)
    # Sonntag 00:00 (CET) -> Beginn 08:00 CEST (= 06:00 UTC, nur 7 Stunden später)
    so = _dt(2026, 3, 29, 0)
    w = naechster_statuswechsel(hof, so)
    assert w == _dt(2026, 3, 29, 8)
    assert (w.astimezone(timezone.utc) - so.astimezone(timezone.utc)) == timedelta(hours=7)
    # Rückstellung: So 2026-10-25, 03:00 -> 02:00; 24h-Tag, Mitternacht korrekt
    w2 = naechster_statuswechsel(hof, _dt(2026, 10, 24, 23))
    assert w2 == _dt(2026, 10, 25, 0)


# --- Entities und Coordinator --------------------------------------------------


def test_coordinator_pollt_nicht_mehr_periodisch() -> None:
    assert DEFAULT_UPDATE_INTERVAL is None


def _entity_id(hass: HomeAssistant, domain: str, suffix: str) -> str:
    from homeassistant.helpers import entity_registry as er

    eid = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{DOMAIN}_{suffix}")
    assert eid is not None
    return eid


async def _einrichten(hass: HomeAssistant) -> Any:
    entry = MockConfigEntry(domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


async def test_binary_sensor_wechselt_zeitgenau_ohne_coordinator_update(
    hass: HomeAssistant, freezer: Any
) -> None:
    tz = dt_util.DEFAULT_TIME_ZONE
    montag = datetime(2026, 1, 5, 7, 59, 30, tzinfo=tz)
    freezer.move_to(montag)
    coordinator = await _einrichten(hass)
    await coordinator.async_save_hofladen({
        "id": "hof-1", "name": "Hof",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "08:00", "ende": "12:00"}],
    })
    await hass.async_block_till_done()
    entity_id = _entity_id(hass, "binary_sensor", "hof-1_geoeffnet")
    assert hass.states.get(entity_id).state == "off"

    freezer.move_to(datetime(2026, 1, 5, 8, 0, 1, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    freezer.move_to(datetime(2026, 1, 5, 12, 0, 1, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"


async def test_sensor_naechste_oeffnung_springt_zum_statuswechsel(
    hass: HomeAssistant, freezer: Any
) -> None:
    tz = dt_util.DEFAULT_TIME_ZONE
    freezer.move_to(datetime(2026, 1, 5, 7, 59, 30, tzinfo=tz))
    coordinator = await _einrichten(hass)
    await coordinator.async_save_hofladen({
        "id": "hof-1", "name": "Hof",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "08:00", "ende": "12:00"}],
    })
    await hass.async_block_till_done()
    sensor_id = _entity_id(hass, "sensor", "hof-1_naechste_oeffnung")
    zuerst = hass.states.get(sensor_id).state
    freezer.move_to(datetime(2026, 1, 5, 8, 0, 1, tzinfo=tz))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    danach = hass.states.get(sensor_id).state
    assert zuerst != danach, "nächste Öffnung muss nach dem Beginn auf den Folgetermin springen"


async def test_zeitplan_wird_bei_datenaenderung_neu_berechnet_und_beim_entfernen_abgemeldet(
    hass: HomeAssistant, freezer: Any
) -> None:
    from custom_components.hofkarte import entity as entity_modul

    tz = dt_util.DEFAULT_TIME_ZONE
    freezer.move_to(datetime(2026, 1, 5, 7, 0, 0, tzinfo=tz))
    angemeldet: list[Any] = []
    abgemeldet: list[Any] = []
    original = entity_modul.async_track_point_in_time

    def spion(hass_, aktion, zeitpunkt):
        angemeldet.append(zeitpunkt)
        abmelden = original(hass_, aktion, zeitpunkt)

        def wrapper() -> None:
            abgemeldet.append(zeitpunkt)
            abmelden()

        return wrapper

    entity_modul.async_track_point_in_time = spion
    try:
        coordinator = await _einrichten(hass)
        await coordinator.async_save_hofladen({
            "id": "hof-1", "name": "Hof",
            "oeffnungszeiten": [{"wochentag": 1, "beginn": "08:00", "ende": "12:00"}],
        })
        await hass.async_block_till_done()
        erster = set(angemeldet)
        assert datetime(2026, 1, 5, 8, 0, tzinfo=tz) in erster

        # geänderte Öffnungszeiten -> neuer Zeitpunkt, alter Timer abgemeldet
        await coordinator.async_save_hofladen({
            "id": "hof-1", "name": "Hof",
            "oeffnungszeiten": [{"wochentag": 1, "beginn": "09:00", "ende": "12:00"}],
        })
        await hass.async_block_till_done()
        assert datetime(2026, 1, 5, 9, 0, tzinfo=tz) in set(angemeldet)
        assert datetime(2026, 1, 5, 8, 0, tzinfo=tz) in set(abgemeldet)

        # Entladen der Config Entry meldet alle Timer ab (async_on_remove)
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert Counter(abgemeldet) == Counter(angemeldet), "jeder Timer wurde abgemeldet"
    finally:
        entity_modul.async_track_point_in_time = original


async def test_devices_werden_nur_bei_aenderung_von_menge_oder_namen_abgeglichen(
    hass: HomeAssistant,
) -> None:
    from unittest.mock import patch

    import custom_components.hofkarte as integration

    with patch.object(integration, "async_sync_devices", wraps=integration.async_sync_devices) as sync:
        coordinator = await _einrichten(hass)
        nach_start = sync.call_count
        await coordinator.async_save_hofladen({"id": "hof-1", "name": "Hof"})
        assert sync.call_count == nach_start + 1, "neuer Hofladen -> Abgleich"
        await coordinator.async_save_hofladen({"id": "hof-1", "name": "Hof", "beschreibung": "x"})
        await coordinator.async_update_hofladen_sortiment("hof-1", angebote=[])
        assert sync.call_count == nach_start + 1, "kein Abgleich ohne Namens-/Mengenänderung"
        await coordinator.async_save_hofladen({"id": "hof-1", "name": "Hof neu"})
        assert sync.call_count == nach_start + 2, "Namensänderung -> Abgleich"
        await coordinator.async_delete_hofladen("hof-1")
        assert sync.call_count == nach_start + 3, "Löschen -> Abgleich"
