"""DataUpdateCoordinator für HofKarte.

Ruft periodisch Rohdaten über einen :class:`HofladenDataProvider` ab,
validiert sie über ``parsing.parse_hofladen`` und stellt sie als Mapping
``Hofladen.id -> Hofladen`` für die gesamte Integration bereit.

Ein gemeinsamer Coordinator verhindert Mehrfachabfragen durch einzelne
Entities (siehe Globale Konventionen): Alle künftigen Entities lesen
ausschliesslich ``coordinator.data``, keine eigenen Abrufe.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DEFAULT_FETCH_TIMEOUT_SECONDS, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .data_provider import (
    HofladenDataProvider,
    HofladenNotFoundError,
    MutableHofladenDataProvider,
)
from .models import Hofladen
from .parsing import HofladenValidationError, parse_hofladen

_LOGGER = logging.getLogger(__name__)


class HofladenVersionConflictError(Exception):
    """Die mitgeschickte erwartete Version stimmt nicht mehr.

    Wird von :meth:`HofKarteUpdateCoordinator.async_save_hofladen` geworfen,
    wenn ein Aufrufer beim Aktualisieren eines bestehenden Hofladens eine
    ``version`` mitschickt, die nicht (mehr) mit der aktuell gespeicherten
    Version übereinstimmt - typischerweise, weil ein anderes Gerät die
    Änderung zwischenzeitlich bereits synchronisiert hat (z. B. zwei
    Haushaltsmitglieder, die denselben Hofladen offline bearbeitet haben).

    Trägt den aktuellen, serverseitigen Stand (``aktueller_hofladen``), damit
    Aufrufer (siehe ``management.ws_save``) eine Konflikt-Ansicht mit beiden
    Versionen anzeigen können, statt die Änderung stillschweigend zu
    verwerfen oder zu überschreiben.
    """

    def __init__(self, aktueller_hofladen: Hofladen) -> None:
        super().__init__(
            f"Versionskonflikt bei Hofladen '{aktueller_hofladen.id}': "
            f"aktuelle Version ist {aktueller_hofladen.version}."
        )
        self.aktueller_hofladen = aktueller_hofladen


class HofKarteUpdateCoordinator(DataUpdateCoordinator[dict[str, Hofladen]]):
    """Koordiniert den Abruf und die Validierung der Hofladen-Daten."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: HofladenDataProvider,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
        fetch_timeout_seconds: float = DEFAULT_FETCH_TIMEOUT_SECONDS,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Coordinator erzeugen.

        ``update_interval`` und ``fetch_timeout_seconds`` sind bewusst
        Konstruktorparameter (statt fest verdrahteter Werte) und damit
        konfigurierbar und testbar. Eine benutzerseitige Einstellung über
        einen Options Flow ist aktuell nicht umgesetzt, kann aber ohne
        Änderung an dieser Klasse ergänzt werden.

        ``config_entry`` wird bewusst explizit durchgereicht: Ohne
        explizite Angabe ermittelt
        ``DataUpdateCoordinator`` die Config Entry implizit über einen
        Kontextvariablen-Fallback (``config_entries.current_entry``) –
        ein von Home Assistant selbst als veraltet markiertes Verhalten,
        das laut Warnhinweis im Home-Assistant-Kern ab Version 2025.11
        nicht mehr unterstützt wird. In Tests ohne echte Config Entry
        bleibt der Parameter ``None`` (Standardwert), was weiterhin
        funktioniert.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self._provider = provider
        self._fetch_timeout_seconds = fetch_timeout_seconds
        self._letzte_erfolgreiche_aktualisierung: datetime | None = None

    @property
    def letzte_erfolgreiche_aktualisierung(self) -> datetime | None:
        """Zeitpunkt (UTC) des letzten erfolgreichen Datenabrufs.

        ``None``, solange noch kein Abruf erfolgreich war. Wird u. a. von
        ``diagnostics.py`` verwendet; die Basisklasse
        ``DataUpdateCoordinator`` verfolgt diesen Zeitpunkt in dieser
        Home-Assistant-Version nicht selbst (nur ``last_update_success``
        als reinen Erfolgs-/Fehlschlag-Status).
        """
        return self._letzte_erfolgreiche_aktualisierung

    @property
    def provider_type_name(self) -> str:
        """Klassenname des aktuell verwendeten Data Providers.

        Für Diagnostics (``diagnostics.py``) – bewusst als öffentliche
        Property statt direktem Zugriff auf ``_provider`` von aussen,
        um die Kapselung konsistent einzuhalten.
        """
        return type(self._provider).__name__

    @property
    def provider_unterstuetzt_schreibzugriffe(self) -> bool:
        """Ob der aktuell verwendete Data Provider Schreibzugriffe unterstützt."""
        return isinstance(self._provider, MutableHofladenDataProvider)

    async def _async_update_data(self) -> dict[str, Hofladen]:
        """Rohdaten abrufen, validieren und als Hofladen-Mapping liefern.

        Netzwerk-/Datenquellenfehler und Zeitüberschreitungen werden in
        ``UpdateFailed`` übersetzt, damit sie Home Assistant nicht
        blockieren und über den Coordinator-Lifecycle (Availability,
        Retry) korrekt behandelt werden. Einzelne ungültige Datensätze
        führen nicht zum Abbruch des gesamten Abrufs, sondern werden
        übersprungen und geloggt.
        """
        try:
            async with asyncio.timeout(self._fetch_timeout_seconds):
                raw_hoflaeden = await self._provider.async_fetch_raw_hoflaeden()
        except TimeoutError as err:
            raise UpdateFailed(
                "Zeitüberschreitung beim Abruf der Hofladen-Daten."
            ) from err
        except Exception as err:  # noqa: BLE001 - unbekannte Provider-Fehler
            # Der Provider kann beliebige Fehler werfen (Netzwerk,
            # Dateisystem, etc.). Diese dürfen Home Assistant nicht
            # blockieren und werden daher in UpdateFailed übersetzt.
            raise UpdateFailed(
                f"Fehler beim Abruf der Hofladen-Daten: {err}"
            ) from err

        hoflaeden: dict[str, Hofladen] = {}
        for index, raw in enumerate(raw_hoflaeden):
            try:
                hofladen = parse_hofladen(raw)
            except HofladenValidationError as err:
                _LOGGER.warning(
                    "Ungültiger Hofladen-Datensatz #%s wird übersprungen: %s",
                    index,
                    err,
                )
                continue
            hoflaeden[hofladen.id] = hofladen

        self._letzte_erfolgreiche_aktualisierung = dt_util.utcnow()
        return hoflaeden

    async def async_add_hofladen(self, raw_hofladen: dict[str, Any]) -> Hofladen:
        """Einen neuen Hofladen hinzufügen und die Daten aktualisieren.

        Die Rohdaten werden zunächst über ``parsing.parse_hofladen``
        validiert (Fail-Fast: bei ungültigen Daten wird nichts geschrieben)
        und erst danach an den Provider übergeben. Anschliessend wird ein
        regulärer Refresh angestossen, damit ``coordinator.data`` sowie die
        über den Coordinator-Listener angebundene Device Registry (siehe
        ``device.py``) konsistent aktualisiert werden.

        Wirft :class:`~custom_components.hofkarte.parsing.HofladenValidationError`
        bei ungültigen Rohdaten, ``NotImplementedError``, falls der
        aktuell konfigurierte Provider keine Schreibzugriffe unterstützt
        (z. B. ein künftiger, rein lesender externer Dienst), und
        :class:`~custom_components.hofkarte.data_provider.DuplicateHofladenIdError`,
        falls die ``id`` bereits vergeben ist.
        """
        # Fail-Fast: fachliche Validierung vor jedem Schreibzugriff auf
        # die Datenquelle, damit dort nie ungültige Datensätze landen.
        hofladen = parse_hofladen(raw_hofladen)

        if not isinstance(self._provider, MutableHofladenDataProvider):
            raise NotImplementedError(
                "Der konfigurierte Data Provider unterstützt keine "
                "Schreibzugriffe (Hinzufügen neuer Hofläden)."
            )

        await self._provider.async_add_raw_hofladen(raw_hofladen)
        await self.async_refresh()

        _LOGGER.debug("Hofladen hinzugefügt: %s", hofladen.id)
        return hofladen

    async def async_update_hofladen_sortiment(
        self,
        hofladen_id: str,
        *,
        angebote: list[dict[str, Any]] | None = None,
        zahlungsarten: list[dict[str, Any]] | None = None,
    ) -> Hofladen:
        """Sortiment und Eigenschaften eines bestehenden Hofladens durch
        die Nutzerin/den Nutzer bearbeiten.

        Bewusst auf genau diese zwei Fachbereiche beschränkt (Angebote,
        Zahlungsarten) – andere Felder eines Hofladens (Name, Adresse,
        Öffnungszeiten, ...) werden über diese Funktion nicht verändert.
        „Angebote“ ersetzt seit der Zusammenlegung von Kategorien und
        Produkten (siehe CHANGELOG) die früheren, getrennten Parameter
        ``kategorien``/``produkte``. Die früheren Fachbereiche
        „Verkaufsarten“ und „Merkmale“ wurden ersatzlos entfernt (siehe
        CHANGELOG) – entsprechende Parameter existieren daher nicht mehr.

        Jeder Parameter, der nicht ``None`` ist, ersetzt die entsprechende
        Sammlung vollständig; ``None`` bedeutet „unverändert lassen“. Um
        eine Sammlung bewusst zu leeren, eine leere Liste ``[]``
        übergeben. Werden keine Parameter gesetzt, bleibt der Hofladen
        unverändert und wird unverändert zurückgegeben.

        Die Rohdaten des bestehenden Hofladens werden mit den Änderungen
        zusammengeführt und über ``parsing.parse_hofladen`` validiert,
        bevor irgendetwas geschrieben wird (Fail-Fast, analog zu
        ``async_add_hofladen``). Anschliessend wird ein regulärer Refresh
        angestossen, damit ``coordinator.data`` sowie abhängige Entities
        (z. B. die Sortiment-Attribute am Binary Sensor „Geöffnet“, siehe
        ``attributes.py``) konsistent aktualisiert werden.

        Wirft :class:`~custom_components.hofkarte.data_provider.HofladenNotFoundError`,
        falls keine ``id`` mit diesem Wert existiert,
        :class:`~custom_components.hofkarte.parsing.HofladenValidationError`
        bei ungültigen Werten, und ``NotImplementedError``, falls der
        aktuell konfigurierte Provider keine Schreibzugriffe unterstützt.
        """
        if not isinstance(self._provider, MutableHofladenDataProvider):
            raise NotImplementedError(
                "Der konfigurierte Data Provider unterstützt keine "
                "Schreibzugriffe (Bearbeiten von Hofläden)."
            )

        aktuelle_rohdaten = await self._provider.async_fetch_raw_hoflaeden()
        aktueller_raw = next(
            (raw for raw in aktuelle_rohdaten if raw.get("id") == hofladen_id),
            None,
        )
        if aktueller_raw is None:
            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )

        updates: dict[str, Any] = {}
        if angebote is not None:
            updates["angebote"] = angebote
        if zahlungsarten is not None:
            updates["zahlungsarten"] = zahlungsarten

        if not updates:
            # Nichts zu ändern: aktuellen, bereits validen Stand liefern.
            return parse_hofladen(aktueller_raw)

        # Fail-Fast: den vollständigen, zusammengeführten Datensatz
        # validieren, bevor der Provider überhaupt geschrieben wird.
        zusammengefuehrter_raw = {**aktueller_raw, **updates}
        validierter_hofladen = parse_hofladen(zusammengefuehrter_raw)

        await self._provider.async_update_raw_hofladen(hofladen_id, updates)
        await self.async_refresh()

        _LOGGER.debug(
            "Sortiment aktualisiert für Hofladen %s: %s", hofladen_id, list(updates)
        )
        return validierter_hofladen

    async def async_save_hofladen(self, raw_hofladen: dict[str, Any]) -> Hofladen:
        """Einen Hofladen mit beliebigen Feldern anlegen oder aktualisieren.

        Im Unterschied zu ``async_update_hofladen_sortiment`` (auf die
        zwei Fachbereiche Angebote und Zahlungsarten beschränkt) erlaubt
        diese Funktion das Setzen beliebiger Hofladen-Felder (Name, Adresse,
        Koordinaten, Öffnungszeiten, Bilder, ...). Wird von der
        grafischen Verwaltungsoberfläche sowie der HofKarte-PWA verwendet
        (siehe ``management.py``), die stets den vollständigen, vom
        Formular bzw. Editor gelieferten Datensatz übergeben.

        Existiert die ``id`` bereits, werden die vorhandenen Felder mit
        ``raw_hofladen`` zusammengeführt; existiert sie nicht, wird ein
        neuer Hofladen angelegt. Validiert (Fail-Fast) über
        ``parsing.parse_hofladen`` und stösst wie die übrigen
        Schreibfunktionen einen Refresh an.

        **Optimistische Versionierung (Konflikterkennung):** Beim
        Aktualisieren eines bestehenden Hofladens wird eine in
        ``raw_hofladen`` enthaltene ``version`` als die zuletzt vom
        Aufrufer gesehene Version interpretiert. Stimmt sie nicht mit der
        aktuell gespeicherten Version überein, wird die Änderung
        **nicht** geschrieben, sondern
        :class:`HofladenVersionConflictError` geworfen (siehe dort) - das
        schützt vor stillschweigendem Verlust einer zwischenzeitlichen
        Änderung eines anderen Geräts (z. B. Offline-Sync, siehe
        Vorgehensplan Phase 8b). Fehlt ``version`` in ``raw_hofladen``
        (z. B. bei älteren Aufrufern oder dem Import), wird **kein**
        Konflikt geprüft - die Änderung wird wie bisher ohne Prüfung
        übernommen (Abwärtskompatibilität). Die tatsächlich gespeicherte
        ``version`` wird in jedem Fall serverseitig bestimmt (bei Neuanlage
        ``1``, sonst ``aktuelle Version + 1``) - ein mitgeschickter Wert
        wird dafür nicht übernommen, ausser als Vergleichswert für die
        Konfliktprüfung.

        Wirft ``NotImplementedError`` bei einem nicht schreibfähigen
        Provider, :class:`~custom_components.hofkarte.parsing.HofladenValidationError`
        bei ungültigen Daten und :class:`HofladenVersionConflictError` bei
        einem Versionskonflikt.
        """
        if not isinstance(self._provider, MutableHofladenDataProvider):
            raise NotImplementedError(
                "Der konfigurierte Data Provider unterstützt keine "
                "Schreibzugriffe (Anlegen/Bearbeiten von Hofläden)."
            )

        hofladen_id = raw_hofladen.get("id")
        bestehender_hofladen = (
            self.data.get(hofladen_id) if self.data and hofladen_id else None
        )

        endgueltiger_raw = dict(raw_hofladen)
        if bestehender_hofladen is not None:
            erwartete_version = raw_hofladen.get("version")
            if (
                erwartete_version is not None
                and int(erwartete_version) != bestehender_hofladen.version
            ):
                raise HofladenVersionConflictError(bestehender_hofladen)
            endgueltiger_raw["version"] = bestehender_hofladen.version + 1
        else:
            endgueltiger_raw["version"] = 1

        # Fail-Fast: vor jedem Schreibzugriff vollständig validieren.
        validierter_hofladen = parse_hofladen(endgueltiger_raw)

        if bestehender_hofladen is not None:
            await self._provider.async_update_raw_hofladen(
                validierter_hofladen.id, endgueltiger_raw
            )
            _LOGGER.debug(
                "Hofladen aktualisiert: %s (Version %s)",
                validierter_hofladen.id,
                validierter_hofladen.version,
            )
        else:
            await self._provider.async_add_raw_hofladen(endgueltiger_raw)
            _LOGGER.debug("Hofladen angelegt: %s", validierter_hofladen.id)

        await self.async_refresh()
        return validierter_hofladen

    async def async_delete_hofladen(self, hofladen_id: str) -> None:
        """Einen Hofladen dauerhaft aus der Datenquelle entfernen.

        Stösst nach dem Löschen einen regulären Refresh an; dadurch wird
        über den bestehenden Coordinator-Listener (siehe ``device.py``)
        automatisch auch das zugehörige Device entfernt.

        Wirft ``NotImplementedError`` bei einem nicht schreibfähigen
        Provider und :class:`~custom_components.hofkarte.data_provider.HofladenNotFoundError`,
        falls keine ``id`` mit diesem Wert existiert.
        """
        if not isinstance(self._provider, MutableHofladenDataProvider):
            raise NotImplementedError(
                "Der konfigurierte Data Provider unterstützt keine "
                "Schreibzugriffe (Löschen von Hofläden)."
            )

        if not self.data or hofladen_id not in self.data:
            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )

        await self._provider.async_delete_raw_hofladen(hofladen_id)
        await self.async_refresh()
        _LOGGER.debug("Hofladen gelöscht: %s", hofladen_id)
