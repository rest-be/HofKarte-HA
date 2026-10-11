"""Detail & Erfassung, Phase 7: Szenario 3 «Angaben ergänzen» (Abgleich, Vorwahl, Übernahme)."""

from __future__ import annotations

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_START = r"""
const t = bauen({ n: 2 });
await sleep(100);
const el = t.el;
const item = t.items[0];
Object.assign(item, {
  name: "Hof Müller", adresse: "Dorfstrasse 1", plz: "3000", ort: "", land: "CH", website: "https://hof.example/", mobilnummer: "",
  email: "alt@hof.example", latitude: 46.9, longitude: 7.4, bewertung: 3, beschreibung: "x",
  oeffnungszeiten: [{ wochentag: 1, beginn: "09:00", ende: "11:00" }],
  angebote: [{ id: "eier", name: "Eier" }], zahlungsarten: [], bilder: [],
  quellen: [{ feld: "angebote", quelle: "angabe", status: "confirmed" }, { feld: "email", quelle: "angabe", status: "confirmed" }],
});
await el.load(); await sleep(30);
el._kiEntitaet = null;
const nachrichten = [];
const abos = [];
let kandidaten = [{ refs: ["node/9"], name: "Hof Müller", latitude: 46.9, longitude: 7.4, entfernung_meter: 12, konfidenz: "hoch", adresse: "Dorfstrasse 1", plz: "3000", ort: "Bern", website: "https://hof.example/" }];
const orig = el.hass.connection.sendMessagePromise;
el.hass.connection.sendMessagePromise = async (m) => { nachrichten.push(m); if (m.type === "hofkarte/management/discover") return { kandidaten }; return orig(m); };
el.hass.connection.subscribeMessage = async (cb, m) => { abos.push({ cb, m }); return () => { abos.at(-1).abgemeldet = true; }; };
const VORSCHLAG = {
  daten: { name: "Hof <b>Müller</b> GmbH", adresse: "Dorfstrasse 1", plz: "3000", ort: "Bern", land: "CH", website: "https://hof.example", mobilnummer: "031 111 22 33", email: "neu@hof.example",
    oeffnungszeiten: [{ wochentag: 1, beginn: "08:00", ende: "12:00" }], angebote: ["Eier", "Honig"], zahlungsarten: ["Bargeld", "TWINT"], latitude: 46.9001, longitude: 7.4001 },
  quellen: [{ feld: "ort", quelle: "openstreetmap", status: "confirmed", url: "https://www.openstreetmap.org/node/9", lizenz: "© OpenStreetMap-Mitwirkende (ODbL)" },
            { feld: "mobilnummer", quelle: "website", status: "confirmed", url: "https://hof.example/" },
            { feld: "email", quelle: "website", status: "confirmed", url: "https://hof.example/" },
            { feld: "oeffnungszeiten", quelle: "website", status: "confirmed", url: "https://hof.example/" },
            { feld: "name", quelle: "website", status: "confirmed", url: "https://hof.example/" },
            { feld: "zahlungsarten", quelle: "website", status: "confirmed", url: "https://hof.example/" }],
  abweichungen: {},
};
const ereignis = async (e) => { abos.at(-1).cb(e); await sleep(20); };
const oeffne = async () => { el.view(el.items.find((x) => x.id === item.id)); await sleep(30); await t.klick("[data-ergaenzen]", 30); };
const titel = () => t.q(".erfassen-titel")?.textContent.trim();
const zeile = (key) => t.q(`[data-erg-feldwahl="${key}"]`);
const wahl = async (key, an) => { const c = zeile(key); c.checked = an; c.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true })); await sleep(10); };
const lauf = async () => { await t.klick("[data-erg-start]", 60); await sleep(30); await ereignis({ phase: "fertig", vorschlag: VORSCHLAG }); };
const status = () => Object.fromEntries(t.qa(".erg-zeile").map((z) => [z.querySelector(".webseite-info-label").textContent, z.querySelector(".erg-badge").textContent]));
"""


@braucht_jsdom
def test_einstiege_detail_header_und_hinweis_oeffnen_den_abgleich() -> None:
    e = _node(
        _START
        + r"""
    el.view(el.items.find((x) => x.id === item.id)); await sleep(30);
    const knoepfe = t.qa("[data-ergaenzen]").length;
    await t.klick(".top [data-ergaenzen]", 30);
    const s1 = { titel: titel(), prozent: t.q(".erg-vollst strong").textContent, noch: t.q(".erg-vollst").textContent.includes("Noch offen"), url: t.q("[data-erg-url]").value, osm: t.q("[data-erg-osm]").checked, ki: !!t.q("[data-erg-ki]") };
    await t.klick("[data-erg-zurueck]", 20);
    const zurueckDetail = !!t.q(".blick");
    console.log(JSON.stringify({ knoepfe, s1, zurueckDetail, aboVorher: abos.length }));
    process.exit(0);
    """
    )
    assert e["knoepfe"] == 2 and e["s1"]["titel"] == "Angaben ergänzen" and "%" in e["s1"]["prozent"] and e["s1"]["noch"]
    assert e["s1"]["url"] == "https://hof.example/" and e["s1"]["osm"] is True and e["s1"]["ki"] is False
    assert e["zurueckDetail"] and e["aboVorher"] == 0


@braucht_jsdom
def test_vergleich_status_vorwahl_nur_luecken_und_escaping() -> None:
    e = _node(
        _START
        + r"""
    await oeffne(); await lauf();
    const st = status();
    const vor = Object.fromEntries(t.qa("[data-erg-feldwahl]").map((c) => [c.dataset.ergFeldwahl, c.checked]));
    const text = t.q(".erg-liste").textContent;
    await t.klick('[data-erg-filter="alle"]', 20);
    const alleStatus = status();
    console.log(JSON.stringify({ st, vor, xss: !t.q(".erg-liste b"), name: text.includes("Hof <b>Müller</b> GmbH"), alleStatus, discover: nachrichten.find((m) => m.type === "hofkarte/management/discover"), abo: abos[0].m, knopf: t.q("[data-erg-uebernehmen]").textContent.trim() }));
    process.exit(0);
    """
    )
    st = e["st"]
    assert st["Name"] == "Abweichend" and st["Adresse"] == "Lücke" and st["Telefon"] == "Lücke"
    assert st["E-Mail"] == "Abweichend" and st["Öffnungszeiten"] == "Abweichend"
    assert st["Angebote"] == "Ergänzung" and st["Zahlungsarten"] == "Lücke"
    assert "Webseite" not in st and "Koordinaten" not in st  # gleich bzw. <= 25 m: nur unter «Alle»
    assert e["alleStatus"]["Webseite"] == "Gleich" and e["alleStatus"]["Koordinaten"] == "Gleich"
    vor = e["vor"]
    assert vor["adresse"] is True and vor["mobilnummer"] is True and vor["zahlungsarten"] is True
    assert vor["name"] is False and vor["email"] is False and vor["oeffnungszeiten"] is False and vor["angebote"] is False
    assert e["xss"] and e["name"]
    assert e["discover"]["radius"] == 250 and e["discover"]["name"] == "Hof Müller"
    assert e["abo"]["kandidat"]["refs"] == ["node/9"] and e["abo"]["website"] == "https://hof.example/"
    assert e["knopf"] == "Auswahl übernehmen (3)"


@braucht_jsdom
def test_uebernahme_nur_gewaehltes_nichts_ueberschrieben_listen_ergaenzt_quellen() -> None:
    e = _node(
        _START
        + r"""
    await oeffne(); await lauf();
    await wahl("angebote", true);       // Liste ergänzen (Abweichung/Ergänzung nur auf Wunsch)
    await wahl("email", false); await wahl("name", false);
    await t.klick("[data-erg-uebernehmen]", 60);
    const ed = el.editing;
    console.log(JSON.stringify({
      editor: !!ed, ergaenzenWeg: el.ergaenzen === null, name: ed.name, email: ed.email, ort: ed.ort, adresse: ed.adresse, tel: ed.mobilnummer, zeiten: ed.oeffnungszeiten,
      angebote: (ed.angebote || []).map((a) => a.name), zahlungsarten: (ed.zahlungsarten || []).map((a) => a.name),
      quellen: (ed.quellen || []).map((q) => q.feld + ":" + q.quelle).sort(), geaendert: el.editGeaendert, hinweis: t.q("[data-auto-info-status]")?.textContent || "",
      gespeichert: nachrichten.filter((m) => m.type === "hofkarte/management/save").length,
    }));
    process.exit(0);
    """
    )
    assert e["editor"] and e["ergaenzenWeg"]
    assert e["name"] == "Hof Müller" and e["email"] == "alt@hof.example"  # Abweichungen ohne Wahl unverändert
    assert e["ort"] == "Bern" and e["tel"] == "031 111 22 33" and e["adresse"] == "Dorfstrasse 1"
    assert e["zeiten"] == [{"wochentag": 1, "beginn": "09:00", "ende": "11:00"}]
    assert e["angebote"] == ["Eier", "Honig"] and e["zahlungsarten"] == ["Bargeld", "TWINT"]
    q = e["quellen"]
    assert "ort:openstreetmap" in q and "mobilnummer:website" in q and "zahlungsarten:website" in q
    assert "angebote:angabe" not in q and not any(x.startswith("angebote:") for x in q)  # gemischte Herkunft: keine falsche Angabe
    assert "email:angabe" in q  # nicht übernommen: bisherige Herkunft bleibt
    assert e["geaendert"] and "übernommen" in e["hinweis"] and e["gespeichert"] == 0


@braucht_jsdom
def test_abweichung_nur_mit_ausdruecklicher_wahl_wird_ersetzt() -> None:
    e = _node(
        _START
        + r"""
    await oeffne(); await lauf();
    await wahl("oeffnungszeiten", true); await wahl("email", true); await wahl("name", true);
    await t.klick("[data-erg-uebernehmen]", 60);
    const ed = el.editing;
    console.log(JSON.stringify({ name: ed.name, email: ed.email, zeiten: ed.oeffnungszeiten, quellen: ed.quellen.map((q) => q.feld + ":" + q.quelle).sort() }));
    process.exit(0);
    """
    )
    assert e["name"] == "Hof <b>Müller</b> GmbH" and e["email"] == "neu@hof.example"
    assert e["zeiten"] == [{"wochentag": 1, "beginn": "08:00", "ende": "12:00"}]
    assert "email:website" in e["quellen"] and "email:angabe" not in e["quellen"]


@braucht_jsdom
def test_filter_nur_luecken_fuellen_nichts_waehlen_und_fussleiste_zaehlt() -> None:
    e = _node(
        _START
        + r"""
    await oeffne(); await lauf();
    await wahl("email", true);
    const n1 = t.q("[data-erg-uebernehmen]").textContent.trim();
    await t.klick("[data-erg-nichts]", 20);
    const n0 = { text: t.q("[data-erg-uebernehmen]").textContent.trim(), aus: t.q("[data-erg-uebernehmen]").disabled, anzahl: t.q("[data-erg-anzahl]").textContent };
    await wahl("name", true);
    await t.klick("[data-erg-luecken]", 20);
    const luecken = Object.fromEntries(t.qa("[data-erg-feldwahl]").map((c) => [c.dataset.ergFeldwahl, c.checked]));
    const unterschiede = t.q('[data-erg-filter="unterschiede"]').textContent;
    const gleichSichtbar0 = t.qa(".erg-gleich").length;
    await t.klick('[data-erg-filter="alle"]', 20);
    const gleichSichtbar1 = t.qa(".erg-gleich").length;
    const gewaehltBleibt = t.q('[data-erg-feldwahl="adresse"]').checked;
    console.log(JSON.stringify({ n1, n0, luecken, unterschiede, gleichSichtbar0, gleichSichtbar1, gewaehltBleibt }));
    process.exit(0);
    """
    )
    assert e["n1"] == "Auswahl übernehmen (4)"
    assert e["n0"] == {"text": "Auswahl übernehmen (0)", "aus": True, "anzahl": "0 gewählt"}
    assert e["luecken"]["name"] is False and e["luecken"]["adresse"] is True and e["luecken"]["email"] is False
    assert "(7)" in e["unterschiede"] and e["gleichSichtbar0"] == 0 and e["gleichSichtbar1"] >= 2 and e["gewaehltBleibt"]


@braucht_jsdom
def test_osm_kein_treffer_nur_webseite_und_fehlerfaelle() -> None:
    e = _node(
        _START
        + r"""
    kandidaten = [];
    await oeffne();
    await t.klick("[data-erg-start]", 80);
    const abo = abos[0]?.m;
    const statusText = t.q(".web-ablauf").textContent;
    await ereignis({ phase: "fertig", vorschlag: VORSCHLAG });
    // Nur OSM, kein Treffer: nichts zum Abgleichen
    await t.klick("[data-erg-zurueck]", 20); await t.klick("[data-ergaenzen]", 30);
    const w = t.q("[data-erg-web]"); w.checked = false; w.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await t.klick("[data-erg-start]", 80);
    const keine = { fehler: t.q(".notice.error")?.textContent || "", abos: abos.length, nochmal: !!t.q("[data-erg-start]") };
    // Keine Quelle gewählt
    await t.klick("[data-erg-zurueck]", 20); await t.klick("[data-ergaenzen]", 30);
    const o = t.q("[data-erg-osm]"); o.checked = false; o.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    const w2 = t.q("[data-erg-web]"); w2.checked = false; w2.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    const gesperrt = t.q("[data-erg-start]").disabled;
    console.log(JSON.stringify({ abo, status: statusText, keine, gesperrt }));
    process.exit(0);
    """
    )
    assert "kandidat" not in e["abo"] and e["abo"]["website"] == "https://hof.example/" and "kein sicherer Treffer" in e["status"]
    assert "kein sicherer Treffer" in e["keine"]["fehler"] and e["keine"]["abos"] == 1 and e["keine"]["nochmal"]
    assert e["gesperrt"] is True


@braucht_jsdom
def test_ki_nachtraeglich_laesst_auswahl_unveraendert_und_von_hand() -> None:
    e = _node(
        _START
        + r"""
    el._kiEntitaet = "ai_task.lokal";
    await oeffne();
    const hinweis = t.q(".web-ablauf").textContent.includes("Datenschutz");
    const k = t.q("[data-erg-ki]"); k.checked = true; k.dispatchEvent(new t.w.Event("change", { bubbles: true, composed: true }));
    await t.klick("[data-erg-start]", 80);
    await ereignis({ phase: "vorlaeufig", vorschlag: VORSCHLAG });
    const laeuft = t.q(".notice[role=status]")?.textContent || "";
    await wahl("email", true); await wahl("adresse", false);
    await ereignis({ phase: "ki", status: "ok" });
    await ereignis({ phase: "fertig", vorschlag: { ...VORSCHLAG, vermutungen: { angebote: ["Trüffel"] } } });
    const danach = { email: zeile("email").checked, adresse: zeile("adresse").checked, neu: t.q(".notice[role=status]")?.textContent || "", verm: t.q(".web-ablauf").textContent.includes("KI-Vermutungen") };
    console.log(JSON.stringify({ hinweis, kiFlag: abos[0].m.ki, laeuft, danach }));
    process.exit(0);
    """
    )
    assert e["hinweis"] and e["kiFlag"] is True and "KI läuft noch" in e["laeuft"]
    assert e["danach"]["email"] is True and e["danach"]["adresse"] is False and "KI-Auswertung ist fertig" in e["danach"]["neu"] and e["danach"]["verm"]


@braucht_jsdom
def test_von_hand_bearbeiten_und_noch_offen_seite_fuehrt_in_den_abgleich() -> None:
    e = _node(
        _START
        + r"""
    await oeffne();
    await t.klick("[data-erg-von-hand]", 40);
    const von = { editor: !!el.editing, name: el.editing?.name, ergaenzenWeg: el.ergaenzen === null };
    el.editing = null; el.render(); await sleep(20);
    // Schnellerfassung: «Jetzt ergänzen» öffnet den Abgleich, Zurück landet im Detail
    el.vorOrt = { schritt: 3, gespeichert: el.items[0], name: "x", website: "" }; el.erfassen = {}; el.render(); await sleep(20);
    await t.klick("[data-vorort-ergaenzen]", 40);
    const ab = { titel: titel(), vorOrtWeg: el.vorOrt === null };
    await t.klick("[data-erg-zurueck]", 20);
    console.log(JSON.stringify({ von, ab, detail: !!t.q(".blick") }));
    process.exit(0);
    """
    )
    assert e["von"] == {"editor": True, "name": "Hof Müller", "ergaenzenWeg": True}
    assert e["ab"] == {"titel": "Angaben ergänzen", "vorOrtWeg": True} and e["detail"]
