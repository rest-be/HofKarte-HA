"""Konservativer, mehrseitiger Website-Abruf für die Anreicherung.

Regeln (Konzept §13, Projekt-Grundsätze):

- **robots.txt wird beachtet**, bevor irgendeine Seite abgerufen wird.
  Auswertung nach RFC 9309: 404/410 und andere 4xx -> alles erlaubt;
  5xx, Netzwerkfehler -> *nichts* abrufen (konservativ); Disallow für
  ``HofKarte`` bzw. ``*`` -> betroffene Seiten nicht abrufen.
- Eigener User-Agent mit Projekt-URL.
- Höchstens ``MAX_SEITEN`` Seiten, nur derselbe Host (inkl. ``www.``),
  nur eine Ebene tief (Links der Startseite), nacheinander mit Pause
  (``PAUSE_SEKUNDEN``), keine Dateien (PDF, Bilder, ...), keine Logins.
- Der SSRF-Schutz bleibt unverändert: derselbe IP-gebundene Resolver und
  dieselbe Weiterleitungsprüfung wie ``webseite_info.py``; dessen
  Extraktion (JSON-LD, Text-Heuristiken) wird wiederverwendet.
- Es werden nur **Fakten** übernommen (Adresse, Kontakt, Zeiten, Angebote);
  keine Beschreibungstexte (Entscheid: kein automatischer Beschreibungstext).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from .. import webseite_info as wi
from ..url_sicherheit import ist_sichere_externe_url

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "HofKarte/HomeAssistant (+https://github.com/rest-be/HofKarte-HA)"
ROBOTS_TOKEN = "HofKarte"
MAX_SEITEN = 4
PAUSE_SEKUNDEN = 1.0
MAX_ROBOTS_BYTES = 500 * 1024  # RFC 9309: mindestens 500 KiB auswerten
GESAMT_TIMEOUT_SEKUNDEN = 45

# Linktext/-pfad-Stichwörter, die auf nützliche Unterseiten hindeuten.
_STICHWOERTER = (
    "kontakt", "contact", "oeffnungszeiten", "öffnungszeiten", "zeiten", "horaires",
    "hofladen", "laden", "shop", "boutique", "produkte", "angebot", "ferme", "impressum",
    "ouverture", "magasin",
)
_DATEI_ENDUNGEN = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip", ".doc", ".docx",
    ".xls", ".xlsx", ".mp3", ".mp4", ".css", ".js", ".ico", ".xml",
)
_LOGIN_TEILE = ("login", "anmelden", "wp-admin", "warenkorb", "cart", "checkout", "account")

# Statuswerte je Seite / für das Gesamtergebnis
OK = "ok"
ROBOTS_GESPERRT = "robots_gesperrt"
ROBOTS_NICHT_LESBAR = "robots_nicht_lesbar"
UNGUELTIG = "ungueltige_url"
FEHLER = "nicht_erreichbar"
LEER = "keine_informationen"


@dataclass(frozen=True)
class SeitenErgebnis:
    url: str
    status: str
    info: wi.WebseiteInfo | None = None
    text: str = ""  # sichtbarer Seitentext, nur mit ``mit_text=True`` (für die optionale KI)


@dataclass(frozen=True)
class WebsiteErgebnis:
    """Ergebnis des Abrufs: Status gesamt plus je Seite die Extraktion."""

    status: str
    start_url: str
    seiten: tuple[SeitenErgebnis, ...] = field(default_factory=tuple)

    @property
    def infos(self) -> list[tuple[str, wi.WebseiteInfo]]:
        return [(s.url, s.info) for s in self.seiten if s.info is not None]


# --- robots.txt ----------------------------------------------------------------


class Robots:
    """Ausgewertete robots.txt (oder ein Pauschalurteil)."""

    def __init__(self, *, alles_erlaubt: bool = False, nichts_erlaubt: bool = False,
                 parser: RobotFileParser | None = None) -> None:
        self._alles = alles_erlaubt
        self._nichts = nichts_erlaubt
        self._parser = parser

    @property
    def nicht_lesbar(self) -> bool:
        """robots.txt war nicht verlässlich lesbar (5xx/Netzwerk) -> kein Abruf."""
        return self._nichts

    def erlaubt(self, url: str) -> bool:
        if self._nichts:
            return False
        if self._alles or self._parser is None:
            return True
        return self._parser.can_fetch(ROBOTS_TOKEN, url)


def parse_robots(text: str) -> Robots:
    """Aus dem Text einer robots.txt (auf ``MAX_ROBOTS_BYTES`` gekürzt)."""
    parser = RobotFileParser()
    parser.parse(text[:MAX_ROBOTS_BYTES].splitlines())
    return Robots(parser=parser)


def _origin(url: str) -> str:
    t = urlsplit(url)
    return f"{t.scheme}://{t.netloc}"


async def lade_robots(session: Any, start_url: str) -> Robots:
    """robots.txt des Hosts holen und nach RFC 9309 einordnen."""
    robots_url = f"{_origin(start_url)}/robots.txt"
    try:
        text = await wi._hole_html(
            session, robots_url, headers={"User-Agent": USER_AGENT}, erlaubte_typen=("text/",)
        )
    except wi.WebseiteNichtErreichbarError as err:
        status = err.status
        if status is not None and 400 <= status < 500:
            return Robots(alles_erlaubt=True)  # nicht vorhanden/nicht zugänglich
        _LOGGER.debug("robots.txt nicht lesbar (%s): %s", robots_url, err)
        return Robots(nichts_erlaubt=True)  # 5xx/Netzwerk: konservativ nichts abrufen
    except wi.WebseiteUngueltigeUrlError:
        return Robots(nichts_erlaubt=True)
    return parse_robots(text)


# --- Linkauswahl ---------------------------------------------------------------


class _LinkSammler(HTMLParser):
    """Sammelt ``<a href>`` mit Linktext (nur Standardbibliothek)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or None
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def _host_ohne_www(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def waehle_links(html_text: str, basis_url: str, max_anzahl: int) -> list[str]:
    """Wählt bis zu ``max_anzahl`` Unterseiten desselben Hosts aus.

    Kriterien: gleicher Host (ohne ``www.``), http(s), keine Datei-
    endungen, keine Login-/Warenkorb-Pfade, Stichwort in Pfad oder
    Linktext. Reihenfolge: Trefferstärke (Anzahl Stichwörter), dann
    Reihenfolge im Dokument. Die Startseite selbst ist ausgeschlossen."""
    sammler = _LinkSammler()
    try:
        sammler.feed(html_text)
    except Exception:  # noqa: BLE001 - kaputtes HTML darf nie abstürzen
        _LOGGER.debug("Links konnten nicht vollständig gelesen werden.")
    basis_host = _host_ohne_www(basis_url)
    basis_ohne_frag = urldefrag(basis_url)[0].rstrip("/")
    bewertet: dict[str, tuple[int, int]] = {}
    for reihenfolge, (href, text) in enumerate(sammler.links):
        absolut = urldefrag(urljoin(basis_url, href.strip()))[0]
        teile = urlsplit(absolut)
        if teile.scheme not in ("http", "https") or _host_ohne_www(absolut) != basis_host:
            continue
        pfad = teile.path.lower()
        if pfad.endswith(_DATEI_ENDUNGEN) or any(x in pfad for x in _LOGIN_TEILE):
            continue
        if absolut.rstrip("/") == basis_ohne_frag:
            continue
        zeichen = f"{pfad} {text.lower()}"
        treffer = sum(1 for w in _STICHWOERTER if w in zeichen)
        if treffer and absolut not in bewertet:
            bewertet[absolut] = (-treffer, reihenfolge)
    return sorted(bewertet, key=lambda u: bewertet[u])[:max_anzahl]


# --- Abruf ---------------------------------------------------------------------


async def _abrufen(session: Any, url: str) -> str:
    return await wi._hole_html(session, url, headers={"User-Agent": USER_AGENT})


async def async_hole_website(
    hass: Any,
    url: str | None,
    *,
    max_seiten: int = MAX_SEITEN,
    pause: float | None = None,
    mit_text: bool = False,
) -> WebsiteErgebnis:
    """Ruft die Startseite und bis zu ``max_seiten - 1`` Unterseiten ab und
    extrahiert je Seite die Fakten. Wirft nie wegen einer einzelnen Seite;
    der Status steht im Ergebnis (siehe Konstanten oben)."""
    url = (url or "").strip()
    if url and "//" not in url:
        url = f"https://{url}"
    if not url or not ist_sichere_externe_url(url):
        return WebsiteErgebnis(UNGUELTIG, url)

    pause_s = PAUSE_SEKUNDEN if pause is None else pause
    seiten: list[SeitenErgebnis] = []
    try:
        async with asyncio.timeout(GESAMT_TIMEOUT_SEKUNDEN):
            async with wi._sichere_session() as session:
                robots = await lade_robots(session, url)
                if not robots.erlaubt(url):
                    status = ROBOTS_NICHT_LESBAR if robots.nicht_lesbar else ROBOTS_GESPERRT
                    return WebsiteErgebnis(status, url)

                start_html = await _abrufen(session, url)
                seiten.append(await _auswerten(hass, url, start_html, mit_text))
                for folge in waehle_links(start_html, url, max_seiten - 1):
                    if not robots.erlaubt(folge) or not ist_sichere_externe_url(folge):
                        seiten.append(SeitenErgebnis(folge, ROBOTS_GESPERRT))
                        continue
                    await asyncio.sleep(pause_s)
                    try:
                        html_text = await _abrufen(session, folge)
                    except (wi.WebseiteNichtErreichbarError, wi.WebseiteUngueltigeUrlError):
                        seiten.append(SeitenErgebnis(folge, FEHLER))
                        continue
                    seiten.append(await _auswerten(hass, folge, html_text, mit_text))
    except (wi.WebseiteNichtErreichbarError, wi.WebseiteUngueltigeUrlError):
        return WebsiteErgebnis(FEHLER, url, tuple(seiten))
    except TimeoutError:
        _LOGGER.debug("Website-Abruf überschritt das Gesamtzeitlimit: %s", url)
        return WebsiteErgebnis(FEHLER if not seiten else OK, url, tuple(seiten))

    gesamt = OK if any(s.info is not None for s in seiten) else LEER
    return WebsiteErgebnis(gesamt, url, tuple(seiten))


def _text_aus_html(html_text: str) -> str:
    """Sichtbarer, begrenzter Seitentext (Skripte/Stile entfernt)."""
    parser = wi._SeitenParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001 - kaputtes HTML darf nie abstürzen
        _LOGGER.debug("Seitentext konnte nicht vollständig gelesen werden.")
    return wi._begrenze_text(parser.sichtbarer_text())


async def _auswerten(hass: Any, url: str, html_text: str, mit_text: bool = False) -> SeitenErgebnis:
    try:
        async with asyncio.timeout(wi.EXTRAKTION_TIMEOUT_SEKUNDEN):
            info = await hass.async_add_executor_job(wi._extrahiere_aus_html, html_text)
            text = await hass.async_add_executor_job(_text_aus_html, html_text) if mit_text else ""
    except TimeoutError:
        return SeitenErgebnis(url, FEHLER)
    if info.ist_leer():
        return SeitenErgebnis(url, LEER, None, text)
    return SeitenErgebnis(url, OK, info, text)
