"""Backend support for the HofKarte management panel.

Alle Schreibzugriffe laufen ausschliesslich über die öffentlichen
``HofKarteUpdateCoordinator``-Methoden (``async_save_hofladen``,
``async_delete_hofladen``) – nicht direkt über den zugrunde liegenden
``HofladenDataProvider``. Das hält die in ``coordinator.py``
implementierte Fail-Fast-Validierung und Refresh-Logik an einer
einzigen Stelle, statt sie hier zu duplizieren.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LISTEN_SORT_RICHTUNG,
    CONF_LISTEN_SORT_SPALTE,
    CONF_OSM_RADIUS_METER,
    DEFAULT_LISTEN_SORT_RICHTUNG,
    DEFAULT_LISTEN_SORT_SPALTE,
    DEFAULT_OSM_RADIUS_METER,
    DOMAIN,
    MAX_IMPORT_EINTRAEGE,
)
from .coordinator import HofKarteUpdateCoordinator, HofladenVersionConflictError
from .data_provider import DuplicateHofladenIdError, HofladenNotFoundError
from .images import get_main_image_url
from .models import Hofladen
from .opening_hours import is_open
from .osm_info import (
    MAX_RADIUS_METER,
    MIN_RADIUS_METER,
    OsmKeineOrteGefundenError,
    OsmNichtErreichbarError,
    OsmUngueltigeKoordinatenError,
    async_ermittle_osm_orte,
)
from .parsing import HofladenValidationError
from .webseite_info import (
    WebseiteInformationenNichtGefundenError,
    WebseiteNichtErreichbarError,
    WebseiteUngueltigeUrlError,
    async_ermittle_webseite_info,
)

WS_LIST = "hofkarte/management/list"
WS_SAVE = "hofkarte/management/save"
WS_DELETE = "hofkarte/management/delete"
WS_IMPORT_PREVIEW = "hofkarte/management/import_preview"
WS_IMPORT_COMMIT = "hofkarte/management/import_commit"
WS_WEBSEITE_INFO = "hofkarte/management/webseite_info"
WS_OSM_INFO = "hofkarte/management/osm_info"
WS_SETTINGS = "hofkarte/management/settings"

# Gültige Werte für "aktion" in einem einzelnen Eintrag von
# WS_IMPORT_COMMIT (siehe ws_import_commit()).
_IMPORT_AKTION_NEU = "neu"
_IMPORT_AKTION_AKTUALISIEREN = "aktualisieren"
_IMPORT_AKTION_UEBERSPRINGEN = "ueberspringen"
_IMPORT_AKTIONEN = {
    _IMPORT_AKTION_NEU,
    _IMPORT_AKTION_AKTUALISIEREN,
    _IMPORT_AKTION_UEBERSPRINGEN,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, time):
        # time.isoformat() liefert standardmässig Sekunden ("08:00:00").
        # Öffnungszeiten werden ausschliesslich über type="time"-Felder
        # ohne Sekundenauflösung erfasst (siehe hofkarte-panel.js) – die
        # Darstellung soll das widerspiegeln (hh:mm statt hh:mm:ss).
        return value.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            field: _json_value(getattr(value, field))
            for field in value.__dataclass_fields__
        }
    return value


def _serialize_hofladen(hofladen: Any, *, now: datetime) -> dict[str, Any]:
    """Rohdaten eines Hofladens für die Verwaltungsoberfläche serialisieren.

    Ergänzt zusätzlich zu den gespeicherten Feldern zwei serverseitig
    berechnete Werte, damit die Verwaltungsoberfläche (Kacheln-/
    Listenansicht, siehe Issue #1) bestehende, teils sicherheitsrelevante
    Fachlogik nicht ein zweites Mal, möglicherweise abweichend, in
    JavaScript nachbauen muss:

    - ``geoeffnet`` (``True``/``False``/``None`` für „unbekannt“) über
      ``opening_hours.is_open`` – exakt dieselbe Funktion, die auch der
      Binary Sensor „Geöffnet“ verwendet (siehe ``binary_sensor.py``).
    - ``hauptbild_url`` (``str | None``) über ``images.get_main_image_url``
      – exakt dieselbe Funktion (inkl. Sicherheitsprüfung gegen
      private/interne IP-Literale), die auch das ``image``-Entity für
      das tatsächliche Hauptbild verwendet (siehe ``image.py``).

    ``now`` wird bewusst von den Aufrufern übergeben (nicht hier selbst
    über ``dt_util.now()`` ermittelt), damit alle Hofläden einer
    einzelnen Anfrage konsistent gegen denselben Zeitpunkt bewertet
    werden.
    """
    daten = _json_value(hofladen)
    daten["geoeffnet"] = is_open(hofladen, now)
    daten["hauptbild_url"] = get_main_image_url(hofladen.bilder)
    return daten


def _normalisiert(text: str | None) -> str:
    """Text für einen tolerant vergleichenden Duplikat-Abgleich
    normalisieren (Gross-/Kleinschreibung sowie führende/nachfolgende
    Leerzeichen werden ignoriert, siehe Issue #5)."""
    return (text or "").strip().casefold()


class _DuplikatIndex:
    """Einmal gebauter Index der bestehenden Hofläden nach normalisiertem
    Namen (Befund F5): statt für jeden Importeintrag alle Bestandsdaten zu
    durchlaufen, werden nur Kandidaten mit gleichem Namen geprüft. Die
    Reihenfolge der Kandidaten bleibt die des Bestands, das Ergebnis ist
    damit identisch zum früheren linearen Durchlauf."""

    def __init__(self, bestehende: list[Hofladen]) -> None:
        self._nach_name: dict[str, list[tuple[Hofladen, str]]] = {}
        for kandidat in bestehende:
            self._nach_name.setdefault(_normalisiert(kandidat.name), []).append(
                (kandidat, _normalisiert(kandidat.adresse))
            )

    def finde(self, hofladen: Hofladen) -> Hofladen | None:
        ziel_adresse = _normalisiert(hofladen.adresse)
        for kandidat, kandidat_adresse in self._nach_name.get(
            _normalisiert(hofladen.name), ()
        ):
            if hofladen.adresse and kandidat.adresse and ziel_adresse != kandidat_adresse:
                continue
            return kandidat
        return None


def _finde_duplikat(
    hofladen: Hofladen, bestehende: list[Hofladen]
) -> Hofladen | None:
    """Ein bestehendes Duplikat für einen zu importierenden Hofladen
    finden (Issue #5).

    Zwei Hofläden gelten als Duplikat, wenn ihr Name übereinstimmt
    (normalisiert, siehe ``_normalisiert``) und - sofern **beide**
    Datensätze eine Adresse besitzen - zusätzlich die Adresse
    übereinstimmt. Fehlt einem der beiden Datensätze die Adresse,
    entscheidet allein der Name. Es wird bewusst keine Fuzzy-Logik
    (z. B. Tippfehlertoleranz) verwendet - das Risiko falscher
    Zusammenführungen (Datenverlust) wiegt schwerer als der
    Komfortgewinn.
    """
    return _DuplikatIndex(bestehende).finde(hofladen)


def _get_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    """Den (einzigen) HofKarte-Coordinator ermitteln.

    Wirft ``ValueError``, falls HofKarte nicht (oder mehrfach) geladen
    ist. Aufrufer müssen dies abfangen und als sauberen WebSocket-Fehler
    zurückmelden statt die Exception unbehandelt durchzureichen.
    """
    entries = hass.data.get(DOMAIN, {})
    if len(entries) != 1:
        raise ValueError(
            "HofKarte ist nicht eingerichtet oder nicht eindeutig geladen."
        )
    return next(iter(entries.values()))


def _settings(coordinator: HofKarteUpdateCoordinator) -> dict[str, Any]:
    """Dauerhaft gespeicherte Einstellungen (Options Flow) mit Vorgabewerten
    für fehlende Schlüssel ermitteln (z. B. eine noch nie über den Options
    Flow bestätigte Config Entry - diese hat ``options == {}``)."""
    optionen = (coordinator.config_entry.options if coordinator.config_entry else None) or {}
    return {
        CONF_LISTEN_SORT_SPALTE: optionen.get(
            CONF_LISTEN_SORT_SPALTE, DEFAULT_LISTEN_SORT_SPALTE
        ),
        CONF_LISTEN_SORT_RICHTUNG: optionen.get(
            CONF_LISTEN_SORT_RICHTUNG, DEFAULT_LISTEN_SORT_RICHTUNG
        ),
        CONF_OSM_RADIUS_METER: optionen.get(
            CONF_OSM_RADIUS_METER, DEFAULT_OSM_RADIUS_METER
        ),
    }


@websocket_api.websocket_command({vol.Required("type"): WS_SETTINGS})
@websocket_api.require_admin
@callback
def ws_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Dauerhaft gespeicherte Einstellungen (Options Flow, siehe
    ``config_flow.HofKarteOptionsFlow``) an die Verwaltungsoberfläche
    liefern - dient dort als Vorgabewert für Sortierung und OSM-
    Suchradius beim erstmaligen Laden eines Formulars/der Übersicht
    (siehe ``static/hofkarte-panel.js``, Initialisierung)."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    connection.send_result(msg["id"], {"einstellungen": _settings(coordinator)})


@websocket_api.websocket_command({vol.Required("type"): WS_LIST})
@websocket_api.require_admin
@callback
def ws_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return all current Hofläden."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    jetzt = dt_util.now()
    connection.send_result(
        msg["id"],
        {
            "hoflaeden": [
                _serialize_hofladen(v, now=jetzt)
                for v in coordinator.data.values()
            ]
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_SAVE, vol.Required("hofladen"): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Create or update a Hofladen (delegiert vollständig an den Coordinator).

    Enthält das zu speichernde ``hofladen`` eine ``version`` (wird von
    Aufrufern, die optimistische Nebenläufigkeitskontrolle unterstützen -
    aktuell die HofKarte-PWA, siehe Vorgehensplan Phase 8b - mit der
    zuletzt bekannten Version befüllt), kann der Coordinator einen
    Versionskonflikt feststellen. In diesem Fall wird **kein** Fehler
    gesendet (ein Konflikt ist kein technischer Fehler, sondern ein
    erwartbarer Normalfall), sondern ein Ergebnis mit ``"konflikt": true``
    und dem aktuellen, serverseitigen Stand unter ``"aktueller_hofladen"``
    - die aufrufende Oberfläche kann daraus eine Konflikt-Ansicht (zwei
    Versionen nebeneinander) aufbauen. Bei Erfolg enthält das Ergebnis
    stattdessen ``"konflikt": false`` und den gespeicherten Hofladen unter
    ``"hofladen"``, inklusive der neuen, serverseitig vergebenen Version.
    """
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    raw = dict(msg["hofladen"])
    if not raw.get("id"):
        raw["id"] = f"hofladen-{uuid4().hex}"

    try:
        parsed = await coordinator.async_save_hofladen(raw)
    except HofladenVersionConflictError as err:
        connection.send_result(
            msg["id"],
            {
                "konflikt": True,
                "aktueller_hofladen": _serialize_hofladen(
                    err.aktueller_hofladen, now=dt_util.now()
                ),
            },
        )
        return
    except HofladenValidationError as err:
        connection.send_error(msg["id"], "invalid_data", str(err))
        return
    except DuplicateHofladenIdError as err:
        # Befund F13: z. B. gleichzeitiges Anlegen derselben ID.
        connection.send_error(msg["id"], "duplicate_id", str(err))
        return
    except HofladenNotFoundError as err:
        # Befund F13: Hofladen wurde zwischenzeitlich gelöscht.
        connection.send_error(msg["id"], "not_found", str(err))
        return
    except NotImplementedError as err:
        connection.send_error(msg["id"], "not_supported", str(err))
        return

    connection.send_result(
        msg["id"],
        {
            "konflikt": False,
            "hofladen": _serialize_hofladen(parsed, now=dt_util.now()),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_DELETE, vol.Required("hofladen_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete a Hofladen from persistent storage (delegiert an den Coordinator)."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    try:
        await coordinator.async_delete_hofladen(msg["hofladen_id"])
    except NotImplementedError as err:
        connection.send_error(msg["id"], "not_supported", str(err))
        return
    except HofladenNotFoundError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    connection.send_result(msg["id"], {})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_IMPORT_PREVIEW, vol.Required("hoflaeden"): [dict]}
)
@websocket_api.require_admin
@callback
def ws_import_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Eine zu importierende Liste von Hofläden validieren und mögliche
    Duplikate gegen den aktuellen Bestand ermitteln (Issue #5).

    Rein lesend - es wird noch nichts gespeichert (siehe ws_import_commit
    für den eigentlichen Import). Fail-Fast: Enthält die Liste auch nur
    einen strukturell ungültigen Datensatz, wird die gesamte Vorschau mit
    einem Fehler abgelehnt (kein Teil-Ergebnis), damit die Nutzeroberfläche
    gar nicht erst mit einer unvollständigen Grundlage weiterarbeitet.
    """
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    rohdaten = msg["hoflaeden"]
    if not rohdaten:
        connection.send_error(
            msg["id"], "invalid_data", "Die Import-Datei enthält keine Hofläden."
        )
        return

    if len(rohdaten) > MAX_IMPORT_EINTRAEGE:
        connection.send_error(
            msg["id"],
            "invalid_data",
            f"Die Import-Datei enthält zu viele Hofläden "
            f"(höchstens {MAX_IMPORT_EINTRAEGE} je Import erlaubt).",
        )
        return

    geparste: list[Hofladen] = []
    for index, raw in enumerate(rohdaten):
        try:
            geparste.append(coordinator.parse_roh(raw))
        except HofladenValidationError as err:
            connection.send_error(
                msg["id"], "invalid_data", f"Datensatz #{index + 1}: {err}"
            )
            return

    # Index einmal bauen statt je Eintrag den gesamten Bestand zu durchlaufen.
    duplikat_index = _DuplikatIndex(list((coordinator.data or {}).values()))
    eintraege = []
    for hofladen in geparste:
        duplikat = duplikat_index.finde(hofladen)
        eintraege.append(
            {
                "hofladen": _json_value(hofladen),
                "duplikat_von": duplikat.id if duplikat else None,
                "bestehend": _json_value(duplikat) if duplikat else None,
            }
        )

    connection.send_result(msg["id"], {"eintraege": eintraege})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_IMPORT_COMMIT, vol.Required("eintraege"): [dict]}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import_commit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Einen zuvor über ws_import_preview vorbereiteten Import tatsächlich
    durchführen (Issue #5).

    Jeder Eintrag benennt eine Aktion: ``"neu"`` (als neuer Hofladen mit
    frisch vergebener ID anlegen - eine im Importdatensatz enthaltene
    ``id`` einer fremden Installation wird dabei bewusst verworfen),
    ``"aktualisieren"`` (bestehenden Hofladen mit der Kennung
    ``bestehende_id`` mit den importierten Daten überschreiben) oder
    ``"ueberspringen"`` (Datensatz unverändert beibehalten, keine
    Schreibaktion).

    Fail-Fast über zwei Phasen, um „kein Datenverlust“/„kein
    Teil-Import“ zu gewährleisten: Zunächst werden **alle** Einträge
    validiert (gültige Aktion, bei „aktualisieren“ eine tatsächlich
    noch vorhandene ``bestehende_id``, sowie die Hofladen-Rohdaten
    selbst über ``parsing.parse_hofladen``); erst wenn diese Prüfung für
    sämtliche Einträge erfolgreich war, werden die Schreibzugriffe
    durchgeführt. Ein zwischenzeitlich (z. B. durch eine andere,
    parallele Sitzung) bereits gelöschter Datensatz führt daher zu einem
    Fehler für den gesamten Import, statt einen Teil davon unbemerkt zu
    verwerfen.
    """
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    eintraege = msg["eintraege"]
    if not eintraege:
        connection.send_error(
            msg["id"], "invalid_data", "Es wurden keine Einträge zum Import übergeben."
        )
        return

    if len(eintraege) > MAX_IMPORT_EINTRAEGE:
        connection.send_error(
            msg["id"],
            "invalid_data",
            f"Es wurden zu viele Einträge übergeben "
            f"(höchstens {MAX_IMPORT_EINTRAEGE} je Import erlaubt).",
        )
        return

    if not coordinator.provider_unterstuetzt_schreibzugriffe:
        connection.send_error(
            msg["id"],
            "not_supported",
            "Der konfigurierte Data Provider unterstützt keine Schreibzugriffe "
            "(Anlegen/Bearbeiten von Hofläden).",
        )
        return

    bestehende_ids = set((coordinator.data or {}).keys())
    # (Aktion, endgültige Rohdaten, validierter Hofladen) - das Ergebnis der
    # Validierungsphase wird beim Schreiben weiterverwendet (kein zweites
    # Parsen, Befund F5).
    vorbereitet: list[tuple[str, dict[str, Any], Hofladen]] = []
    zwischenstand: dict[str, Hofladen] = {}

    for index, eintrag in enumerate(eintraege):
        context = f"Eintrag #{index + 1}"
        aktion = eintrag.get("aktion")
        if aktion not in _IMPORT_AKTIONEN:
            connection.send_error(
                msg["id"], "invalid_data", f"{context}: unbekannte Aktion '{aktion}'."
            )
            return

        if aktion == _IMPORT_AKTION_UEBERSPRINGEN:
            continue

        raw = dict(eintrag.get("hofladen") or {})
        if aktion == _IMPORT_AKTION_AKTUALISIEREN:
            bestehende_id = eintrag.get("bestehende_id")
            if not bestehende_id or bestehende_id not in bestehende_ids:
                connection.send_error(
                    msg["id"],
                    "invalid_data",
                    f"{context}: 'bestehende_id' verweist auf keinen (mehr) "
                    "vorhandenen Hofladen.",
                )
                return
            raw["id"] = bestehende_id
        else:  # _IMPORT_AKTION_NEU
            raw["id"] = f"hofladen-{uuid4().hex}"

        try:
            endgueltig, hofladen, _ = coordinator.bereite_save_vor(raw, zwischenstand)
        except HofladenValidationError as err:
            connection.send_error(
                msg["id"], "invalid_data", f"{context}: {err}"
            )
            return
        zwischenstand[hofladen.id] = hofladen

        vorbereitet.append((aktion, endgueltig, hofladen))

    uebersprungen = len(eintraege) - len(vorbereitet)
    aktualisiert = sum(1 for aktion, _, _ in vorbereitet if aktion == _IMPORT_AKTION_AKTUALISIEREN)
    importiert = len(vorbereitet) - aktualisiert

    # Ein Schreibvorgang und ein Coordinator-Update für den gesamten Import.
    try:
        await coordinator.async_schreibe_vorbereitete(
            [(roh, hofladen) for _, roh, hofladen in vorbereitet]
        )
    except NotImplementedError as err:
        connection.send_error(msg["id"], "not_supported", str(err))
        return

    connection.send_result(
        msg["id"],
        {
            "importiert": importiert,
            "aktualisiert": aktualisiert,
            "uebersprungen": uebersprungen,
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_WEBSEITE_INFO, vol.Required("website"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_webseite_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Informationen von einer vom Benutzer angegebenen Website ermitteln
    (Issue #8, "Informationen aus Homepage").

    Liefert ausschliesslich **Vorschlagsdaten zur Überprüfung** – es wird
    dabei nichts gespeichert; das Speichern erfolgt unverändert über
    ``ws_save``, nachdem die Benutzerin/der Benutzer die vorgeschlagenen
    Werte im Formular geprüft und ggf. angepasst hat.

    Bildet die drei im Issue geforderten Fehlerfälle jeweils auf einen
    eigenen, unterscheidbaren Fehlercode ab (siehe ``webseite_info.py``
    für die jeweilige Bedeutung):

    - ``invalid_url`` - keine oder syntaktisch ungültige/unsichere
      Website-Adresse (Fehlerfall 1).
    - ``unreachable`` - Website nicht erreichbar oder nicht lesbar
      (Fehlerfall 2).
    - ``not_found`` - keine verwertbaren Informationen gefunden
      (Fehlerfall 3).

    Prüft (wie die übrigen Verwaltungsbefehle) zunächst, ob HofKarte
    eindeutig eingerichtet ist – der eigentliche Abruf verwendet den
    Coordinator zwar nicht, die Prüfung verhindert aber, dass die
    Verwaltungsoberfläche diesen Befehl in einem nicht betriebsbereiten
    Zustand aufrufen kann, konsistent mit ``ws_list``/``ws_save``/etc.
    """
    try:
        _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    try:
        info = await async_ermittle_webseite_info(hass, msg["website"])
    except WebseiteUngueltigeUrlError as err:
        connection.send_error(msg["id"], "invalid_url", str(err))
        return
    except WebseiteNichtErreichbarError as err:
        connection.send_error(msg["id"], "unreachable", str(err))
        return
    except WebseiteInformationenNichtGefundenError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    connection.send_result(msg["id"], {"info": _json_value(info)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_OSM_INFO,
        vol.Required("latitude"): vol.Coerce(float),
        vol.Required("longitude"): vol.Coerce(float),
        vol.Optional("radius"): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_RADIUS_METER, max=MAX_RADIUS_METER)
        ),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_osm_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """In der Nähe der angegebenen Koordinaten nach Orten (OpenStreetMap /
    Overpass API) suchen (Issue #10, "Ort in der Nähe suchen").

    Liefert ausschliesslich **Vorschlagsdaten zur Überprüfung** – es wird
    dabei nichts gespeichert; das Speichern erfolgt unverändert über
    ``ws_save``, nachdem die Benutzerin/der Benutzer einen der
    vorgeschlagenen Treffer geprüft und ggf. angepasst hat.

    Bildet die drei möglichen Fehlerfälle jeweils auf einen eigenen,
    unterscheidbaren Fehlercode ab (siehe ``osm_info.py`` für die
    jeweilige Bedeutung):

    - ``invalid_coordinates`` - Koordinaten fehlen oder sind ausserhalb
      des gültigen Wertebereichs.
    - ``unreachable`` - Overpass API nicht erreichbar oder Antwort nicht
      auswertbar.
    - ``not_found`` - keine (benannten) Orte im Suchradius gefunden.

    Prüft (wie die übrigen Verwaltungsbefehle) zunächst, ob HofKarte
    eindeutig eingerichtet ist – der eigentliche Abruf verwendet den
    Coordinator zwar nicht, die Prüfung verhindert aber, dass die
    Verwaltungsoberfläche diesen Befehl in einem nicht betriebsbereiten
    Zustand aufrufen kann, konsistent mit ``ws_list``/``ws_save``/
    ``ws_webseite_info``.

    ``radius`` ist seit Issue #11 optional (fehlt er, greift der über den
    Options Flow dauerhaft gespeicherte Vorgabewert, siehe ``_settings``)
    und wird bereits über das Nachrichtenschema auf
    ``MIN_RADIUS_METER``-``MAX_RADIUS_METER`` begrenzt (ein Wert
    ausserhalb dieses Bereichs führt zu einem
    regulären Schema-Validierungsfehler der Verwaltungsoberfläche); die
    zusätzliche Begrenzung in ``async_ermittle_osm_orte`` selbst bleibt
    als zweite, unabhängige Absicherung bestehen (siehe ``osm_info.py``).
    """
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    # Ohne vom Aufrufer angegebenen Radius greift der über den Options
    # Flow dauerhaft gespeicherte Vorgabewert (Fallback auf
    # ``STANDARD_RADIUS_METER``, falls keine Config Entry ermittelbar
    # ist) - siehe Moduldoc von ``config_flow.py``. Die Verwaltungs-
    # oberfläche selbst sendet den Radius inzwischen ohnehin stets
    # explizit (initialisiert aus ``ws_settings``), dieser Fallback
    # greift daher primär für andere WebSocket-Aufrufer.
    radius = msg.get("radius")
    if radius is None:
        radius = _settings(coordinator)[CONF_OSM_RADIUS_METER]

    try:
        orte = await async_ermittle_osm_orte(
            hass,
            msg["latitude"],
            msg["longitude"],
            radius_meter=radius,
        )
    except OsmUngueltigeKoordinatenError as err:
        connection.send_error(msg["id"], "invalid_coordinates", str(err))
        return
    except OsmNichtErreichbarError as err:
        connection.send_error(msg["id"], "unreachable", str(err))
        return
    except OsmKeineOrteGefundenError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    connection.send_result(
        msg["id"], {"orte": [_json_value(ort) for ort in orte]}
    )


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """HofKarte-WebSocket-Befehle registrieren (einmalig, Domain-Ebene)."""
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_import_preview)
    websocket_api.async_register_command(hass, ws_import_commit)
    websocket_api.async_register_command(hass, ws_webseite_info)
    websocket_api.async_register_command(hass, ws_osm_info)
    websocket_api.async_register_command(hass, ws_settings)
