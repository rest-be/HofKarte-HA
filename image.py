"""Image Entity für das Hauptbild eines Hofladens.

Nutzt Home Assistants natives ``image``-Entity-Platform
(Architekturentscheid): Nur eine echte Image-Entity wird von
Home-Assistant-Dashboards automatisch als Bild dargestellt (Picture-Card,
Bildvorschau in der Entity-Liste, ``entity_picture``) – ein beliebiges
Attribut mit einer URL würde das nicht tun.

URL-Validierung und Hauptbild-Ermittlung erfolgen ausschliesslich in
``images.py``; dieses Modul enthält selbst keine Sicherheitsprüfungen.

Home Assistants ``ImageEntity`` kümmert sich über ihren eigenen,
bereits vorhandenen Proxy-Mechanismus (``/api/image_proxy/...``) um das
Abrufen und Zwischenspeichern der Bild-Bytes; es wird bewusst keine
eigene Fetch-/Caching-Pipeline implementiert (Grundsatz:
„keine unnötige lokale Bildkopie erzeugen“).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .entity import HofKarteEntity, async_setup_hofladen_entities
from .images import get_additional_images, get_main_image_url

# Alle Hofladen-Daten stammen aus einem gemeinsamen Coordinator-Abruf
# (siehe entity.py); das eigentliche Bild wird über Home Assistants
# eigenen Image-Proxy abgerufen, nicht über einen von uns parallel zu
# drosselnden Zugriff.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Hauptbild-Entity für alle aktuellen und künftigen Hofläden einrichten."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    def _factory(
        coord: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> HofKarteHauptbildImage:
        return HofKarteHauptbildImage(hass, coord, hofladen_id)

    entry.async_on_unload(
        async_setup_hofladen_entities(coordinator, async_add_entities, [_factory])
    )


class HofKarteHauptbildImage(HofKarteEntity, ImageEntity):
    """Zeigt das Hauptbild eines Hofladens.

    Das Hauptbild ist definiert als das erste Bild in
    ``Hofladen.bilder`` mit einer sicheren, ladbaren URL (siehe
    ``images.is_valid_image_url`` – lehnt u. a. ``file://``, eingebettete
    Daten-URLs, Zugangsdaten in der URL sowie URLs, die auf
    private/interne IP-Adressen zeigen, ab). Ein Bild mit unsicherer URL
    wird nie als Hauptbild verwendet.

    Existieren keine (sicheren) Bilder, liefert die Entity kein Bild
    (``image_url`` = ``None``) statt abzustürzen oder etwas zu erfinden;
    sie bleibt dabei regulär „available“, analog zum Verhalten der
    übrigen HofKarte-Entities bei fehlenden Daten (siehe ``entity.py``).
    """

    _attr_name = "Hauptbild"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HofKarteUpdateCoordinator,
        hofladen_id: str,
    ) -> None:
        HofKarteEntity.__init__(self, coordinator, hofladen_id)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_hauptbild"
        self._letzte_bild_url: str | None = None
        self._sync_bild_url()

    def _ermittelte_bild_url(self) -> str | None:
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return get_main_image_url(hofladen.bilder)

    def _sync_bild_url(self) -> None:
        """Internen Bild-Cache invalidieren, wenn sich die URL geändert hat.

        Home Assistants ``ImageEntity`` cached abgerufene Bild-Bytes
        intern (``_cached_image``) unbegrenzt, bis der Cache explizit
        geleert wird. Ohne diesen Abgleich würde eine geänderte
        Bild-URL (z. B. nach einer Bearbeitung über die
        Verwaltungsoberfläche) nicht erkannt und weiterhin das alte Bild
        ausgeliefert.
        """
        neue_url = self._ermittelte_bild_url()
        if neue_url != self._letzte_bild_url:
            self._letzte_bild_url = neue_url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow() if neue_url else None

    @property
    def image_url(self) -> str | None:
        """URL des Hauptbildes, oder ``None`` ohne (sicheres) Bild."""
        return self._letzte_bild_url

    @callback
    def _handle_coordinator_update(self) -> None:
        self._sync_bild_url()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Weitere (sichere) Bilder ausser dem Hauptbild.

        Home Assistant kennt keine native Mehrbild-/Galerie-Darstellung
        pro Entity. Weitere Bilder werden daher – analog zu den
        Sortiment-Attributen (siehe ``attributes.py``) – als kompakte
        Liste an dieser einen Entity bereitgestellt statt als eigene
        Entities.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return {"weitere_bilder": get_additional_images(hofladen.bilder)}
