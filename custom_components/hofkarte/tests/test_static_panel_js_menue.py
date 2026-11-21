"""A1: Menü-Knopf des Panels auf schmalen Bildschirmen (iPhone).

Home Assistant zeigt für eigene Panels keine Kopfzeile; auf dem Smartphone
fehlt dadurch der Zugang zum Menü. Das Panel muss bei ``narrow`` einen
eigenen Knopf anbieten, der das Ereignis ``hass-toggle-menu`` auslöst.
"""

from __future__ import annotations

from pathlib import Path

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_QUELLTEXT = (Path(__file__).parent.parent / "static" / "hofkarte-panel.js").read_text(encoding="utf-8")


@braucht_jsdom
def test_menueleiste_ist_standardmaessig_und_bei_breitem_bildschirm_verborgen() -> None:
    e = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    const r = {};
    r.start = t.q(".menueleiste").hidden;
    t.el.narrow = false; r.breit = t.q(".menueleiste").hidden;
    r.getter = t.el.narrow;
    console.log(JSON.stringify(r));
    process.exit(0);
    """
    )
    assert e["start"] is True and e["breit"] is True and e["getter"] is False


@braucht_jsdom
def test_schmal_zeigt_knopf_mit_beschriftung_und_loest_menue_ereignis_aus() -> None:
    e = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    const r = { ereignisse: [] };
    t.w.document.addEventListener("hass-toggle-menu", (ev) => r.ereignisse.push({ bubbles: ev.bubbles, composed: ev.composed }));
    t.el.narrow = true;
    r.sichtbar = !t.q(".menueleiste").hidden;
    const knopf = t.q("[data-ha-menue]");
    r.label = knopf.getAttribute("aria-label");
    r.art = knopf.getAttribute("type");
    r.klasse = knopf.className;
    await t.klick(knopf, 10);
    await t.klick(knopf, 10);
    t.el.narrow = false;
    r.wiederVerborgen = t.q(".menueleiste").hidden;
    console.log(JSON.stringify(r));
    process.exit(0);
    """
    )
    assert e["sichtbar"] is True
    assert e["label"] == "Menü" and e["art"] == "button" and "icon-btn" in e["klasse"]
    # Je Klick genau ein Ereignis (bubbles + composed: erreicht HA über die Shadow-Grenze).
    assert e["ereignisse"] == [{"bubbles": True, "composed": True}] * 2
    assert e["wiederVerborgen"] is True


@braucht_jsdom
def test_menueleiste_bleibt_beim_neuzeichnen_und_im_editor_erhalten() -> None:
    e = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    t.el.narrow = true;
    const r = {};
    const knopf = t.q("[data-ha-menue]");
    t.el.render();
    r.gleicherKnopf = t.q("[data-ha-menue]") === knopf;
    await t.klick("[data-erfassen-open]", 30);
    r.imAblauf = !t.q(".menueleiste").hidden && !!t.q("[data-ha-menue]");
    // Die Leiste liegt ausserhalb von <main> und wird nicht mit ersetzt.
    r.ausserhalbMain = !t.q("main").contains(t.q(".menueleiste"));
    console.log(JSON.stringify(r));
    process.exit(0);
    """
    )
    assert e == {"gleicherKnopf": True, "imAblauf": True, "ausserhalbMain": True}


def test_menueleiste_beruecksichtigt_sicheren_bereich_und_touchflaeche() -> None:
    # Sicherer Bereich oben (Notch/Dynamic Island) und links/rechts (Querformat).
    assert "env(safe-area-inset-top" in _QUELLTEXT
    assert "env(safe-area-inset-left" in _QUELLTEXT and "env(safe-area-inset-right" in _QUELLTEXT
    # Knopf: gemeinsame Klasse mit 44 x 44 px Touchfläche.
    assert "button.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px" in _QUELLTEXT
    # Farben der HA-Kopfzeile mit Rückfall (Kontrast kommt vom Theme).
    assert "var(--app-header-background-color" in _QUELLTEXT and "var(--app-header-text-color" in _QUELLTEXT
    # Verborgen ist wirklich verborgen (display:flex würde [hidden] sonst überstimmen).
    assert ".menueleiste[hidden]{display:none}" in _QUELLTEXT
