"""Detail & Erfassung, Phase 1: Gruppenmodell und Akkordeon.

Gemeinsame Bausteine für Detail und Bearbeiten (sieben Gruppen, einklappbar,
Zusammenfassung, Vollständigkeitspunkt). Verhaltenstests mit Node/jsdom.
"""

from __future__ import annotations

from .test_static_panel_js_uebersicht import _node, braucht_jsdom

_VOLL = r"""
const voll = { id: "a".repeat(32), name: "Hof Voll", beschreibung: "Käse, Eier und Obst direkt vom Hof.", bewertung: 4,
  adresse: "Seestrasse 12", plz: "6045", ort: "Meggen", land: "CH", latitude: 47.04, longitude: 8.33,
  mobilnummer: "041 555 12 34", email: "laden@hof.example", website: "https://hof.example/",
  oeffnungszeiten: [1,2,3,4,5].map((t) => ({ wochentag: t, beginn: "08:00", ende: "18:30" })).concat([{ wochentag: 6, beginn: "08:00", ende: "16:00" }]),
  sonderoeffnungszeiten: [], angebote: [{ name: "Eier" }, { name: "Käse" }], zahlungsarten: [{ name: "Bargeld" }],
  bilder: [{ url: "/x.jpg" }], quellen: [{ feld: "name", quelle: "website" }] };
const leer = { id: "b".repeat(32), name: "Hof Leer" };
"""


@braucht_jsdom
def test_vollstaendigkeit_und_zusammenfassungen() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    const v = t.el.vollstaendigkeit(voll), l = t.el.vollstaendigkeit(leer);
    const z = (d) => Object.fromEntries(["grunddaten","adresse","kontakt","zeiten","angebote","bilder","herkunft"].map((i) => [i, t.el.gruppenZusammenfassung(d, i)]));
    console.log(JSON.stringify({ v, l, zv: z(voll), zl: z(leer) }));
    process.exit(0);
    """
    )
    assert e["v"]["gruppen"] == {"grunddaten": "ok", "adresse": "ok", "kontakt": "ok", "zeiten": "ok", "angebote": "ok", "bilder": "ok", "herkunft": None}
    assert e["v"]["prozent"] == 100 and e["v"]["alleFehlend"] == []
    assert e["l"]["gruppen"]["grunddaten"] == "leer" and e["l"]["gruppen"]["bilder"] == "leer"
    assert e["l"]["prozent"] == 0
    assert "Zahlungsarten" in e["l"]["alleFehlend"] and "Koordinaten" in e["l"]["alleFehlend"]
    assert e["zv"]["zeiten"] == "Mo–Fr 08:00–18:30 · Sa 08:00–16:00"
    assert e["zv"]["angebote"] == "2 Angebote · 1 Zahlungsart"
    assert e["zv"]["kontakt"] == "041 555 12 34 · laden@hof.example · hof.example"
    assert e["zv"]["grunddaten"].endswith("4 von 5 Sternen")
    assert e["zl"]["zeiten"] == "Keine Öffnungszeiten" and e["zl"]["bilder"] == "Keine Bilder"
    assert e["zl"]["angebote"] == "0 Angebote · 0 Zahlungsarten"


@braucht_jsdom
def test_teilweise_gefuellt_ist_teil_und_kontakt_zwei_von_drei() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    const teil = { ...voll, email: "", website: "", angebote: [], bewertung: 0 };
    const v = t.el.vollstaendigkeit(teil);
    console.log(JSON.stringify({ g: v.gruppen, f: v.fehlend, p: v.prozent }));
    process.exit(0);
    """
    )
    assert e["g"]["kontakt"] == "teil" and e["g"]["angebote"] == "teil" and e["g"]["grunddaten"] == "teil"
    assert e["f"]["kontakt"] == ["E-Mail", "Webseite"]
    assert e["f"]["angebote"] == ["Angebote"]
    assert 0 < e["p"] < 100


@braucht_jsdom
def test_gruppen_standard_auf_und_zuklappen_ohne_render() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    const el = t.el;
    const html = el.gruppenAlleHtml("detail") + ["grunddaten","bilder"].map((id) => el.gruppeHtml({ modus: "detail", id, zusammenfassung: "Sum <b>", zustand: "teil", inhalt: '<input name="x" value="1">' })).join("");
    t.q("main").innerHTML = html;
    const kopf = (id) => t.q(`[data-gruppe-toggle="${id}"]`);
    const inhalt = (id) => t.q(`[data-gruppe="${id}"] .gruppe-inhalt`);
    const start = { g: kopf("grunddaten").getAttribute("aria-expanded"), b: kopf("bilder").getAttribute("aria-expanded"), gh: inhalt("grunddaten").hidden, bh: inhalt("bilder").hidden };
    const feld = t.q('[data-gruppe="bilder"] input');
    await t.klick(kopf("bilder"));
    const nachAuf = { b: kopf("bilder").getAttribute("aria-expanded"), bh: inhalt("bilder").hidden, gleichesFeld: t.q('[data-gruppe="bilder"] input') === feld, ctrl: kopf("bilder").getAttribute("aria-controls") === inhalt("bilder").id };
    await t.klick(kopf("grunddaten"));
    const alleText1 = t.q("[data-gruppen-alle]").textContent;
    await t.klick("[data-gruppen-alle]");
    const auf = ["grunddaten","bilder"].map((id) => inhalt(id).hidden);
    const alleText2 = t.q("[data-gruppen-alle]").textContent;
    await t.klick("[data-gruppen-alle]");
    const zu = ["grunddaten","bilder"].map((id) => inhalt(id).hidden);
    console.log(JSON.stringify({ start, nachAuf, alleText1, zu, alleText2, auf, summe: t.q("[data-gruppe-summe]").innerHTML, punkt: t.q(".gruppe-punkt").getAttribute("aria-label"), punktText: t.q(".gruppe-punkt").textContent }));
    process.exit(0);
    """
    )
    assert e["start"] == {"g": "true", "b": "false", "gh": False, "bh": True}
    assert e["nachAuf"] == {"b": "true", "bh": False, "gleichesFeld": True, "ctrl": True}
    # Nicht alle Gruppen offen -> der Knopf öffnet zuerst alle, beim zweiten Klick schliesst er alle.
    assert e["auf"] == [False, False] and e["zu"] == [True, True]
    assert e["alleText1"] == "Alle ausklappen" and e["alleText2"] == "Alle einklappen"
    assert "<b>" not in e["summe"] and "&lt;b&gt;" in e["summe"]
    assert e["punkt"] == "teilweise ausgefüllt" and e["punktText"] == "½"


@braucht_jsdom
def test_zustand_je_maske_getrennt_und_gruppenreihenfolge() -> None:
    e = _node(
        r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    const el = t.el;
    el.setzeAlleGruppen("detail", false);
    console.log(JSON.stringify({
      detailBilder: el.gruppeOffen("detail", "bilder"), editorGrund: el.gruppeOffen("editor", "grunddaten"),
      editorKontakt: el.gruppeOffen("editor", "kontakt"), detailKontakt: el.gruppeOffen("detail", "kontakt"),
      ids: el.constructor.HOF_GRUPPEN.map((g) => g.id),
    }));
    process.exit(0);
    """
    )
    assert e["detailBilder"] is False and e["editorGrund"] is True
    assert e["editorKontakt"] is False and e["detailKontakt"] is False
    assert e["ids"] == ["grunddaten", "adresse", "kontakt", "zeiten", "angebote", "bilder", "herkunft"]


# --- Phase 2: Detailansicht ---------------------------------------------------


@braucht_jsdom
def test_detail_zeigt_sieben_gruppen_in_fester_reihenfolge_und_auf_einen_blick() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    t.el.view({ ...voll, geoeffnet: true, status_wechsel: { art: "schliesst", zeit: "16:00", wochentag: 6, heute: true }, hauptbild_url: null });
    await sleep(40);
    const gruppen = t.qa("[data-gruppe]").map((s) => s.dataset.gruppe);
    const offen = Object.fromEntries(t.qa("[data-gruppe-toggle]").map((b) => [b.dataset.gruppeToggle, b.getAttribute("aria-expanded")]));
    const blick = t.q(".blick");
    console.log(JSON.stringify({
      gruppen, offen, h1: blick.querySelector("h1").textContent, status: blick.querySelector(".status-badge").textContent.trim(),
      aktionen: [...blick.querySelectorAll(".schnellaktionen a")].map((a) => a.textContent.trim() + "|" + a.getAttribute("href").split(":")[0]),
      unvollst: !!t.q(".unvollstaendig"), zurueck: !!t.q("[data-back]"), bearb: !!t.q("[data-edit-from-detail]"),
      menue: t.qa("[data-kachel-menue] [role=menuitem]").map((m) => m.textContent.trim()),
      heute: t.qa(".opening-table tr.heute").length, hatErgaenzen: !!t.q("[data-ergaenzen]"),
    }));
    process.exit(0);
    """
    )
    assert e["gruppen"] == ["grunddaten", "adresse", "kontakt", "zeiten", "angebote", "bilder", "herkunft"]
    assert e["offen"] == {"grunddaten": "true", "adresse": "true", "kontakt": "true", "zeiten": "true", "angebote": "true", "bilder": "false", "herkunft": "false"}
    assert e["h1"] == "Hof Voll" and e["status"].endswith("Offen bis 16:00")
    assert e["aktionen"][-3:] == ["📞 Anrufen|tel", "🔗 Webseite|https", "✉️ E-Mail|mailto"]
    assert e["unvollst"] is False and e["hatErgaenzen"] is True  # «Angaben ergänzen» im Kopf, Hinweis nur bei Lücken
    assert e["zurueck"] and e["bearb"]
    assert e["menue"] == ["Löschen …"]
    assert e["heute"] == 1


@braucht_jsdom
def test_detail_unvollstaendig_hinweis_leerzustaende_und_ergaenzen() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    t.el.items.push({ ...leer, geoeffnet: null });
    t.el.view(t.el.items.at(-1));
    await sleep(40);
    const hinweis = t.q(".unvollstaendig").textContent.replace(/\s+/g, " ").trim();
    const text = t.q("main").textContent;
    const status = t.q(".status-badge").textContent.trim();
    const aktionen = t.qa(".schnellaktionen a").length;
    await t.klick("[data-ergaenzen]", 60);
    console.log(JSON.stringify({ hinweis, text: text.includes("Keine Kontaktangaben hinterlegt") && text.includes("Keine Bilder hinterlegt") && text.includes("Noch keine Bewertung"), status, aktionen, ergaenzen: t.q(".erfassen-titel")?.textContent.trim(), editor: !!t.q("form"), viewing: !!t.el.viewing }));
    process.exit(0);
    """
    )
    assert e["hinweis"].startswith("Noch unvollständig: Beschreibung, Bewertung, Adresse, Ort, Koordinaten, Telefon, E-Mail, Webseite")
    assert e["text"] is True
    assert e["status"] == "Unbekannt"
    assert e["aktionen"] == 0  # nur die (deaktivierten) Routenknöpfe sind Schaltflächen, keine Links
    assert e["ergaenzen"] == "Angaben ergänzen" and e["editor"] is False and e["viewing"] is True  # Abgleich statt direktem Editor


@braucht_jsdom
def test_detail_escaped_inhalte_und_filtert_unsichere_links() -> None:
    e = _node(
        _VOLL
        + r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    t.el.view({ ...voll, name: '<img src=x onerror=1>', beschreibung: '<script>boom()</script>', website: "javascript:alert(1)", email: "a@b.ch?cc=x@y.ch", geoeffnet: false,
      status_wechsel: { art: "oeffnet", zeit: "<b>x</b>", wochentag: 1, heute: false }, hauptbild_url: "javascript:alert(1)" });
    await sleep(40);
    const main = t.q("main");
    console.log(JSON.stringify({
      img: main.querySelectorAll("img[onerror]").length, script: main.querySelectorAll("script").length,
      js: [...main.querySelectorAll("a")].filter((a) => /^javascript:/i.test(a.getAttribute("href") || "")).length,
      mail: [...main.querySelectorAll("a")].filter((a) => (a.getAttribute("href") || "").startsWith("mailto:")).length,
      status: t.q(".status-badge").textContent.trim(),
    }));
    process.exit(0);
    """
    )
    assert e["img"] == 0 and e["script"] == 0 and e["js"] == 0
    assert e["mail"] == 0
    assert e["status"] == "🔴 Geschlossen"  # ungültige Zeitangabe wird nicht angezeigt


@braucht_jsdom
def test_status_wechsel_texte() -> None:
    e = _node(
        r"""
    const t = bauen({ n: 1 });
    await sleep(80);
    const b = (g, w) => t.el.geoeffnetBadge(g, w).replace(/<[^>]+>/g, "").trim();
    console.log(JSON.stringify([
      b(true, { art: "schliesst", zeit: "16:00", wochentag: 6, heute: true }),
      b(true, { art: "schliesst", zeit: "01:00", wochentag: 7, heute: false }),
      b(false, { art: "oeffnet", zeit: "08:00", wochentag: 1, heute: false }),
      b(false, { art: "oeffnet", zeit: "14:00", wochentag: 6, heute: true }),
      b(true, null), b(false, undefined), b(null, null),
    ]));
    process.exit(0);
    """
    )
    assert e == ["🟢 Offen bis 16:00", "🟢 Offen bis So 01:00", "🔴 Geschlossen · öffnet Mo 08:00", "🔴 Geschlossen · öffnet heute 14:00", "🟢 Geöffnet", "🔴 Geschlossen", "Unbekannt"]
