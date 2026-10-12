"""Detail & Erfassung, Phase 8: Zugänglichkeit (Fokusführung, Beschriftungen, Statusmeldungen)."""

from __future__ import annotations

from pathlib import Path

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_QUELLTEXT = (Path(__file__).parent.parent / "static" / "hofkarte-panel.js").read_text(encoding="utf-8")

_START = r"""
const t = bauen({ n: 2 });
await sleep(100);
const el = t.el;
const item = t.items[0];
Object.assign(item, { website: "https://hof.example/", latitude: 46.9, longitude: 7.4, bewertung: 2 });
await el.load(); await sleep(30);
el._kiEntitaet = null;
const abos = [];
el.hass.connection.subscribeMessage = async (cb, m) => { abos.push({ cb, m }); return () => {}; };
const orig = el.hass.connection.sendMessagePromise;
el.hass.connection.sendMessagePromise = async (m) => {
  if (m.type === "hofkarte/management/discover") return { kandidaten: [{ refs: ["node/1"], name: "Hof A", latitude: 46.9, longitude: 7.4, entfernung_meter: 10, konfidenz: "hoch" }] };
  if (m.type === "hofkarte/management/save") return { konflikt: false, hofladen: { ...m.hofladen, id: "f".repeat(32) } };
  return orig(m);
};
t.w.Object.defineProperty(t.w.navigator, "geolocation", { configurable: true, value: { getCurrentPosition: (ok) => ok({ coords: { latitude: 46.9, longitude: 7.4, accuracy: 5 } }) } });
t.w.confirm = () => true;
const fokus = () => { const a = el.shadowRoot.activeElement; return a ? (a.matches(".erfassen-titel") ? "titel:" + a.textContent.trim() : a.tagName.toLowerCase()) : "keiner"; };
"""


@braucht_jsdom
def test_fokus_wandert_bei_schrittwechsel_auf_die_ueberschrift() -> None:
    e = _node(
        _START
        + r"""
    const f = {};
    await t.klick("[data-erfassen-open]", 30); f.einstieg = fokus();
    await t.klick("[data-vorort-start]", 80); f.vorOrt1 = fokus();
    await t.klick('[data-vorort-kandidat="0"]', 40); f.vorOrt2 = fokus();
    tipp = (sel, v) => { const x = t.q(sel); x.value = v; x.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); };
    await t.klick("[data-vorort-speichern]", 150); f.vorOrt3 = fokus();
    await t.klick("[data-vorort-fertig]", 30);
    // Webseite
    await t.klick("[data-erfassen-open]", 30);
    tipp("[data-erfassen-url]", "https://hof.example/");
    await t.klick("[data-erfassen-auslesen]", 40); f.web2 = fokus();
    abos[0].cb({ phase: "fertig", vorschlag: { daten: { name: "Hof" }, quellen: [], abweichungen: {} } }); await sleep(30); f.web3 = fokus();
    await t.klick("[data-web-zurueck]", 30);
    await t.klick("[data-erfassen-zurueck]", 30);
    // Ergänzen
    el.view(el.items[0]); await sleep(20);
    await t.klick("[data-ergaenzen]", 30); f.erg1 = fokus();
    await t.klick("[data-erg-start]", 80); f.erg2 = fokus();
    console.log(JSON.stringify(f));
    process.exit(0);
    """
    )
    assert e["einstieg"] == "titel:Hofladen erfassen"
    assert e["vorOrt1"] == "titel:Vor Ort erfassen" and e["vorOrt2"] == "titel:Schnell erfassen" and e["vorOrt3"] == "titel:Gespeichert"
    assert e["web2"] == "titel:Webseite wird ausgelesen" and e["web3"] == "titel:Angaben prüfen"
    assert e["erg1"] == "titel:Angaben ergänzen" and e["erg2"] == "titel:Angaben ergänzen"


@braucht_jsdom
def test_ablaeufe_haben_h1_schrittanzeige_mit_aria_current_und_statusmeldungen_mit_text() -> None:
    e = _node(
        _START
        + r"""
    const r = {};
    await t.klick("[data-erfassen-open]", 30);
    tipp = (sel, v) => { const x = t.q(sel); x.value = v; x.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); };
    tipp("[data-erfassen-url]", "https://hof.example/");
    await t.klick("[data-erfassen-auslesen]", 40);
    abos[0].cb({ phase: "website", status: "ok" }); await sleep(20);
    r.h1 = t.qa("h1").length; r.tab = t.q("h1").getAttribute("tabindex");
    r.aktuell = t.qa('.web-schritte [aria-current="step"]').map((x) => x.textContent.replace(/\s+/g, " ").trim());
    r.liste = t.q(".web-schritte").getAttribute("aria-label");
    r.statusRolle = t.q(".web-status-liste").getAttribute("role");
    r.statusText = t.q(".web-status-liste").textContent.replace(/\s+/g, " ");
    r.icons = t.qa(".web-status .gruppe-punkt").every((x) => x.getAttribute("aria-hidden") === "true");
    abos[0].cb({ phase: "fertig", vorschlag: { daten: { name: "Hof", mobilnummer: "031 1" }, quellen: [], abweichungen: {} } }); await sleep(30);
    r.cb = t.qa("[data-web-feldwahl]").length;
    r.vorschau = t.q("[data-web-vorschau]").getAttribute("aria-label");
    console.log(JSON.stringify(r));
    process.exit(0);
    """
    )
    assert e["h1"] == 1 and e["tab"] == "-1" and e["aktuell"] == ["2Auslesen"]
    assert e["liste"] == "Fortschritt" and e["statusRolle"] == "status" and e["icons"] is True
    assert "Erledigt:" in e["statusText"]
    assert e["cb"] == 2 and e["vorschau"] == "Vorschau"


@braucht_jsdom
def test_abgleich_checkboxen_haben_namen_und_filter_zeigen_zustand() -> None:
    e = _node(
        _START
        + r"""
    el.view(el.items[0]); await sleep(20);
    await t.klick("[data-ergaenzen]", 30);
    await t.klick("[data-erg-start]", 80);
    abos[0].cb({ phase: "fertig", vorschlag: { daten: { mobilnummer: "031 111", adresse: "Weg 1" }, quellen: [{ feld: "mobilnummer", quelle: "website" }], abweichungen: {} } }); await sleep(30);
    console.log(JSON.stringify({
      namen: t.qa("[data-erg-feldwahl]").map((c) => c.getAttribute("aria-label")),
      filter: t.qa("[data-erg-filter]").map((b) => b.getAttribute("aria-pressed")),
      liste: t.q(".erg-liste").getAttribute("role"), eintraege: t.qa(".erg-zeile").every((z) => z.getAttribute("role") === "listitem"),
      status: t.q(".erg-badge").textContent.trim(), sr: t.q(".web-ablauf").textContent.includes("Erledigt:") || t.q(".web-ablauf").textContent.includes("Hinweis:"),
    }));
    process.exit(0);
    """
    )
    assert "Telefon übernehmen" in e["namen"] and e["filter"] == ["true", "false"]
    assert e["liste"] == "list" and e["eintraege"] and e["sr"]


def test_reduzierte_bewegung_und_fokusrahmen_im_quelltext() -> None:
    assert "prefers-reduced-motion:reduce" in _QUELLTEXT
    assert "button:focus-visible" in _QUELLTEXT and "input:focus-visible" in _QUELLTEXT
    assert ".sr-nur{" in _QUELLTEXT
    # Jede Übergangs-/Animationsangabe ist durch reduzierte Bewegung abgedeckt (aktuell nur der Gruppenpfeil).
    uebergaenge = [z for z in _QUELLTEXT.splitlines() if ("transition:" in z or "animation:" in z) and "@media" not in z]
    assert len(uebergaenge) == 1 and "gruppe-pfeil" in uebergaenge[0]
