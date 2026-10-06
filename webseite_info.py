"""Ermittlung von Hofladen-Informationen aus einer vom Benutzer angegebenen
Website (Issue #8, "Informationen aus Homepage").

## Architektonische Tragweite: erste eigene ausgehende Netzwerkanfrage

Dieses Modul führt die **erste eigene, ausgehende HTTP-Anfrage im
Backend-Code von HofKarte** aus. Bisher delegierte HofKarte jede
Netzwerkkommunikation entweder an Home Assistants eigene
``image``-Entity-Infrastruktur (Hofladen-Bilder, siehe ``images.py``) oder
an den Browser (Leaflet/OpenStreetMap-Kartenkacheln). Diese Erweiterung ist
daher bewusst und ausführlich dokumentiert (siehe README.md, Abschnitt
„Datenschutz- und Standort-Hinweise“, SECURITY.md sowie
``quality_scale.yaml``, Kriterium ``inject-websession``).

## Kein externer/Cloud-/KI-Dienst

Die Extraktion erfolgt **vollständig lokal und deterministisch** – es wird
kein Cloud-Dienst, kein LLM und kein "Scraping-as-a-Service" eingebunden.
Das würde dem Kernprinzip "kein externer Dienst" widersprechen, das dieses
Projekt konsequent verfolgt. Stattdessen wird ausschliesslich
maschinenlesbare, von der Zielseite selbst veröffentlichte, strukturierte
Auszeichnung ausgewertet:

1. **Primär:** schema.org-konforme JSON-LD-Daten
   (``<script type="application/ld+json">``), typischerweise vom Typ
   ``LocalBusiness`` oder einer Unterart davon. Diese Daten sind
   maschinenlesbar und werden ohne Heuristik zuverlässig ausgewertet.
2. **Ergänzend, nur zur Lückenfüllung:** ``<title>`` (als schwacher,
   aber unverfälschter Namens-Fallback, falls JSON-LD keinen Namen
   liefert) sowie ``<meta name="description">`` (als Beschreibungs-
   Fallback). Beides sind Rohdaten der Seite selbst, nichts wird daraus
   interpretiert oder geraten.

Es findet **keine KI-artige Freitext-Interpretation** statt (z. B. aus
Fliesstext "vermutete" Öffnungszeiten oder Adressen). Keine
Python-Bibliothek ausserhalb der Standardbibliothek wird benötigt
(``html.parser``, ``json``) – es entsteht dadurch bewusst **keine neue
Abhängigkeit**.

## Prinzip "lieber nichts als falsch"

Felder, die sich nicht zuverlässig strukturiert auslesen lassen, bleiben
bewusst leer, statt eine möglicherweise falsche Angabe vorzuschlagen. Da
die Benutzerin/der Benutzer die ermittelten Werte ohnehin vor dem
Speichern prüft (siehe ``management.py``, ``ws_webseite_info``), ist ein
leeres Feld der Benutzererfahrung nicht abträglich, eine erfundene Angabe
hingegen schon.

Bekannte, bewusste Einschränkung: Das kompakte schema.org-Kurzformat für
Öffnungszeiten (``openingHours``, z. B. ``"Mo-Fr 08:00-18:00"``) wird
**nicht** ausgewertet – nur das vollständig strukturierte
``openingHoursSpecification`` (Liste einzelner Wochentag/Uhrzeit-Objekte).
Das Kurzformat erfordert Tagesbereich-Parsing (``Mo-Fr`` → mehrere
Wochentage), das eine zusätzliche, potenziell fehleranfällige
Interpretationsschicht wäre; angesichts von "lieber nichts als falsch"
wurde bewusst auf diese zusätzliche Komplexität verzichtet.

## SSRF-Schutz – über den Standard aus ``images.py`` hinaus

Diese Funktion ist ein **sensitiveres Angriffsziel** als die bestehende
Bild-URL-Prüfung in ``images.py``: HofKarte führt den HTTP-Request hier
selbst aus (nicht delegiert an eine Home-Assistant-Komponente) und
verarbeitet den Antwortinhalt selbst (nicht nur eine URL-Referenz). Neben
der syntaktischen Grundprüfung aus ``url_sicherheit.py`` (Schema,
Zugangsdaten, "localhost", private/interne IP-Literale – siehe dessen
Moduldoc zur bewussten Grenze ohne DNS-Auflösung) gelten hier zusätzlich:

- **Antwortgrössen-Limit** (``MAX_ANTWORT_BYTES``): verhindert
  übermässigen Speicher-/Bandbreitenverbrauch durch sehr grosse oder
  gezielt präparierte Antworten.
- **Content-Type-Prüfung**: nur HTML-artige Antworten werden geparst.
- **Zeitüberschreitung** (``ABRUF_TIMEOUT_SEKUNDEN``): ein nicht
  antwortender Server blockiert die Verwaltungsoberfläche nicht
  unbegrenzt.
- **Manuelle, erneut geprüfte Weiterleitungen**: Automatische
  Weiterleitungen (``aiohttp``s eingebautes ``allow_redirects``) würden
  eine erste, sichere URL akzeptieren und stillschweigend einem
  ``Location``-Header an ein beliebiges (auch internes) Ziel folgen. Hier
  wird jede Weiterleitung einzeln aufgelöst und erneut gegen dieselbe
  Sicherheitsprüfung wie die ursprüngliche URL geprüft, mit einer festen
  Obergrenze an Sprüngen (``_MAX_REDIRECTS``).

- **DNS-Prüfung mit Bindung an die geprüfte IP (Befund F4, Code Review
  2026.9.2):** Die rein syntaktische Prüfung erkennt keinen Domainnamen,
  der auf eine private Adresse zeigt (z. B. ``127.0.0.1.nip.io`` oder
  DNS-Rebinding). Der Abruf läuft deshalb über eine eigene, kurzlebige
  ``aiohttp.ClientSession`` mit ``_OeffentlichAufloeser``: Er löst jeden
  Hostnamen (Erstanfrage **und** jeden Weiterleitungssprung) asynchron auf,
  prüft **alle** A/AAAA-Einträge mit ``url_sicherheit.ist_oeffentliche_ip``
  (``is_global``) und liefert genau diese geprüften Adressen an den
  Verbindungsaufbau zurück – Prüfung und Verbindung nutzen dieselbe
  Auflösung, ein Wechsel der Antwort dazwischen (Rebinding) ist nicht
  möglich. Gemischte Antworten werden abgelehnt. Keine Wiederverwendung
  von Verbindungen (``force_close``).

Abweichung von Home Assistants verwalteter Client-Session
(``async_get_clientsession``, ``quality_scale.yaml``, Kriterium
``inject-websession``): Ein eigener Resolver lässt sich an der geteilten
Session nicht einhängen; die Session wird deshalb je Abruf erzeugt und
sicher geschlossen. Für IP-Literale entfällt die Auflösung (sie sind
bereits syntaktisch geprüft).

Nicht abgedeckt bleibt die synchrone Bild-URL-Prüfung (``images.py``): Sie
kann nicht auflösen und bleibt syntaktisch.

## Vertiefte Text-Heuristik (Issue #9)

Issue #8 hat bewusst auf jede Interpretation von Freitext verzichtet
(siehe oben, "Prinzip 'lieber nichts als falsch'"), da ermittelte Werte
damals **direkt** in die Formularfelder des Verwaltungspanels geschrieben
wurden. Seit Issue #9 ist zwischen Ermittlung und Übernahme zwingend ein
Bestätigungs-Popup geschaltet (siehe ``static/hofkarte-panel.js``,
``ermittleWebseiteInfo()``/``uebernehmeWebseiteInfo()``) - die Benutzerin/
der Benutzer sieht und bestätigt jeden Vorschlag explizit, bevor er in ein
Formularfeld übernommen wird. Diese zusätzliche Kontrollinstanz
rechtfertigt eine vorsichtige Erweiterung um dokumentierte,
nachvollziehbare Text-Heuristiken für Adresse und Öffnungszeiten, **wenn**
sich diese nicht bereits zuverlässig aus JSON-LD ermitteln liessen (siehe
``_extrahiere_adresse_aus_text``/``_extrahiere_oeffnungszeiten_aus_text``).
Weiterhin **kein** externer/Cloud-/KI-Dienst - die Heuristiken sind reine,
lokale, deterministische Regex-Mustererkennung auf dem bereits
abgerufenen, sichtbaren Seitentext (kein zusätzlicher Netzwerk-Request).
Und weiterhin gilt "lieber nichts als falsch": beide Heuristiken liefern
bei mehrdeutigem oder widersprüchlichem Text bewusst **keinen** Vorschlag,
statt einen unsicheren zu raten - siehe die jeweiligen Funktionsdocstrings
für die genauen, dokumentierten Grenzen dieses Ansatzes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from yarl import URL as YarlURL

from .url_sicherheit import ist_oeffentliche_ip, ist_sichere_externe_url

_LOGGER = logging.getLogger(__name__)

# 2 MB genügt für praktisch jede normale Homepage-HTML-Seite und begrenzt
# gleichzeitig den Ressourcenverbrauch durch übergrosse Antworten.
MAX_ANTWORT_BYTES = 2 * 1024 * 1024
ABRUF_TIMEOUT_SEKUNDEN = 10
_LESE_CHUNK_BYTES = 65536
_MAX_REDIRECTS = 3
_ERLAUBTE_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_WEITERLEITUNGS_STATUS = (301, 302, 303, 307, 308)

# --- Laufzeitbegrenzung der Text-Heuristiken (Befund F2, Code Review 2026.9.2) --
#
# Der sichtbare Seitentext stammt von einer **nicht vertrauenswürdigen**
# Website. Die Fallback-Regexe unten liefen früher ungebremst und
# synchron in der Home-Assistant-Event-Loop; mit gezielt gebauten Seiten
# (z. B. ein einziges, 100 000 Zeichen langes „Wort“) wuchs die Laufzeit
# quadratisch (Review-Messung: Adress-Regex ≈ 52 s bei 40 000 Zeichen)
# und fror HA ein. Daher gilt mehrstufig:
#
# 1. Eingabe begrenzen (``_begrenze_text``): Gesamttext und Zeilenlänge.
# 2. Muster selbst begrenzen: jede Wiederholung hat eine Obergrenze und
#    beginnt nur an einer Wortgrenze (Lookbehind) - dadurch wird jede
#    Textposition höchstens konstant oft als Trefferstart versucht.
# 3. Die gesamte Extraktion läuft im Executor, abgesichert durch ein
#    Zeitlimit (``EXTRAKTION_TIMEOUT_SEKUNDEN``), damit selbst ein
#    unerwartet teures Muster die Event-Loop nicht blockiert.
#
# Die Grenzen sind grosszügig gewählt: Echte Impressum-/Kontaktzeilen sind
# weit kürzer, die Trefferqualität ändert sich dadurch nicht.
MAX_SICHTBARER_TEXT_ZEICHEN = 200_000
# Eine Zeile mit mehr Zeichen ist kein Adress-/Öffnungszeiten-/Kontakteintrag
# (sondern z. B. minifizierter Inline-Code oder ein Datenblock) und wird
# vor den Heuristiken verworfen.
MAX_ZEILE_ZEICHEN = 500
EXTRAKTION_TIMEOUT_SEKUNDEN = 10
# Obergrenzen der Musterbausteine (siehe Muster unten).
_MAX_WORT_ZEICHEN = 60  # Strassen-/Ortswort
_MAX_EMAIL_LOCAL = 64  # RFC 5321: Local-Part höchstens 64 Zeichen
_MAX_EMAIL_DOMAIN = 255  # RFC 1035: Domain höchstens 255 Zeichen
_MAX_LEERRAUM = 10  # aufeinanderfolgende Leerzeichen/Tabs in einem Muster

_WOCHENTAGE_SCHEMA_ORG = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}

# --- Vertiefte Text-Heuristik (Issue #9) -----------------------------------
#
# Deutschsprachige Wochentag-Kurz- und Langformen, wie sie auf
# Hofladen-Websites typischerweise für Öffnungszeiten verwendet werden.
# Wochentag-Nummerierung (1=Montag...7=Sonntag) entspricht der bereits im
# Projekt etablierten Konvention (siehe ``WEEKDAYS`` in
# ``static/hofkarte-panel.js`` sowie ``models.py``).
_WOCHENTAG_TEXT = {
    "mo": 1, "montag": 1,
    "di": 2, "dienstag": 2,
    "mi": 3, "mittwoch": 3,
    "do": 4, "donnerstag": 4,
    "fr": 5, "freitag": 5,
    "sa": 6, "samstag": 6,
    "so": 7, "sonntag": 7,
}
_WOCHENTAG_ALTERNATIVEN = "|".join(_WOCHENTAG_TEXT.keys())

# Erkennt Zeilen wie "Mo-Fr 08:00-18:00 Uhr", "Montag bis Freitag: 8 – 18
# Uhr" oder "Sa 08:00–12:00" (Issue #9). Der Tagesbereich (via "bis"/"-"/
# Gedankenstrich) sowie das "Uhr"-Suffix sind optional; Uhrzeiten dürfen
# ohne führende Null und ohne Minutenangabe vorkommen (z. B. "8" statt
# "08:00"). Bewusst **kein** Versuch, jede erdenkliche Freitext-Variante
# abzudecken - siehe Docstring von ``_extrahiere_oeffnungszeiten_aus_text``
# für die dokumentierten Grenzen.
#
# Bewusst [ \t] statt \s als Trenner verwendet (nicht \n): siehe
# ``_SeitenParser.sichtbarer_text()`` - ein Treffer darf nicht über die
# Grenze zweier unabhängiger Block-Elemente/Absätze hinweg zusammengesetzt
# werden (sonst könnten z. B. ein Wochentag aus einem Absatz und eine
# völlig unabhängige Uhrzeit aus dem nächsten fälschlich kombiniert
# werden). Dokumentierte Folge: eine über mehrere Zeilen verteilte Angabe
# (z. B. Wochentag und Uhrzeit in getrennten Absätzen) wird nicht erkannt.
_LZ = rf"[ \t]{{0,{_MAX_LEERRAUM}}}"  # begrenzter Leerraum (F2)
_OEFFNUNGSZEIT_TEXT_MUSTER = re.compile(
    rf"(?P<von_tag>{_WOCHENTAG_ALTERNATIVEN})\b"
    rf"(?:{_LZ}(?:bis|-|–|—){_LZ}(?P<bis_tag>{_WOCHENTAG_ALTERNATIVEN})\b)?"
    rf"{_LZ}:?{_LZ}"
    r"(?P<beginn_h>\d{1,2})(?:[:.](?P<beginn_m>\d{2}))?"
    rf"{_LZ}(?:-|–|—|bis){_LZ}"
    r"(?P<ende_h>\d{1,2})(?:[:.](?P<ende_m>\d{2}))?"
    rf"{_LZ}(?:uhr)?",
    re.IGNORECASE,
)

# Erkennt das im DACH-Raum übliche Adressmuster "<Strasse> <Hausnummer>,
# <PLZ> <Ort>" (Issue #9). Der Strassenname muss bewusst auf eine der
# gängigen deutschsprachigen Strassenbezeichnungs-Endungen enden, damit
# nicht beliebiger grossgeschriebener Fliesstext fälschlich als Adresse
# erkannt wird (siehe Docstring von ``_extrahiere_adresse_aus_text`` für
# die dokumentierten Grenzen dieses bewusst konservativen Ansatzes).
_STRASSEN_ENDUNGEN = (
    "strasse", "straße", "weg", "gasse", "platz", "ring", "allee",
    "rain", "halde", "feld", "hof", "steig",
)

# Im Deutschen wird die Strassenbezeichnungs-Endung (z. B. "-weg",
# "-strasse") in aller Regel **ohne** Leerzeichen an den eigentlichen
# Strassennamen angehängt (z. B. "Musterweg", nicht "Muster weg"). Die
# Regex erfasst daher zunächst nur eine plausible Kandidatenphrase (ein bis
# drei grossgeschriebene, durch Leerzeichen getrennte Wörter direkt vor
# einer Hausnummer und einer vierstelligen PLZ); ob das letzte Wort davon
# tatsächlich auf eine der ``_STRASSEN_ENDUNGEN`` endet, wird bewusst erst
# danach in Python geprüft (siehe ``_hat_strassen_endung``) - das ist
# deutlich wartbarer als eine Regex, die Wortstamm und Endung ohne
# Leerzeichen zusammenhängend, aber dennoch mehrdeutig trennen müsste.
#
# Auch hier bewusst [ \t] statt \s (siehe Kommentar bei
# ``_OEFFNUNGSZEIT_TEXT_MUSTER`` sowie ``_SeitenParser.sichtbarer_text()``):
# eine über mehrere Absätze verteilte Adresse (z. B. Strasse in einer
# eigenen Zeile, PLZ/Ort in der nächsten - auf Impressum-Seiten durchaus
# üblich) wird dadurch bewusst **nicht** erkannt, statt fälschlich mit dem
# nächsten, inhaltlich unabhängigen Absatz kombiniert zu werden.
# Befund F2: Jedes Wort ist auf ``_MAX_WORT_ZEICHEN`` begrenzt und beginnt
# nur an einer Wortgrenze (Lookbehind ``_WORT_START``). Zuvor war das erste
# Wort unbegrenzt und konnte an jeder Position eines langen Wortes neu
# beginnen - quadratische Laufzeit.
_WORTZEICHEN = r"\wÀ-ÖØ-öø-ÿ.\-"
_WORT_START = rf"(?<![{_WORTZEICHEN}])"
_GROSSWORT = rf"[A-ZÄÖÜ][{_WORTZEICHEN}]{{0,{_MAX_WORT_ZEICHEN}}}"
_ADRESSE_TEXT_MUSTER = re.compile(
    rf"{_WORT_START}(?P<strasse>{_GROSSWORT}(?:[ \t]{{1,{_MAX_LEERRAUM}}}{_GROSSWORT}){{0,2}})"
    rf"[ \t]{{1,{_MAX_LEERRAUM}}}(?P<hausnummer>\d{{1,4}}[a-zA-Z]?)"
    rf"{_LZ},?{_LZ}"
    r"(?P<plz>\d{4})"
    rf"[ \t]{{1,{_MAX_LEERRAUM}}}(?P<ort>{_GROSSWORT}(?:[ \t]{{1,{_MAX_LEERRAUM}}}{_GROSSWORT}){{0,2}})",
    re.IGNORECASE,
)


# Erkennt Standard-E-Mail-Adressen im sichtbaren Seitentext (Issue für
# Mobilnummer/E-Mail-Auto-Ermittlung). Bewusst eine einfache, gängige
# Teilmenge der RFC-5322-Syntax statt eines vollständig konformen Musters -
# für die hier relevanten, von Menschen auf einer Website veröffentlichten
# Kontaktadressen ist das ausreichend ("lieber nichts als falsch": eine
# exotische, technisch zwar gültige aber untypische Adresse wird im
# Zweifel nicht erkannt, statt eine falsche Interpretation zu riskieren).
#
# Befund F2: Local-Part (<= 64) und Domain (<= 255) sind begrenzt, ein Treffer
# beginnt nur dort, wo das davorstehende Zeichen kein Local-Part-Zeichen ist
# (Lookbehind) - zuvor wurde bei langen Zeichenfolgen ohne "@" an jeder
# Position erneut bis zum Ende gescannt (quadratisch). Die TLD ist auf 24
# Zeichen begrenzt (längste real vergebene TLDs: 24).
_EMAIL_TEXT_MUSTER = re.compile(
    rf"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{{1,{_MAX_EMAIL_LOCAL}}}"
    rf"@[A-Za-z0-9.\-]{{1,{_MAX_EMAIL_DOMAIN}}}\.[A-Za-z]{{2,24}}"
)

# Erkennt im DACH-Raum übliche Telefonnummern-Schreibweisen, z. B.
# "+41 79 123 45 67", "079 123 45 67" oder "0791234567". Erfordert eine
# führende "+" (internationale Vorwahl) oder eine führende "0" (nationale
# Schreibweise) sowie insgesamt mindestens 9 Ziffern, damit nicht
# beliebige kurze Ziffernfolgen (z. B. Postleitzahlen, Jahreszahlen)
# fälschlich als Telefonnummer erkannt werden. Leerzeichen, Schrägstriche
# und Bindestriche innerhalb der Nummer sind erlaubt (im Feld selbst
# unverändert übernommen, siehe ``_extrahiere_kontakt_aus_text``).
_TELEFON_TEXT_MUSTER = re.compile(
    r"(?<![\d/])(\+\d{2}|0)[ \t]?\d{2}[ \t/\-]?\d{3}[ \t/\-]?\d{2}[ \t/\-]?\d{2}(?!\d)"
)


def _begrenze_text(text: str) -> str:
    """Begrenzt den Eingabetext der Text-Heuristiken (Befund F2).

    Kappt den Gesamttext auf ``MAX_SICHTBARER_TEXT_ZEICHEN`` und verwirft
    Zeilen mit mehr als ``MAX_ZEILE_ZEICHEN`` Zeichen (keine plausiblen
    Adress-/Öffnungszeiten-/Kontaktzeilen). Schützt unabhängig von den
    (ebenfalls begrenzten) Mustern vor übergrossen Eingaben.
    """
    if len(text) > MAX_SICHTBARER_TEXT_ZEICHEN:
        text = text[:MAX_SICHTBARER_TEXT_ZEICHEN]
    if "\n" not in text:
        return text if len(text) <= MAX_ZEILE_ZEICHEN else ""
    return "\n".join(
        zeile for zeile in text.split("\n") if len(zeile) <= MAX_ZEILE_ZEICHEN
    )


def _hat_strassen_endung(wort: str) -> bool:
    wort_klein = wort.lower()
    return any(wort_klein.endswith(endung) for endung in _STRASSEN_ENDUNGEN)


class WebseiteUngueltigeUrlError(Exception):
    """Es wurde keine Website-Adresse angegeben, oder sie ist syntaktisch
    ungültig bzw. zeigt auf ein nicht erlaubtes Ziel (Fehlerfall 1)."""


class WebseiteNichtErreichbarError(Exception):
    """Die Website konnte nicht erreicht oder nicht gelesen werden
    (Fehlerfall 2: Verbindungsfehler, Timeout, HTTP-Fehlerstatus,
    ungültiges/nicht-HTML-Antwortformat, zu grosse Antwort, unsichere
    Weiterleitung)."""


class WebseiteInformationenNichtGefundenError(Exception):
    """Die Website war erreichbar, es konnten aber keine verwertbaren
    Informationen ermittelt werden (Fehlerfall 3)."""


@dataclass(frozen=True, slots=True)
class WebseiteInfo:
    """Aus einer Website ermittelte, noch ungeprüfte Hofladen-Informationen.

    Reine Vorschlagsdaten zur Überprüfung durch die Benutzerin/den
    Benutzer im Verwaltungs-Panel – nichts hiervon wird automatisch
    gespeichert (siehe ``management.py``, ``ws_webseite_info``). Felder
    sind ``None`` bzw. leer, wenn die jeweilige Information nicht
    zuverlässig ermittelt werden konnte (siehe Moduldoc, Prinzip "lieber
    nichts als falsch").
    """

    name: str | None = None
    beschreibung: str | None = None
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    mobilnummer: str | None = None
    email: str | None = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    angebote: tuple[str, ...] = ()
    zahlungsarten: tuple[str, ...] = ()

    def ist_leer(self) -> bool:
        """Ob überhaupt keine verwertbare Information ermittelt wurde."""
        return not (
            self.name
            or self.beschreibung
            or self.adresse
            or self.plz
            or self.ort
            or self.land
            or self.mobilnummer
            or self.email
            or self.oeffnungszeiten
            or self.angebote
            or self.zahlungsarten
        )


def _str_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


class _SeitenParser(HTMLParser):
    """Extrahiert ausschliesslich ``<title>``, ``<meta name="description">``
    und den Inhalt aller ``<script type="application/ld+json">``-Blöcke aus
    einer HTML-Seite. Bewusst mit der Python-Standardbibliothek
    (``html.parser``) statt einer zusätzlichen Abhängigkeit umgesetzt."""

    # Tags, deren Textinhalt nicht für sichtbare Freitext-Heuristiken
    # (Issue #9, ``sichtbarer_text``) verwendet werden soll - Skript-/
    # Stilinhalt ist kein für Menschen sichtbarer Seiteninhalt, und der
    # Titel wird bereits separat über ``self.titel`` erfasst.
    _IGNORIERTE_TEXT_TAGS = {"script", "style", "noscript", "title"}

    # Block-Elemente erzeugen im gerenderten Layout einen Zeilenumbruch -
    # ihre Tag-Grenzen werden in ``sichtbarer_text()`` daher als
    # Zeilenumbruch statt als einfaches Leerzeichen abgebildet. Das ist die
    # einzige Grenzinformation, die den Fallback-Heuristiken (Adresse/
    # Öffnungszeiten, siehe Moduldoc) zur Verfügung steht, um zufällige
    # Wortfolgen über mehrere, inhaltlich unabhängige Absätze/Zeilen hinweg
    # NICHT als einen zusammenhängenden Treffer misszuinterpretieren
    # (siehe dortige Docstrings, "Dokumentierte Grenzen": eine über mehrere
    # Zeilen verteilte Adresse, z. B. Strasse und PLZ/Ort in getrennten
    # Absätzen, wird deshalb bewusst nicht erkannt).
    _BLOCK_TAGS = {
        "p", "div", "li", "br", "tr", "td", "th", "section", "article",
        "header", "footer", "address", "dd", "dt", "h1", "h2", "h3", "h4",
        "h5", "h6", "ul", "ol", "table", "blockquote",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titel = ""
        self.beschreibung_meta: str | None = None
        self.json_ld_bloecke: list[str] = []
        # Grob normalisierter, für Menschen sichtbarer Seitentext (Issue #9)
        # - dient ausschliesslich den Fallback-Heuristiken für Adresse/
        # Öffnungszeiten, siehe Moduldoc "Vertiefte Text-Heuristik". Zwischen
        # Elementen wird ein Leerzeichen eingefügt (sonst würden z. B.
        # aufeinanderfolgende <p>-Absätze ohne Trennzeichen aneinander
        # kleben); Mehrfach-Leerraum wird beim Zusammensetzen in
        # ``sichtbarer_text()`` normalisiert.
        self._text_teile: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_puffer: list[str] = []
        self._ignoriere_text_tiefe = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "").strip().lower()
            inhalt = attrs_dict.get("content", "").strip()
            if name == "description" and inhalt and self.beschreibung_meta is None:
                self.beschreibung_meta = inhalt
        elif tag == "script" and attrs_dict.get("type", "").strip().lower() == (
            "application/ld+json"
        ):
            self._in_json_ld = True
            self._json_ld_puffer = []
        if tag in self._IGNORIERTE_TEXT_TAGS:
            self._ignoriere_text_tiefe += 1
        self._text_teile.append("\n" if tag in self._BLOCK_TAGS else " ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld_bloecke.append("".join(self._json_ld_puffer))
        if tag in self._IGNORIERTE_TEXT_TAGS and self._ignoriere_text_tiefe > 0:
            self._ignoriere_text_tiefe -= 1
        self._text_teile.append("\n" if tag in self._BLOCK_TAGS else "")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.titel += data
        elif self._in_json_ld:
            self._json_ld_puffer.append(data)
        elif self._ignoriere_text_tiefe == 0:
            self._text_teile.append(data)

    def sichtbarer_text(self) -> str:
        """Der gesammelte, für Menschen sichtbare Seitentext (Issue #9).

        Innerhalb einer Zeile wird Leerraum auf ein einzelnes Leerzeichen
        normalisiert; Zeilenumbrüche zwischen Block-Elementen (siehe
        ``_BLOCK_TAGS``) bleiben dabei bewusst erhalten - sie sind die
        einzige verfügbare Grenzinformation, damit die Fallback-
        Heuristiken (Adresse/Öffnungszeiten) nicht versehentlich Wörter aus
        zwei unabhängigen Absätzen zu einem falschen Treffer verketten."""
        roh = "".join(self._text_teile)
        zeilen = (re.sub(r"[ \t]+", " ", zeile).strip() for zeile in roh.split("\n"))
        return "\n".join(zeile for zeile in zeilen if zeile)


def _flatten_json_ld(wert: Any) -> list[dict[str, Any]]:
    """Baut eine flache Liste von JSON-LD-Objekten auf – löst dabei
    Listen sowie das schema.org-``@graph``-Konstrukt auf (mehrere
    Entitäten in einem einzigen ``<script>``-Block).

    Iterativ statt rekursiv (Befund F13): Eine bösartig tief verschachtelte
    Liste (``[[[[…]]]]``) soll nie zu einem ``RecursionError`` führen. Die
    Reihenfolge der Objekte entspricht der bisherigen rekursiven
    Tiefensuche (von links nach rechts).
    """
    ergebnis: list[dict[str, Any]] = []
    stapel: list[Any] = [wert]
    while stapel:
        aktuell = stapel.pop()
        if isinstance(aktuell, list):
            stapel.extend(reversed(aktuell))
        elif isinstance(aktuell, dict):
            graph = aktuell.get("@graph")
            if isinstance(graph, list):
                stapel.extend(reversed(graph))
            else:
                ergebnis.append(aktuell)
    return ergebnis


def _iter_json_ld_objekte(bloecke: list[str]) -> list[dict[str, Any]]:
    objekte: list[dict[str, Any]] = []
    for roh in bloecke:
        try:
            geparst = json.loads(roh)
        except (ValueError, RecursionError):
            # json.JSONDecodeError ist eine ValueError. RecursionError
            # (Befund F13): ``json.loads`` kann bei extrem tiefer
            # Verschachtelung (z. B. 200 000 x "[") daran scheitern.
            continue
        objekte.extend(_flatten_json_ld(geparst))
    return objekte


def _ist_business_kandidat(obj: dict[str, Any]) -> bool:
    if not isinstance(obj.get("name"), str) or not obj["name"].strip():
        return False
    geeignete_felder = (
        "address",
        "openingHours",
        "openingHoursSpecification",
        "telephone",
        "priceRange",
        "paymentAccepted",
        "makesOffer",
    )
    return any(feld in obj for feld in geeignete_felder)


def _waehle_business_objekt(objekte: list[dict[str, Any]]) -> dict[str, Any] | None:
    for obj in objekte:
        if isinstance(obj, dict) and _ist_business_kandidat(obj):
            return obj
    return None


def _extrahiere_adresse(
    obj: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str | None]:
    adresse = obj.get("address")
    if isinstance(adresse, str):
        return _str_or_none(adresse), None, None, None
    if isinstance(adresse, dict):
        strasse = _str_or_none(adresse.get("streetAddress"))
        plz = _str_or_none(adresse.get("postalCode"))
        ort = _str_or_none(adresse.get("addressLocality"))
        land_roh = adresse.get("addressCountry")
        if isinstance(land_roh, dict):
            land = _str_or_none(land_roh.get("name"))
        else:
            land = _str_or_none(land_roh)
        return strasse, plz, ort, land
    return None, None, None, None


def _wochentag_aus_schema_org(wert: str) -> int | None:
    kurz = wert.strip().rsplit("/", 1)[-1].strip().lower()
    return _WOCHENTAGE_SCHEMA_ORG.get(kurz)


def _parse_uhrzeit(wert: Any) -> str | None:
    if not isinstance(wert, str):
        return None
    wert = wert.strip()
    if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", wert):
        return wert[:5]
    return None


def _extrahiere_oeffnungszeiten(obj: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Wertet ausschliesslich das vollständig strukturierte
    ``openingHoursSpecification`` aus (siehe Moduldoc zur bewusst nicht
    unterstützten Kurzform ``openingHours``). Unvollständige oder
    widersprüchliche Einzeleinträge werden übersprungen, nicht geraten."""
    spec = obj.get("openingHoursSpecification")
    if spec is None:
        return ()
    eintraege = spec if isinstance(spec, list) else [spec]

    ergebnis: list[dict[str, Any]] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        opens = _parse_uhrzeit(eintrag.get("opens"))
        closes = _parse_uhrzeit(eintrag.get("closes"))
        if opens is None or closes is None or opens == closes:
            continue

        tage_roh = eintrag.get("dayOfWeek")
        tage = tage_roh if isinstance(tage_roh, list) else [tage_roh]
        for tag_roh in tage:
            if not isinstance(tag_roh, str):
                continue
            wochentag = _wochentag_aus_schema_org(tag_roh)
            if wochentag is None:
                continue
            ergebnis.append({"wochentag": wochentag, "beginn": opens, "ende": closes})

    return tuple(ergebnis)


def _extrahiere_kontakt(obj: dict[str, Any]) -> tuple[str | None, str | None]:
    """Mobilnummer/Telefon (``telephone``) und E-Mail (``email``) aus dem
    JSON-LD-Businessobjekt lesen, sofern vorhanden. Beide Felder sind laut
    schema.org einfache Zeichenketten - keine strukturierte Auswertung
    nötig, anders als z. B. ``address``."""
    return _str_or_none(obj.get("telephone")), _str_or_none(obj.get("email"))


def _extrahiere_kontakt_aus_text(
    text: str,
) -> tuple[str | None, str | None]:
    """Fallback-Erkennung von Mobilnummer/Telefon und E-Mail im sichtbaren
    Seitentext, falls JSON-LD keine (oder keine vollständigen)
    Kontaktangaben liefert.

    Bewusst konservativ (Prinzip "lieber nichts als falsch", siehe
    Moduldoc): Werden im Text **mehrere unterschiedliche** Treffer für
    dasselbe Feld gefunden, ist das Ergebnis uneindeutig - dann wird für
    dieses Feld kein Vorschlag geliefert (identische Wiederholungen, z. B.
    im Kopf- und Fussbereich der Seite, zählen dabei nicht als
    Widerspruch). Beide Felder werden unabhängig voneinander ausgewertet.
    """
    text = _begrenze_text(text)
    telefon_treffer = {m.group(0).strip() for m in _TELEFON_TEXT_MUSTER.finditer(text)}
    # E-Mail-Suche nur, wenn überhaupt ein "@" vorkommt (F2).
    email_treffer = (
        {m.group(0).strip() for m in _EMAIL_TEXT_MUSTER.finditer(text)}
        if "@" in text
        else set()
    )

    telefon = next(iter(telefon_treffer)) if len(telefon_treffer) == 1 else None
    email = next(iter(email_treffer)) if len(email_treffer) == 1 else None
    return telefon, email


def _extrahiere_zahlungsarten(obj: dict[str, Any]) -> tuple[str, ...]:
    wert = obj.get("paymentAccepted")
    if isinstance(wert, str):
        teile = [teil.strip() for teil in wert.split(",")]
        return tuple(teil for teil in teile if teil)
    if isinstance(wert, list):
        return tuple(
            str(teil).strip() for teil in wert if isinstance(teil, str) and teil.strip()
        )
    return ()


def _extrahiere_angebote(obj: dict[str, Any]) -> tuple[str, ...]:
    angebote_roh = obj.get("makesOffer")
    if angebote_roh is None:
        return ()
    eintraege = angebote_roh if isinstance(angebote_roh, list) else [angebote_roh]

    namen: list[str] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        name: str | None = None
        item = eintrag.get("itemOffered")
        if isinstance(item, dict):
            name = _str_or_none(item.get("name"))
        if name is None:
            name = _str_or_none(eintrag.get("name"))
        if name is not None:
            namen.append(name)

    return tuple(namen)


def _normalisiere_uhrzeit_text(stunde: str, minute: str | None) -> str | None:
    """Wie ``_parse_uhrzeit`` (JSON-LD-Pfad), aber für die aus Freitext
    per Regex einzeln eingefangenen Stunden-/Minuten-Anteile - erlaubt
    dabei zusätzlich eine fehlende Minutenangabe (z. B. "8" statt "08:00",
    im Freitext üblich, in JSON-LD dagegen nicht). Liefert ``None`` bei
    unplausiblen Werten (z. B. Stunde > 23), statt einen ungültigen Wert
    zu übernehmen."""
    try:
        stunde_int = int(stunde)
        minute_int = int(minute) if minute is not None else 0
    except (TypeError, ValueError):
        return None
    if not (0 <= stunde_int <= 23 and 0 <= minute_int <= 59):
        return None
    return f"{stunde_int:02d}:{minute_int:02d}"


def _wochentag_bereich(von_tag: int, bis_tag: int | None) -> list[int]:
    """Liste der Wochentage eines Bereichs (z. B. Mo-Fr -> [1,2,3,4,5]).
    Unterstützt auch über die Wochengrenze laufende Bereiche (z. B.
    Sa-Mo -> [6,7,1]), da diese bei Hofladen-Öffnungszeiten (z. B.
    "Wochenend-Stand") durchaus vorkommen. Ohne ``bis_tag`` wird nur der
    einzelne Tag geliefert."""
    if bis_tag is None:
        return [von_tag]
    if von_tag <= bis_tag:
        return list(range(von_tag, bis_tag + 1))
    return list(range(von_tag, 8)) + list(range(1, bis_tag + 1))


def _extrahiere_oeffnungszeiten_aus_text(text: str) -> tuple[dict[str, Any], ...]:
    """Fallback-Öffnungszeiten-Erkennung im sichtbaren Seitentext
    (Issue #9), falls JSON-LD keine ``openingHoursSpecification`` liefert.

    Erkennt gängige deutschsprachige Freitext-Muster wie "Mo-Fr
    08:00-18:00 Uhr", "Montag bis Freitag: 8 – 18 Uhr" oder "Sa
    08:00–12:00" (siehe ``_OEFFNUNGSZEIT_TEXT_MUSTER``). Wochentag-Bereiche
    werden auf die einzelnen Wochentage abgebildet.

    Bewusst konservativ (Prinzip "lieber nichts als falsch"): Findet sich
    im Text für ein und denselben Wochentag mehr als eine unterschiedliche
    Zeitangabe (z. B. zwei widersprüchliche Angaben an verschiedenen
    Stellen der Seite, oder mehrere separate, nicht zusammengefasste
    Zeitfenster für denselben Tag wie eine Mittagspause), wird für diesen
    Wochentag **kein** Vorschlag geliefert - andere, eindeutige Wochentage
    sind davon nicht betroffen.

    Dokumentierte Grenzen: Es wird bewusst kein Versuch unternommen,
    mehrere Zeitfenster desselben Tages (z. B. "Mo 08:00-12:00 und
    14:00-18:00") korrekt als *ein* zusammengehöriger Tag mit zwei
    Intervallen zu erkennen - das zweite, nicht erneut mit dem Wochentag
    eingeleitete Zeitfenster wird von der Regex gar nicht erst erfasst.
    Ebenso werden Feiertags-/Ausnahme-Hinweise ("ausser an Feiertagen")
    nicht ausgewertet. Beides wäre zusätzliche Interpretation mit
    Fehlerpotenzial - im Zweifel wird hier lieber ein unvollständiges statt
    ein falsches Ergebnis geliefert.
    """
    kandidaten: dict[int, set[tuple[str, str]]] = {}
    for treffer in _OEFFNUNGSZEIT_TEXT_MUSTER.finditer(_begrenze_text(text)):
        von_tag = _WOCHENTAG_TEXT.get(treffer.group("von_tag").lower())
        bis_tag_roh = treffer.group("bis_tag")
        bis_tag = _WOCHENTAG_TEXT.get(bis_tag_roh.lower()) if bis_tag_roh else None
        if von_tag is None:
            continue

        beginn = _normalisiere_uhrzeit_text(treffer.group("beginn_h"), treffer.group("beginn_m"))
        ende = _normalisiere_uhrzeit_text(treffer.group("ende_h"), treffer.group("ende_m"))
        if beginn is None or ende is None or beginn == ende:
            continue

        for tag in _wochentag_bereich(von_tag, bis_tag):
            kandidaten.setdefault(tag, set()).add((beginn, ende))

    ergebnis: list[dict[str, Any]] = []
    for tag in sorted(kandidaten):
        zeiten = kandidaten[tag]
        if len(zeiten) != 1:
            continue  # widersprüchliche Fundstellen -> kein Vorschlag für diesen Tag
        beginn, ende = next(iter(zeiten))
        ergebnis.append({"wochentag": tag, "beginn": beginn, "ende": ende})
    return tuple(ergebnis)


def _extrahiere_adresse_aus_text(
    text: str,
) -> tuple[str | None, str | None, str | None]:
    """Fallback-Adresserkennung im sichtbaren Seitentext (Issue #9), falls
    JSON-LD keine ``PostalAddress`` liefert.

    Erkennt das im DACH-Raum übliche Muster "<Strasse> <Hausnummer>, <PLZ>
    <Ort>" (vierstellige Postleitzahl, siehe ``_ADRESSE_TEXT_MUSTER`` sowie
    die bereits im Projekt etablierte ``plz``/``ort``-Feldtrennung in
    ``models.py``). Liefert ``(strasse_mit_hausnummer, plz, ort)``, oder
    drei ``None``-Werte, wenn kein eindeutiger Treffer gefunden wurde.

    Bewusst konservativ (Prinzip "lieber nichts als falsch"): Der
    Strassenname muss auf eine gängige deutschsprachige
    Strassenbezeichnungs-Endung enden (siehe ``_STRASSEN_ENDUNGEN``), damit
    nicht beliebiger grossgeschriebener Fliesstext fälschlich als Adresse
    erkannt wird. Werden im Text **mehrere unterschiedliche** Kandidaten
    gefunden (z. B. Liefer- und Rechnungsadresse), ist das Ergebnis
    uneindeutig - dann wird kein Vorschlag geliefert (identische
    Wiederholungen derselben Adresse, z. B. im Kopf- und Fussbereich der
    Seite, zählen dabei nicht als Widerspruch).

    Dokumentierte Grenzen: Strassennamen ohne eine der erkannten Endungen
    (z. B. reine Ortsnamen als Strassenname, oder nicht-deutschsprachige
    Bezeichnungen) sowie Postleitzahlen ausserhalb des vierstelligen
    DACH-Formats werden nicht erkannt - hier bleibt das Feld bewusst leer,
    statt einen unsicheren Vorschlag zu liefern.
    """
    eindeutige = set()
    for m in _ADRESSE_TEXT_MUSTER.finditer(_begrenze_text(text)):
        strasse_worte = m.group("strasse").split()
        if not strasse_worte or not _hat_strassen_endung(strasse_worte[-1]):
            continue  # kein erkanntes Strassenmuster -> kein Kandidat
        eindeutige.add((
            " ".join(strasse_worte),
            m.group("hausnummer"),
            m.group("plz"),
            " ".join(m.group("ort").split()),
        ))
    if len(eindeutige) != 1:
        return None, None, None

    strasse, hausnummer, plz, ort = next(iter(eindeutige))
    return f"{strasse} {hausnummer}", plz, ort


def _extrahiere_aus_html(html_text: str) -> WebseiteInfo:
    parser = _SeitenParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001 - HTMLParser soll nie zum Absturz führen
        _LOGGER.debug("Website-HTML konnte nicht vollständig geparst werden.")

    objekte = _iter_json_ld_objekte(parser.json_ld_bloecke)
    business = _waehle_business_objekt(objekte)

    name: str | None = None
    beschreibung: str | None = None
    adresse = plz = ort = land = None
    mobilnummer: str | None = None
    email: str | None = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    angebote: tuple[str, ...] = ()
    zahlungsarten: tuple[str, ...] = ()

    if business is not None:
        name = _str_or_none(business.get("name"))
        beschreibung = _str_or_none(business.get("description"))
        adresse, plz, ort, land = _extrahiere_adresse(business)
        mobilnummer, email = _extrahiere_kontakt(business)
        oeffnungszeiten = _extrahiere_oeffnungszeiten(business)
        angebote = _extrahiere_angebote(business)
        zahlungsarten = _extrahiere_zahlungsarten(business)

    if beschreibung is None:
        # Nicht erfunden, sondern die von der Seite selbst hinterlegte
        # Meta-Beschreibung - ein Standard-SEO-Feld.
        beschreibung = _str_or_none(parser.beschreibung_meta)

    if name is None:
        # Schwacher, aber unverfälschter Fallback: der komplette,
        # getrimmte Seitentitel. Ein Versuch, daraus nur den
        # "Betriebsnamen-Teil" herauszulösen (z. B. vor einem " - " oder
        # " | "), wäre Raten über die Struktur des Titels - siehe Moduldoc,
        # Prinzip "lieber nichts als falsch". Der volle Titel wird daher
        # unverändert übernommen; die Benutzerin/der Benutzer prüft und
        # kürzt ihn bei Bedarf selbst vor dem Speichern.
        name = _str_or_none(parser.titel)

    # Vertiefte Text-Heuristik (Issue #9) - greift ausschliesslich als
    # Fallback, wenn JSON-LD für Adresse bzw. Öffnungszeiten nichts
    # geliefert hat (siehe Moduldoc, Abschnitt "Vertiefte Text-Heuristik").
    # Adresse wird bewusst nur als Ganzes ergänzt (nicht feldweise) - eine
    # aus JSON-LD bereits teilweise vorhandene, zuverlässigere Adresse soll
    # nicht mit unsicheren Text-Treffern vermischt werden.
    # Der sichtbare Text wird nur einmal aufgebaut und (Befund F2) begrenzt.
    sichtbarer_text = _begrenze_text(parser.sichtbarer_text())

    if adresse is None and plz is None and ort is None:
        adresse, plz, ort = _extrahiere_adresse_aus_text(sichtbarer_text)

    if not oeffnungszeiten:
        oeffnungszeiten = _extrahiere_oeffnungszeiten_aus_text(sichtbarer_text)

    # Mobilnummer/E-Mail per Text-Heuristik nur ergänzen, wenn JSON-LD das
    # jeweilige Feld nicht geliefert hat - je Feld unabhängig, analog zu
    # Öffnungszeiten (nicht wie bei der Adresse "alles oder nichts", da
    # Telefon und E-Mail inhaltlich unabhängige Einzelwerte ohne
    # gegenseitige Konsistenzbeziehung sind).
    if mobilnummer is None or email is None:
        text_mobilnummer, text_email = _extrahiere_kontakt_aus_text(
            sichtbarer_text
        )
        if mobilnummer is None:
            mobilnummer = text_mobilnummer
        if email is None:
            email = text_email

    return WebseiteInfo(
        name=name,
        beschreibung=beschreibung,
        adresse=adresse,
        plz=plz,
        ort=ort,
        land=land,
        mobilnummer=mobilnummer,
        email=email,
        oeffnungszeiten=oeffnungszeiten,
        angebote=angebote,
        zahlungsarten=zahlungsarten,
    )


def _aufgeloeste_weiterleitungsziel(basis_url: str, location_header: str) -> str:
    """Löst einen (ggf. relativen) ``Location``-Header gegenüber der
    aktuellen URL auf."""
    return str(YarlURL(basis_url).join(YarlURL(location_header)))


async def _lese_antwort_text(antwort: aiohttp.ClientResponse) -> str:
    """Liest den Antwortkörper begrenzt auf ``MAX_ANTWORT_BYTES`` und
    dekodiert ihn. Muss innerhalb des ``async with``-Blocks der Anfrage
    aufgerufen werden."""
    content_type = (antwort.content_type or "").lower()
    if not any(content_type.startswith(t) for t in _ERLAUBTE_CONTENT_TYPES):
        raise WebseiteNichtErreichbarError(
            "Die Antwort der Website ist keine lesbare HTML-Seite "
            f"(Content-Type: '{content_type or 'unbekannt'}')."
        )

    rohdaten = bytearray()
    async for chunk in antwort.content.iter_chunked(_LESE_CHUNK_BYTES):
        rohdaten.extend(chunk)
        if len(rohdaten) > MAX_ANTWORT_BYTES:
            raise WebseiteNichtErreichbarError(
                "Die Antwort der Website ist zu gross, um verarbeitet zu werden."
            )

    try:
        encoding = antwort.get_encoding()
    except (LookupError, RuntimeError, UnicodeError):
        encoding = "utf-8"

    return bytes(rohdaten).decode(encoding, errors="replace")


class _NichtOeffentlichError(OSError):
    """Ein Hostname löst (auch) auf eine nicht öffentliche Adresse auf."""


class _OeffentlichAufloeser(aiohttp.abc.AbstractResolver):
    """Löst Hostnamen auf und akzeptiert **nur** öffentliche Adressen (F4).

    Gibt genau die geprüften Adressen an ``aiohttp`` zurück - der
    Verbindungsaufbau nutzt damit dieselbe Auflösung wie die Prüfung
    (Schutz vor DNS-Rebinding zwischen Prüfung und Abruf). Eine einzige
    nicht öffentliche Adresse in der Antwort lehnt die gesamte Antwort ab.
    """

    def __init__(self) -> None:
        self._intern = aiohttp.ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[dict[str, Any]]:
        treffer = await self._intern.resolve(host, port, family)
        adressen = [eintrag["host"] for eintrag in treffer]
        if not adressen or not all(ist_oeffentliche_ip(a) for a in adressen):
            raise _NichtOeffentlichError(
                f"'{host}' löst nicht ausschliesslich auf öffentliche Adressen auf."
            )
        return list(treffer)

    async def close(self) -> None:
        await self._intern.close()


@contextlib.asynccontextmanager
async def _sichere_session() -> Any:
    """Kurzlebige ``aiohttp``-Session mit ``_OeffentlichAufloeser`` (F4)."""
    connector = aiohttp.TCPConnector(
        resolver=_OeffentlichAufloeser(), force_close=True, use_dns_cache=False
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        yield session


async def _hole_html(session: aiohttp.ClientSession, url: str) -> str:
    """Ruft ``url`` ab und liefert den (begrenzten) HTML-Text zurück.

    Löst Weiterleitungen bewusst **manuell** auf (``allow_redirects=False``
    je Einzelanfrage) und prüft jedes Weiterleitungsziel erneut über
    ``ist_sichere_externe_url`` – siehe Moduldoc, Abschnitt „SSRF-Schutz“.
    """
    timeout = aiohttp.ClientTimeout(total=ABRUF_TIMEOUT_SEKUNDEN)
    aktuelle_url = url

    for sprung in range(_MAX_REDIRECTS + 1):
        try:
            async with session.get(
                aktuelle_url, timeout=timeout, allow_redirects=False
            ) as antwort:
                if antwort.status in _WEITERLEITUNGS_STATUS:
                    location = antwort.headers.get("Location")
                    if not location:
                        raise WebseiteNichtErreichbarError(
                            "Die Website hat eine Weiterleitung ohne Ziel gesendet."
                        )
                    ziel = _aufgeloeste_weiterleitungsziel(aktuelle_url, location)
                    if not ist_sichere_externe_url(ziel):
                        raise WebseiteNichtErreichbarError(
                            "Die Website hat auf ein nicht erlaubtes Ziel "
                            "weitergeleitet."
                        )
                    aktuelle_url = ziel
                    continue

                if antwort.status >= 400:
                    raise WebseiteNichtErreichbarError(
                        "Die Website hat einen Fehler zurückgegeben "
                        f"(Status {antwort.status})."
                    )

                return await _lese_antwort_text(antwort)
        except WebseiteNichtErreichbarError:
            raise
        except aiohttp.ClientConnectorError as err:
            if isinstance(err.os_error, _NichtOeffentlichError):
                # Befund F4: Hostname zeigt (auch) auf eine nicht
                # öffentliche Adresse.
                if sprung == 0:
                    raise WebseiteUngueltigeUrlError(
                        "Die Website-Adresse ist ungültig oder zeigt auf ein "
                        "nicht erlaubtes Ziel."
                    ) from err
                raise WebseiteNichtErreichbarError(
                    "Die Website hat auf ein nicht erlaubtes Ziel weitergeleitet."
                ) from err
            raise WebseiteNichtErreichbarError(
                "Die Website konnte nicht erreicht werden."
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WebseiteNichtErreichbarError(
                "Die Website konnte nicht erreicht werden."
            ) from err

    raise WebseiteNichtErreichbarError(
        "Die Website hat zu viele Weiterleitungen ausgelöst."
    )


async def async_ermittle_webseite_info(hass: HomeAssistant, url: str | None) -> WebseiteInfo:
    """Ruft ``url`` ab und ermittelt daraus Hofladen-Informationen.

    Wirft (siehe Moduldoc und Issue #8 für die drei geforderten
    Fehlerfälle):

    - :class:`WebseiteUngueltigeUrlError` - keine URL angegeben, oder sie
      ist syntaktisch ungültig bzw. zeigt auf ein nicht erlaubtes Ziel
      (Fehlerfall 1).
    - :class:`WebseiteNichtErreichbarError` - Verbindungsfehler, Timeout,
      HTTP-Fehlerstatus, unlesbares Antwortformat, zu grosse Antwort oder
      unsichere Weiterleitung (Fehlerfall 2).
    - :class:`WebseiteInformationenNichtGefundenError` - die Website war
      erreichbar, es konnten aber keine verwertbaren Informationen
      ermittelt werden (Fehlerfall 3).

    Das Ergebnis ist ausschliesslich ein Vorschlag zur Überprüfung - siehe
    ``management.py``, ``ws_webseite_info``.
    """
    if not url or not url.strip():
        raise WebseiteUngueltigeUrlError("Es wurde keine Website-Adresse angegeben.")

    url = url.strip()
    if not ist_sichere_externe_url(url):
        raise WebseiteUngueltigeUrlError(
            "Die Website-Adresse ist ungültig oder zeigt auf ein nicht "
            "erlaubtes Ziel."
        )

    async with _sichere_session() as session:
        html_text = await _hole_html(session, url)

    # Befund F2: Die Auswertung (HTML-Parser + Regex-Heuristiken) ist
    # CPU-gebunden und läuft deshalb im Executor statt in der Event-Loop;
    # das Zeitlimit stellt sicher, dass auch ein unerwartet teures Muster
    # den Aufrufer nicht dauerhaft blockiert.
    try:
        async with asyncio.timeout(EXTRAKTION_TIMEOUT_SEKUNDEN):
            info = await hass.async_add_executor_job(
                _extrahiere_aus_html, html_text
            )
    except TimeoutError as err:
        raise WebseiteNichtErreichbarError(
            "Die Auswertung der Website hat zu lange gedauert."
        ) from err
    if info.ist_leer():
        raise WebseiteInformationenNichtGefundenError(
            "Auf der Website konnten keine verwertbaren Informationen "
            "gefunden werden."
        )
    return info
