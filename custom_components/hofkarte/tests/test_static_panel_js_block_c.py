"""Block C (Code Review 2026.9.2): F7 (Leaflet lokal), F8/F9 (Ladefehler ohne
Schleife), F10 (Performance der Übersicht), F14 (Vorschaubilder).

Statische Prüfungen laufen immer. Die Verhaltenstests brauchen Node und das
npm-Paket ``jsdom`` (Suchpfad über ``NODE_PATH``, z. B. ``npm i jsdom`` in
einem Verzeichnis ausserhalb des Repositorys); fehlt es, werden sie
übersprungen. Leaflet/markercluster stammen dabei aus ``static/vendor``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parent.parent / "static"
_PANEL_JS = _STATIC / "hofkarte-panel.js"
_VENDOR = _STATIC / "vendor"
_REPO = Path(__file__).resolve().parents[3]


def _quelle() -> str:
    return _PANEL_JS.read_text(encoding="utf-8")


def _jsdom_vorhanden() -> bool:
    if shutil.which("node") is None:
        return False
    r = subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True, timeout=20)
    return r.returncode == 0


_JSDOM = _jsdom_vorhanden()
braucht_jsdom = pytest.mark.skipif(not _JSDOM, reason="Node/jsdom nicht verfügbar")


# --- F7: lokal gebündelt -------------------------------------------------------


def test_kein_cdn_im_panel_und_in_der_integration() -> None:
    quelle = _quelle()
    assert "cdn.jsdelivr.net" not in quelle
    assert "unpkg.com" not in quelle
    for datei in (_STATIC).rglob("*.js"):
        if "vendor" in datei.parts:
            continue
        assert "cdn.jsdelivr.net" not in datei.read_text(encoding="utf-8"), datei


@pytest.mark.parametrize(
    "pfad",
    [
        "leaflet/leaflet.js",
        "leaflet/leaflet.css",
        "leaflet/LICENSE",
        "leaflet/images/marker-icon.png",
        "leaflet/images/layers.png",
        "leaflet.markercluster/leaflet.markercluster.js",
        "leaflet.markercluster/MarkerCluster.css",
        "leaflet.markercluster/MarkerCluster.Default.css",
        "leaflet.markercluster/LICENSE",
    ],
)
def test_vendor_dateien_vorhanden(pfad: str) -> None:
    assert (_VENDOR / pfad).is_file()


def test_panel_referenziert_lokale_vendor_pfade_mit_version() -> None:
    quelle = _quelle()
    assert '"/api/hofkarte/static/vendor"' in quelle
    assert "leaflet/leaflet.js?v=${LEAFLET_VERSION}" in quelle
    assert 'const LEAFLET_VERSION = "1.9.4";' in quelle
    assert 'const MARKERCLUSTER_VERSION = "1.5.3";' in quelle
    assert "1.9.4" in (_VENDOR / "leaflet" / "leaflet.js").read_text(encoding="utf-8")[:400]


def test_third_party_notices_nennen_bibliotheken_und_pruefsummen() -> None:
    import hashlib

    text = (_REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for name in ("Leaflet", "leaflet.markercluster", "BSD-2-Clause", "MIT"):
        assert name in text
    for datei in (
        _VENDOR / "leaflet" / "leaflet.js",
        _VENDOR / "leaflet.markercluster" / "leaflet.markercluster.js",
    ):
        assert hashlib.sha256(datei.read_bytes()).hexdigest() in text, datei.name


# --- F8/F9/F10 statisch --------------------------------------------------------


def test_initkarte_fehlerpfad_ruft_kein_render_auf() -> None:
    quelle = _quelle()
    start = quelle.index("  async initKarte() {")
    ende = quelle.index("  async aktualisiereMarker() {")
    funktion = quelle[start:ende]
    catch_block = funktion[funktion.index("catch (err)") : funktion.index("// Zwischenzeitlich")]
    assert "this.render()" not in catch_block
    assert "zeigeKarteFehler" in catch_block
    fehler = quelle[quelle.index("  zeigeKarteFehler(text) {") : quelle.index("  async initKarte() {")]
    assert "textContent" in fehler and "innerHTML" not in fehler


def test_style_wird_nur_einmal_gesetzt() -> None:
    quelle = _quelle()
    assert quelle.count("this.styles()") == 1
    assert "<style>${this.styles()}</style>" not in quelle


# --- Verhaltenstests (jsdom) ---------------------------------------------------

_HARNESS = r"""
const { JSDOM } = require("jsdom");
const fs = require("fs");
const STATIC = process.env.HOFKARTE_STATIC;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function bauen({ n = 10, listFehler = false, mitLeaflet = false, scriptModus = "ok" } = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only", url: "https://ha.example/", pretendToBeVisual: true });
  const w = dom.window;
  const log = { listAufrufe: 0, scriptAnfragen: [], timerDelays: [], listener: 0 };
  const origAdd = w.EventTarget.prototype.addEventListener;
  w.EventTarget.prototype.addEventListener = function (...a) { log.listener++; return origAdd.apply(this, a); };
  const origTimeout = w.setTimeout.bind(w);
  w.setTimeout = (fn, ms, ...r) => { if (ms >= 1000) { log.timerDelays.push(ms); return 0; } return origTimeout(fn, ms, ...r); };
  // Skripte werden nicht geladen: je nach Modus Fehler melden.
  const origAppend = w.document.head.appendChild.bind(w.document.head);
  w.document.head.appendChild = (el) => {
    if (el.tagName === "SCRIPT") {
      log.scriptAnfragen.push(el.src);
      origAppend(el);
      if (scriptModus === "fehler") origTimeout(() => el.onerror && el.onerror(new w.Event("error")), 0);
      return el;
    }
    return origAppend(el);
  };
  if (mitLeaflet) {
    w.eval(fs.readFileSync(STATIC + "/vendor/leaflet/leaflet.js", "utf8"));
    w.eval(fs.readFileSync(STATIC + "/vendor/leaflet.markercluster/leaflet.markercluster.js", "utf8"));
  }
  const items = Array.from({ length: n }, (_, i) => ({
    id: String(i).padStart(32, "0"), name: `Hof ${i} ${i % 2 ? "Müller" : "Meier"}`, adresse: "Weg " + i, plz: "8000", ort: "Ort", land: "CH",
    latitude: 46 + (i % 50) / 50, longitude: 7 + (i % 70) / 50, geoeffnet: i % 3 === 0 ? true : i % 3 === 1 ? false : null, bewertung: 0, website: "",
    bilder: i === 1 ? [{ url: "https://ha.example/api/image/serve/" + "a".repeat(32) + "/original", beschreibung: null, hochgeladen: true }] : [], hauptbild_url: i === 1 ? "https://ha.example/api/image/serve/" + "a".repeat(32) + "/original" : "",
    oeffnungszeiten: [], sonderoeffnungszeiten: [], angebote: [], zahlungsarten: [],
  }));
  const hass = { connection: { sendMessagePromise: async (m) => {
    if (m.type.endsWith("settings")) return { einstellungen: {} };
    log.listAufrufe++;
    if (listFehler) throw new Error("Server nicht erreichbar");
    return { hoflaeden: items };
  } } };
  w.eval(fs.readFileSync(STATIC + "/hofkarte-panel.js", "utf8"));
  const el = w.document.createElement("hofkarte-panel");
  w.document.body.appendChild(el);
  el.hass = hass;
  const klick = async (sel, warte = 50) => { el.shadowRoot.querySelector(sel).dispatchEvent(new w.MouseEvent("click", { bubbles: true, composed: true })); await sleep(warte); };
  return { w, el, sr: el.shadowRoot, log, hass, items, klick };
}
"""


def _node(test_js: str) -> dict:
    skript = _HARNESS + "\n(async () => {\n" + test_js + "\n})().catch((e) => { console.error(e); process.exit(1); });"
    r = subprocess.run(
        ["node", "-e", skript],
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "HOFKARTE_STATIC": str(_STATIC)},
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@braucht_jsdom
def test_f8_leaflet_ladefehler_loest_keine_schleife_aus_und_retry_ist_explizit() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ scriptModus: "fehler" });
    await sleep(100);
    await t.klick('[data-ansicht="karte"]', 300);
    const nachErstem = t.log.scriptAnfragen.length;
    // weitere Renders / hass-Änderungen / Filter lösen KEINEN neuen Versuch aus
    t.el.hass = { ...t.hass };
    t.el.render(); t.el.render();
    await sleep(300);
    const nachWeiteren = t.log.scriptAnfragen.length;
    const box = t.sr.querySelector("[data-karte-fehler]");
    const sichtbar = box && !box.hidden;
    const text = t.sr.querySelector("[data-karte-fehler-text]").textContent;
    const scriptsImHead = t.w.document.head.querySelectorAll("script").length;
    await t.klick("[data-karte-erneut]", 300);
    console.log(JSON.stringify({ nachErstem, nachWeiteren, sichtbar, text, scriptsImHead, nachRetry: t.log.scriptAnfragen.length }));
    process.exit(0);
    """
    )
    assert ergebnis["nachErstem"] == 1
    assert ergebnis["nachWeiteren"] == 1, "Fehlerpfad darf kein weiteres ladeLeaflet() auslösen"
    assert ergebnis["sichtbar"] is True
    assert "Kartenbibliothek" in ergebnis["text"]
    assert ergebnis["scriptsImHead"] == 0, "fehlgeschlagenes <script> muss entfernt werden"
    assert ergebnis["nachRetry"] == 2, "Retry nur auf ausdrückliche Anforderung"


@braucht_jsdom
def test_f9_ladefehler_keine_neuladung_pro_hass_aenderung_backoff_und_button() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ listFehler: true });
    await sleep(100);
    const nachStart = t.log.listAufrufe;
    for (let i = 0; i < 5; i++) { t.el.hass = { ...t.hass }; await sleep(10); }
    const nachHass = t.log.listAufrufe;
    const hatButton = !!t.sr.querySelector("[data-erneut-laden]");
    const ersterDelay = t.log.timerDelays[0];
    await t.klick("[data-erneut-laden]", 100);
    const nachButton = t.log.listAufrufe;
    for (let i = 0; i < 10; i++) { t.el.ladeErneut(); await sleep(20); }
    console.log(JSON.stringify({ nachStart, nachHass, hatButton, ersterDelay, nachButton, delays: t.log.timerDelays }));
    process.exit(0);
    """
    )
    assert ergebnis["nachStart"] == 1
    assert ergebnis["nachHass"] == 1, "hass-Änderungen dürfen nach Fehlschlag nicht neu laden"
    assert ergebnis["hatButton"] is True
    assert ergebnis["ersterDelay"] == 2000
    assert ergebnis["nachButton"] == 2
    assert max(ergebnis["delays"]) == 60000
    assert ergebnis["delays"][:4] == [2000, 4000, 8000, 16000]


@braucht_jsdom
def test_f10_filter_debounce_teilupdate_und_einmaliges_stylesheet() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 40 });
    await sleep(100);
    await t.klick('[data-ansicht="liste"]');
    const styles = () => t.sr.querySelectorAll("style").length;
    const feld = t.sr.querySelector("[data-listen-filter]");
    const body = t.sr.querySelector("[data-list-body]");
    const styleEl = t.sr.querySelector("style");
    let aenderungen = 0;
    new t.w.MutationObserver((r) => { aenderungen += r.length; }).observe(body, { childList: true });
    const l0 = t.log.listener;
    for (const v of ["m", "mü", "mül", "müll"]) { feld.value = v; feld.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); await sleep(5); }
    const sofort = t.sr.querySelectorAll("[data-list-body] tr").length;
    await sleep(300);
    const zeilen = t.sr.querySelectorAll("[data-list-body] tr").length;
    console.log(JSON.stringify({
      sofort, zeilen, aenderungen, gleichesFeld: t.sr.querySelector("[data-listen-filter]") === feld, gleicherBody: t.sr.querySelector("[data-list-body]") === body,
      neueListener: t.log.listener - l0, styles: styles(), gleichesStyle: t.sr.querySelector("style") === styleEl,
    }));
    process.exit(0);
    """
    )
    assert ergebnis["sofort"] == 40, "Debounce: sofort noch keine Änderung"
    assert ergebnis["zeilen"] == 20
    assert ergebnis["aenderungen"] == 1, "ein Tippschub = genau ein Teil-Update"
    assert ergebnis["gleichesFeld"] and ergebnis["gleicherBody"]
    assert ergebnis["neueListener"] == 0
    assert ergebnis["styles"] == 1 and ergebnis["gleichesStyle"]


@braucht_jsdom
def test_f10_auswahl_ohne_vollstaendigen_render_und_ohne_neue_listener() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 30 });
    await sleep(100);
    const main = t.sr.querySelector("main");
    const erste = t.sr.querySelector(".tile-card");
    await t.klick("[data-auswahlmodus]", 50); // Checkboxen gibt es nur im Auswahlmodus
    const erste2 = t.sr.querySelector(".tile-card");
    const l0 = t.log.listener;
    const cb = t.sr.querySelector("[data-auswahl]");
    cb.checked = true; cb.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    console.log(JSON.stringify({
      text: t.sr.querySelector("[data-auswahl-anzahl]").textContent,
      exportAktiv: !t.sr.querySelector("[data-export]").disabled,
      gleicheKarte: t.sr.querySelector(".tile-card") === erste2,
      neueListener: t.log.listener - l0,
    }));
    process.exit(0);
    """
    )
    assert ergebnis["text"] == "1 ausgewählt"
    assert ergebnis["exportAktiv"] is True
    assert ergebnis["gleicheKarte"] is True
    assert ergebnis["neueListener"] == 0


@braucht_jsdom
def test_f10_karte_einmal_erzeugt_nur_marker_ebene_getauscht_teardown_beim_verlassen() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 30, mitLeaflet: true });
    await sleep(100);
    await t.klick('[data-ansicht="karte"]', 200);
    const karte = t.el._leafletMap, host = t.el._karteHost, ebene1 = t.el._markerLayer;
    const cb = t.sr.querySelector("[data-karte-nur-geoeffnet]");
    cb.checked = true; cb.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await sleep(100);
    t.el.render(); await sleep(100); // z. B. durch ein Neuladen
    const nachFilter = { gleicheKarte: t.el._leafletMap === karte, gleicherHost: t.el._karteHost === host, hostImDom: t.sr.contains(host), andereEbene: t.el._markerLayer !== ebene1 };
    const popupHandler = (karte._events.popupopen || []).length;
    await t.klick('[data-ansicht="liste"]', 100);
    console.log(JSON.stringify({ ...nachFilter, popupHandler, nachVerlassen: t.el._leafletMap === null, hostWeg: t.el._karteHost === null, links: t.sr.querySelectorAll("link").length }));
    process.exit(0);
    """
    )
    assert ergebnis["gleicheKarte"] and ergebnis["gleicherHost"] and ergebnis["hostImDom"]
    assert ergebnis["andereEbene"]
    assert ergebnis["popupHandler"] == 1, "ein gemeinsamer Popup-Handler"
    assert ergebnis["nachVerlassen"] and ergebnis["hostWeg"]
    assert ergebnis["links"] == 1, "Leaflet-Stylesheet nur einmal eingehängt"


@braucht_jsdom
def test_f10_clustering_nur_ueber_schwelle() -> None:
    ergebnis = _node(
        r"""
    const ergebnisse = {};
    for (const n of [50, 250]) {
      const t = bauen({ n, mitLeaflet: true });
      await sleep(100);
      await t.klick('[data-ansicht="karte"]', 400);
      ergebnisse[n] = { cluster: !!(t.el._markerLayer && t.el._markerLayer instanceof t.w.L.MarkerClusterGroup), icons: t.sr.querySelectorAll(".leaflet-marker-icon").length };
    }
    console.log(JSON.stringify(ergebnisse));
    process.exit(0);
    """
    )
    assert ergebnis["50"]["cluster"] is False
    assert ergebnis["250"]["cluster"] is True
    assert ergebnis["250"]["icons"] < 250


@braucht_jsdom
def test_f14_vorschau_in_karten_original_in_detail() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 3 });
    await sleep(100);
    const img = t.sr.querySelector(".tile-card img.tile-image");
    const id1 = "1".padStart(32, "0");
    const karte = { src: img.getAttribute("src"), original: img.dataset.original, decoding: img.getAttribute("decoding") };
    const id = "a".repeat(32);
    await t.klick(`[data-view="${id1}"]`, 100);
    const detailImg = t.sr.querySelector(".thumbs img");
    console.log(JSON.stringify({ karte, id, detailSrc: detailImg ? detailImg.getAttribute("src") : null }));
    process.exit(0);
    """
    )
    id_ = ergebnis["id"]
    assert ergebnis["karte"]["src"] == f"https://ha.example/api/image/serve/{id_}/256x256"
    assert ergebnis["karte"]["original"] == f"https://ha.example/api/image/serve/{id_}/original"
    assert ergebnis["karte"]["decoding"] == "async"
