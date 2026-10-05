"""Tests für webseite_info.py (Issue #8, "Informationen aus Homepage").

Deckt beide Ebenen ab: die reine HTML-/JSON-LD-Extraktion (ohne
Netzwerk) sowie den asynchronen Abruf inkl. SSRF-Schutz, Grössen-/
Content-Type-/Timeout-Limits und der drei geforderten Fehlerfälle. Der
HTTP-Abruf wird dabei über eine leichtgewichtige Fake-Session
nachgebildet (kein echtes Netzwerk, kein zusätzliches Test-Framework).
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest

from custom_components.hofkarte.webseite_info import (
    MAX_ANTWORT_BYTES,
    WebseiteInfo,
    WebseiteInformationenNichtGefundenError,
    WebseiteNichtErreichbarError,
    WebseiteUngueltigeUrlError,
    _extrahiere_aus_html,
    async_ermittle_webseite_info,
)


# ---------------------------------------------------------------------------
# Reine HTML-/JSON-LD-Extraktion (kein Netzwerk)
# ---------------------------------------------------------------------------


def _json_ld_seite(payload: str) -> str:
    return (
        "<html><head><title>Seitentitel</title>"
        '<meta name="description" content="Meta-Beschreibung">'
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body></body></html>"
    )


def test_extrahiert_vollstaendiges_local_business_objekt() -> None:
    payload = """
    {
      "@context": "https://schema.org",
      "@type": "FoodEstablishment",
      "name": "Hofladen Muster",
      "description": "Frische Eier, Gemüse und Honig direkt vom Bauernhof.",
      "address": {
        "@type": "PostalAddress",
        "streetAddress": "Musterweg 1",
        "postalCode": "3000",
        "addressLocality": "Bern",
        "addressCountry": {"@type": "Country", "name": "Schweiz"}
      },
      "openingHoursSpecification": [
        {"@type": "OpeningHoursSpecification", "dayOfWeek": ["https://schema.org/Monday", "https://schema.org/Tuesday"], "opens": "08:00", "closes": "18:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Saturday", "opens": "08:00", "closes": "12:00"}
      ],
      "paymentAccepted": "Cash, Twint",
      "makesOffer": [{"itemOffered": {"name": "Eier"}}, {"itemOffered": {"name": "Honig"}}],
      "telephone": "+41 79 123 45 67",
      "email": "info@hofladen-muster.ch"
    }
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))

    assert info.name == "Hofladen Muster"
    assert info.beschreibung == "Frische Eier, Gemüse und Honig direkt vom Bauernhof."
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"
    assert info.land == "Schweiz"
    assert info.mobilnummer == "+41 79 123 45 67"
    assert info.email == "info@hofladen-muster.ch"
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 6, "beginn": "08:00", "ende": "12:00"},
    )
    assert info.angebote == ("Eier", "Honig")
    assert info.zahlungsarten == ("Cash", "Twint")
    assert not info.ist_leer()


def test_ignoriert_json_ld_ohne_business_merkmale() -> None:
    """Ein blosses 'WebSite'-Objekt ohne Adresse/Öffnungszeiten/etc. gilt
    nicht als Hofladen-Kandidat - die Meta-Beschreibung/der Titel greifen
    als Fallback."""
    payload = '{"@context": "https://schema.org", "@type": "WebSite", "name": "Meine Seite"}'
    info = _extrahiere_aus_html(_json_ld_seite(payload))

    assert info.name == "Seitentitel"
    assert info.beschreibung == "Meta-Beschreibung"
    assert info.adresse is None


def test_ungueltiges_json_ld_wird_ignoriert_kein_absturz() -> None:
    html = _json_ld_seite("{kaputtes json")
    info = _extrahiere_aus_html(html)

    assert info.name == "Seitentitel"
    assert info.beschreibung == "Meta-Beschreibung"


def test_at_graph_wird_aufgeloest() -> None:
    payload = """
    {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": "Seite"},
        {"@type": "Store", "name": "Hofladen Graph", "telephone": "+41 00 000 00 00"}
    ]}
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.name == "Hofladen Graph"


def test_oeffnungszeiten_ohne_opens_oder_closes_werden_uebersprungen() -> None:
    payload = """
    {"@type": "Store", "name": "Hofladen", "telephone": "0",
     "openingHoursSpecification": [
        {"dayOfWeek": "Monday", "opens": "08:00"},
        {"dayOfWeek": "Tuesday", "opens": "08:00", "closes": "08:00"}
     ]}
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.oeffnungszeiten == ()


def test_zahlungsarten_als_liste() -> None:
    payload = '{"@type": "Store", "name": "Hofladen", "paymentAccepted": ["Bar", "Twint"]}'
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.zahlungsarten == ("Bar", "Twint")


def test_leere_seite_ohne_jegliche_information_ist_leer() -> None:
    info = _extrahiere_aus_html("<html><head></head><body></body></html>")
    assert info.ist_leer()


# ---------------------------------------------------------------------------
# Mobilnummer/E-Mail: Text-Heuristik als Fallback, wenn JSON-LD dafür
# nichts liefert.
# ---------------------------------------------------------------------------


def test_telefon_und_email_werden_aus_text_erkannt_wenn_kein_json_ld_vorhanden() -> None:
    html = (
        "<html><head><title>Seitentitel</title></head>"
        "<body><p>Kontakt: +41 79 123 45 67, info@hofladen.ch</p></body></html>"
    )
    info = _extrahiere_aus_html(html)

    assert info.mobilnummer == "+41 79 123 45 67"
    assert info.email == "info@hofladen.ch"


def test_mehrere_unterschiedliche_telefonnummern_liefern_keinen_vorschlag() -> None:
    html = (
        "<html><head><title>Seitentitel</title></head>"
        "<body><p>+41 79 123 45 67</p><p>+41 78 987 65 43</p></body></html>"
    )
    info = _extrahiere_aus_html(html)

    assert info.mobilnummer is None


def test_identisch_wiederholte_telefonnummer_gilt_nicht_als_mehrdeutig() -> None:
    html = (
        "<html><head><title>Seitentitel</title></head>"
        "<body><p>+41 79 123 45 67</p><p>+41 79 123 45 67</p></body></html>"
    )
    info = _extrahiere_aus_html(html)

    assert info.mobilnummer == "+41 79 123 45 67"


def _text_seite(*absaetze: str) -> str:
    """Baut eine einfache HTML-Seite ohne JSON-LD aus mehreren
    Absätzen (<p>) - jeder Absatz landet als eigene Zeile im
    ``sichtbarer_text()`` der Seite (siehe ``_SeitenParser``)."""
    body = "".join(f"<p>{absatz}</p>" for absatz in absaetze)
    return f"<html><head><title>Hofladen Muster</title></head><body>{body}</body></html>"


def test_adresse_wird_aus_text_erkannt_wenn_kein_json_ld_vorhanden() -> None:
    info = _extrahiere_aus_html(_text_seite("Musterweg 1, 3000 Bern"))
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_adresse_ohne_komma_wird_ebenfalls_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Bahnhofstrasse 12 8400 Winterthur"))
    assert info.adresse == "Bahnhofstrasse 12"
    assert info.plz == "8400"
    assert info.ort == "Winterthur"


def test_adresse_mit_mehrwortort_wird_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Dorfgasse 3, 9490 Vaduz Liechtenstein"))
    assert info.adresse == "Dorfgasse 3"
    assert info.plz == "9490"
    assert info.ort == "Vaduz Liechtenstein"


def test_adresse_ueber_getrennte_absaetze_wird_nicht_erkannt() -> None:
    """Dokumentierte Grenze: eine über zwei Absätze verteilte Adresse
    (Strasse in einer Zeile, PLZ/Ort in der nächsten) wird bewusst nicht
    erkannt, statt fälschlich mit unabhängigem Text kombiniert zu werden
    (siehe ``_SeitenParser.sichtbarer_text()``)."""
    info = _extrahiere_aus_html(_text_seite("Bahnhofstrasse 12", "8400 Winterthur"))
    assert info.adresse is None
    assert info.plz is None
    assert info.ort is None


def test_mehrdeutige_adresse_liefert_keinen_vorschlag() -> None:
    """Zwei unterschiedliche Adresskandidaten im Text -> uneindeutig,
    also lieber gar kein Vorschlag (Prinzip "lieber nichts als falsch")."""
    info = _extrahiere_aus_html(
        _text_seite("Musterweg 1, 3000 Bern", "Dorfweg 5, 3001 Bern")
    )
    assert info.adresse is None
    assert info.plz is None
    assert info.ort is None


def test_identisch_wiederholte_adresse_gilt_nicht_als_mehrdeutig() -> None:
    """Dieselbe Adresse an zwei Stellen der Seite (z. B. Kopf- und
    Fussbereich) ist kein Widerspruch."""
    info = _extrahiere_aus_html(
        _text_seite("Musterweg 1, 3000 Bern", "Kontakt: Musterweg 1, 3000 Bern")
    )
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_strasse_ohne_erkannte_endung_wird_nicht_als_adresse_erkannt() -> None:
    """Strassennamen ohne eine der erkannten Endungen (-strasse, -weg,
    ...) werden bewusst nicht erkannt (dokumentierte Grenze)."""
    info = _extrahiere_aus_html(_text_seite("Via Nassa 1, 6900 Lugano"))
    assert info.adresse is None


def test_json_ld_adresse_hat_vorrang_vor_text_heuristik() -> None:
    """Die Text-Heuristik darf eine bereits aus JSON-LD ermittelte
    Adresse nicht überschreiben oder ergänzen."""
    payload = """
    {
      "@type": "Store", "name": "Hofladen",
      "address": {"streetAddress": "Musterweg 1", "postalCode": "3000", "addressLocality": "Bern"}
    }
    """
    html = (
        "<html><head><title>t</title>"
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body><p>Andere Strasse 9, 8000 Zürich</p></body></html>"
    )
    info = _extrahiere_aus_html(html)
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_oeffnungszeiten_werden_aus_tagesbereich_mit_bindestrich_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Mo-Fr 08:00-18:00 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_oeffnungszeiten_werden_aus_ausgeschriebenem_tagesbereich_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Montag bis Freitag: 8 – 18 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_oeffnungszeiten_werden_aus_einzelnem_tag_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Sa 08:00–12:00"))
    assert info.oeffnungszeiten == ({"wochentag": 6, "beginn": "08:00", "ende": "12:00"},)


def test_widerspruechliche_oeffnungszeiten_fuer_einen_tag_werden_ausgelassen() -> None:
    """Zwei unterschiedliche Angaben für Montag -> für Montag kein
    Vorschlag; die übrigen, eindeutigen Tage bleiben davon unberührt."""
    info = _extrahiere_aus_html(_text_seite("Mo-Fr 08:00-18:00 Uhr", "Mo 09:00-17:00 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_identisch_wiederholte_oeffnungszeit_gilt_nicht_als_widerspruch() -> None:
    info = _extrahiere_aus_html(_text_seite("Mo 08:00-12:00 Uhr", "Montag: 08:00-12:00 Uhr"))
    assert info.oeffnungszeiten == ({"wochentag": 1, "beginn": "08:00", "ende": "12:00"},)


def test_json_ld_oeffnungszeiten_haben_vorrang_vor_text_heuristik() -> None:
    payload = """
    {
      "@type": "Store", "name": "Hofladen",
      "openingHoursSpecification": [
        {"dayOfWeek": "Saturday", "opens": "08:00", "closes": "12:00"}
      ]
    }
    """
    html = (
        "<html><head><title>t</title>"
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body><p>Mo-Fr 08:00-18:00 Uhr</p></body></html>"
    )
    info = _extrahiere_aus_html(html)
    assert info.oeffnungszeiten == ({"wochentag": 6, "beginn": "08:00", "ende": "12:00"},)


def test_ohne_erkennbares_muster_bleiben_oeffnungszeiten_leer() -> None:
    info = _extrahiere_aus_html(_text_seite("Wir freuen uns auf Ihren Besuch."))
    assert info.oeffnungszeiten == ()


# ---------------------------------------------------------------------------
# async_ermittle_webseite_info: URL-Validierung (Fehlerfall 1)
# ---------------------------------------------------------------------------


async def test_leere_url_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "")


async def test_nur_leerzeichen_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "   ")


async def test_none_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, None)


async def test_private_ip_literal_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "http://192.168.1.1/")


async def test_unsicheres_schema_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "file:///etc/passwd")


# ---------------------------------------------------------------------------
# async_ermittle_webseite_info: HTTP-Abruf (Fake-Session, kein echtes Netzwerk)
# ---------------------------------------------------------------------------


class _FakeContent:
    def __init__(self, data: bytes, chunk_size: int = 4096) -> None:
        self._data = data
        self._chunk_size = chunk_size

    def iter_chunked(self, _n: int):
        data = self._data
        chunk_size = self._chunk_size

        async def _generator():
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        return _generator()


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        content_type: str = "text/html",
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}
        self.content = _FakeContent(body)
        self._encoding = encoding

    def get_encoding(self) -> str:
        return self._encoding

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _RaisingGet:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __call__(self, *args: Any, **kwargs: Any):
        raise self._exc


class _FakeSession:
    def __init__(self, antworten: list[_FakeResponse]) -> None:
        self._antworten = list(antworten)
        self.abgefragte_urls: list[str] = []

    def get(self, url: str, *, timeout: Any = None, allow_redirects: Any = None):
        self.abgefragte_urls.append(url)
        return self._antworten.pop(0)


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    """Ersetzt die (seit F4 je Abruf erzeugte) sichere Session durch ``session``."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _fake_sichere_session() -> Any:
        yield session

    monkeypatch.setattr(
        "custom_components.hofkarte.webseite_info._sichere_session",
        _fake_sichere_session,
    )


async def test_erfolgreicher_abruf_liefert_webseiteinfo(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = _json_ld_seite(
        '{"@type": "Store", "name": "Hofladen Erfolg", "telephone": "0"}'
    )
    session = _FakeSession([_FakeResponse(body=html.encode("utf-8"))])
    _patch_session(monkeypatch, session)

    info = await async_ermittle_webseite_info(hass, "https://beispiel-hofladen.example")

    assert isinstance(info, WebseiteInfo)
    assert info.name == "Hofladen Erfolg"


async def test_http_fehlerstatus_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(status=500)])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_unpassender_content_type_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(content_type="application/pdf", body=b"%PDF-1.4")]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_zu_grosse_antwort_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    zu_gross = b"<html>" + b"x" * (MAX_ANTWORT_BYTES + 1)
    session = _FakeSession([_FakeResponse(body=zu_gross)])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_verbindungsfehler_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.get = _RaisingGet(aiohttp.ClientConnectionError("nope"))
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_timeout_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.get = _RaisingGet(asyncio.TimeoutError())
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_erreichbare_seite_ohne_informationen_wirft_not_found(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(body=b"<html><head></head><body>Nichts hier.</body></html>")]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteInformationenNichtGefundenError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_weiterleitung_auf_sicheres_ziel_wird_verfolgt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = _json_ld_seite('{"@type": "Store", "name": "Nach Weiterleitung", "telephone": "0"}')
    session = _FakeSession(
        [
            _FakeResponse(status=301, headers={"Location": "https://ziel.example/neu"}),
            _FakeResponse(body=html.encode("utf-8")),
        ]
    )
    _patch_session(monkeypatch, session)

    info = await async_ermittle_webseite_info(hass, "https://beispiel.example")

    assert info.name == "Nach Weiterleitung"
    assert session.abgefragte_urls == [
        "https://beispiel.example",
        "https://ziel.example/neu",
    ]


async def test_weiterleitung_auf_unsicheres_ziel_wird_abgelehnt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(status=302, headers={"Location": "http://192.168.1.1/intern"})]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_weiterleitung_ohne_location_header_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(status=302, headers={})])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_zu_viele_weiterleitungen_werden_abgelehnt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _MAX_REDIRECTS erlaubt 3 Sprünge -> ein vierter muss scheitern.
    antworten = [
        _FakeResponse(status=302, headers={"Location": f"https://ziel-{i}.example/"})
        for i in range(5)
    ]
    session = _FakeSession(antworten)
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


# ---------------------------------------------------------------------------
# F2 (Code Review 2026.9.2): Laufzeitbegrenzung der Text-Heuristiken
# ---------------------------------------------------------------------------
#
# Vor der Korrektur wuchs die Laufzeit der Adress- und E-Mail-Regex bei
# langen, nicht trennbaren Zeichenfolgen quadratisch (≈ 13 s bei 20 000
# Zeichen, Review-Messung ≈ 52 s bei 40 000). Diese Tests haben harte
# Zeitgrenzen und wären vor der Korrektur rot gewesen.

import json as _json  # noqa: E402
import time  # noqa: E402

from custom_components.hofkarte import webseite_info as _wi  # noqa: E402

_ZEITGRENZE_SEKUNDEN = 0.2

_BOESARTIGE_EINGABEN = {
    "a_x100000": "a" * 100_000,
    "A_x100000": "A" * 100_000,
    "Aa_x40000": "Aa " * 40_000,
    "a@_x50000": "a@" * 50_000,
    "1_x100000": "1" * 100_000,
    "Mo_plus_Leerzeichen": "Mo" + " " * 100_000 + "x",
    "x@_a._x50000": "x@" + "a." * 50_000,
}

_TEXT_HEURISTIKEN = {
    "adresse": _wi._extrahiere_adresse_aus_text,
    "oeffnungszeiten": _wi._extrahiere_oeffnungszeiten_aus_text,
    "kontakt": _wi._extrahiere_kontakt_aus_text,
}


def _gemessen(funktion: Any, text: str) -> float:
    start = time.perf_counter()
    funktion(text)
    return time.perf_counter() - start


@pytest.mark.parametrize("heuristik", sorted(_TEXT_HEURISTIKEN))
@pytest.mark.parametrize("name", sorted(_BOESARTIGE_EINGABEN))
def test_text_heuristiken_sind_bei_boesartiger_eingabe_schnell(
    heuristik: str, name: str
) -> None:
    dauer = _gemessen(_TEXT_HEURISTIKEN[heuristik], _BOESARTIGE_EINGABEN[name])

    assert dauer < _ZEITGRENZE_SEKUNDEN, f"{heuristik}/{name}: {dauer:.3f}s"


@pytest.mark.parametrize(
    "muster_name",
    [
        "_ADRESSE_TEXT_MUSTER",
        "_EMAIL_TEXT_MUSTER",
        "_OEFFNUNGSZEIT_TEXT_MUSTER",
        "_TELEFON_TEXT_MUSTER",
    ],
)
@pytest.mark.parametrize("name", sorted(_BOESARTIGE_EINGABEN))
def test_muster_selbst_sind_ohne_vorfilter_schnell(
    muster_name: str, name: str
) -> None:
    """Die Muster müssen **auch ohne** den Vorfilter ``_begrenze_text``
    begrenzt sein (Defense in Depth): direkt gegen die Roh-Eingabe."""
    muster = getattr(_wi, muster_name)

    dauer = _gemessen(
        lambda t: list(muster.finditer(t)), _BOESARTIGE_EINGABEN[name]
    )

    assert dauer < _ZEITGRENZE_SEKUNDEN, f"{muster_name}/{name}: {dauer:.3f}s"


def test_begrenze_text_verwirft_zu_lange_zeilen_und_kappt_gesamttext() -> None:
    lang = "x" * (_wi.MAX_ZEILE_ZEICHEN + 1)

    assert _wi._begrenze_text(f"kurz\n{lang}\nauch kurz") == "kurz\nauch kurz"
    assert _wi._begrenze_text(lang) == ""
    gross = "a\n" * _wi.MAX_SICHTBARER_TEXT_ZEICHEN
    assert len(_wi._begrenze_text(gross)) <= _wi.MAX_SICHTBARER_TEXT_ZEICHEN


def test_normale_erkennung_bleibt_nach_begrenzung_unveraendert() -> None:
    text = (
        "Hofladen Muster\nMusterweg 12, 3000 Bern\n"
        "Mo-Fr 08:00-18:00 Uhr\nTel. 079 123 45 67\nhof@beispiel.ch"
    )

    assert _wi._extrahiere_adresse_aus_text(text) == (
        "Musterweg 12",
        "3000",
        "Bern",
    )
    assert _wi._extrahiere_oeffnungszeiten_aus_text(text)[0] == {
        "wochentag": 1,
        "beginn": "08:00",
        "ende": "18:00",
    }
    assert _wi._extrahiere_kontakt_aus_text(text) == (
        "079 123 45 67",
        "hof@beispiel.ch",
    )


def test_email_ohne_at_wird_gar_nicht_erst_gesucht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Spion:
        def finditer(self, _text: str) -> Any:
            raise AssertionError("E-Mail-Regex darf ohne '@' nicht laufen")

    monkeypatch.setattr(_wi, "_EMAIL_TEXT_MUSTER", _Spion())

    assert _wi._extrahiere_kontakt_aus_text("Tel 079 123 45 67") == (
        "079 123 45 67",
        None,
    )


def test_extraktion_ganzer_boesartiger_seite_ist_schnell() -> None:
    html = "<html><body><p>" + "a" * 300_000 + "</p></body></html>"

    start = time.perf_counter()
    _extrahiere_aus_html(html)

    assert time.perf_counter() - start < 1.0


async def test_extraktion_laeuft_im_executor_nicht_in_der_event_loop(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    aufrufe: list[str] = []
    original = hass.async_add_executor_job

    def _spion(funktion: Any, *args: Any) -> Any:
        aufrufe.append(funktion.__name__)
        return original(funktion, *args)

    monkeypatch.setattr(hass, "async_add_executor_job", _spion)
    session = _FakeSession(
        [_FakeResponse(body=_json_ld_seite('{"@type":"Store","name":"X"}').encode())]
    )
    _patch_session(monkeypatch, session)

    await async_ermittle_webseite_info(hass, "https://beispiel.ch")

    assert aufrufe == ["_extrahiere_aus_html"]


async def test_extraktion_ueberschreitet_zeitlimit_wird_sauber_gemeldet(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_wi, "EXTRAKTION_TIMEOUT_SEKUNDEN", 0.05)

    async def _haengt(_funktion: Any, *_args: Any) -> Any:
        await asyncio.sleep(5)

    monkeypatch.setattr(hass, "async_add_executor_job", _haengt)
    session = _FakeSession([_FakeResponse(body=b"<html></html>")])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError, match="zu lange"):
        await async_ermittle_webseite_info(hass, "https://beispiel.ch")


# ---------------------------------------------------------------------------
# F13 (Code Review 2026.9.2): Robustheit gegen tief verschachteltes JSON-LD
# ---------------------------------------------------------------------------


def test_tief_verschachteltes_json_ld_fuehrt_nicht_zum_absturz() -> None:
    """``json.loads`` löst bei 200 000 x "[" einen ``RecursionError`` aus
    (kein ``ValueError``) - vor der Korrektur ein unbehandelter Absturz."""
    html = _json_ld_seite("[" * 200_000)

    info = _extrahiere_aus_html(html)

    assert info.ist_leer() or info.name is not None  # kein Absturz


def test_flatten_json_ld_ist_iterativ_und_erhaelt_reihenfolge() -> None:
    tief: Any = {"name": "tief"}
    for _ in range(50_000):
        tief = [tief]

    assert _wi._flatten_json_ld(tief) == [{"name": "tief"}]
    assert _wi._flatten_json_ld(
        [{"name": "a"}, {"@graph": [{"name": "b"}, [{"name": "c"}]]}, {"name": "d"}]
    ) == [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]
    assert _wi._flatten_json_ld("kein json-ld") == []
    assert _wi._iter_json_ld_objekte(["[" * 200_000, _json.dumps({"name": "ok"})]) == [
        {"name": "ok"}
    ]


# ---------------------------------------------------------------------------
# F4 (Code Review 2026.9.2): DNS-Prüfung mit Bindung an die geprüfte IP
# ---------------------------------------------------------------------------


def _aufgeloest(*adressen: str) -> list[dict[str, Any]]:
    return [
        {"hostname": "h", "host": a, "port": 443, "family": 2, "proto": 0, "flags": 0}
        for a in adressen
    ]


async def _loese(resolver: Any, host: str, *adressen: str) -> list[dict[str, Any]]:
    async def _intern(_host: str, _port: int = 0, _family: int = 0) -> Any:
        return _aufgeloest(*adressen)

    resolver._intern.resolve = _intern
    return await resolver.resolve(host, 443, 0)


async def test_aufloeser_laesst_oeffentliche_adresse_durch_und_liefert_sie_unveraendert() -> None:
    resolver = _wi._OeffentlichAufloeser()

    treffer = await _loese(resolver, "beispiel.ch", "93.184.216.34", "2606:2800:220:1::1")

    assert [t["host"] for t in treffer] == ["93.184.216.34", "2606:2800:220:1::1"]


@pytest.mark.parametrize(
    "adressen",
    [
        ("127.0.0.1",),  # z. B. 127.0.0.1.nip.io
        ("192.168.1.20",),
        ("100.64.0.1",),  # CGNAT
        ("93.184.216.34", "10.0.0.5"),  # gemischte Antwort
        ("::ffff:127.0.0.1",),
        ("::1",),
        (),  # leere Antwort
    ],
)
async def test_aufloeser_lehnt_nicht_oeffentliche_oder_gemischte_antworten_ab(
    adressen: tuple[str, ...],
) -> None:
    resolver = _wi._OeffentlichAufloeser()

    with pytest.raises(_wi._NichtOeffentlichError):
        await _loese(resolver, "127.0.0.1.nip.io", *adressen)


async def test_domain_die_auf_private_ip_aufloest_wird_als_nicht_erlaubtes_ziel_gemeldet(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ende-zu-Ende mit echtem ``aiohttp``-Connector (ohne Netzwerk): Der
    Aufloeser lehnt ab, der Abruf meldet den Fehlerfall 1 (nicht erlaubtes
    Ziel) - es wird keine Verbindung aufgebaut."""

    async def _privat(self: Any, _host: str, _port: int = 0, _family: int = 0) -> Any:
        return _aufgeloest("192.168.1.20")

    monkeypatch.setattr(aiohttp.ThreadedResolver, "resolve", _privat)

    with pytest.raises(WebseiteUngueltigeUrlError, match="nicht erlaubtes Ziel"):
        await async_ermittle_webseite_info(hass, "https://rebinding.beispiel.ch/")


async def test_weiterleitung_auf_domain_mit_privater_ip_wird_abgelehnt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bei einem Weiterleitungssprung (nicht der Erstanfrage) lautet der
    Fehler 'weitergeleitet' (Fehlerfall 2)."""
    from aiohttp.client_reqrep import ConnectionKey

    schluessel = ConnectionKey("h", 443, True, True, None, None, None)

    class _Sprung:
        def __init__(self) -> None:
            self.aufrufe = 0

        def get(self, url: str, **_kw: Any) -> Any:
            self.aufrufe += 1
            if self.aufrufe == 1:
                return _FakeResponse(
                    status=302, headers={"Location": "https://intern.beispiel.ch/"}
                )
            raise aiohttp.ClientConnectorError(
                schluessel, _wi._NichtOeffentlichError("privat")
            )

    with pytest.raises(WebseiteNichtErreichbarError, match="weitergeleitet"):
        await _wi._hole_html(_Sprung(), "https://beispiel.ch/")  # type: ignore[arg-type]
