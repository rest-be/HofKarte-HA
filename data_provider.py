"""Data Provider für Hofladen-Rohdaten.

Architekturentscheid (löst die zuvor offene Frage der Datenquelle, siehe
CHANGELOG): Home Assistant ist sowohl Laufzeitumgebung als auch
Verwaltungsoberfläche für HofKarte. Die vom Benutzer gepflegten Hofläden
werden in einem integrationsinternen, persistenten Store gehalten (Home
Assistants ``helpers.storage.Store``, siehe
:class:`StorageHofladenDataProvider`) – keine externe Datenbank, kein
externer Dienst. Der ``HofladenDataProvider`` kapselt diesen Store;
Coordinator und Entities greifen ausschliesslich über diese Abstraktion
darauf zu und kennen die konkrete Speicherform nicht.

Dieses Modul definiert dazu eine klar abgegrenzte Provider-Schnittstelle
(:class:`HofladenDataProvider`), deren produktive Implementierung
(:class:`StorageHofladenDataProvider`) sowie eine reine
Testdaten-Implementierung ohne Persistenz
(:class:`StaticTestDataProvider`) für die Testsuite.

``MutableHofladenDataProvider`` deckt sowohl das Hinzufügen neuer
Hofläden als auch das teilweise Aktualisieren bestehender Hofläden ab
(z. B. um die nutzereditierbaren Fachbereiche Angebote und
Zahlungsarten zu ändern, siehe CHANGELOG).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


class HofladenDataProvider(ABC):
    """Abstrakte Schnittstelle für den Abruf roher Hofladen-Daten.

    Implementierungen liefern eine Liste roher, noch nicht validierter
    Hofladen-Mappings, wie sie von ``parsing.parse_hofladen`` erwartet
    werden. Die Validierung selbst ist bewusst nicht Aufgabe des Providers.
    """

    @abstractmethod
    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Rohdaten aller bekannten Hofläden asynchron abrufen.

        Implementierungen müssen echte, nicht-blockierende Asynchronität
        verwenden (z. B. ``aiohttp`` oder Home-Assistant-Executor-Helper für
        Dateisystemzugriffe) und dürfen den Event Loop nicht blockieren.
        """


class MutableHofladenDataProvider(HofladenDataProvider):
    """Optionale Erweiterung für Provider, die auch Schreibzugriffe erlauben.

    Nicht jede künftige Datenquelle wird Schreibzugriffe unterstützen (z. B.
    ein rein lesender externer Dienst). Dieses zusätzliche Interface hält
    Schreiboperationen daher bewusst getrennt von der grundlegenden,
    nur-lesenden Provider-Schnittstelle.
    """

    @abstractmethod
    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen neuen, rohen Hofladen-Datensatz zur Datenquelle hinzufügen.

        Implementierungen müssen sicherstellen, dass ein bereits
        vorhandener Datensatz mit identischer ``id`` nicht stillschweigend
        überschrieben wird (siehe ``StaticTestDataProvider`` für ein
        Beispiel).
        """

    @abstractmethod
    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens aktualisieren.

        ``updates`` enthält nur die zu ändernden Felder; alle übrigen,
        nicht in ``updates`` enthaltenen Felder des bestehenden
        Datensatzes bleiben unverändert (teilweise Aktualisierung, kein
        vollständiger Ersatz). Wirft :class:`HofladenNotFoundError`, wenn
        keine ``id`` mit diesem Wert existiert.
        """

    @abstractmethod
    async def async_delete_raw_hofladen(self, hofladen_id: str) -> None:
        """Einen bestehenden Hofladen dauerhaft entfernen."""

    async def async_apply_changes(
        self,
        upserts: list[dict[str, Any]],
        loeschungen: list[str] | None = None,
    ) -> None:
        """Mehrere Änderungen in **einem** Schreibvorgang anwenden (Befund F5).

        ``upserts`` enthält vollständige oder teilweise Rohdatensätze mit
        ``id``: Existiert die ``id`` bereits, werden die übergebenen Felder
        in den bestehenden Datensatz gemischt (wie
        :meth:`async_update_raw_hofladen`), sonst wird ein neuer Datensatz
        angehängt. ``loeschungen`` nennt zu entfernende IDs; unbekannte IDs
        lösen :class:`HofladenNotFoundError` aus.

        Alle Änderungen gelten ganz oder gar nicht: Bei einem Fehler
        bleibt der bisherige Stand unverändert. Diese Standardimplementierung
        ruft die Einzeloperationen nacheinander auf (kein atomarer
        Sammelschreibvorgang); Provider mit eigener Persistenz überschreiben
        sie, um genau einmal zu speichern.
        """
        vorhandene_ids = {r.get("id") for r in await self.async_fetch_raw_hoflaeden()}
        for roh in upserts:
            if roh.get("id") in vorhandene_ids:
                await self.async_update_raw_hofladen(roh["id"], roh)
            else:
                await self.async_add_raw_hofladen(roh)
                vorhandene_ids.add(roh.get("id"))
        for hofladen_id in loeschungen or []:
            await self.async_delete_raw_hofladen(hofladen_id)


class DuplicateHofladenIdError(ValueError):
    """Es existiert bereits ein Hofladen mit der angegebenen ID."""


class HofladenNotFoundError(KeyError):
    """Es existiert kein Hofladen mit der angegebenen ID."""


# Home Assistant migriert die gespeicherte Struktur automatisch, falls
# diese Versionsnummer künftig erhöht wird (siehe Store-Dokumentation).
_STORAGE_VERSION = 1
_STORAGE_KEY = "hofkarte_hoflaeden"


def _wende_aenderungen_an(
    bestehend: list[dict[str, Any]],
    upserts: list[dict[str, Any]],
    loeschungen: list[str],
) -> list[dict[str, Any]]:
    """Änderungen auf einer Kopie anwenden (reine Funktion, Befund F5).

    Mit ``id``-Index statt wiederholter Listendurchläufe (O(n + m)).
    Wirft :class:`HofladenNotFoundError` für unbekannte Lösch-IDs; das
    Original wird nie verändert.
    """
    ergebnis = list(bestehend)
    position = {roh.get("id"): i for i, roh in enumerate(ergebnis)}
    for roh in upserts:
        hofladen_id = roh.get("id")
        if hofladen_id in position:
            i = position[hofladen_id]
            ergebnis[i] = {**ergebnis[i], **roh}
        else:
            position[hofladen_id] = len(ergebnis)
            ergebnis.append(dict(roh))
    zu_loeschen = set()
    for hofladen_id in loeschungen:
        if hofladen_id not in position:
            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )
        zu_loeschen.add(hofladen_id)
    if zu_loeschen:
        ergebnis = [r for r in ergebnis if r.get("id") not in zu_loeschen]
    return ergebnis


class StorageHofladenDataProvider(MutableHofladenDataProvider):
    """Produktiver, persistenter Hofladen-Datenspeicher.

    Kapselt Home Assistants ``helpers.storage.Store`` (JSON-Datei unter
    ``.storage/`` im Konfigurationsverzeichnis) gemäss Architekturentscheid:
    HofKarte verwaltet die vom Benutzer gepflegten Hofläden vollständig
    integrationsintern – keine externe Datenbank, kein externer Dienst,
    kein manuelles Bearbeiten der Datei nötig (Bearbeitung erfolgt
    ausschliesslich über ``async_add_raw_hofladen``/
    ``async_update_raw_hofladen``, die diese Klasse implementiert).

    Die geladenen Daten werden nach dem ersten Zugriff im Arbeitsspeicher
    gehalten (keine wiederholten Store-Lesezugriffe bei jedem
    Coordinator-Update) und bei jeder Schreiboperation sowohl im Speicher
    als auch im Store aktualisiert, sodass beide stets konsistent sind.
    Ein ``asyncio.Lock`` verhindert verlorene Schreibzugriffe bei
    gleichzeitigen Änderungen.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY
        )
        self._raw_hoflaeden: list[dict[str, Any]] | None = None
        self._lock = asyncio.Lock()

    async def _async_geladene_daten(self) -> list[dict[str, Any]]:
        """Daten bei Bedarf einmalig aus dem Store laden (Lazy Load)."""
        if self._raw_hoflaeden is None:
            geladen = await self._store.async_load()
            # Ein frisch eingerichteter Store enthält noch keine Datei
            # (async_load liefert dann None). Bewusst mit einer leeren
            # Liste starten statt erfundener Beispieldaten – die
            # Hofläden werden vollständig von der Nutzerin/dem Nutzer
            # gepflegt.
            self._raw_hoflaeden = geladen if geladen is not None else []
        return self._raw_hoflaeden

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Alle im Store gehaltenen Hofladen-Rohdaten zurückgeben."""
        daten = await self._async_geladene_daten()
        return list(daten)

    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen neuen Hofladen persistent ergänzen.

        Wirft :class:`DuplicateHofladenIdError`, falls bereits ein
        Datensatz mit derselben ``id`` vorhanden ist.
        """
        async with self._lock:
            daten = await self._async_geladene_daten()

            neue_id = raw_hofladen.get("id")
            if any(vorhanden.get("id") == neue_id for vorhanden in daten):
                raise DuplicateHofladenIdError(
                    f"Ein Hofladen mit der ID '{neue_id}' existiert bereits."
                )

            daten.append(dict(raw_hofladen))
            await self._store.async_save(daten)

    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens persistent aktualisieren.

        Wirft :class:`HofladenNotFoundError`, falls keine ``id`` mit
        diesem Wert existiert.
        """
        async with self._lock:
            daten = await self._async_geladene_daten()

            for index, vorhandener in enumerate(daten):
                if vorhandener.get("id") == hofladen_id:
                    daten[index] = {**vorhandener, **updates}
                    await self._store.async_save(daten)
                    return

            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )

    async def async_delete_raw_hofladen(self, hofladen_id: str) -> None:
        """Einen Hofladen aus dem persistenten Store entfernen."""
        async with self._lock:
            daten = await self._async_geladene_daten()
            for index, vorhanden in enumerate(daten):
                if vorhanden.get("id") == hofladen_id:
                    del daten[index]
                    await self._store.async_save(daten)
                    return
            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )

    async def async_apply_changes(
        self,
        upserts: list[dict[str, Any]],
        loeschungen: list[str] | None = None,
    ) -> None:
        """Mehrere Änderungen anwenden und **genau einmal** speichern (F5).

        Läuft vollständig unter dem Lock. Die Änderungen werden auf einer
        Kopie angewendet; erst nach erfolgreichem Speichern wird der
        Arbeitsspeicherstand ersetzt (bei einem Fehler bleibt alles beim
        Alten, kein Teilergebnis).
        """
        async with self._lock:
            daten = await self._async_geladene_daten()
            neu = _wende_aenderungen_an(daten, upserts, loeschungen or [])
            await self._store.async_save(neu)
            self._raw_hoflaeden = neu


class StaticTestDataProvider(MutableHofladenDataProvider):
    """Reiner Testdaten-Provider ohne Persistenz und ohne externe Anbindung.

    Wird ausschliesslich von der Testsuite verwendet, um Coordinator und
    Entities isoliert und deterministisch zu testen, ohne einen echten
    Home-Assistant-Store zu benötigen. Für den produktiven Betrieb wird
    stattdessen :class:`StorageHofladenDataProvider` verwendet (siehe
    ``__init__.py``). Daten liegen nur im Arbeitsspeicher und gehen bei
    einem Neustart verloren.
    """

    def __init__(self, raw_hoflaeden: list[dict[str, Any]] | None = None) -> None:
        """Testdaten-Provider erzeugen.

        Ohne explizite ``raw_hoflaeden`` wird ein einzelner Beispiel-
        Hofladen als Platzhalter zurückgegeben.
        """
        self._raw_hoflaeden = (
            list(raw_hoflaeden) if raw_hoflaeden is not None else list(_DEFAULT_TEST_DATA)
        )

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Die konfigurierten Testdaten zurückgeben.

        ``asyncio.sleep(0)`` gibt die Kontrolle explizit an den Event Loop
        zurück, obwohl kein echter I/O-Zugriff stattfindet. Das hält die
        Funktion konsistent asynchron, analog zu einem künftigen echten
        Provider.
        """
        await asyncio.sleep(0)
        return list(self._raw_hoflaeden)

    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen rohen Hofladen-Datensatz im Arbeitsspeicher ergänzen.

        Wirft :class:`DuplicateHofladenIdError`, falls bereits ein
        Datensatz mit derselben ``id`` vorhanden ist. Die inhaltliche
        Validierung (Pflichtfelder, Wertebereiche etc.) obliegt bewusst
        nicht dem Provider, sondern ``parsing.parse_hofladen`` – siehe
        ``coordinator.HofKarteUpdateCoordinator.async_add_hofladen`` für
        den empfohlenen Aufrufweg inklusive Validierung.
        """
        await asyncio.sleep(0)

        neue_id = raw_hofladen.get("id")
        if any(vorhanden.get("id") == neue_id for vorhanden in self._raw_hoflaeden):
            raise DuplicateHofladenIdError(
                f"Ein Hofladen mit der ID '{neue_id}' existiert bereits."
            )

        self._raw_hoflaeden.append(dict(raw_hofladen))

    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens im Arbeitsspeicher
        aktualisieren (teilweise Aktualisierung, siehe Basisklasse).

        Wirft :class:`HofladenNotFoundError`, falls keine ``id`` mit
        diesem Wert existiert. Die inhaltliche Validierung des
        resultierenden Gesamtdatensatzes obliegt bewusst nicht dem
        Provider, sondern ``parsing.parse_hofladen`` – siehe
        ``coordinator.HofKarteUpdateCoordinator.async_update_hofladen_sortiment``
        für den empfohlenen Aufrufweg inklusive Validierung.
        """
        await asyncio.sleep(0)

        for index, vorhandener in enumerate(self._raw_hoflaeden):
            if vorhandener.get("id") == hofladen_id:
                self._raw_hoflaeden[index] = {**vorhandener, **updates}
                return

        raise HofladenNotFoundError(
            f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
        )

    async def async_apply_changes(
        self,
        upserts: list[dict[str, Any]],
        loeschungen: list[str] | None = None,
    ) -> None:
        """Mehrere Änderungen atomar im Arbeitsspeicher anwenden (F5)."""
        await asyncio.sleep(0)
        self._raw_hoflaeden = _wende_aenderungen_an(
            self._raw_hoflaeden, upserts, loeschungen or []
        )

    async def async_delete_raw_hofladen(self, hofladen_id: str) -> None:
        """Einen Hofladen aus dem Testspeicher entfernen."""
        await asyncio.sleep(0)
        for index, vorhanden in enumerate(self._raw_hoflaeden):
            if vorhanden.get("id") == hofladen_id:
                del self._raw_hoflaeden[index]
                return
        raise HofladenNotFoundError(
            f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
        )


_DEFAULT_TEST_DATA: list[dict[str, Any]] = [
    {
        "id": "platzhalter-hofladen",
        "name": "Platzhalter-Hofladen",
    },
]

