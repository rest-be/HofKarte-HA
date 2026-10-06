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

## Härtung (Befund F4, Code Review 2026.9.2)

Die Prüfung normalisiert den Hostnamen (Kleinschreibung, abschliessender
Punkt, IDNA), deutet auch unübliche IPv4-Schreibweisen (``127.1``, ``0``,
``2130706433``, ``0x7f000001``, ``017700000001``) und IPv4-gemappte
IPv6-Adressen wie ``inet_aton`` und verlangt für IP-Adressen die
Positivprüfung ``is_global`` (schliesst z. B. CGNAT ``100.64.0.0/10`` ein).
Interne Hostnamen (``localhost``, ``*.localhost``, ``*.local``,
``*.internal``, ``*.lan``, ``*.home.arpa``, Einzel-Label-Hosts) werden
abgelehnt. Die DNS-Auflösung bleibt hier bewusst aus (synchrone
Aufrufer); der Website-Abruf (``webseite_info.py``) ergänzt eine
asynchrone Auflösungsprüfung mit Bindung an die geprüfte IP
(``pruefe_aufloesung``/``ist_oeffentliche_ip``).

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

# Befund F4 (Code Review 2026.9.2): Hostnamen-Endungen, die auf interne
# Ziele zeigen (RFC 6761/8375 sowie gängige Heimnetz-Konventionen). Ein
# Hostname ohne Punkt (Einzel-Label wie ``homeassistant``) wird ebenfalls
# abgelehnt: er löst nur über die lokale Suchdomäne/mDNS auf.
UNSICHERE_HOSTNAME_ENDUNGEN = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home.arpa",
    ".localdomain",
)


def _parse_ipv4_teil(teil: str) -> int | None:
    """Ein Segment einer IPv4-Schreibweise im Sinne von ``inet_aton``
    (dezimal, oktal mit führender 0, hexadezimal mit ``0x``)."""
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", teil):
        return int(teil, 16)
    if re.fullmatch(r"0[0-7]*", teil):
        return int(teil, 8) if len(teil) > 1 else 0
    if re.fullmatch(r"[1-9][0-9]*", teil):
        return int(teil, 10)
    return None


def _parse_numerischen_host(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Host als IP-Adresse deuten - **mit** ``inet_aton``-Semantik.

    Befund F4: HTTP-Clients/Betriebssysteme akzeptieren auch verkürzte oder
    anders kodierte IPv4-Adressen (``127.1``, ``0``, ``2130706433``,
    ``0x7f000001``, ``017700000001``); ``ipaddress.ip_address`` kennt nur die
    vierteilige Dezimalform und würde sie als „Domainname“ durchwinken.
    Plattformunabhängig selbst umgesetzt (kein ``socket.inet_aton``, das je
    nach libc abweicht). ``None``, wenn ``host`` keine IP-Schreibweise ist.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    teile = host.split(".")
    if not 1 <= len(teile) <= 4:
        return None
    werte = [_parse_ipv4_teil(t) for t in teile]
    if any(w is None for w in werte):
        return None
    *vorne, letzter = werte  # type: ignore[misc]
    if any(w > 255 for w in vorne):  # type: ignore[operator]
        return None
    if letzter >= 256 ** (5 - len(teile)):  # type: ignore[operator]
        return None
    wert = 0
    for w in vorne:
        wert = (wert << 8) | w  # type: ignore[operator]
    wert = (wert << (8 * (5 - len(teile)))) | letzter  # type: ignore[operator]
    return ipaddress.IPv4Address(wert)


def _eingebettetes_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """IPv4-Adresse, die in einer IPv6-Adresse steckt (IPv4-gemappt,
    NAT64 ``64:ff9b::/96``, 6to4 ``2002::/16``), sonst ``None``."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in ipaddress.IPv6Network("64:ff9b::/96"):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    return None


def ist_oeffentliche_ip(adresse: ipaddress.IPv4Address | ipaddress.IPv6Address | str) -> bool:
    """Positivprüfung: Ob eine IP-Adresse öffentlich (global routbar) ist.

    Befund F4: Statt einer Negativliste (``is_private or is_loopback or …``,
    die z. B. CGNAT ``100.64.0.0/10`` oder ``0.0.0.0/8`` übersieht) wird
    ``is_global`` verlangt; zusätzlich werden Multicast/Reserviert/
    Link-Local/unspezifiziert/Loopback ausdrücklich ausgeschlossen, da
    ``is_global`` je nach Python-Version z. B. Multicast-Adressen zulässt.
    Eingebettete IPv4-Adressen (IPv4-gemappt, NAT64, 6to4) werden
    ausgepackt und selbst geprüft.
    """
    if isinstance(adresse, str):
        try:
            adresse = ipaddress.ip_address(adresse)
        except ValueError:
            return False
    if isinstance(adresse, ipaddress.IPv6Address):
        eingebettet = _eingebettetes_ipv4(adresse)
        if eingebettet is not None:
            return ist_oeffentliche_ip(eingebettet)
    return bool(
        adresse.is_global
        and not adresse.is_multicast
        and not adresse.is_reserved
        and not adresse.is_loopback
        and not adresse.is_link_local
        and not adresse.is_unspecified
    )


def pruefe_aufloesung(adressen: Iterable[str]) -> bool:
    """Ob **alle** aufgelösten Adressen öffentlich sind (und mindestens eine
    vorhanden ist). Gemischte Antworten (öffentlich + privat) werden
    abgelehnt - ein Angreifer könnte sonst auf die private Adresse
    ausweichen."""
    adressen = list(adressen)
    return bool(adressen) and all(ist_oeffentliche_ip(a) for a in adressen)


def normalisiere_hostname(hostname: str | None) -> str | None:
    """Hostnamen normalisieren: Kleinschreibung, höchstens ein
    abschliessender Punkt entfernt, IDNA (Punycode). ``None`` bei leerem
    oder nicht kodierbarem Hostnamen (Fail-Fast: im Zweifel ablehnen)."""
    if not hostname:
        return None
    host = hostname.strip().lower()
    if host.endswith("."):
        host = host[:-1]
    if not host or host.endswith(".") or ".." in host:
        return None
    if ":" in host:  # IPv6-Literal bleibt unverändert
        return host
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def ist_unsicheres_ip_literal(hostname: str) -> bool:
    """Ob ein Hostname ein IP-Literal ist, das nicht öffentlich routbar ist
    (Loopback, privates Netz, CGNAT, Link-Local, reserviert, Multicast, …),
    **einschliesslich** der unüblichen IPv4-Schreibweisen (``127.1``, ``0``,
    ``2130706433``, ``0x7f000001``, ``017700000001``) und IPv4-gemappter
    IPv6-Adressen. Reine String-/Literal-Prüfung, **keine DNS-Auflösung**:
    Ist ``hostname`` keine IP-Schreibweise (sondern ein Domainname), liefert
    diese Funktion ``False`` (siehe Moduldoc, Abschnitt „Bewusste Grenze“).
    """
    ip = _parse_numerischen_host(hostname)
    if ip is None:
        return False
    return not ist_oeffentliche_ip(ip)


def ist_sichere_externe_url(url: str | None) -> bool:
    """Prüft, ob eine frei eingegebene, nicht vertrauenswürdige URL den
    grundlegenden syntaktischen Sicherheitsanforderungen genügt.

    Akzeptiert nur http/https, lehnt eingebettete Zugangsdaten, interne
    Hostnamen (``localhost``, ``*.localhost``, ``*.local``, ``*.internal``,
    ``*.lan``, ``*.home.arpa``, Einzel-Label-Hosts wie ``homeassistant``),
    jede IP-Schreibweise, die nicht öffentlich routbar ist (siehe
    ``ist_unsicheres_ip_literal``), sowie Hosts mit rein numerischer
    Endung ab. Der Hostname wird vorher normalisiert (Kleinschreibung,
    abschliessender Punkt, IDNA, Befund F4). Kennt – anders als
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
        parsed.port  # noqa: B018 - löst ValueError bei ungültigem Port aus
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.username or parsed.password:
        return False

    hostname = normalisiere_hostname(parsed.hostname)
    if not hostname:
        return False
    if _parse_numerischen_host(hostname) is not None:
        return not ist_unsicheres_ip_literal(hostname)
    if hostname in UNSICHERE_HOSTNAMEN:
        return False
    if hostname.endswith(UNSICHERE_HOSTNAME_ENDUNGEN):
        return False
    if "." not in hostname:
        return False  # Einzel-Label-Host (z. B. "homeassistant")
    letztes_label = hostname.rsplit(".", 1)[1]
    if letztes_label.isdigit() or letztes_label.startswith("0x"):
        return False  # numerische "TLD": mehrdeutige IP-Schreibweise

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
