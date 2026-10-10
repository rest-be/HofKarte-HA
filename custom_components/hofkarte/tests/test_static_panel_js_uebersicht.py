"""GUI-Überarbeitung der Übersicht (Phase 1): gemeinsame Kopf- und
Steuerleiste für Kacheln, Liste und Karte.

Verhaltenstests mit Node und ``jsdom`` (wie ``test_static_panel_js_block_c.py``);
fehlt beides, werden sie übersprungen. Leaflet stammt aus ``static/vendor``.
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
function bauen({ n = 9, mitLeaflet = false, namen = null } = {}) {
  const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only", url: "https://ha.example/", pretendToBeVisual: true });
  const w = dom.window;
  if (mitLeaflet) {
    w.eval(fs.readFileSync(STATIC + "/vendor/leaflet/leaflet.js", "utf8"));
    w.eval(fs.readFileSync(STATIC + "/vendor/leaflet.markercluster/leaflet.markercluster.js", "utf8"));
  }
  const items = Array.from({ length: n }, (_, i) => ({
    id: String(i).padStart(32, "0"), name: namen ? namen[i] : `Hof ${i} ${i % 2 ? "Müller" : "Meier"}`,
    adresse: "Weg " + i, plz: "8000", ort: "Ort", land: "CH",
    latitude: 46 + i / 50, longitude: 7 + i / 50, geoeffnet: i % 3 === 0 ? true : i % 3 === 1 ? false : null, bewertung: i % 6,
    website: "", bilder: [], hauptbild_url: null, oeffnungszeiten: [], sonderoeffnungszeiten: [], angebote: [], zahlungsarten: [],
  }));
  const hass = { connection: { sendMessagePromise: async (m) => {
    if (m.type.endsWith("settings")) return { einstellungen: {} };
    return { hoflaeden: items };
  } } };
  w.eval(fs.readFileSync(STATIC + "/hofkarte-panel.js", "utf8"));
  const el = w.document.createElement("hofkarte-panel");
  w.document.body.appendChild(el);
  el.hass = hass;
  const sr = el.shadowRoot;
  const q = (s) => sr.querySelector(s);
  const qa = (s) => [...sr.querySelectorAll(s)];
  const klick = async (sel, warte = 30) => { const e = typeof sel === "string" ? q(sel) : sel; if (!e) throw new Error("fehlt: " + sel); e.dispatchEvent(new w.MouseEvent("click", { bubbles: true, composed: true })); await sleep(warte); };
  const tippe = async (sel, wert) => { const e = q(sel); e.value = wert; e.dispatchEvent(new w.Event("input", { bubbles: true, composed: true })); await sleep(250); };
  const wahl = async (sel, checked) => { const e = q(sel); e.checked = checked; e.dispatchEvent(new w.Event("change", { bubbles: true, composed: true })); await sleep(60); };
  const auswahlWert = async (sel, wert) => { const e = q(sel); e.value = wert; e.dispatchEvent(new w.Event("change", { bubbles: true, composed: true })); await sleep(60); };
  const taste = async (sel, key) => { q(sel).dispatchEvent(new w.KeyboardEvent("keydown", { key, bubbles: true, composed: true })); await sleep(20); };
  const kacheln = () => qa(".tile-card h2").map((h) => h.textContent.trim());
  return { w, el, sr, q, qa, klick, tippe, wahl, auswahlWert, taste, kacheln, items };
}
"""


def _node(test_js: str) -> dict:
    skript = _HARNESS + "\n(async () => {\n" + test_js + "\n})().catch((e) => { console.error(e); process.exit(1); });"
    r = subprocess.run(
        ["node", "-e", skript],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOFKARTE_STATIC": str(_STATIC)},
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@braucht_jsdom
def test_gemeinsame_steuerleiste_in_allen_drei_ansichten() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ mitLeaflet: true });
    await sleep(100);
    const sel = ["[data-listen-filter]", "[data-karte-nur-geoeffnet]", "[data-sortierung]", "[data-sortrichtung]", '[data-ansicht="kacheln"]', '[data-ansicht="liste"]', '[data-ansicht="karte"]', "[data-menue-toggle]", "[data-finden-open]", "[data-new]"];
    const out = {};
    for (const a of ["kacheln", "liste", "karte"]) {
      if (a !== "kacheln") await t.klick(`[data-ansicht="${a}"]`, 200);
      out[a] = sel.filter((s) => !t.q(s));
      out[a + "_aktiv"] = t.q('[data-ansicht="' + a + '"]').getAttribute("aria-pressed");
    }
    console.log(JSON.stringify(out));
    process.exit(0);
    """
    )
    for a in ("kacheln", "liste", "karte"):
        assert ergebnis[a] == [], f"{a}: fehlende Bedienelemente {ergebnis[a]}"
        assert ergebnis[a + "_aktiv"] == "true"


@braucht_jsdom
def test_suche_und_nur_geoeffnet_gelten_in_allen_ansichten_und_bleiben_beim_wechsel() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 9, mitLeaflet: true });
    await sleep(100);
    const raster = t.q("[data-kacheln]");
    await t.tippe("[data-listen-filter]", "müller");
    const nachSuche = t.kacheln().length;
    const gleichesRaster = t.q("[data-kacheln]") === raster;
    const zaehler = t.q("[data-zaehler]").textContent;
    await t.wahl("[data-karte-nur-geoeffnet]", true);
    const nachBeidem = t.kacheln();
    await t.klick('[data-ansicht="liste"]');
    const zeilen = t.qa("[data-list-body] tr").length;
    const feldWert = t.q("[data-listen-filter]").value;
    const chip = t.q("[data-karte-nur-geoeffnet]").checked;
    await t.klick('[data-ansicht="karte"]', 300);
    const marker = t.sr.querySelectorAll(".leaflet-marker-icon").length;
    console.log(JSON.stringify({ nachSuche, gleichesRaster, zaehler, nachBeidem, zeilen, feldWert, chip, marker }));
    process.exit(0);
    """
    )
    # Müller = ungerade Indizes 1,3,5,7 -> 4; davon geöffnet (i % 3 == 0): nur 3
    assert ergebnis["nachSuche"] == 4
    assert ergebnis["gleichesRaster"] is True, "Teil-Update statt Voll-Render"
    assert ergebnis["zaehler"] == "4 von 9 Hofläden"
    assert ergebnis["nachBeidem"] == ["Hof 3 Müller"]
    assert ergebnis["zeilen"] == 1
    assert ergebnis["feldWert"] == "müller" and ergebnis["chip"] is True
    assert ergebnis["marker"] == 1


@braucht_jsdom
def test_leerzustand_mit_filter_zuruecksetzen() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 4 });
    await sleep(100);
    await t.tippe("[data-listen-filter]", "gibtesnicht");
    const leer = !!t.q(".leerzustand");
    const anzahlLeer = t.kacheln().length;
    await t.klick("[data-filter-zuruecksetzen]", 60);
    console.log(JSON.stringify({ leer, anzahlLeer, danach: t.kacheln().length, feld: t.q("[data-listen-filter]").value, zaehler: t.q("[data-zaehler]").textContent }));
    process.exit(0);
    """
    )
    assert ergebnis["leer"] is True and ergebnis["anzahlLeer"] == 0
    assert ergebnis["danach"] == 4 and ergebnis["feld"] == ""
    assert ergebnis["zaehler"] == "4 Hofläden"


@braucht_jsdom
def test_sortierung_gilt_auch_fuer_kacheln() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 5, namen: ["Berg", "Dorf", "Acker", "Cham", "Eich"] });
    await sleep(100);
    const standard = t.kacheln();
    await t.klick("[data-sortrichtung]", 60);
    const absteigend = t.kacheln();
    await t.auswahlWert("[data-sortierung]", "bewertung");
    const nachBewertung = { spalte: t.q("[data-sortierung]").value, aufsteigend: t.q("[data-sortrichtung]").textContent.trim() };
    console.log(JSON.stringify({ standard, absteigend, nachBewertung }));
    process.exit(0);
    """
    )
    assert ergebnis["standard"] == ["Acker", "Berg", "Cham", "Dorf", "Eich"], "Standard: Name aufsteigend"
    assert ergebnis["absteigend"] == ["Eich", "Dorf", "Cham", "Berg", "Acker"]
    assert ergebnis["nachBewertung"] == {"spalte": "bewertung", "aufsteigend": "▲"}


@braucht_jsdom
def test_ueberlaufmenue_oeffnet_schliesst_per_klick_daneben_und_escape() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 3 });
    await sleep(100);
    const menue = () => t.q("[data-menue]");
    const exp = () => t.q("[data-menue-toggle]").getAttribute("aria-expanded");
    const start = { hidden: menue().hidden, exp: exp(), importDrin: !!t.q("[data-menue] [data-import-start]") };
    await t.klick("[data-menue-toggle]");
    const offen = { hidden: menue().hidden, exp: exp() };
    await t.klick("h1");
    const nachKlickDaneben = { hidden: menue().hidden, exp: exp() };
    await t.klick("[data-menue-toggle]");
    await t.taste("[data-menue]", "Escape");
    const nachEscape = { hidden: menue().hidden, exp: exp() };
    console.log(JSON.stringify({ start, offen, nachKlickDaneben, nachEscape }));
    process.exit(0);
    """
    )
    assert ergebnis["start"] == {"hidden": True, "exp": "false", "importDrin": True}
    assert ergebnis["offen"] == {"hidden": False, "exp": "true"}
    assert ergebnis["nachKlickDaneben"] == {"hidden": True, "exp": "false"}
    assert ergebnis["nachEscape"] == {"hidden": True, "exp": "false"}


@braucht_jsdom
def test_kontextleiste_im_auswahlmodus_und_alle_auswaehlen_nur_sichtbare() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 9 });
    await sleep(100);
    const leiste = () => t.q("[data-kontextleiste]");
    const start = { hidden: leiste().hidden, checkboxen: t.qa("[data-auswahl]").length };
    await t.klick("[data-auswahlmodus]");
    const imModus = { hidden: leiste().hidden, checkboxen: t.qa("[data-auswahl]").length, text: t.q("[data-auswahl-anzahl]").textContent, export: t.q("[data-export]").disabled };
    await t.wahl("[data-auswahl]", true);
    const nachEiner = { text: t.q("[data-auswahl-anzahl]").textContent, export: t.q("[data-export]").disabled };
    await t.klick("[data-auswahl-keine]");
    const nachAufheben = { hidden: leiste().hidden, text: t.q("[data-auswahl-anzahl]").textContent };
    await t.tippe("[data-listen-filter]", "müller");
    await t.klick("[data-auswahl-alle]");
    const text = t.q("[data-auswahl-anzahl]").textContent;
    await t.klick("[data-auswahlmodus]"); // beenden
    const nachBeenden = { hidden: leiste().hidden, checkboxen: t.qa("[data-auswahl]").length, text: t.q("[data-auswahl-anzahl]").textContent };
    console.log(JSON.stringify({ start, imModus, nachEiner, nachAufheben, text, nachBeenden }));
    process.exit(0);
    """
    )
    assert ergebnis["start"] == {"hidden": True, "checkboxen": 0}
    assert ergebnis["imModus"] == {"hidden": False, "checkboxen": 9, "text": "0 ausgewählt", "export": True}
    assert ergebnis["nachEiner"] == {"text": "1 ausgewählt", "export": False}
    assert ergebnis["nachAufheben"] == {"hidden": False, "text": "0 ausgewählt"}
    assert ergebnis["text"] == "4 ausgewählt", "nur die sichtbaren (gefilterten) Hofläden"
    assert ergebnis["nachBeenden"] == {"hidden": True, "checkboxen": 0, "text": "0 ausgewählt"}


@braucht_jsdom
def test_suchwert_wird_als_attribut_maskiert() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    t.el.listenFilter = '"><img src=x onerror=window.xss=1><b id="x';
    t.el.render();
    await sleep(30);
    console.log(JSON.stringify({ wert: t.q("[data-listen-filter]").value, fremdesElement: !!t.sr.querySelector("main img, main b#x"), xss: !!t.w.xss }));
    process.exit(0);
    """
    )
    assert ergebnis["wert"].startswith('"><img')
    assert ergebnis["fremdesElement"] is False and ergebnis["xss"] is False


@braucht_jsdom
def test_kachel_ganze_flaeche_klickbar_und_menue_aktionen_rufen_bestehende_handler() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 3 });
    await sleep(100);
    const log = [];
    t.el.view = (x) => log.push("view:" + x.name);
    t.el.start = (x) => log.push("edit:" + x.name);
    t.el.remove = (id) => log.push("delete:" + id);
    const k = t.q(".tile-card");
    const id = k.querySelector("[data-kachel-menue-toggle]").dataset.kachelMenueToggle;
    const vorher = { menueOffen: !k.querySelector("[data-kachel-menue]").hidden, aktionenInKachel: k.querySelectorAll("[data-delete]").length, ohneCheckbox: k.querySelectorAll("[data-auswahl]").length };
    await t.klick(k.querySelector(".tile-link"));
    await t.klick(k.querySelector("[data-kachel-menue-toggle]"));
    const offen = !k.querySelector("[data-kachel-menue]").hidden;
    const expanded = k.querySelector("[data-kachel-menue-toggle]").getAttribute("aria-expanded");
    const eintraege = [...k.querySelectorAll("[data-kachel-menue] [role=menuitem]")].map((e) => e.textContent.trim());
    const letzter = eintraege[eintraege.length - 1];
    const routeHref = k.querySelector("[data-kachel-menue] a")?.getAttribute("href") || "";
    await t.klick(k.querySelector("[data-edit]"));
    const nachBearbeiten = !k.querySelector("[data-kachel-menue]").hidden;
    await t.klick(k.querySelector("[data-kachel-menue-toggle]"));
    await t.klick(k.querySelector("[data-delete]"));
    // Klick daneben schliesst, Escape schliesst und fokussiert den Knopf
    await t.klick(k.querySelector("[data-kachel-menue-toggle]"));
    await t.klick(t.q("h1"));
    const nachDaneben = !k.querySelector("[data-kachel-menue]").hidden;
    await t.klick(k.querySelector("[data-kachel-menue-toggle]"));
    await t.taste("main", "Escape");
    const nachEscape = !k.querySelector("[data-kachel-menue]").hidden;
    console.log(JSON.stringify({ vorher, offen, expanded, letzter, routeHref, log, nachBearbeiten, nachDaneben, nachEscape, id }));
    process.exit(0);
    """
    )
    assert ergebnis["vorher"] == {"menueOffen": False, "aktionenInKachel": 1, "ohneCheckbox": 0}
    assert ergebnis["offen"] is True and ergebnis["expanded"] == "true"
    assert ergebnis["letzter"].startswith("Löschen"), "destruktive Aktion zuunterst"
    assert ergebnis["routeHref"].startswith("https://"), ergebnis["routeHref"]
    assert ergebnis["log"][0].startswith("view:")
    assert ergebnis["log"][1].startswith("edit:")
    assert ergebnis["log"][2] == "delete:" + ergebnis["id"]
    assert ergebnis["nachBearbeiten"] is False, "Menü schliesst nach Auswahl eines Eintrags"
    assert ergebnis["nachDaneben"] is False
    assert ergebnis["nachEscape"] is False


@braucht_jsdom
def test_kachel_nur_ein_menue_gleichzeitig_und_auswahl_markiert_kachel() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 3 });
    await sleep(100);
    const knoepfe = t.qa("[data-kachel-menue-toggle]");
    await t.klick(knoepfe[0]);
    await t.klick(knoepfe[1]);
    const offene = t.qa("[data-kachel-menue]").filter((m) => !m.hidden).length;
    await t.klick("[data-auswahlmodus]");
    const modus = t.q("[data-auswahlmodus]").getAttribute("aria-pressed");
    await t.wahl("[data-auswahl]", true);
    const markiert = t.qa(".tile-card.ausgewaehlt").length;
    console.log(JSON.stringify({ offene, modus, markiert }));
    process.exit(0);
    """
    )
    assert ergebnis["offene"] == 1
    assert ergebnis["modus"] == "true"
    assert ergebnis["markiert"] == 1


@braucht_jsdom
def test_liste_spalten_sortierkoepfe_und_zeilenmenue() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 6 });
    await sleep(100);
    await t.klick('[data-ansicht="liste"]', 100);
    const koepfe = t.qa("thead th").map((th) => th.textContent.trim());
    const aria0 = t.qa("thead th[aria-sort]").map((th) => th.getAttribute("aria-sort"));
    await t.klick('[data-sort="ort"]', 60);
    const nachOrt = t.qa("thead th[aria-sort]").map((th) => th.getAttribute("aria-sort"));
    const sortSelect = t.q("[data-sortierung]").value;
    const zeile = t.q("[data-list-body] tr");
    const log = [];
    t.el.start = (x) => log.push("edit:" + x.name);
    t.el.remove = (id) => log.push("delete");
    await t.klick(zeile.querySelector("[data-kachel-menue-toggle]"));
    const offen = !zeile.querySelector("[data-kachel-menue]").hidden;
    const letzter = [...zeile.querySelectorAll("[role=menuitem]")].pop().textContent.trim();
    await t.klick(zeile.querySelector("[data-edit]"));
    const zu = zeile.querySelector("[data-kachel-menue]").hidden;
    console.log(JSON.stringify({ koepfe, aria0, nachOrt, sortSelect, offen, letzter, zu, log, adresseInZeile: !!zeile.querySelector(".zeilen-adresse") }));
    process.exit(0);
    """
    )
    assert ergebnis["koepfe"][1:5] == ["Name & Adresse ▲", "Ort", "Status", "Bewertung"]
    assert ergebnis["aria0"] == ["ascending", "none", "none", "none"]
    assert ergebnis["nachOrt"] == ["none", "ascending", "none", "none"]
    assert ergebnis["sortSelect"] == "ort"
    assert ergebnis["offen"] is True and ergebnis["zu"] is True
    assert ergebnis["letzter"].startswith("Löschen")
    assert ergebnis["log"][0].startswith("edit:")
    assert ergebnis["adresseInZeile"] is True


@braucht_jsdom
def test_liste_kopf_checkbox_waehlt_nur_sichtbare_und_zeigt_teilzustand() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 9 });
    await sleep(100);
    await t.klick('[data-ansicht="liste"]', 100);
    const box = () => t.q("[data-auswahl-alle-box]");
    await t.tippe("[data-listen-filter]", "müller");
    await t.wahl("[data-auswahl-alle-box]", true);
    const nachAlle = { text: t.q("[data-auswahl-anzahl]").textContent, geprueft: box().checked, markiert: t.qa("[data-list-body] tr.ausgewaehlt").length };
    await t.wahl("[data-list-body] [data-auswahl]", false);
    const teil = { checked: box().checked, indeterminate: box().indeterminate };
    await t.wahl("[data-auswahl-alle-box]", false);
    console.log(JSON.stringify({ nachAlle, teil, ende: t.q("[data-auswahl-anzahl]").textContent }));
    process.exit(0);
    """
    )
    assert ergebnis["nachAlle"] == {"text": "4 ausgewählt", "geprueft": True, "markiert": 4}
    assert ergebnis["teil"] == {"checked": False, "indeterminate": True}
    assert ergebnis["ende"] == "0 ausgewählt"


@braucht_jsdom
def test_menue_hat_deckenden_hintergrund() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 1 });
    await sleep(100);
    const css = t.sr.querySelector("style").textContent;
    const regel = css.match(/\.menue\{[^}]*\}/)[0];
    console.log(JSON.stringify({ regel }));
    process.exit(0);
    """
    )
    assert "background-color:var(--primary-background-color" in ergebnis["regel"]
    assert "--ha-card-background" not in ergebnis["regel"], "keine (evtl. transparente) Kartenfarbe als einziger Hintergrund"


@braucht_jsdom
def test_karte_seitenliste_legende_und_synchronisierung_mit_den_markern() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 9, mitLeaflet: true });
    await sleep(100);
    await t.klick('[data-ansicht="karte"]', 300);
    const anzahl0 = t.qa("[data-karte-waehle]").length;
    const legende = t.qa(".karte-legende li").map((li) => li.textContent.trim());
    // Liste -> Karte
    const id = t.qa("[data-karte-waehle]")[2].dataset.karteWaehle;
    await t.klick(t.qa("[data-karte-waehle]")[2], 100);
    const marker = t.el._markerById.get(id);
    const popupOffen = marker.isPopupOpen();
    const popupText = t.el._leafletMap._container.querySelector(".karte-popup")?.textContent || "";
    const markiert = t.qa(".karte-eintrag.aktiv").map((b) => b.dataset.karteWaehle);
    // Karte -> Liste
    const id2 = t.qa("[data-karte-waehle]")[5].dataset.karteWaehle;
    t.el._markerById.get(id2).openPopup();
    await sleep(50);
    const markiert2 = t.qa(".karte-eintrag.aktiv").map((b) => b.dataset.karteWaehle);
    // Filter wirkt auf Liste und Marker; Auswahl ausserhalb des Filters verfällt
    await t.tippe("[data-listen-filter]", "müller");
    const nachFilter = { eintraege: t.qa("[data-karte-waehle]").length, marker: t.el._markerById.size, aktiv: t.qa(".karte-eintrag.aktiv").length };
    // Popup-Klick auf Details ruft die Detailansicht
    let detail = null; t.el.view = (x) => { detail = x.id; };
    const m = [...t.el._markerById.values()][0]; m.openPopup(); await sleep(50);
    t.el._leafletMap._container.querySelector("[data-karte-view]").dispatchEvent(new t.w.MouseEvent("click", { bubbles: true }));
    console.log(JSON.stringify({ anzahl0, legende, popupOffen, popupText, markiert, id, id2, markiert2, nachFilter, detailGesetzt: !!detail }));
    process.exit(0);
    """
    )
    assert ergebnis["anzahl0"] == 9
    assert ergebnis["legende"] == ["Geöffnet", "Geschlossen", "Unbekannt"]
    assert ergebnis["popupOffen"] is True
    assert "Hof" in ergebnis["popupText"] and "Details" in ergebnis["popupText"]
    assert ergebnis["markiert"] == [ergebnis["id"]]
    assert ergebnis["markiert2"] == [ergebnis["id2"]]
    assert ergebnis["nachFilter"]["eintraege"] == 4 and ergebnis["nachFilter"]["marker"] == 4
    assert ergebnis["detailGesetzt"] is True


@braucht_jsdom
def test_karte_liste_zeigt_hofladen_ohne_koordinaten_und_maskiert_namen() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 3, mitLeaflet: true, namen: ['<img src=x onerror=window.xss=1>', 'B', 'C'] });
    await sleep(60);
    t.el.items[1].latitude = null; t.el.items[1].longitude = null;
    await t.klick('[data-ansicht="karte"]', 300);
    const texte = t.qa("[data-karte-waehle]").map((b) => b.textContent.replace(/\s+/g, " ").trim());
    console.log(JSON.stringify({ texte, img: !!t.q(".karte-liste img"), xss: !!t.w.xss }));
    process.exit(0);
    """
    )
    assert any("keine Koordinaten" in x for x in ergebnis["texte"])
    assert ergebnis["img"] is False and ergebnis["xss"] is False


@braucht_jsdom
def test_menue_wird_beim_oeffnen_deckend_berechnet_und_hebt_die_kachel_an() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    const gesehen = [];
    t.w.HTMLCanvasElement.prototype.getContext = function () {
      return { set fillStyle(v) { gesehen.push(v); }, fillRect() {}, getImageData: () => ({ data: [10, 20, 30, 255] }) };
    };
    await t.klick(t.q("[data-kachel-menue-toggle]"));
    const menue = t.q("[data-kachel-menue]");
    const css = t.sr.querySelector("style").textContent;
    // Kopfzeilen-Menü ebenso
    await t.klick(t.q("[data-menue-toggle]"));
    console.log(JSON.stringify({ bg: menue.style.backgroundColor, bild: menue.style.backgroundImage, kopf: t.q("[data-menue]").style.backgroundColor, gesehen: gesehen.length > 1, anheben: css.includes(".tile-card:has([data-kachel-menue]:not([hidden])){z-index:10}") }));
    process.exit(0);
    """
    )
    assert ergebnis["bg"] == "rgb(10, 20, 30)" and ergebnis["bild"] == "none"
    assert ergebnis["kopf"] == "rgb(10, 20, 30)"
    assert ergebnis["gesehen"] and ergebnis["anheben"]


@braucht_jsdom
def test_menue_tastatur_fokus_pfeiltasten_und_escape() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 2 });
    await sleep(100);
    const knopf = t.q("[data-kachel-menue-toggle]");
    await t.klick(knopf); // Tastatur-Aktivierung (detail 0) -> Fokus auf ersten Eintrag
    const eintraege = [...t.qa("[data-kachel-menue]")[0].querySelectorAll("[role=menuitem]")];
    const aktiv = () => eintraege.indexOf(t.sr.activeElement);
    const start = aktiv();
    const taste = async (key) => { t.sr.activeElement.dispatchEvent(new t.w.KeyboardEvent("keydown", { key, bubbles: true, composed: true })); await sleep(10); };
    await taste("ArrowDown"); const nachUnten = aktiv();
    await taste("End"); const ende = aktiv();
    await taste("ArrowDown"); const umlauf = aktiv();
    await taste("ArrowUp"); const zurueck = aktiv();
    await taste("Escape");
    console.log(JSON.stringify({ start, nachUnten, ende, umlauf, zurueck, anzahl: eintraege.length, fokusKnopf: t.sr.activeElement === knopf }));
    process.exit(0);
    """
    )
    n = ergebnis["anzahl"]
    assert ergebnis["start"] == 0 and ergebnis["nachUnten"] == 1
    assert ergebnis["ende"] == n - 1 and ergebnis["umlauf"] == 0 and ergebnis["zurueck"] == n - 1
    assert ergebnis["fokusKnopf"] is True


@braucht_jsdom
def test_auswaehlen_liegt_im_kopfmenue_und_nur_bei_kacheln() -> None:
    ergebnis = _node(
        r"""
    const t = bauen({ n: 4, mitLeaflet: true });
    await sleep(100);
    const inSteuerleiste = !!t.q(".steuerleiste [data-auswahlmodus]");
    const kacheln = { imMenue: !!t.q("[data-menue] [data-auswahlmodus]"), text: t.q("[data-auswahlmodus]").textContent.trim() };
    await t.klick(t.q("[data-menue-toggle]"));
    await t.klick(t.q("[data-menue] [data-auswahlmodus]"));
    const nachWahl = { menueZu: t.q("[data-menue]").hidden, checkboxen: t.qa("[data-auswahl]").length, text: t.q("[data-auswahlmodus]").textContent.trim() };
    await t.klick('[data-ansicht="liste"]', 100);
    const liste = !!t.q("[data-auswahlmodus]");
    await t.klick('[data-ansicht="karte"]', 200);
    const karte = !!t.q("[data-auswahlmodus]");
    console.log(JSON.stringify({ inSteuerleiste, kacheln, nachWahl, liste, karte }));
    process.exit(0);
    """
    )
    assert ergebnis["inSteuerleiste"] is False
    assert ergebnis["kacheln"] == {"imMenue": True, "text": "Auswählen"}
    assert ergebnis["nachWahl"] == {"menueZu": True, "checkboxen": 4, "text": "Auswahl beenden"}
    assert ergebnis["liste"] is False and ergebnis["karte"] is False
