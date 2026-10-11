"""Detail & Erfassung, Phase 4: Einstieg «Hofladen erfassen»."""

from __future__ import annotations

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_START = r"""
const t = bauen({ n: 3 });
await sleep(100);
const el = t.el;
let bestaetigung = true; let fragen = [];
t.w.confirm = (m) => { fragen.push(m); return bestaetigung; };
const einstieg = async () => { await t.klick("[data-erfassen-open]", 20); };
"""


@braucht_jsdom
def test_kopfzeile_hat_einen_knopf_und_einstieg_oeffnet_und_schliesst() -> None:
    e = _node(
        _START
        + r"""
    const kopf = { erfassen: t.qa("[data-erfassen-open]").length, finden: t.qa("[data-finden-open]").length, neu: t.qa("[data-new]").length, text: t.q("[data-erfassen-open]").textContent.trim() };
    await einstieg();
    const karten = t.qa(".erfassen-karte h3").map((h) => h.textContent.trim());
    const listeWeg = !t.q("[data-listen-filter]");
    await t.klick("[data-erfassen-zurueck]", 20);
    console.log(JSON.stringify({ kopf, karten, listeWeg, zurueck: !!t.q("[data-listen-filter]"), einstiegWeg: !t.q(".erfassen-karte") }));
    process.exit(0);
    """
    )
    assert e["kopf"] == {"erfassen": 1, "finden": 0, "neu": 0, "text": "Hofladen erfassen"}
    assert e["karten"] == ["Ich stehe vor dem Hofladen", "Ich habe eine Webseite", "Von Hand erfassen"]
    assert e["listeWeg"] and e["zurueck"] and e["einstiegWeg"]


@braucht_jsdom
def test_auslesen_nur_bei_gueltiger_http_adresse_und_fokus_bleibt() -> None:
    e = _node(
        _START
        + r"""
    await einstieg();
    const feld = t.q("[data-erfassen-url]");
    const knopf = () => t.q("[data-erfassen-auslesen]");
    const zustand = {};
    for (const wert of ["", "hof", "hof.ch", "javascript:alert(1)", "ftp://hof.ch", "https://hof", "https://hof.ch", " http://www.hof.ch/laden "]) {
      feld.value = wert; feld.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true }));
      zustand[JSON.stringify(wert)] = knopf().disabled;
    }
    console.log(JSON.stringify({ zustand, gleichesFeld: t.q("[data-erfassen-url]") === feld, gemerkt: el.erfassen.url }));
    process.exit(0);
    """
    )
    z = e["zustand"]
    assert [v for k, v in z.items() if k in ('""', '"hof"', '"hof.ch"', '"javascript:alert(1)"', '"ftp://hof.ch"', '"https://hof"')] == [True] * 6
    assert z['"https://hof.ch"'] is False and z['" http://www.hof.ch/laden "'] is False
    assert e["gleichesFeld"] is True


@braucht_jsdom
def test_vor_ort_uebernimmt_name_und_webseite_startet_auslesen_ohne_standort() -> None:
    e = _node(
        _START
        + r"""
    let geoAufrufe = 0;
    t.w.Object.defineProperty(t.w.navigator, "geolocation", { configurable: true, value: { getCurrentPosition: () => { geoAufrufe++; } } });
    await einstieg();
    const name = t.q("[data-erfassen-name]"); name.value = "Hofladen Seeblick"; name.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true }));
    await t.klick("[data-finden-open]", 30);
    const vorOrt = { name: t.q('[data-finden-feld="name"]').value, geo: geoAufrufe, dialog: !!t.q("[data-finden-dialog]"), website: t.q('[data-finden-feld="website"]').value };
    await t.klick("[data-finden-abbrechen]", 30);
    const nochEinstieg = !!t.q("[data-erfassen-url]");
    // Webseite: Auslesen startet direkt die Auswertung der Webseite, ohne Standortabfrage
    const aufrufe = [];
    el.reichereFindenAn = async (o) => { aufrufe.push(o); };
    const url = t.q("[data-erfassen-url]"); url.value = "https://hof.example/"; url.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true }));
    await t.klick("[data-erfassen-auslesen]", 30);
    console.log(JSON.stringify({ vorOrt, nochEinstieg, aufrufe, geoNachWebseite: geoAufrufe, website: el.finden?.website, nameWeb: el.finden?.name }));
    process.exit(0);
    """
    )
    assert e["vorOrt"]["name"] == "Hofladen Seeblick" and e["vorOrt"]["dialog"] is True and e["vorOrt"]["geo"] == 1
    assert e["nochEinstieg"] is True
    assert e["aufrufe"] == [{"ohneKandidat": True}]
    assert e["geoNachWebseite"] == 1  # kein zweiter Abruf
    assert e["website"] == "https://hof.example/"


@braucht_jsdom
def test_enter_im_url_feld_liest_aus_nur_wenn_gueltig() -> None:
    e = _node(
        _START
        + r"""
    const aufrufe = [];
    el.reichereFindenAn = async (o) => { aufrufe.push(o); };
    await einstieg();
    const url = t.q("[data-erfassen-url]");
    const enter = () => url.dispatchEvent(new t.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true, cancelable: true }));
    url.value = "kaputt"; url.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); enter(); await sleep(20);
    const ungueltig = aufrufe.length;
    url.value = "https://hof.example"; url.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); enter(); await sleep(20);
    console.log(JSON.stringify({ ungueltig, gueltig: aufrufe.length }));
    process.exit(0);
    """
    )
    assert e["ungueltig"] == 0 and e["gueltig"] == 1


@braucht_jsdom
def test_von_hand_oeffnet_formular_und_abbrechen_fuehrt_zur_liste() -> None:
    e = _node(
        _START
        + r"""
    await einstieg();
    await t.klick("[data-new]", 30);
    const form = !!t.q("form") && !t.q(".erfassen-karte");
    await t.klick("[data-cancel]", 30);
    console.log(JSON.stringify({ form, liste: !!t.q("[data-listen-filter]"), einstieg: !!t.q(".erfassen-karte") }));
    process.exit(0);
    """
    )
    assert e["form"] is True and e["liste"] is True and e["einstieg"] is False


@braucht_jsdom
def test_duplikatpruefung_beim_speichern_eines_neuen_hofladens() -> None:
    e = _node(
        _START
        + r"""
    const aufrufe = [];
    el.call = async (typ, daten) => { aufrufe.push(typ); return typ.endsWith("list") ? { hoflaeden: t.items } : {}; };
    const speichern = async (name, lat = "", lon = "") => {
      el.start(); await sleep(20);
      const f = t.q("form"); f.elements["name"].value = name; f.elements["latitude"].value = lat; f.elements["longitude"].value = lon;
      fragen.length = 0; aufrufe.length = 0;
      await el.save(); await sleep(20);
      return { gespeichert: aufrufe.some((a) => a.endsWith("save")), gefragt: fragen.length, frage: fragen[0] || "" };
    };
    const ergebnis = {};
    bestaetigung = false;
    ergebnis.gleicherName = await speichern("  hof 0 meier ");
    ergebnis.gleicheNaehe = await speichern("Ganz anders", String(t.items[1].latitude + 0.0002), String(t.items[1].longitude));
    ergebnis.eindeutig = await speichern("Völlig neu");
    bestaetigung = true;
    ergebnis.bestaetigt = await speichern("Hof 0 Meier");
    // bestehender Hofladen bearbeiten: keine Rückfrage
    el.start(t.items[0]); await sleep(20);
    fragen.length = 0; aufrufe.length = 0;
    await el.save(); await sleep(20);
    ergebnis.bearbeiten = { gespeichert: aufrufe.some((a) => a.endsWith("save")), gefragt: fragen.length };
    console.log(JSON.stringify(ergebnis));
    process.exit(0);
    """
    )
    assert e["gleicherName"]["gespeichert"] is False and e["gleicherName"]["gefragt"] == 1 and "Hof 0 Meier" in e["gleicherName"]["frage"]
    assert e["gleicheNaehe"]["gespeichert"] is False and e["gleicheNaehe"]["gefragt"] == 1
    assert e["eindeutig"] == {"gespeichert": True, "gefragt": 0, "frage": ""}
    assert e["bestaetigt"]["gespeichert"] is True and e["bestaetigt"]["gefragt"] == 1
    assert e["bearbeiten"] == {"gespeichert": True, "gefragt": 0}
