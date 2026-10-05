"""Gemeinsame, rein syntaktische SSRF-Grundprüfung für frei eingegebene URLs.

Dieses Modul bündelt die Sicherheitsprüfung, die ursprünglich ausschliesslich
in ``images.py`` für Hofladen-Bild-URLs existierte (siehe dessen Moduldoc für
die ausführliche Begründung) und die mit Issue #8 ("Informationen aus
Homepage") ein zweites Mal benötigt wird: Für die dort neu eingeführte,
serverseitige Website-Abfrage (siehe ``webseite_info.py``) gelten dieselben
Grundregeln (nur http/https, keine Zugangsdaten, kein "localhost" und keine
privaten/internen IP-Literale) – deshalb hier zentral statt zweimal
dupliziert.

## Bewusste Grenze: rein syntaktische Prüfung, keine DNS-Auflösung

Wie in ``images.py`` beschrieben, prüft dieses Modul ausschliesslich die
URL-Syntax – es findet **keine DNS-Auflösung** statt. Ein Domainname wird
akzeptiert, ohne zu prüfen, wohin er tatsächlich auflöst; ein
DNS-Rebinding-Angriff (Domainname löst zum Zeitpunkt des eigentlichen
Requests auf eine private IP auf) wird durch diese Prüfung **nicht**
abgedeckt. IP-Literale und der Hostname "localhost" werden aber zuverlässig
abgelehnt.

``webseite_info.py`` behandelt diese Grenze bewusst genauso wie
``images.py`` es für Bild-URLs tut (siehe dessen Moduldoc-Abschnitt zur
DNS-Auflösung als blockierendem Aufruf) – zusätzlich zur hier geprüften
URL-Syntax begrenzt ``webseite_info.py`` aber auch Antwortgrösse,
Content-Type und Zeitüberschreitung des eigentlichen HTTP-Abrufs, da es
(anders als ``images.py``) den Antwortinhalt selbst verarbeitet.

## Herkunft eigener Uploads (Befund F1, Code Review 2026.9.2)

``Bild.hochgeladen`` befreit eine Bild-URL von der private-IP-Prüfung (siehe
``images.py``). Dieses Flag darf daher **nie** aus Client- oder Importdaten
übernommen werden: Ein manipulierter Datensatz
(``{"url": "http://192.168.1.20/relay/0?turn=on", "hochgeladen": true}``)
würde Home Assistant sonst zu einem Abruf beliebiger interner Ziele
(SSRF) bewegen. Stattdessen wird es serverseitig **abgeleitet**:
``ist_eigene_upload_url`` ist nur dann wahr, wenn die URL exakt dem Muster
des eigenen Uploads (Home Assistants ``image_upload``:
``/api/image/serve/<32 Hex-Zeichen>/<original|BxH>``) entspricht **und**
ihr Origin (Schema, Host, Port) zu dieser Home-Assistant-Instanz gehört.
Die Origin-Menge ermittelt ``instanz_origin.py`` (hass-abhängig); die
Muster-/Origin-Prüfung selbst ist rein und ohne Home Assistant testbar.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from urllib.parse import urlparse

UNSICHERE_HOSTNAMEN = frozenset({"localhost"})


def ist_unsicheres_ip_literal(hostname: str) -> bool:
    """Ob ein Hostname ein IP-Literal ist, das auf ein privates/internes
    Ziel zeigt (Loopback, privates Netz, Link-Local, reserviert,
    Multicast). Reine String-/Literal-Prüfung, **keine DNS-Auflösung**:
    Ist ``hostname`` kein IP-Literal (sondern ein Domainname), liefert
    diese Funktion ``False`` – die Domain wird dann nicht weiter geprüft
    (siehe Moduldoc, Abschnitt „Bewusste Grenze“).
    """
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False  # kein IP-Literal, sondern ein Domainname.
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def ist_sichere_externe_url(url: str | None) -> bool:
    """Prüft, ob eine frei eingegebene, nicht vertrauenswürdige URL den
    grundlegenden syntaktischen Sicherheitsanforderungen genügt.

    Akzeptiert nur http/https, lehnt eingebettete Zugangsdaten,
    den Hostnamen "localhost" sowie private/interne IP-Literale ab (siehe
    ``ist_unsicheres_ip_literal`` und die Moduldoc zur bewussten Grenze
    dieser rein syntaktischen Prüfung). Kennt – anders als
    ``images.is_valid_image_url`` mit ``hochgeladen=True`` – keine
    Herkunfts-Ausnahme: Diese Funktion ist ausschliesslich für frei
    eingegebene, potenziell nicht vertrauenswürdige URLs gedacht.

    Args:
        url: Die zu prüfende URL (oder ``None``).

    Returns:
        ``True``, wenn die URL den syntaktischen Sicherheitsprüfungen
        genügt.
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

    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in UNSICHERE_HOSTNAMEN:
        return False
    if ist_unsicheres_ip_literal(hostname):
        return False

    return True


# Pfad eines über Home Assistants ``image_upload`` erzeugten Bildes: die ID ist
# eine UUID4 in Hex-Schreibweise (32 Zeichen), gefolgt von ``original`` oder
# einer Grössenangabe (``<Breite>x<Höhe>``). Bewusst exakt (``fullmatch``), ohne
# Query/Fragment: Alles andere ist kein von HofKarte erzeugter Upload.
_UPLOAD_PFAD_MUSTER = re.compile(r"/api/image/serve/[0-9a-f]{32}/(?:original|\d{1,4}x\d{1,4})")

_STANDARD_PORTS = {"http": 80, "https": 443}


def normalisiere_origin(url: str | None) -> str | None:
    """Origin (``schema://host[:port]``) einer http(s)-URL normalisieren.

    Schema und Host werden kleingeschrieben, Standardports (80/443) entfallen.
    Liefert ``None`` bei ungültigen URLs, anderen Schemata, fehlendem Host
    oder eingebetteten Zugangsdaten (Fail-Fast: im Zweifel keine Origin).
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname
    if not hostname:
        return None
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is None or port == _STANDARD_PORTS[parsed.scheme]:
        return f"{parsed.scheme}://{host}"
    return f"{parsed.scheme}://{host}:{port}"


def ist_eigene_upload_url(url: str | None, eigene_origins: Iterable[str]) -> bool:
    """Ob ``url`` ein von dieser Home-Assistant-Instanz erzeugter Upload ist.

    Wahr nur, wenn (1) der Pfad exakt dem Upload-Muster entspricht (keine
    Query, kein Fragment, keine Parameter) und (2) die normalisierte Origin
    in ``eigene_origins`` enthalten ist (siehe ``instanz_origin.py``). Ohne
    bekannte Origins ist die Antwort stets ``False`` (fail-closed).

    Relative URLs gelten bewusst **nicht** als eigener Upload: Home
    Assistants Bild-Abruf (``ImageEntity``) benötigt eine absolute
    http(s)-URL, und das Panel speichert stets die absolute URL
    (``window.location.origin`` + Pfad).
    """
    if not url or not isinstance(url, str):
        return False
    origins = {o for o in (normalisiere_origin(x) for x in eigene_origins) if o}
    if not origins:
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.query or parsed.fragment or parsed.params:
        return False
    if not _UPLOAD_PFAD_MUSTER.fullmatch(parsed.path):
        return False
    return normalisiere_origin(url) in origins
