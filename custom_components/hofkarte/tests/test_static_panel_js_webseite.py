"""Detail & Erfassung, Phase 6: Szenario 2 «Von Webseite» (Schritte, Prüfansicht, KI nachträglich)."""

from __future__ import annotations

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_START = r"""
const t = bauen({ n: 2 });
await sleep(100);
const el = t.el;
const abos = [];
el.hass.connection.subscribeMessage = async (cb, m) => { abos.push({ cb, m }); return () => { abos.at(-1).abgemeldet = true; }; };
const URL_ = "https://hof.example/";
const VORSCHLAG = {
  daten: { name: "Hofladen <i>Müller</i>", adresse: "Dorfstrasse 1", plz: "3000", ort: "Bern", website: URL_, mobilnummer: "031 111 22 33",
    oeffnungszeiten: [{ wochentag: 1, beginn: "08:00", ende: "12:00" }], angebote: ["Eier", "Honig"], zahlungsarten: ["Bargeld"] },
  quellen: [{ feld: "name", quelle: "website", status: "confirmed", url: URL_ }, { feld: "adresse", quelle: "website", status: "confirmed", url: URL_ },
            { feld: "angebote", quelle: "website", status: "confirmed", url: URL_ }],
  abweichungen: { mobilnummer: "openstreetmap" },
};
const MIT_KI = { ...VORSCHLAG, vermutungen: { angebote: ["Trüffel"] } };
const ereignis = async (e) => { abos.at(-1).cb(e); await sleep(20); };
const einstieg = async () => { await t.klick("[data-erfassen-open]", 20); };
const url = async (wert) => { const f = t.q("[data-erfassen-url]"); f.value = wert; f.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); await sleep(10); };
const titel = () => t.q(".erfassen-titel")?.textContent.trim();
const schritte = () => t.qa(".web-schritt").map((l) => l.className.replace("web-schritt", "").trim() + ":" + l.textContent.replace(/\s+/g, " ").trim());
const wahl = async (key, an) => { const c = t.q(`[data-web-feldwahl="${key}"]`); c.checked = an; c.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true })); await sleep(10); };
"""


@braucht_jsdom
def test_ohne_ki_wird_sofort_ausgelesen_und_zeigt_schritte() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = null;
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    const s2 = { titel: titel(), schritte: schritte(), abo: abos[0].m, status: t.q(".web-status-liste").textContent.replace(/\s+/g, " ") };
    await ereignis({ phase: "osm", status: "uebersprungen" });
    await ereignis({ phase: "website", status: "ok", url: URL_, seiten: 2 });
    const zwischen = titel();
    await ereignis({ phase: "fertig", vorschlag: VORSCHLAG });
    console.log(JSON.stringify({ s2, zwischen, titel: titel(), schritte: schritte(), zeilen: t.qa("[data-web-feldwahl]").length }));
    process.exit(0);
    """
    )
    assert e["s2"]["titel"] == "Webseite wird ausgelesen"
    assert e["s2"]["schritte"][0].startswith("erledigt") and e["s2"]["schritte"][1].startswith("aktiv")
    assert e["s2"]["abo"] == {"type": "hofkarte/management/enrich", "website": "https://hof.example/"}
    assert "KI-Auswertung nicht eingerichtet" in e["s2"]["status"]
    assert e["zwischen"] == "Webseite wird ausgelesen" and e["titel"] == "Angaben prüfen"
    assert e["schritte"][2].startswith("aktiv") and e["zeilen"] >= 6


@braucht_jsdom
def test_mit_ki_zuerst_wahl_mit_datenschutzhinweis_und_ki_flag() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = "ai_task.lokal";
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    const s1 = { titel: titel(), abos: abos.length, hinweis: t.q(".web-ablauf").textContent.includes("Datenschutz") && t.q(".web-ablauf").textContent.includes("ai_task.lokal"), ki: t.q("[data-web-ki]").checked, url: t.q("[data-web-url]").value };
    const ki = t.q("[data-web-ki]"); ki.checked = true; ki.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await t.klick("[data-web-start]", 30);
    console.log(JSON.stringify({ s1, abo: abos[0].m, titel: titel() }));
    process.exit(0);
    """
    )
    assert e["s1"] == {"titel": "Von Webseite erfassen", "abos": 0, "hinweis": True, "ki": False, "url": "https://hof.example/"}
    assert e["abo"] == {"type": "hofkarte/management/enrich", "website": "https://hof.example/", "ki": True}
    assert e["titel"] == "Webseite wird ausgelesen"


@braucht_jsdom
def test_vorliegendes_pruefen_und_ki_nachtraeglich_ohne_wahl_zu_aendern() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = "ai_task.lokal";
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    t.q("[data-web-ki]").checked = true; t.q("[data-web-ki]").dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await t.klick("[data-web-start]", 30);
    const ohneKnopf = !t.q("[data-web-vorlaeufig]");
    await ereignis({ phase: "website", status: "ok" });
    await ereignis({ phase: "vorlaeufig", vorschlag: VORSCHLAG });
    const stillSchritt2 = titel();
    await t.klick("[data-web-vorlaeufig]", 30);
    const pruefen = { titel: titel(), ladt: t.q(".notice[role=status]")?.textContent || "", vermutung: !!t.q(".finden-vermutung") };
    await wahl("website", false); // Nutzer wählt eine Zeile ab
    await ereignis({ phase: "ki", status: "ok" });
    await ereignis({ phase: "fertig", vorschlag: MIT_KI });
    const danach = {
      titel: titel(), neu: t.q(".notice[role=status]").textContent, vermutung: !!t.q(".finden-vermutung"),
      vermutungGewaehlt: t.q('[data-web-feldwahl="vermutung:angebote"]').checked,
      websiteGewaehlt: t.q('[data-web-feldwahl="website"]').checked, nameGewaehlt: t.q('[data-web-feldwahl="name"]').checked,
      abgemeldet: abos[0].abgemeldet === true,
    };
    console.log(JSON.stringify({ ohneKnopf, stillSchritt2, pruefen, danach }));
    process.exit(0);
    """
    )
    assert e["ohneKnopf"] and e["stillSchritt2"] == "Webseite wird ausgelesen"
    assert e["pruefen"]["titel"] == "Angaben prüfen" and "KI läuft noch" in e["pruefen"]["ladt"] and e["pruefen"]["vermutung"] is False
    d = e["danach"]
    assert "KI-Auswertung ist fertig" in d["neu"] and d["vermutung"] is True
    assert d["vermutungGewaehlt"] is False  # nie vorausgewählt
    assert d["websiteGewaehlt"] is False and d["nameGewaehlt"] is True  # Nutzerwahl bleibt


@braucht_jsdom
def test_pruefansicht_quelle_abweichung_vorschau_und_escaping() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = null;
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    await ereignis({ phase: "fertig", vorschlag: MIT_KI });
    const text = t.q(".web-zeilen").textContent;
    const vorschau1 = t.q("[data-web-vorschau]").textContent;
    const vorbelegt = t.qa("[data-web-feldwahl]").filter((c) => c.checked).length;
    await wahl("adresse", false);
    const vorschau2 = t.q("[data-web-vorschau]").textContent;
    await wahl("vermutung:angebote", true);
    const vorschau3 = t.q("[data-web-vorschau]").textContent;
    console.log(JSON.stringify({
      xss: !t.q(".web-ablauf i"), name: text.includes("Hofladen <i>Müller</i>"), quelle: text.includes("Website"), abw: text.includes("weicht von OpenStreetMap ab"),
      verm: t.q(".finden-vermutung").textContent.includes("nicht im Text"), vorbelegt, vorschau1, vorschau2, vorschau3,
      knopf: t.q("[data-web-uebernehmen]").textContent.trim(),
      link: !!t.q('.web-zeile a.website-link[href="https://hof.example/"]'),
    }));
    process.exit(0);
    """
    )
    assert e["xss"] and e["name"] and e["quelle"] and e["abw"] and e["verm"] and e["link"]
    assert "Dorfstrasse 1" in e["vorschau1"] and "Dorfstrasse 1" not in e["vorschau2"]
    assert "Trüffel" not in e["vorschau1"] and "Trüffel" in e["vorschau3"]
    assert e["vorbelegt"] == 7 and e["knopf"] == "In Formular übernehmen (7)"


@braucht_jsdom
def test_uebernahme_ins_formular_mit_quellen_und_vermutung_als_inferred() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = null;
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    await ereignis({ phase: "fertig", vorschlag: MIT_KI });
    await wahl("mobilnummer", false);
    await wahl("vermutung:angebote", true);
    await t.klick("[data-web-uebernehmen]", 60);
    const ed = el.editing;
    console.log(JSON.stringify({
      editor: !!ed, name: ed.name, website: ed.website, tel: ed.mobilnummer || "", adresse: ed.adresse,
      angebote: JSON.stringify(ed.angebote), quellen: (ed.quellen || []).map((q) => q.feld + ":" + q.quelle + ":" + q.status),
      ablaufWeg: el.webseite === null && el.erfassen === null, titel: !!t.q("[data-save], form, .editor-fuss, [data-abbrechen]"),
    }));
    process.exit(0);
    """
    )
    assert e["editor"] and e["name"] == "Hofladen <i>Müller</i>" and e["website"] == "https://hof.example/" and e["tel"] == ""
    assert e["adresse"] == "Dorfstrasse 1" and all(n in e["angebote"] for n in ("Eier", "Honig", "Trüffel"))
    assert "name:website:confirmed" in e["quellen"] and "angebote:ki:inferred" in e["quellen"]
    assert e["ablaufWeg"]


@braucht_jsdom
def test_nichts_gefunden_fehler_zurueck_und_von_hand() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = null;
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    await ereignis({ phase: "website", status: "robots_gesperrt" });
    await ereignis({ phase: "fertig", vorschlag: { daten: {}, quellen: [], abweichungen: {} } });
    const leer = { text: t.q(".web-ablauf").textContent, status: t.q(".web-ablauf").textContent.includes("robots.txt"), keineZeile: !t.q("[data-web-feldwahl]") };
    await t.klick("[data-web-zurueck]", 30);
    const einstiegDa = !!t.q("[data-erfassen-url]") && t.q("[data-erfassen-url]").value === URL_;
    await t.klick("[data-erfassen-auslesen]", 30);
    await ereignis({ phase: "fertig", vorschlag: { daten: {}, quellen: [], abweichungen: {} } });
    await t.klick("[data-web-leer]", 60);
    const ed = { website: el.editing?.website, offen: !!el.editing };
    console.log(JSON.stringify({ leer, einstiegDa, ed, abos: abos.length, abgemeldet: abos[0].abgemeldet === true }));
    process.exit(0);
    """
    )
    assert e["leer"]["status"] and e["leer"]["keineZeile"] and "keine verwertbaren" in e["leer"]["text"]
    assert e["einstiegDa"] and e["ed"] == {"website": "https://hof.example/", "offen": True} and e["abgemeldet"]


@braucht_jsdom
def test_abofehler_zeigt_meldung_und_erneut_versuchen() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = null;
    let versuche = 0;
    el.hass.connection.subscribeMessage = async (cb, m) => { versuche++; if (versuche === 1) throw { code: "not_ready" }; abos.push({ cb, m }); return () => {}; };
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    const fehler = t.q(".web-ablauf .notice.error")?.textContent || "";
    await t.klick("[data-web-start]", 30);
    console.log(JSON.stringify({ fehler, versuche, fehlerWeg: !t.q(".web-ablauf .notice.error") }));
    process.exit(0);
    """
    )
    assert "nicht bereit" in e["fehler"] and e["versuche"] == 2 and e["fehlerWeg"]


@braucht_jsdom
def test_schritt1_url_validierung_und_enter() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = "ai_task.lokal";
    await einstieg(); await url(URL_);
    await t.klick("[data-erfassen-auslesen]", 30);
    const f = t.q("[data-web-url]");
    f.value = "kaputt"; f.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true }));
    const gesperrt = t.q("[data-web-start]").disabled;
    f.dispatchEvent(new t.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true, cancelable: true })); await sleep(20);
    const meldung = t.q(".notice.error")?.textContent || "";
    const nochSchritt1 = abos.length === 0;
    t.q("[data-web-url]").value = "https://anderer.example/";
    t.q("[data-web-url]").dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true }));
    t.q("[data-web-url]").dispatchEvent(new t.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true, cancelable: true })); await sleep(30);
    console.log(JSON.stringify({ gesperrt, meldung, nochSchritt1, abo: abos[0]?.m }));
    process.exit(0);
    """
    )
    assert e["gesperrt"] and "gültige Webseite" in e["meldung"] and e["nochSchritt1"]
    assert e["abo"]["website"] == "https://anderer.example/"
