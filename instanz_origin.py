"""Ermittlung der Origins dieser Home-Assistant-Instanz (Befund F1).

Dünne, hass-abhängige Anbindung für ``url_sicherheit.ist_eigene_upload_url``:
Liefert die Menge der Origins (``schema://host[:port]``), unter denen diese
Instanz erreichbar ist - interne, externe und Nabu-Casa-Cloud-URL sowie die
automatisch erkannte lokale Adresse (``allow_ip``). Die eigentliche
Muster-/Origin-Prüfung ist hass-frei in ``url_sicherheit.py`` umgesetzt.

Bekannte Grenze: Wird Home Assistant über einen Hostnamen aufgerufen, der
weder als interne noch als externe URL konfiguriert ist (z. B.
``http://homeassistant.local:8123`` ohne entsprechende Einstellung unter
*Einstellungen → System → Netzwerk*), gilt ein dort hochgeladenes Bild nicht
mehr als eigener Upload und wird wie eine frei eingegebene externe URL
geprüft (also bei privater IP abgelehnt). Das ist die sichere Seite
("lieber nichts als falsch"); abhilfe: interne/externe URL konfigurieren.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .url_sicherheit import normalisiere_origin

# Je Variante genau eine Quelle aktivieren, damit ``get_url`` nicht nur die
# bevorzugte, sondern jede konfigurierte URL liefert.
_VARIANTEN: tuple[dict[str, bool], ...] = (
    {"allow_internal": True, "allow_external": False, "allow_cloud": False},
    {"allow_internal": False, "allow_external": True, "allow_cloud": False},
    {"allow_internal": False, "allow_external": False, "allow_cloud": True},
)


def ermittle_eigene_origins(hass: HomeAssistant) -> frozenset[str]:
    """Alle Origins dieser Home-Assistant-Instanz (leer, falls unbekannt)."""
    origins: set[str] = set()
    for variante in _VARIANTEN:
        try:
            url = get_url(
                hass,
                allow_ip=True,
                require_ssl=False,
                require_standard_port=False,
                **variante,
            )
        except NoURLAvailableError:
            continue
        origin = normalisiere_origin(url)
        if origin:
            origins.add(origin)
    return frozenset(origins)
