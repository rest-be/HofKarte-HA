"""Tests für ``discovery.website``, ``provenance`` und ``enrich`` sowie den
WS-Befehl ``enrich``. Kein Netzwerk: eine Fake-Session beantwortet die
Abrufe je URL."""

from __future__ import annotations

import contextlib
import json
from typing import Any

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.hofkarte.discovery import enrich, overpass, provenance, website
from custom_components.hofkarte.discovery.overpass import kandidat_aus_dict
from custom_components.hofkarte.management import ws_enrich

from .test_management import _FakeConnection, _setup_mit_coordinator
from .test_webseite_info import _FakeResponse

BASIS = "https://hof-mueller.example"


def _html(titel: str = "Hof Müller", extra: str = "", jsonld: dict | None = None) -> bytes:
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    return f"<html><head><title>{titel}</title>{ld}</head><body>{extra}</body></html>".encode()


LD_HOF = {
    "@type": "LocalBusiness",
    "name": "Hof Müller",
    "description": "Ein langer Werbetext, der nicht übernommen werden darf.",
    "address": {"streetAddress": "Dorfstrasse 5", "postalCode": "3000", "addressLocality": "Bern"},
    "telephone": "+41 31 111 22 33",
    "email": "info@hof-mueller.example",
    "openingHoursSpecification": [
        {"dayOfWeek": "Friday", "opens": "09:00", "closes": "12:00"},
    ],
    "paymentAccepted": "Twint, Bargeld",
}


class _Seite:
    def __init__(self, status: int = 200, body: bytes = b"", ctype: str = "text/html") -> None:
        self.status, self.body, self.ctype = status, body, ctype


class _Site:
    """Fake-Session: antwortet je URL; unbekannte URLs -> 404."""

    def __init__(self, seiten: dict[str, _Seite | Exception]) -> None:
        self.seiten = seiten
        self.abrufe: list[tuple[str, dict | None]] = []

    def get(self, url: str, *, timeout: Any = None, allow_redirects: Any = None, headers: Any = None):
        self.abrufe.append((url, headers))
        s = self.seiten.get(url, _Seite(404))
        if isinstance(s, Exception):
            raise s
        return _FakeResponse(status=s.status, content_type=s.ctype, body=s.body)

    @property
    def urls(self) -> list[str]:
        return [u for u, _ in self.abrufe]


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch):
    holder: dict[str, _Site] = {}

    @contextlib.asynccontextmanager
    async def _session() -> Any:
        yield holder["s"]

    monkeypatch.setattr("custom_components.hofkarte.webseite_info._sichere_session", _session)

    def setze(seiten: dict[str, _Seite | Exception]) -> _Site:
        holder["s"] = _Site(seiten)
        return holder["s"]

    return setze


@pytest.fixture(autouse=True)
def _ohne_pause(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(website, "PAUSE_SEKUNDEN", 0)


# --- robots.txt --------------------------------------------------------------------


def test_parse_robots_disallow_fuer_wildcard_und_token() -> None:
    r = website.parse_robots("User-agent: *\nDisallow: /privat/\n")
    assert r.erlaubt(f"{BASIS}/kontakt") and not r.erlaubt(f"{BASIS}/privat/x")
    r2 = website.parse_robots("User-agent: HofKarte\nDisallow: /\n")
    assert not r2.erlaubt(f"{BASIS}/")


async def test_robots_404_erlaubt_alles(hass: HomeAssistant, site) -> None:
    s = site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    e = await website.async_hole_website(hass, f"{BASIS}/")
    assert e.status == website.OK and s.urls[0].endswith("/robots.txt")


async def test_robots_gesperrt_ruft_keine_seite_ab(hass: HomeAssistant, site) -> None:
    s = site(
        {
            f"{BASIS}/robots.txt": _Seite(body=b"User-agent: *\nDisallow: /\n", ctype="text/plain"),
            f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF)),
        }
    )
    e = await website.async_hole_website(hass, f"{BASIS}/")
    assert e.status == website.ROBOTS_GESPERRT and e.seiten == ()
    assert s.urls == [f"{BASIS}/robots.txt"]  # nur robots.txt, keine Seite


@pytest.mark.parametrize("fehler", [_Seite(500), _Seite(503), aiohttp.ClientError("x")])
async def test_robots_nicht_lesbar_ist_konservativ(hass: HomeAssistant, site, fehler) -> None:
    s = site({f"{BASIS}/robots.txt": fehler, f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    e = await website.async_hole_website(hass, f"{BASIS}/")
    assert e.status == website.ROBOTS_NICHT_LESBAR
    assert s.urls == [f"{BASIS}/robots.txt"]


async def test_robots_403_gilt_als_nicht_vorhanden(hass: HomeAssistant, site) -> None:
    site({f"{BASIS}/robots.txt": _Seite(403), f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    assert (await website.async_hole_website(hass, f"{BASIS}/")).status == website.OK


async def test_disallow_einzelner_unterseite(hass: HomeAssistant, site) -> None:
    start = _html(extra='<a href="/kontakt">Kontakt</a><a href="/hofladen">Hofladen</a>')
    s = site(
        {
            f"{BASIS}/robots.txt": _Seite(body=b"User-agent: *\nDisallow: /kontakt\n", ctype="text/plain"),
            f"{BASIS}/": _Seite(body=start),
            f"{BASIS}/hofladen": _Seite(body=_html(jsonld=LD_HOF)),
        }
    )
    e = await website.async_hole_website(hass, f"{BASIS}/")
    assert f"{BASIS}/kontakt" not in s.urls and f"{BASIS}/hofladen" in s.urls
    stati = {x.url: x.status for x in e.seiten}
    assert stati[f"{BASIS}/kontakt"] == website.ROBOTS_GESPERRT


async def test_eigener_user_agent_wird_gesendet(hass: HomeAssistant, site) -> None:
    s = site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=_html())})
    await website.async_hole_website(hass, f"{BASIS}/")
    assert all(h and h["User-Agent"] == website.USER_AGENT for _, h in s.abrufe)
    assert "github.com/rest-be" in website.USER_AGENT


# --- Seitenauswahl / Limits ------------------------------------------------------------


def test_waehle_links_filtert_und_begrenzt() -> None:
    html = """
    <a href="/kontakt">Kontakt</a>
    <a href="https://www.hof-mueller.example/oeffnungszeiten#x">Zeiten</a>
    <a href="https://fremd.example/kontakt">Fremd</a>
    <a href="/prospekt.pdf">Hofladen Prospekt</a>
    <a href="/login">Login Kontakt</a>
    <a href="/blog">Blog</a>
    <a href="/">Start</a>
    <a href="mailto:a@b.ch">Kontakt</a>
    <a href="/produkte">Produkte</a><a href="/shop">Shop</a><a href="/impressum">Impressum</a>
    """
    links = website.waehle_links(html, f"{BASIS}/", 3)
    assert len(links) == 3
    assert all(l.startswith(("https://hof-mueller.example", "https://www.hof-mueller.example")) for l in links)
    assert not any(x in " ".join(links) for x in ("fremd", ".pdf", "login", "blog", "mailto"))
    assert f"{BASIS}/" not in links


async def test_max_seiten_wird_eingehalten(hass: HomeAssistant, site) -> None:
    start = _html(extra="".join(f'<a href="/kontakt{i}">Kontakt {i}</a>' for i in range(10)))
    seiten: dict[str, _Seite | Exception] = {f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=start)}
    for i in range(10):
        seiten[f"{BASIS}/kontakt{i}"] = _Seite(body=_html(jsonld=LD_HOF))
    s = site(seiten)
    await website.async_hole_website(hass, f"{BASIS}/")
    seitenabrufe = [u for u in s.urls if not u.endswith("robots.txt")]
    assert len(seitenabrufe) == website.MAX_SEITEN


async def test_unterseite_nicht_erreichbar_bricht_nicht_ab(hass: HomeAssistant, site) -> None:
    start = _html(extra='<a href="/kontakt">Kontakt</a>', jsonld=LD_HOF)
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=start), f"{BASIS}/kontakt": _Seite(500)})
    e = await website.async_hole_website(hass, f"{BASIS}/")
    assert e.status == website.OK
    assert [s.status for s in e.seiten] == [website.OK, website.FEHLER]


async def test_startseite_nicht_erreichbar(hass: HomeAssistant, site) -> None:
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(500)})
    assert (await website.async_hole_website(hass, f"{BASIS}/")).status == website.FEHLER


async def test_seite_ohne_informationen(hass: HomeAssistant, site) -> None:
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=b"<html><body></body></html>")})
    assert (await website.async_hole_website(hass, f"{BASIS}/")).status == website.LEER


@pytest.mark.parametrize("url", [None, "", "  ", "http://localhost/x", "http://192.168.1.5/", "ftp://x.example/"])
async def test_unsichere_oder_leere_url(hass: HomeAssistant, site, url) -> None:
    s = site({})
    e = await website.async_hole_website(hass, url)
    assert e.status == website.UNGUELTIG and not s.abrufe


async def test_url_ohne_schema_wird_zu_https(hass: HomeAssistant, site) -> None:
    s = site({"https://hof-mueller.example/robots.txt": _Seite(404), "https://hof-mueller.example": _Seite(body=_html(jsonld=LD_HOF))})
    e = await website.async_hole_website(hass, "hof-mueller.example")
    assert e.start_url == "https://hof-mueller.example" and s.urls[0].startswith("https://hof-mueller.example")


# --- Zusammenführung / Herkunft --------------------------------------------------------------


def _osm(**tags: Any) -> overpass.Kandidat:
    el = {"type": "node", "id": 7, "lat": 46.948, "lon": 7.4474, "tags": {"shop": "farm", **tags}}
    return overpass.parse_kandidaten([el], 46.948, 7.4474)[0]


def _web(info_kwargs: dict[str, Any], url: str = f"{BASIS}/") -> website.WebsiteErgebnis:
    from custom_components.hofkarte.webseite_info import WebseiteInfo

    return website.WebsiteErgebnis(
        website.OK, url, (website.SeitenErgebnis(url, website.OK, WebseiteInfo(**info_kwargs)),)
    )


def test_osm_hat_vorrang_bei_name_adresse_kontakt() -> None:
    k = _osm(name="Hof Müller", **{"addr:street": "Weg", "addr:housenumber": "1", "addr:city": "Bern", "phone": "+41 31 000 00 00"})
    v = provenance.baue_vorschlag(
        k, _web({"name": "Müller AG", "adresse": "Andere 9", "plz": "3000", "ort": "Thun", "mobilnummer": "+41 79 111 11 11"})
    )
    assert v.daten["name"] == "Hof Müller" and v.quellen["name"].quelle == "openstreetmap"
    assert (v.daten["adresse"], v.daten["ort"]) == ("Weg 1", "Bern") and "plz" not in v.daten
    assert v.daten["mobilnummer"] == "+41 31 000 00 00"
    assert set(v.abweichungen) == {"name", "adresse", "mobilnummer"}
    assert v.quellen["name"].lizenz and "ODbL" in v.quellen["name"].lizenz
    assert v.quellen["name"].url == "https://www.openstreetmap.org/node/7"


def test_website_fuellt_luecken_und_hat_vorrang_bei_oeffnungszeiten() -> None:
    k = _osm(opening_hours="Mo-Fr 08:00-12:00")
    zeiten = ({"day": 4, "open": "09:00", "close": "12:00"},)
    v = provenance.baue_vorschlag(
        k, _web({"name": "Hof Müller", "adresse": "Dorfstrasse 5", "plz": "3000", "ort": "Bern", "email": "a@b.example", "oeffnungszeiten": zeiten})
    )
    assert v.daten["name"] == "Hof Müller" and v.quellen["name"].quelle == "website"
    assert v.daten["adresse"] == "Dorfstrasse 5" and v.quellen["plz"].url == f"{BASIS}/"
    assert v.daten["email"] == "a@b.example"
    assert v.quellen["oeffnungszeiten"].quelle == "website"
    assert v.abweichungen["oeffnungszeiten"] == "openstreetmap"


def test_oeffnungszeiten_nur_osm() -> None:
    v = provenance.baue_vorschlag(_osm(opening_hours="Mo-Fr 08:00-12:00"), None)
    assert v.quellen["oeffnungszeiten"].quelle == "openstreetmap" and v.daten["oeffnungszeiten"]


def test_beschreibung_wird_nie_uebernommen() -> None:
    v = provenance.baue_vorschlag(None, _web({"name": "X", "beschreibung": "Werbetext"}))
    assert "beschreibung" not in v.daten


def test_listen_werden_ueber_seiten_vereinigt_ohne_duplikate() -> None:
    from custom_components.hofkarte.webseite_info import WebseiteInfo

    seiten = (
        website.SeitenErgebnis("u1", website.OK, WebseiteInfo(angebote=("Eier", "Milch"), zahlungsarten=("Twint",))),
        website.SeitenErgebnis("u2", website.OK, WebseiteInfo(angebote=("milch", "Käse"), zahlungsarten=("Bargeld",))),
        website.SeitenErgebnis("u3", website.ROBOTS_GESPERRT),
    )
    v = provenance.baue_vorschlag(None, website.WebsiteErgebnis(website.OK, "u1", seiten))
    assert v.daten["angebote"] == ["Eier", "Milch", "Käse"]
    assert v.daten["zahlungsarten"] == ["Twint", "Bargeld"]
    assert v.quellen["angebote"].url == "u1"


def test_koordinate_und_angegebene_website() -> None:
    v = provenance.baue_vorschlag(_osm(name="X"), None, angegebene_website="https://x.example")
    assert (v.daten["latitude"], v.daten["longitude"]) == (46.948, 7.4474)
    assert v.daten["website"] == "https://x.example" and v.quellen["website"].quelle == "angabe"


def test_vorschlag_ist_json_serialisierbar() -> None:
    v = provenance.baue_vorschlag(_osm(name="X", opening_hours="Mo-Fr 08:00-12:00"), _web({"email": "a@b.example"}))
    json.dumps(v.als_dict())


def test_ohne_irgendeine_quelle_leerer_vorschlag() -> None:
    assert provenance.baue_vorschlag(None, None).daten == {}


def test_kandidat_aus_dict_roundtrip_und_bereinigung() -> None:
    k = _osm(name="Hof", website="https://h.example", opening_hours="Mo 08:00-12:00")
    k2 = kandidat_aus_dict(k.als_dict())
    assert k2.als_dict() == k.als_dict()
    boese = kandidat_aus_dict({"latitude": 1, "longitude": 2, "name": "A\x00B" + "x" * 999})
    assert "\x00" not in boese.name and len(boese.name) <= 300


# --- enrich / WS ---------------------------------------------------------------------------------


async def test_enrich_ereignisse_in_reihenfolge(hass: HomeAssistant, site) -> None:
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    ereignisse: list[dict] = []
    v = await enrich.async_anreichern(hass, _osm(name="Hof Müller", website=f"{BASIS}/"), fortschritt=ereignisse.append)
    assert [e["phase"] for e in ereignisse] == ["osm", "website", "fertig"]
    assert ereignisse[1]["status"] == website.OK
    assert v.daten["mobilnummer"] == "+41 31 111 22 33"
    assert "beschreibung" not in v.daten


async def test_enrich_website_gesperrt_liefert_osm_ergebnis(hass: HomeAssistant, site) -> None:
    site({f"{BASIS}/robots.txt": _Seite(body=b"User-agent: *\nDisallow: /\n", ctype="text/plain")})
    ereignisse: list[dict] = []
    v = await enrich.async_anreichern(hass, _osm(name="Hof", website=f"{BASIS}/"), fortschritt=ereignisse.append)
    assert ereignisse[1]["status"] == website.ROBOTS_GESPERRT
    assert v.daten["name"] == "Hof"


async def test_enrich_ohne_website_wird_uebersprungen(hass: HomeAssistant) -> None:
    ereignisse: list[dict] = []
    await enrich.async_anreichern(hass, _osm(name="Hof"), fortschritt=ereignisse.append)
    assert ereignisse[1] == {"phase": "website", "status": "uebersprungen"}


async def test_enrich_angegebene_website_ersetzt_osm_website(hass: HomeAssistant, site) -> None:
    s = site({"https://neu.example/robots.txt": _Seite(404), "https://neu.example/": _Seite(body=_html())})
    await enrich.async_anreichern(hass, _osm(name="Hof", website="https://alt.example"), website_url="https://neu.example/")
    assert all("alt.example" not in u for u in s.urls)


class _Verbindung(_FakeConnection):
    def __init__(self) -> None:
        super().__init__()
        self.subscriptions: dict[int, Any] = {}
        self.nachrichten: list[Any] = []

    def send_message(self, msg: Any) -> None:
        self.nachrichten.append(msg)


async def _enrich(hass: HomeAssistant, msg: dict) -> _Verbindung:
    c = _Verbindung()
    ws_enrich(hass, c, {"id": 95, "type": "hofkarte/management/enrich", **msg})
    await hass.async_block_till_done()
    import asyncio

    for _ in range(200):
        if c.errors or any(m.get("event", {}).get("phase") == "fertig" for m in c.nachrichten):
            break
        await asyncio.sleep(0.01)
    return c


async def test_ws_enrich_subscription_und_ereignisse(hass: HomeAssistant, site) -> None:
    await _setup_mit_coordinator(hass)
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    k = _osm(name="Hof Müller", website=f"{BASIS}/").als_dict()
    c = await _enrich(hass, {"kandidat": k})
    assert not c.errors and c.results == [(95, None)] and 95 in c.subscriptions
    phasen = [m["event"]["phase"] for m in c.nachrichten]
    assert phasen == ["osm", "website", "fertig"] and all(m["id"] == 95 for m in c.nachrichten)
    vorschlag = c.nachrichten[-1]["event"]["vorschlag"]
    assert vorschlag["daten"]["name"] == "Hof Müller"
    assert vorschlag["quellen"]["email"]["quelle"] == "website"


async def test_ws_enrich_nur_website(hass: HomeAssistant, site) -> None:
    await _setup_mit_coordinator(hass)
    site({f"{BASIS}/robots.txt": _Seite(404), f"{BASIS}/": _Seite(body=_html(jsonld=LD_HOF))})
    c = await _enrich(hass, {"website": f"{BASIS}/"})
    assert c.nachrichten[-1]["event"]["vorschlag"]["daten"]["name"] == "Hof Müller"


async def test_ws_enrich_ohne_angaben_ist_invalid_format(hass: HomeAssistant) -> None:
    await _setup_mit_coordinator(hass)
    c = await _enrich(hass, {})
    assert c.errors[0][:2] == (95, "invalid_format") and not c.results


async def test_ws_enrich_not_ready(hass: HomeAssistant) -> None:
    c = await _enrich(hass, {"website": "https://x.example"})
    assert c.errors[0][:2] == (95, "not_ready")


async def test_ws_enrich_nimmt_discover_ergebnis_mit_bewertung_an(hass: HomeAssistant) -> None:
    from custom_components.hofkarte.management import _KANDIDAT_SCHEMA

    k = _osm(name="Hof").als_dict() | {"score": 0.9, "konfidenz": "hoch", "signale": {"distanz": 1}}
    assert _KANDIDAT_SCHEMA(k)["name"] == "Hof"
