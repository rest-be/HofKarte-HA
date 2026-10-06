"""Verhaltenstests für den Dialog "Hofladen finden" (Discovery, Phase 5).

Laufen mit Node und ``jsdom`` (wie ``test_static_panel_js_block_c.py``);
fehlt beides, werden sie übersprungen. Der Server (WebSocket) wird
nachgebildet; Geolocation des Browsers wird je Test gesetzt.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parent.parent / "static"


def _jsdom_vorhanden() -> bool:
    if shutil.which("node") is None:
        return False
    return subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True, timeout=20).returncode == 0


braucht_jsdom = pytest.mark.skipif(not _jsdom_vorhanden(), reason="Node/jsdom nicht verfügbar")

_HARNESS = r"""
const fs = require("fs");
const { JSDOM } = require("jsdom");
const STATIC = process.env.HOFKARTE_STATIC;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const KANDIDAT = (extra = {}) => ({
  refs: ["node/1"], name: "Famille Martin", weitere_namen: [], latitude: 46.5, longitude: 6.8, entfernung_meter: 8,
  typ: ["shop=farm"], adresse: "Chemin 4", plz: "1070", ort: "Puidoux", website: "https://martin.example", telefon: null,
  email: null, oeffnungszeiten: null, score: 0.95, konfidenz: "hoch", signale: { distanz: 1, name: 0.3, website: false }, ...extra,
});
function bauen({ geo = "fehler", items = [], discover = null, haConfig = { latitude: 46.948, longitude: 7.4474 }, unsicher = false } = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only", url: "https://ha.example/", pretendToBeVisual: true });
  const w = dom.window;
  const log = { calls: [], subs: [], unsubs: 0, geoAufrufe: 0 };
  const geoObj = {
    getCurrentPosition(ok, fail) {
      log.geoAufrufe++;
      if (geo === "fehler") setTimeout(() => fail({ code: 1 }), 0);
      else if (geo === "ok") setTimeout(() => ok({ coords: { latitude: 46.123456789, longitude: 6.987654321, accuracy: 12.4 } }), 0);
      // "haengt": nie antworten
    },
  };
  if (geo !== "keine") Object.defineProperty(w.navigator, "geolocation", { value: geoObj, configurable: true });
  if (unsicher) Object.defineProperty(w, "isSecureContext", { value: false, configurable: true });
  const hass = {
    config: haConfig,
    connection: {
      sendMessagePromise: async (m) => {
        log.calls.push(m);
        if (m.type.endsWith("settings")) return { einstellungen: {} };
        if (m.type.endsWith("/list")) return { hoflaeden: items };
        if (m.type.endsWith("/discover")) { if (discover instanceof Error) throw discover; return discover || { kandidaten: [KANDIDAT()], radius: m.radius }; }
        if (m.type.endsWith("/save")) return { konflikt: false, hofladen: m.hofladen };
        return {};
      },
      subscribeMessage: async (cb, m) => { const sub = { cb, m }; log.subs.push(sub); return () => { log.unsubs++; }; },
    },
  };
  w.eval(fs.readFileSync(STATIC + "/hofkarte-panel.js", "utf8"));
  const el = w.document.createElement("hofkarte-panel");
  w.document.body.appendChild(el);
  el.hass = hass;
  const sr = el.shadowRoot;
  const q = (s) => sr.querySelector(s);
  const klick = async (sel, warte = 20) => { const e = q(sel); if (!e) throw new Error("fehlt: " + sel); e.dispatchEvent(new w.MouseEvent("click", { bubbles: true, composed: true })); await sleep(warte); };
  const tippe = async (sel, wert) => { const e = q(sel); e.value = wert; e.dispatchEvent(new w.Event("input", { bubbles: true, composed: true })); await sleep(5); };
  const wahl = async (sel, checked) => { const e = q(sel); e.checked = checked; e.dispatchEvent(new w.Event("change", { bubbles: true, composed: true })); await sleep(5); };
  const ereignis = async (sub, e) => { sub.cb(e); await sleep(5); };
  const fertig = (daten, quellen = {}, abweichungen = {}) => ({ phase: "fertig", vorschlag: { daten, quellen, abweichungen } });
  return { w, el, sr, q, log, klick, tippe, wahl, ereignis, fertig, hass };
}
"""


def _node(test_js: str) -> dict:
    skript = _HARNESS + "\n(async () => {\n" + test_js + "\n})().catch((e) => { console.error(e); process.exit(1); });"
    r = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, timeout=60,
        env={**os.environ, "HOFKARTE_STATIC": str(_STATIC)},
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_panel_js_syntaktisch_gueltig() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node nicht verfügbar")
    r = subprocess.run(["node", "--check", str(_STATIC / "hofkarte-panel.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@braucht_jsdom
def test_dialog_oeffnet_und_uebernimmt_geraetestandort() -> None:
    e = _node(r"""
    const t = bauen({ geo: "ok" });
    await sleep(50);
    await t.klick("[data-finden-open]", 60);
    console.log(JSON.stringify({
      lat: t.q('[data-finden-feld="latitude"]').value, lon: t.q('[data-finden-feld="longitude"]').value,
      status: t.q("[data-finden-standort-text]").textContent, geo: t.log.geoAufrufe,
      keinSuchaufruf: !t.log.calls.some(c => c.type.endsWith("/discover")),
      radius: t.q("[data-finden-radius]").value,
    }));
    process.exit(0);
    """)
    assert (e["lat"], e["lon"]) == ("46.123457", "6.987654")
    assert "Gerät" in e["status"] and "±12 m" in e["status"]
    assert e["geo"] == 1 and e["keinSuchaufruf"], "Suche darf nie automatisch starten"
    assert e["radius"] == "2000"


@braucht_jsdom
@pytest.mark.parametrize("geo", ["fehler", "keine"])
def test_ohne_geraetestandort_bleibt_ha_standort(geo: str) -> None:
    e = _node(
        'const t = bauen({ geo: "%s" }); await sleep(50); await t.klick("[data-finden-open]", 60);' % geo
        + r"""
    console.log(JSON.stringify({ lat: t.q('[data-finden-feld="latitude"]').value, status: t.q("[data-finden-standort-text]").textContent }));
    process.exit(0);
    """)
    assert e["lat"] == "46.948" and "Home Assistant" in e["status"]


@braucht_jsdom
def test_eingaben_gehen_beim_rerender_nicht_verloren_und_geo_antwort_stoert_nicht() -> None:
    e = _node(r"""
    const t = bauen({ geo: "ok" });
    await sleep(50);
    await t.klick("[data-finden-open]", 0);
    await t.tippe('[data-finden-feld="name"]', "Hofladen Rohrer");
    await sleep(60); // Geolocation-Antwort trifft ein
    t.el.render();
    console.log(JSON.stringify({ name: t.q('[data-finden-feld="name"]').value }));
    process.exit(0);
    """)
    assert e["name"] == "Hofladen Rohrer"


@braucht_jsdom
def test_suche_sendet_erwartete_nachricht_und_waehlt_hohe_konfidenz_vor() -> None:
    e = _node(r"""
    const t = bauen({ geo: "fehler" });
    await sleep(50);
    await t.klick("[data-finden-open]", 40);
    await t.tippe('[data-finden-feld="name"]', "  Boucherie de Campagne ");
    await t.tippe("[data-finden-radius]", "3500");
    await t.wahl("[data-finden-erweitert]", true);
    await t.klick("[data-finden-suchen]", 40);
    const m = t.log.calls.find(c => c.type.endsWith("/discover"));
    console.log(JSON.stringify({ m,
      schritt2: !!t.q("[data-finden-kandidat]"),
      vorgewaehlt: t.q("[data-finden-kandidat]").checked,
      weiterAus: t.q("[data-finden-weiter]").disabled,
      text: t.q("[data-finden-dialog]").textContent }));
    process.exit(0);
    """)
    m = e["m"]
    assert m == {
        "type": "hofkarte/management/discover", "latitude": 46.948, "longitude": 7.4474,
        "radius": 3500, "erweitert": True, "name": "Boucherie de Campagne",
    }
    assert e["schritt2"] and e["vorgewaehlt"] and not e["weiterAus"]
    assert "Famille Martin" in e["text"] and "hohe Sicherheit" in e["text"] and "sehr nah (8 m)" in e["text"]


@braucht_jsdom
def test_niedrige_konfidenz_wird_nicht_vorgewaehlt() -> None:
    e = _node(r"""
    const t = bauen({ discover: { kandidaten: [KANDIDAT({ konfidenz: "niedrig", score: 0.1 })] } });
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40);
    console.log(JSON.stringify({ vor: t.q("[data-finden-kandidat]").checked, weiterAus: t.q("[data-finden-weiter]").disabled }));
    process.exit(0);
    """)
    assert e["vor"] is False and e["weiterAus"] is True


@braucht_jsdom
def test_ungueltige_koordinaten_rufen_den_server_nicht_auf() -> None:
    e = _node(r"""
    const t = bauen({ geo: "fehler" });
    await sleep(50); await t.klick("[data-finden-open]", 20);
    await t.tippe('[data-finden-feld="latitude"]', "abc");
    await t.klick("[data-finden-suchen]", 20);
    console.log(JSON.stringify({ calls: t.log.calls.filter(c => c.type.endsWith("/discover")).length, fehler: t.q(".notice.error")?.textContent || "" }));
    process.exit(0);
    """)
    assert e["calls"] == 0 and "Latitude" in e["fehler"]


@braucht_jsdom
def test_serverfehler_wird_angezeigt_und_dialog_bleibt_bedienbar() -> None:
    e = _node(r"""
    const err = Object.assign(new Error("x"), { code: "unreachable" });
    const t = bauen({ discover: err });
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40);
    console.log(JSON.stringify({ fehler: t.q(".notice.error").textContent, knopf: t.q("[data-finden-suchen]").disabled }));
    process.exit(0);
    """)
    assert "Overpass" in e["fehler"] and e["knopf"] is False


@braucht_jsdom
def test_keine_treffer_bietet_website_und_manuell_an() -> None:
    e = _node(r"""
    const t = bauen({ discover: { kandidaten: [] } });
    await sleep(50); await t.klick("[data-finden-open]", 20);
    await t.tippe('[data-finden-feld="name"]', "Beutlers Hoflädeli");
    await t.tippe('[data-finden-feld="website"]', "https://beutlers.example");
    await t.klick("[data-finden-suchen]", 40);
    const hatNurWebsite = !!t.q("[data-finden-nur-website]");
    await t.klick("[data-finden-leer]", 30);
    const f = t.q("form");
    console.log(JSON.stringify({ hatNurWebsite, dialogWeg: !t.q("[data-finden-dialog]"),
      name: f.elements["name"].value, website: f.elements["website"].value, lat: f.elements["latitude"].value }));
    process.exit(0);
    """)
    assert e["hatNurWebsite"] and e["dialogWeg"]
    assert e["name"] == "Beutlers Hoflädeli" and e["website"] == "https://beutlers.example" and e["lat"] == "46.948"


@braucht_jsdom
def test_anreicherung_ereignisse_pruefansicht_und_uebernahme_mit_quellen() -> None:
    e = _node(r"""
    const t = bauen();
    await sleep(50); await t.klick("[data-finden-open]", 20);
    await t.tippe('[data-finden-feld="website"]', "https://martin.example");
    await t.klick("[data-finden-suchen]", 40);
    await t.klick("[data-finden-weiter]", 30);
    const sub = t.log.subs[0];
    const subNachricht = sub.m;
    const wartet = t.q("[data-finden-dialog]").textContent;
    await t.ereignis(sub, { phase: "osm", status: "ok" });
    await t.ereignis(sub, { phase: "website", status: "robots_gesperrt", url: "https://martin.example", seiten: 0 });
    const zwischen = t.q(".finden-fortschritt").textContent;
    const daten = { name: "Famille Martin", adresse: "Chemin 4", plz: "1070", ort: "Puidoux", email: "a@martin.example",
      oeffnungszeiten: [{ wochentag: 5, beginn: "09:00", ende: "12:00" }, { wochentag: 5, beginn: "14:00", ende: "18:00" }],
      angebote: ["Eier", "Milch"], latitude: 46.5, longitude: 6.8 };
    const quellen = {
      name: { quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/1", lizenz: "© OpenStreetMap-Mitwirkende (ODbL)" },
      adresse: { quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/1" },
      plz: { quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/1" },
      ort: { quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/1" },
      email: { quelle: "website", status: "confirmed", url: "https://martin.example/kontakt" },
      oeffnungszeiten: { quelle: "website", status: "confirmed", url: "https://martin.example/" },
      angebote: { quelle: "website", status: "confirmed", url: "https://martin.example/" },
      latitude: { quelle: "openstreetmap", status: "confirmed" }, longitude: { quelle: "openstreetmap", status: "confirmed" },
    };
    await t.ereignis(sub, t.fertig(daten, quellen, { oeffnungszeiten: "openstreetmap" }));
    const dlg = t.q("[data-finden-dialog]").textContent;
    const zeilen = t.sr.querySelectorAll("[data-finden-feldwahl]").length;
    const linkOsm = t.q('a[href="https://www.openstreetmap.org/node/1"]') !== null;
    await t.wahl('[data-finden-feldwahl="angebote"]', false);   // Angebote abwählen
    await t.klick("[data-finden-uebernehmen]", 30);
    const f = t.q("form");
    // Speichern -> Payload prüfen
    t.log.calls.length = 0;
    await t.el.save();
    await sleep(30);
    const save = t.log.calls.find(c => c.type.endsWith("/save"));
    console.log(JSON.stringify({ subNachricht, wartet, zwischen, dlg, zeilen, linkOsm, dialogWeg: !t.q("[data-finden-dialog]"),
      name: save.hofladen.name, plz: save.hofladen.plz, email: save.hofladen.email,
      zeiten: save.hofladen.oeffnungszeiten, angebote: save.hofladen.angebote, lat: save.hofladen.latitude,
      quellen: save.hofladen.quellen, unsubs: t.log.unsubs }));
    process.exit(0);
    """)
    assert e["subNachricht"]["type"] == "hofkarte/management/enrich"
    assert e["subNachricht"]["website"] == "https://martin.example" and e["subNachricht"]["kandidat"]["name"] == "Famille Martin"
    assert "OpenStreetMap" in e["wartet"]
    assert "verbietet automatisches Auslesen" in e["zwischen"]
    assert "Fr 09:00–12:00, 14:00–18:00" in e["dlg"] and "weicht von OpenStreetMap ab" in e["dlg"]
    assert "© OpenStreetMap-Mitwirkende (ODbL)" in e["dlg"]
    assert e["zeilen"] >= 6 and e["linkOsm"] and e["dialogWeg"]
    assert (e["name"], e["plz"], e["email"]) == ("Famille Martin", "1070", "a@martin.example")
    assert e["zeiten"] == [
        {"wochentag": 5, "beginn": "09:00", "ende": "12:00"}, {"wochentag": 5, "beginn": "14:00", "ende": "18:00"}
    ]
    assert e["angebote"] == [], "abgewählte Zeile darf nicht übernommen werden"
    assert e["lat"] == 46.5
    felder = {q["feld"] for q in e["quellen"]}
    assert felder == {"name", "adresse", "plz", "ort", "email", "oeffnungszeiten", "latitude", "longitude"}
    assert "angebote" not in felder
    assert all(set(q) == {"feld", "quelle", "status", "url", "lizenz"} for q in e["quellen"])
    assert e["unsubs"] >= 1, "Subscription muss nach 'fertig' abgemeldet werden"


@braucht_jsdom
def test_manuell_geaendertes_feld_verliert_herkunftsangabe() -> None:
    e = _node(r"""
    const t = bauen();
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40); await t.klick("[data-finden-weiter]", 30);
    await t.ereignis(t.log.subs[0], t.fertig({ name: "Famille Martin", email: "a@martin.example" },
      { name: { quelle: "openstreetmap", status: "confirmed" }, email: { quelle: "website", status: "confirmed" } }));
    await t.klick("[data-finden-uebernehmen]", 30);
    t.q("form").elements["email"].value = "ganz-anders@martin.example";   // von Hand geändert
    t.log.calls.length = 0;
    await t.el.save(); await sleep(30);
    const save = t.log.calls.find(c => c.type.endsWith("/save"));
    console.log(JSON.stringify({ felder: save.hofladen.quellen.map(q => q.feld) }));
    process.exit(0);
    """)
    assert e["felder"] == ["name"]


@braucht_jsdom
def test_enrich_fehler_beim_abonnieren_und_zurueck_meldet_ab() -> None:
    e = _node(r"""
    const t = bauen();
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40); await t.klick("[data-finden-weiter]", 30);
    await t.klick("[data-finden-zurueck]", 30);   // während der Anreicherung zurück
    await sleep(20);
    console.log(JSON.stringify({ unsubs: t.log.unsubs, schritt2: !!t.q("[data-finden-kandidat]") }));
    process.exit(0);
    """)
    assert e["unsubs"] == 1 and e["schritt2"]


@braucht_jsdom
def test_escape_schliesst_dialog_und_meldet_ab() -> None:
    e = _node(r"""
    const t = bauen();
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40); await t.klick("[data-finden-weiter]", 30);
    t.q("[data-finden-dialog]").dispatchEvent(new t.w.KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await sleep(30);
    console.log(JSON.stringify({ weg: !t.q("[data-finden-dialog]"), unsubs: t.log.unsubs, listeAnzeige: !!t.q("[data-new]") }));
    process.exit(0);
    """)
    assert e["weg"] and e["unsubs"] == 1 and e["listeAnzeige"]


@braucht_jsdom
def test_fremdtexte_werden_escaped_und_unsichere_links_nicht_gerendert() -> None:
    e = _node(r"""
    const boese = KANDIDAT({ name: '<img src=x onerror="window.__xss=1">', adresse: "<b>x</b>" });
    const t = bauen({ discover: { kandidaten: [boese] } });
    await sleep(50); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40);
    const imgs2 = t.sr.querySelectorAll("[data-finden-dialog] img").length;
    await t.wahl("[data-finden-kandidat]", true);
    await t.klick("[data-finden-weiter]", 30);
    await t.ereignis(t.log.subs[0], t.fertig({ name: "X" }, { name: { quelle: "website", status: "confirmed", url: "javascript:alert(1)" } }));
    const jsLink = t.sr.querySelectorAll('a[href^="javascript"]').length;
    console.log(JSON.stringify({ imgs2, xss: t.w.__xss === undefined, jsLink, b: t.sr.querySelectorAll("[data-finden-dialog] b").length }));
    process.exit(0);
    """)
    assert e["imgs2"] == 0 and e["xss"] and e["jsLink"] == 0 and e["b"] == 0


@braucht_jsdom
def test_bestehender_hofladen_wird_als_hinweis_angezeigt() -> None:
    e = _node(r"""
    const items = [{ id: "1", name: "famille martin", latitude: null, longitude: null, oeffnungszeiten: [], angebote: [], zahlungsarten: [], bilder: [], sonderoeffnungszeiten: [], bewertung: 0, geoeffnet: null }];
    const t = bauen({ items });
    await sleep(80); await t.klick("[data-finden-open]", 20); await t.klick("[data-finden-suchen]", 40);
    console.log(JSON.stringify({ hinweis: t.q(".finden-warnung")?.textContent || "" }));
    process.exit(0);
    """)
    assert "schon erfasst" in e["hinweis"]


@braucht_jsdom
def test_detailansicht_zeigt_herkunft() -> None:
    e = _node(r"""
    const item = { id: "1", name: "Hof", latitude: null, longitude: null, oeffnungszeiten: [], angebote: [], zahlungsarten: [], bilder: [], sonderoeffnungszeiten: [], bewertung: 0, geoeffnet: null,
      quellen: [{ feld: "name", quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/1", lizenz: null },
                { feld: "email", quelle: "website", status: "confirmed", url: "javascript:alert(1)", lizenz: null }] };
    const t = bauen({ items: [item] });
    await sleep(80);
    t.el.view(item);
    await sleep(20);
    console.log(JSON.stringify({ text: t.sr.textContent, osmLink: !!t.q('a[href="https://www.openstreetmap.org/node/1"]'), js: t.sr.querySelectorAll('a[href^="javascript"]').length }));
    process.exit(0);
    """)
    assert "Herkunft der Angaben" in e["text"] and "ODbL" in e["text"] and e["osmLink"] and e["js"] == 0


@braucht_jsdom
def test_unsicherer_kontext_wird_benannt_ohne_geolocation_aufruf() -> None:
    e = _node(r"""
    const t = bauen({ geo: "ok", unsicher: true });
    await sleep(50); await t.klick("[data-finden-open]", 60);
    console.log(JSON.stringify({ status: t.q("[data-finden-standort-text]").textContent, geo: t.log.geoAufrufe, lat: t.q('[data-finden-feld="latitude"]').value }));
    process.exit(0);
    """)
    assert "HTTPS" in e["status"] and e["geo"] == 0 and e["lat"] == "46.948"


@braucht_jsdom
def test_button_mein_standort_fragt_erneut() -> None:
    e = _node(r"""
    const t = bauen({ geo: "ok" });
    await sleep(50); await t.klick("[data-finden-open]", 40);
    await t.tippe('[data-finden-feld="latitude"]', "1");
    await t.klick("[data-finden-standort]", 40);
    console.log(JSON.stringify({ geo: t.log.geoAufrufe, lat: t.q('[data-finden-feld="latitude"]').value }));
    process.exit(0);
    """)
    assert e["geo"] == 2 and e["lat"] == "46.123457"
