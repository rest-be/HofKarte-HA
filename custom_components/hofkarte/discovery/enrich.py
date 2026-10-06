"""Anreicherung eines Hofladen-Kandidaten (deterministisch, ohne KI).

Schritte (je Schritt ein Fortschrittsereignis):

1. ``osm``     - die übergebenen OSM-Angaben des Kandidaten.
2. ``website`` - Website abrufen (robots.txt, max. ``MAX_SEITEN`` Seiten).
3. ``fertig``  - Vorschlag mit Herkunft je Feld.

Ein Fehler bei der Website bricht nichts ab: das Ergebnis enthält dann
die OSM-Angaben und im Ereignis ``website`` den Status
(``robots_gesperrt``, ``nicht_erreichbar``, ...).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import website as web
from .overpass import Kandidat
from .provenance import Vorschlag, baue_vorschlag

Fortschritt = Callable[[dict[str, Any]], Awaitable[None] | None]


async def _melde(fortschritt: Fortschritt | None, ereignis: dict[str, Any]) -> None:
    if fortschritt is None:
        return
    r = fortschritt(ereignis)
    if r is not None:
        await r


async def async_anreichern(
    hass: Any,
    kandidat: Kandidat | None,
    website_url: str | None = None,
    fortschritt: Fortschritt | None = None,
) -> Vorschlag:
    """Reichert ``kandidat`` an. ``website_url`` ersetzt die Website des
    Kandidaten (z. B. vom Benutzer eingegeben)."""
    await _melde(fortschritt, {"phase": "osm", "status": "ok" if kandidat else "uebersprungen"})

    url = (website_url or "").strip() or (kandidat.website if kandidat else None)
    ergebnis: web.WebsiteErgebnis | None = None
    if url:
        ergebnis = await web.async_hole_website(hass, url)
        await _melde(
            fortschritt,
            {
                "phase": "website",
                "status": ergebnis.status,
                "url": ergebnis.start_url,
                "seiten": len(ergebnis.seiten),
            },
        )
    else:
        await _melde(fortschritt, {"phase": "website", "status": "uebersprungen"})

    vorschlag = baue_vorschlag(kandidat, ergebnis, angegebene_website=url)
    await _melde(fortschritt, {"phase": "fertig", "vorschlag": vorschlag.als_dict()})
    return vorschlag
