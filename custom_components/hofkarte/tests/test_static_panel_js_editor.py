"""Detail & Erfassung, Phase 3: Bearbeitungsformular mit denselben sieben
Gruppen wie die Detailansicht, Chips, Zeiten kopieren, Fussleiste."""

from __future__ import annotations

from .test_static_panel_js_gruppen import _VOLL
from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_START = r"""
const t = bauen({ n: 1 });
await sleep(80);
const el = t.el;
let bestaetigung = true;
t.w.confirm = () => bestaetigung;
const form = () => t.q("form");
const f = (n) => form().elements[n];
const tippe = async (name, wert) => { const x = f(name); x.value = wert; x.dispatchEvent(new t.w.Event("input", { bubbles: true, composed: true })); await sleep(20); };
"""


@braucht_jsdom
def test_editor_hat_dieselben_gruppen_wie_das_detail_und_speichert_unveraendert() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.view({ ...voll, geoeffnet: true });
    await sleep(30);
    const detailGruppen = t.qa("[data-gruppe]").map((s) => s.dataset.gruppe);
    el.start(voll);
    await sleep(30);
    const editorGruppen = t.qa("[data-gruppe]").map((s) => s.dataset.gruppe);
    const offen = Object.fromEntries(t.qa("[data-gruppe-toggle]").map((b) => [b.dataset.gruppeToggle, b.getAttribute("aria-expanded")]));
    const d = el.formData();
    const schluessel = ["name","beschreibung","bemerkung","adresse","plz","ort","land","mobilnummer","email","website","latitude","longitude","bewertung"];
    const gleich = schluessel.filter((k) => JSON.stringify(d[k] ?? null) !== JSON.stringify(voll[k] ?? null));
    console.log(JSON.stringify({ detailGruppen, editorGruppen, offen, gleichAbweichend: gleich,
      zeiten: d.oeffnungszeiten, angebote: d.angebote.map((x) => x.name), zahl: d.zahlungsarten.map((x) => x.name), bilder: d.bilder.length, id: d.id,
      fussleiste: !!t.q(".fussleiste [data-cancel]") && !!t.q(".fussleiste button[type=submit]"), versteckt: t.q("[data-ungespeichert]").hidden }));
    process.exit(0);
    """
    )
    assert e["detailGruppen"] == e["editorGruppen"] == ["grunddaten", "adresse", "kontakt", "zeiten", "angebote", "bilder", "herkunft"]
    assert e["offen"] == {"grunddaten": "true", "adresse": "true", "kontakt": "false", "zeiten": "false", "angebote": "true", "bilder": "false", "herkunft": "false"}
    assert e["gleichAbweichend"] == []
    assert e["angebote"] == ["Eier", "Käse"] and e["zahl"] == ["Bargeld"] and e["bilder"] == 1
    assert e["zeiten"][0] == {"wochentag": 1, "beginn": "08:00", "ende": "18:30"} and len(e["zeiten"]) == 6
    assert e["id"] == "a" * 32
    assert e["fussleiste"] is True and e["versteckt"] is True


@braucht_jsdom
def test_chips_hinzufuegen_entfernen_umschalten_und_enter_sendet_nicht_ab() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.start({ ...voll, angebote: [{ id: "eier", name: "Eier" }], zahlungsarten: [{ id: "twint", name: "TWINT" }, { id: "bio", name: "Rechnung" }] });
    await sleep(30);
    let gespeichert = 0;
    el.save = () => { gespeichert++; };
    const eingabe = t.q('[data-chip-eingabe="angebote"]');
    eingabe.value = "  Hof  Honig ";
    eingabe.dispatchEvent(new t.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true, cancelable: true }));
    await sleep(20);
    const nachEnter = { felder: f("angebote").value, leer: eingabe.value, gespeichert };
    eingabe.value = "eier"; // Duplikat (ohne Gross-/Kleinschreibung)
    await t.klick('[data-chip-hinzufuegen="angebote"]');
    const nachDuplikat = f("angebote").value;
    eingabe.value = '<img src=x onerror=1> "Q"';
    await t.klick('[data-chip-hinzufuegen="angebote"]');
    const xss = { img: t.qa("img[onerror]").length, wert: f("angebote").value.split("\n").pop() };
    // Entfernen des Chips mit Sonderzeichen
    const knopf = t.qa("[data-chip-entfernen]").find((b) => b.dataset.chipEntfernen.startsWith("<img"));
    await t.klick(knopf);
    const nachEntf = f("angebote").value;
    // Zahlungsarten: TWINT ist an, Bargeld hinzufügen, TWINT ausschalten, "Rechnung" ist ein eigener Chip
    const toggle = (n) => t.qa('[data-chip-feld="zahlungsarten"][data-chip-vorschlag]').find((b) => b.dataset.chipVorschlag === n);
    const pressed0 = toggle("TWINT").getAttribute("aria-pressed");
    await t.klick(toggle("Bargeld"));
    await t.klick(toggle("TWINT"));
    const zahl = f("zahlungsarten").value;
    const pressed1 = [toggle("TWINT").getAttribute("aria-pressed"), toggle("Bargeld").getAttribute("aria-pressed")];
    await t.klick(t.qa('[data-chip-feld="zahlungsarten"][data-chip-entfernen]')[0]);
    const d = el.formData();
    console.log(JSON.stringify({ nachEnter, nachDuplikat, xss, nachEntf, pressed0, pressed1, zahl, ang: d.angebote.map((x) => x.name), zahlen: d.zahlungsarten.map((x) => x.name), geaendert: !t.q("[data-ungespeichert]").hidden }));
    process.exit(0);
    """
    )
    assert e["nachEnter"] == {"felder": "Eier\nHof Honig", "leer": "", "gespeichert": 0}
    assert e["nachDuplikat"] == "Eier\nHof Honig"
    assert e["xss"]["img"] == 0 and e["xss"]["wert"] == '<img src=x onerror=1> "Q"'
    assert e["nachEntf"] == "Eier\nHof Honig"
    assert e["pressed0"] == "true" and e["pressed1"] == ["false", "true"]
    assert e["zahl"] == "Rechnung\nBargeld"
    assert e["ang"] == ["Eier", "Hof Honig"] and e["zahlen"] == ["Bargeld"]
    assert e["geaendert"] is True


@braucht_jsdom
def test_zeiten_kopieren_montag_auf_dienstag_bis_freitag() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.start({ ...voll, oeffnungszeiten: [{ wochentag: 1, beginn: "09:00", ende: "12:00" }, { wochentag: 1, beginn: "14:00", ende: "18:00" }, { wochentag: 3, beginn: "05:00", ende: "06:00" }, { wochentag: 6, beginn: "08:00", ende: "10:00" }] });
    await sleep(30);
    await t.klick("[data-kopiere-montag]");
    const d = el.formData().oeffnungszeiten.map((z) => `${z.wochentag} ${z.beginn}-${z.ende}`);
    // entfernen-Knopf einer kopierten Zeile funktioniert
    const zeile = t.qa('[data-day-interval="4"]')[0];
    await t.klick(zeile.querySelector("[data-remove-interval]"));
    const nach = el.formData().oeffnungszeiten.filter((z) => z.wochentag === 4).length;
    // Modus "geschlossen" wird ebenfalls kopiert
    el.start({ ...voll, oeffnungszeiten: [{ wochentag: 2, beginn: "08:00", ende: "09:00" }] });
    await sleep(30);
    await t.klick("[data-kopiere-montag]");
    console.log(JSON.stringify({ d, nach, geschlossen: el.formData().oeffnungszeiten }));
    process.exit(0);
    """
    )
    erwartet = []
    for tag in (1, 2, 3, 4, 5):
        erwartet += [f"{tag} 09:00-12:00", f"{tag} 14:00-18:00"]
    assert e["d"] == erwartet + ["6 08:00-10:00"]
    assert e["nach"] == 1
    assert e["geschlossen"] == []


@braucht_jsdom
def test_ungespeichert_anzeige_rueckfrage_und_live_zusammenfassung() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.start(voll);
    await sleep(30);
    const vorher = { hidden: t.q("[data-ungespeichert]").hidden, summe: t.q('[data-gruppe-toggle="adresse"] [data-gruppe-summe]').textContent };
    await t.klick("[data-cancel]");
    const ohneAenderung = !!t.q("form") === false; // ohne Änderung ohne Rückfrage zurück
    el.start(voll);
    await sleep(30);
    await tippe("adresse", "Neue Strasse 1");
    await tippe("beschreibung", "");
    const nach = { hidden: t.q("[data-ungespeichert]").hidden, summe: t.q('[data-gruppe-toggle="adresse"] [data-gruppe-summe]').textContent,
      punkt: t.q('[data-gruppe-toggle="grunddaten"] .gruppe-punkt').getAttribute("aria-label") };
    bestaetigung = false;
    await t.klick("[data-cancel]");
    const bleibt = !!t.q("form");
    bestaetigung = true;
    await t.klick("[data-cancel]");
    const weg = !t.q("form");
    el.start(voll);
    await sleep(30);
    console.log(JSON.stringify({ vorher, ohneAenderung, nach, bleibt, weg, nachNeustart: t.q("[data-ungespeichert]").hidden }));
    process.exit(0);
    """
    )
    assert e["vorher"]["hidden"] is True and e["vorher"]["summe"].startswith("Seestrasse 12, 6045 Meggen")
    assert e["ohneAenderung"] is True
    assert e["nach"]["hidden"] is False and e["nach"]["summe"].startswith("Neue Strasse 1, 6045 Meggen")
    assert e["nach"]["punkt"] == "teilweise ausgefüllt"
    assert e["bleibt"] is True and e["weg"] is True and e["nachNeustart"] is True


@braucht_jsdom
def test_fehler_und_pflichtfeld_oeffnen_eingeklappte_gruppen() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.start(voll);
    await sleep(30);
    // Pflichtfeld "Name" in eingeklappter Gruppe: invalid-Ereignis öffnet sie
    await t.klick('[data-gruppe-toggle="grunddaten"]');
    const zu = t.q('[data-gruppe-toggle="grunddaten"]').getAttribute("aria-expanded");
    f("name").dispatchEvent(new t.w.Event("invalid", { bubbles: false, cancelable: true }));
    const auf = t.q('[data-gruppe-toggle="grunddaten"]').getAttribute("aria-expanded");
    // Validierungsfehler bei Öffnungszeiten: Gruppe ist danach offen
    await t.klick('[data-gruppe-toggle="zeiten"]');
    const zeitenZu = t.q('[data-gruppe-toggle="zeiten"]').getAttribute("aria-expanded");
    const z = t.qa('[data-day-interval="1"]')[0];
    z.querySelector("[name=beginn]").value = "10:00"; z.querySelector("[name=ende]").value = "10:00";
    if (zeitenZu === "true") await t.klick('[data-gruppe-toggle="zeiten"]');
    t.el.call = async () => ({});
    await el.save();
    await sleep(30);
    console.log(JSON.stringify({ zu, auf, fehler: t.q(".notice.error")?.textContent, zeitenOffen: t.q('[data-gruppe-toggle="zeiten"]').getAttribute("aria-expanded") }));
    process.exit(0);
    """
    )
    assert e["zu"] == "false" and e["auf"] == "true"
    assert "Öffnungszeiten" in e["fehler"] and e["zeitenOffen"] == "true"


@braucht_jsdom
def test_mein_standort_im_editor_setzt_koordinaten_ohne_render() -> None:
    e = _node(
        _VOLL
        + _START
        + r"""
    el.start({ ...voll, latitude: "", longitude: "" });
    await sleep(30);
    t.w.Object.defineProperty(t.w.navigator, "geolocation", { configurable: true, value: { getCurrentPosition: (ok) => ok({ coords: { latitude: 47.123456789, longitude: 8.5, accuracy: 12.4 } }) } });
    const feld = f("adresse");
    await t.klick("[data-mein-standort]");
    const erst = ({ lat: f("latitude").value, lon: f("longitude").value, status: t.q("[data-standort-status]").textContent, gleichesFeld: f("adresse") === feld, geaendert: !t.q("[data-ungespeichert]").hidden,
      koordPunkt: t.q('[data-gruppe-toggle="adresse"] .gruppe-punkt').getAttribute("aria-label") });
    // verweigert
    t.w.Object.defineProperty(t.w.navigator, "geolocation", { configurable: true, value: { getCurrentPosition: (ok, err) => err({ code: 1 }) } });
    await t.klick("[data-mein-standort]");
    console.log(JSON.stringify({ ...erst, status2: t.q("[data-standort-status]").textContent, lat2: f("latitude").value }));
    process.exit(0);
    """
    )
    assert e["lat"] == "47.123457" and e["lon"] == "8.5" and "±12 m" in e["status"]
    assert e["gleichesFeld"] is True and e["geaendert"] is True and e["koordPunkt"] == "vollständig"
    assert "nicht verfügbar" in e["status2"] and e["lat2"] == "47.123457"  # Koordinaten bleiben bei Ablehnung unverändert
