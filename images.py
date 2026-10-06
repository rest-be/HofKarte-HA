"""Sichere Verarbeitung und Validierung von Hofladen-Bildern.

Dieses Modul stellt sicher, dass Bild-URLs sicher sind und keinen
Sicherheitsrisiken entsprechen:

- Nur http und https URLs werden akzeptiert
- file:// Zugriffe sind explizit nicht gestattet
- IP-Literale, die auf private/interne Ziele zeigen (z. B. 127.0.0.1,
  192.168.x.x, 169.254.169.254 – Cloud-Metadata-Endpunkte), werden
  abgelehnt, ebenso der Hostname "localhost"
- Fehlende oder ungültige Bilder werden robust behandelt

## Ausnahme: über den geführten Upload erzeugte Bilder

Über den geführten Bilder-Upload (siehe ``hofkarte-panel.js``, Home
Assistants eigene ``image_upload``-Komponente) erzeugte Bilder werden
zwangsläufig über eine URL referenziert, die auf die eigene
Home-Assistant-Instanz zeigt – bei den meisten Heiminstallationen eine
private LAN-Adresse (z. B. ``http://192.168.1.50:8123/...``). Die
private-IP-Prüfung unten dient dem Schutz vor SSRF über **frei
eingegebene, nicht vertrauenswürdige** externe URLs; sie ist bei einer
von HofKarte selbst über den offiziellen Home-Assistant-Upload-Weg
erzeugten URL nicht das richtige Kriterium – hier zählt die **Herkunft**
(von uns selbst erzeugt), nicht der Adressbereich. Bilder mit
``Bild.hochgeladen = True`` überspringen daher gezielt die
private-IP-/localhost-Prüfung, durchlaufen aber unverändert die
übrigen Prüfungen (nur http/https, keine eingebetteten Zugangsdaten).

## Bewusste Grenze: rein syntaktische Prüfung, keine DNS-Auflösung

(Stand 2026.10.0-dev.5, Befunde F1/F4 des Code Reviews zu 2026.9.2: Die
syntaktische Prüfung selbst ist gehärtet - normalisierter Hostname,
unübliche IPv4-Schreibweisen, ``is_global``, interne Hostnamen, siehe
``url_sicherheit.py``. Die Ausnahme ``hochgeladen=True`` wird nie aus
Eingabedaten übernommen, sondern serverseitig abgeleitet (``parsing.py``,
``url_sicherheit.ist_eigene_upload_url``). Die **DNS-Auflösungsprüfung** mit
Bindung an die geprüfte IP gibt es nur beim Website-Abruf
(``webseite_info.py``); für ``image_url`` - eine synchrone Entity-Property -
ist sie hier nicht möglich, die Grenze unten gilt dort unverändert.)

Die Prüfung erfolgt ausschliesslich anhand der URL-Syntax (Schema,
Zugangsdaten, IP-Literale) – es findet **keine DNS-Auflösung** statt.
Das ist eine bewusste Entscheidung: Eine Auflösung über
``socket.getaddrinfo`` ist ein blockierender Aufruf und dürfte aus
synchronen Home-Assistant-Entity-Properties (siehe ``image.py``:
``image_url`` wird von Home Assistant als reguläre, synchrone Property
aufgerufen) nicht direkt erfolgen, ohne den Event Loop zu blockieren.

Ein Domainname wie ``https://böser-domain.example`` wird daher nicht per
DNS geprüft; er wird akzeptiert und Home Assistants eigener
(asynchroner) Bild-Abruf (``ImageEntity.async_image``) übernimmt den
eigentlichen HTTP-Request. Ein DNS-Rebinding-Angriff (Domainname löst
zum Zeitpunkt des Requests auf eine private IP auf) wird durch diese
Prüfung nicht abgedeckt – IP-Literale und der Hostname "localhost"
werden aber zuverlässig abgelehnt, was den Hauptteil versehentlicher
oder offensichtlich böswilliger interner Ziele abdeckt.

## Gemeinsamer Prüfkern: ``url_sicherheit.py``

Die eigentliche Schema-/Zugangsdaten-/IP-Literal-Prüfung ist seit Issue #8
("Informationen aus Homepage", die serverseitig erstmals eine frei
eingegebene Website-URL selbst abruft) in ``url_sicherheit.py``
ausgelagert, da dieselbe Grundprüfung dort ein zweites Mal benötigt wird.
Dieses Modul ergänzt ausschliesslich noch die oben beschriebene
Herkunfts-Ausnahme für über den geführten Upload erzeugte Bilder.

Das Hauptbild eines Hofladens wird über Home Assistants natives
``image``-Entity-Platform dargestellt (siehe ``image.py``) – das ist die
plattformgerechte Lösung, da nur echte Image-Entities in Lovelace
automatisch als Bild gerendert werden (ein beliebiges Attribut würde das
nicht tun). Weitere Bilder (über das Hauptbild hinaus) werden als
Attribut an dieser Entity bereitgestellt, da Home Assistant keine native
"Galerie"-Darstellung für mehrere Bilder pro Entity kennt.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .models import Bild
from .url_sicherheit import ist_sichere_externe_url


def is_valid_image_url(url: str | None, *, hochgeladen: bool = False) -> bool:
    """Überprüft, ob eine URL ein gültiges, sicheres Bild ist.

    Akzeptiert nur http/https URLs. Lehnt ab:
    - file:// URLs (lokale Dateizugriffe)
    - data: URLs (Embedded Data)
    - Andere unsichere Protokolle
    - URLs mit eingebetteten Zugangsdaten
    - Den Hostnamen "localhost" sowie IP-Literale, die auf ein
      privates/internes Ziel zeigen (siehe Moduldoc zur bewussten Grenze
      dieser rein syntaktischen, nicht-blockierenden Prüfung) –
      **ausser** bei ``hochgeladen=True`` (siehe Moduldoc, Abschnitt
      „Ausnahme: über den geführten Upload erzeugte Bilder“)
    - Ungültige/leere URLs

    Args:
        url: Die zu validierende URL (oder None)
        hochgeladen: Ob die URL über HofKartes eigenen, geführten
            Bilder-Upload erzeugt wurde (siehe ``Bild.hochgeladen``).

    Returns:
        True, wenn die URL den syntaktischen Sicherheitsprüfungen genügt.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    # Nur http und https erlaubt
    if parsed.scheme not in ("http", "https"):
        return False
    # Keine Credentials in URL
    if parsed.username or parsed.password:
        return False
    # Zumindest Host erforderlich
    hostname = parsed.hostname
    if not hostname:
        return False
    if hochgeladen:
        # Herkunft (von HofKarte selbst über den offiziellen
        # Home-Assistant-Upload-Weg erzeugt) ersetzt hier die
        # Adressbereichs-Prüfung, siehe Moduldoc.
        return True
    # Schema/Zugangsdaten wurden bereits oben geprüft; die restliche
    # Prüfung (localhost/private IP-Literale) übernimmt der gemeinsame
    # Prüfkern in url_sicherheit.py (siehe Moduldoc).
    return ist_sichere_externe_url(url)


def get_main_image_url(bilder: tuple[Bild, ...]) -> str | None:
    """Ermittelt die URL des Hauptbildes aus einer Liste von Bildern.

    Das erste Bild mit gültiger, sicherer URL ist das Hauptbild
    (Reihenfolge in ``Hofladen.bilder`` bestimmt die Priorität). Gibt
    ``None`` zurück, wenn keine gültigen Bilder vorhanden sind.

    Args:
        bilder: Tupel von Bild-Objekten

    Returns:
        URL des Hauptbildes oder None.
    """
    if not bilder:
        return None

    for bild in bilder:
        if is_valid_image_url(bild.url, hochgeladen=bild.hochgeladen):
            return bild.url

    return None


def get_additional_images(bilder: tuple[Bild, ...]) -> list[dict[str, str | None]]:
    """Alle sicheren Bilder ausser dem Hauptbild, als einfache Attributliste.

    Home Assistant kennt keine native Mehrbild-/Galerie-Darstellung pro
    Entity; diese Liste wird daher als ``extra_state_attributes`` am
    Hauptbild-Entity bereitgestellt (siehe ``image.py``), nicht als
    eigene Entities. Unsichere Bilder werden konsequent ausgeschlossen,
    genau wie beim Hauptbild.

    Args:
        bilder: Tupel von Bild-Objekten

    Returns:
        Liste von ``{"url": ..., "beschreibung": ...}``, ohne das
        Hauptbild. Leer, wenn keine weiteren sicheren Bilder existieren.
    """
    hauptbild_url = get_main_image_url(bilder)
    weitere: list[dict[str, str | None]] = []
    hauptbild_bereits_uebersprungen = False

    for bild in bilder:
        if not is_valid_image_url(bild.url, hochgeladen=bild.hochgeladen):
            continue
        if not hauptbild_bereits_uebersprungen and bild.url == hauptbild_url:
            hauptbild_bereits_uebersprungen = True
            continue
        weitere.append({"url": bild.url, "beschreibung": bild.beschreibung})

    return weitere
