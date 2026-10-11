"""Detail & Erfassung, Phase 5: Szenario 1 «Vor Ort» (Schnellerfassung)."""

from __future__ import annotations

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_START = r"""
const t = bauen({ n: 3 });
await sleep(100);
const el = t.el;
const nachrichten = [];
let geo = "ok"; let geoAufrufe = 0; let discoverFehler = null;
const KANDIDATEN = [
  { refs: ["node/42"], name: "Hofladen <b>Seeblick</b>", latitude: 46.9, longitude: 7.4, entfernung_meter: 35, adresse: "Dorfstrasse 1", plz: "3000", ort: "Bern", website: "https://seeblick.example/", konfidenz: "hoch" },
  { refs: ["node/43"], name: "Hof Nebenan", latitude: 46.901, longitude: 7.401, entfernung_meter: 120, adresse: "", plz: "", ort: "", website: "", konfidenz: "mittel" },
];
let kandidaten = KANDIDATEN;
t.w.Object.defineProperty(t.w.navigator, "geolocation", { configurable: true, value: { getCurrentPosition: (ok, ng) => {
  geoAufrufe++;
  if (geo === "ok") ok({ coords: { latitude: 46.9, longitude: 7.4, accuracy: 12.4 } }); else ng({ code: 1 });
} } });
const orig = el.hass.connection.sendMessagePromise;
el.hass.connection.sendMessagePromise = async (m) => {
  nachrichten.push(m);
  if (m.type === "hofkarte/management/discover") { if (discoverFehler) throw discoverFehler; return { kandidaten }; }
  if (m.type === "hofkarte/management/save") {
    const neu = { ...m.hofladen, id: "f".repeat(32), geoeffnet: null, hauptbild_url: null };
    t.items.push(neu);
    return { konflikt: false, hofladen: neu };
  }
  if (m.type === "image/delete") return {};
  return orig(m);
};
let bestaetigung = true; const fragen = [];
t.w.confirm = (m) => { fragen.push(m); return bestaetigung; };
const start = async (warte = 60) => { if (t.q("[data-erfassen-open]")) await t.klick("[data-erfassen-open]", 20); await t.klick("[data-vorort-start]", warte); };
const tipp = (sel, wert) => { const e = t.q(sel); e.value = wert; e.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); };
const treffer = () => t.qa("[data-vorort-kandidat]").map((b) => b.querySelector(".vorort-treffer-name").textContent);
const disc = () => nachrichten.filter((m) => m.type === "hofkarte/management/discover");
"""


@braucht_jsdom
def test_standort_und_trefferliste_mit_entfernung_und_wahrscheinlich_dieser() -> None:
    e = _node(
        _START
        + r"""
    await start();
    const aufrufe0 = geoAufrufe;
    const text = t.q(".vorort").textContent;
    console.log(JSON.stringify({
      aufrufe0, treffer: treffer(), standort: text.includes("Standort ermittelt") && text.includes("±12 m"),
      wahrscheinlich: t.qa(".vorort-treffer.wahrscheinlich").length, badge: text.includes("Wahrscheinlich dieser"),
      dist: text.includes("35 m") && text.includes("120 m"), nachricht: disc()[0],
      radien: t.qa("[data-vorort-radius]").map((b) => b.textContent.trim() + ":" + b.getAttribute("aria-pressed")),
      keiner: !!t.q("[data-vorort-keiner]"), titel: t.q(".erfassen-titel").textContent,
      xss: !t.q(".vorort b"),
    }));
    process.exit(0);
    """
    )
    assert e["aufrufe0"] == 1
    assert e["treffer"] == ["Hofladen <b>Seeblick</b>", "Hof Nebenan"]
    assert e["standort"] and e["badge"] and e["dist"] and e["xss"]
    assert e["wahrscheinlich"] == 1
    assert e["nachricht"]["latitude"] == 46.9 and e["nachricht"]["radius"] == 250
    assert e["radien"] == ["100 m:false", "250 m:true", "500 m:false"]
    assert e["keiner"] and e["titel"] == "Vor Ort erfassen"


@braucht_jsdom
def test_umkreis_chips_suchen_neu_und_keine_treffer() -> None:
    e = _node(
        _START
        + r"""
    await start();
    kandidaten = [];
    await t.klick('[data-vorort-radius="500"]', 60);
    const leer = t.q(".vorort").textContent.includes("Im Umkreis von 500 m");
    console.log(JSON.stringify({ radius: disc().map((m) => m.radius), leer, pressed: t.q('[data-vorort-radius="500"]').getAttribute("aria-pressed"), keiner: !!t.q("[data-vorort-keiner]") }));
    process.exit(0);
    """
    )
    assert e["radius"] == [250, 500] and e["leer"] and e["pressed"] == "true" and e["keiner"]


@braucht_jsdom
def test_standort_verweigert_zeigt_hinweis_und_erneut_versuchen() -> None:
    e = _node(
        _START
        + r"""
    geo = "nein";
    await start();
    const text1 = t.q(".vorort").textContent;
    const ohneSuche = disc().length;
    geo = "ok";
    await t.klick("[data-vorort-neu-standort]", 60);
    console.log(JSON.stringify({ hinweis: text1.includes("Standort nicht verfügbar") && text1.includes("verweigert"), ohneSuche, danach: treffer().length, keinerImmer: true }));
    process.exit(0);
    """
    )
    assert e["hinweis"] and e["ohneSuche"] == 0 and e["danach"] == 2


@braucht_jsdom
def test_unsichere_verbindung_und_suchfehler() -> None:
    e = _node(
        _START
        + r"""
    t.w.isSecureContext = false;
    await start();
    const unsicher = t.q(".vorort").textContent.includes("sichere Verbindung");
    await t.klick("[data-vorort-zurueck]", 20);
    t.w.isSecureContext = true;
    discoverFehler = { code: "unreachable", message: "x" };
    await start();
    const fehler = t.q(".vorort .notice.error")?.textContent || "";
    console.log(JSON.stringify({ unsicher, fehler, einstieg: !!t.q(".erfassen-karte") }));
    process.exit(0);
    """
    )
    assert e["unsicher"] and "Overpass" in e["fehler"]


@braucht_jsdom
def test_treffer_waehlen_fuellt_name_und_webseite_vor_speichert_mit_osm_quellen() -> None:
    e = _node(
        _START
        + r"""
    await start();
    await t.klick('[data-vorort-kandidat="0"]', 30);
    const vor = { name: t.q("[data-vorort-name]").value, website: t.q("[data-vorort-website]").value, standort: t.q(".vorort").textContent.includes("Standort übernommen") };
    await t.klick("[data-vorort-speichern]", 150);
    const save = nachrichten.find((m) => m.type === "hofkarte/management/save").hofladen;
    console.log(JSON.stringify({ vor, save, schritt3: t.q(".erfassen-titel").textContent, text: t.q(".vorort").textContent }));
    process.exit(0);
    """
    )
    assert e["vor"] == {"name": "Hofladen <b>Seeblick</b>", "website": "https://seeblick.example/", "standort": True}
    s = e["save"]
    assert s["latitude"] == 46.9 and s["adresse"] == "Dorfstrasse 1" and s["plz"] == "3000" and s["ort"] == "Bern"
    felder = {q["feld"] for q in s["quellen"]}
    assert {"name", "adresse", "plz", "ort", "latitude", "longitude", "website"} <= felder
    assert all(q["quelle"] == "openstreetmap" and q["url"] == "https://www.openstreetmap.org/node/42" and "ODbL" in q["lizenz"] for q in s["quellen"])
    assert e["schritt3"] == "Gespeichert"
    for offen in ("Öffnungszeiten", "Angebote", "Zahlungsarten", "Foto"):
        assert offen in e["text"]


@braucht_jsdom
def test_keiner_davon_pflichtfeld_name_und_ungueltige_webseite() -> None:
    e = _node(
        _START
        + r"""
    await start();
    await t.klick("[data-vorort-keiner]", 30);
    const leer = t.q("[data-vorort-name]").value;
    await t.klick("[data-vorort-speichern]", 30);
    const f1 = t.q(".vorort .notice.error")?.textContent || "";
    tipp("[data-vorort-name]", "Mein Hof");
    tipp("[data-vorort-website]", "javascript:alert(1)");
    await t.klick("[data-vorort-speichern]", 30);
    const f2 = t.q(".vorort .notice.error")?.textContent || "";
    const gespeichert = nachrichten.filter((m) => m.type === "hofkarte/management/save").length;
    tipp("[data-vorort-website]", "");
    await t.klick("[data-vorort-speichern]", 150);
    const save = nachrichten.find((m) => m.type === "hofkarte/management/save").hofladen;
    console.log(JSON.stringify({ leer, f1, f2, gespeichert, save }));
    process.exit(0);
    """
    )
    assert e["leer"] == "" and "Namen" in e["f1"] and "Webseite" in e["f2"] and e["gespeichert"] == 0
    s = e["save"]
    assert s["name"] == "Mein Hof" and s["website"] is None and s["quellen"] == []
    assert s["latitude"] == 46.9 and s["longitude"] == 7.4


@braucht_jsdom
def test_duplikatwarnung_bei_bereits_erfasstem_hof() -> None:
    e = _node(
        _START
        + r"""
    t.items[0].name = "Hof Nebenan"; t.items[0].latitude = 46.901; t.items[0].longitude = 7.401;
    await el.load(); await sleep(30);
    await start();
    const warnung = t.q(".vorort").textContent.includes("Möglicherweise schon erfasst");
    await t.klick('[data-vorort-kandidat="1"]', 30);
    bestaetigung = false;
    await t.klick("[data-vorort-speichern]", 100);
    const nachNein = nachrichten.filter((m) => m.type === "hofkarte/management/save").length;
    bestaetigung = true;
    await t.klick("[data-vorort-speichern]", 150);
    console.log(JSON.stringify({ warnung, fragen, nachNein, nachJa: nachrichten.filter((m) => m.type === "hofkarte/management/save").length }));
    process.exit(0);
    """
    )
    assert e["warnung"] and len(e["fragen"]) == 2 and e["nachNein"] == 0 and e["nachJa"] == 1


@braucht_jsdom
def test_foto_upload_speichern_mit_bild_und_aufraeumen_beim_abbruch() -> None:
    e = _node(
        _START
        + r"""
    el.hass.auth = { accessToken: "tok" };
    const ID = "a".repeat(32);
    t.w.fetch = async () => ({ ok: true, status: 200, json: async () => ({ id: ID }) });
    await start();
    await t.klick("[data-vorort-keiner]", 30);
    const eingabe = t.q("[data-vorort-foto-input]");
    const attrs = { capture: eingabe.getAttribute("capture"), accept: eingabe.getAttribute("accept") };
    const datei = new t.w.File(["x"], "foto.jpg", { type: "image/jpeg" });
    t.w.Object.defineProperty(eingabe, "files", { configurable: true, value: [datei] });
    eingabe.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await sleep(100);
    const mitFoto = !!t.q("[data-vorort-foto-entfernen]");
    // Abbruch ohne Speichern räumt das Foto auf
    await t.klick("[data-vorort-zurueck]", 20);
    await t.klick("[data-vorort-zurueck]", 20);
    const geloescht = nachrichten.filter((m) => m.type === "image/delete").map((m) => m.image_id);
    // Zweiter Lauf: Foto bleibt beim Speichern erhalten
    await start();
    await t.klick("[data-vorort-keiner]", 30);
    tipp("[data-vorort-name]", "Hof mit Foto");
    const e2 = t.q("[data-vorort-foto-input]");
    t.w.Object.defineProperty(e2, "files", { configurable: true, value: [datei] });
    e2.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await sleep(100);
    await t.klick("[data-vorort-speichern]", 150);
    const save = nachrichten.filter((m) => m.type === "hofkarte/management/save").pop().hofladen;
    const offen = t.q(".vorort-offen").textContent;
    console.log(JSON.stringify({ attrs, mitFoto, geloescht, bilder: save.bilder, offenFoto: offen.includes("Foto"), geloeschtGesamt: nachrichten.filter((m) => m.type === "image/delete").length }));
    process.exit(0);
    """
    )
    assert e["attrs"] == {"capture": "environment", "accept": "image/*"}
    assert e["mitFoto"] and e["geloescht"] == ["a" * 32]
    assert len(e["bilder"]) == 1 and e["bilder"][0]["hochgeladen"] is True
    assert e["offenFoto"] is False and e["geloeschtGesamt"] == 1


@braucht_jsdom
def test_abschluss_jetzt_ergaenzen_oeffnet_editor_fertig_zeigt_liste() -> None:
    e = _node(
        _START
        + r"""
    const lauf = async () => {
      await start();
      await t.klick("[data-vorort-keiner]", 30);
      tipp("[data-vorort-name]", "Neuer Hof");
      await t.klick("[data-vorort-speichern]", 150);
    };
    await lauf();
    await t.klick("[data-vorort-ergaenzen]", 100);
    const editor = { offen: !!el.editing, name: el.editing?.name, vorOrt: el.vorOrt };
    el.editing = null; el.render(); await sleep(30);
    await lauf();
    await t.klick("[data-vorort-fertig]", 50);
    console.log(JSON.stringify({ editor, liste: !!t.q("[data-listen-filter]"), vorOrtWeg: el.vorOrt === null, kacheln: t.kacheln().includes("Neuer Hof") }));
    process.exit(0);
    """
    )
    assert e["editor"]["offen"] and e["editor"]["name"] == "Neuer Hof" and e["editor"]["vorOrt"] is None
    assert e["liste"] and e["vorOrtWeg"]


@braucht_jsdom
def test_zurueck_navigation_und_enter_im_namensfeld_speichert() -> None:
    e = _node(
        _START
        + r"""
    await start();
    await t.klick('[data-vorort-kandidat="1"]', 30);
    await t.klick("[data-vorort-zurueck]", 30);
    const schritt1 = t.q(".erfassen-titel").textContent;
    const trefferNoch = treffer().length;
    await t.klick('[data-vorort-kandidat="1"]', 30);
    await t.taste("[data-vorort-name]", "Enter");
    await sleep(150);
    console.log(JSON.stringify({ schritt1, trefferNoch, titel: t.q(".erfassen-titel").textContent }));
    process.exit(0);
    """
    )
    assert e["schritt1"] == "Vor Ort erfassen" and e["trefferNoch"] == 2 and e["titel"] == "Gespeichert"
