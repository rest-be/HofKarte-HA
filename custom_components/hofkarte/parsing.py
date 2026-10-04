"""Parsing und Validierung roher Hofladen-Daten.

Dieses Modul trennt bewusst Rohdaten (``Mapping``/``dict``) von der internen,
typisierten Darstellung in ``models.py``. Die produktive Datenquelle ist der
integrationsinterne Home-Assistant-Storage, der über den Data Provider
kapselt wird. Das Parsing kennt bewusst keine konkrete Speicher- oder
Persistenzimplementierung und erwartet lediglich ein einfaches,
JSON-kompatibles Mapping je Hofladen.

Ungültige oder unvollständige Pflichtdaten führen zu einer
:class:`HofladenValidationError` mit einer für Menschen verständlichen
Fehlermeldung. Fehlende optionale Felder werden robust auf ``None`` bzw.
leere Sammlungen abgebildet.

Intervall-Regel für ``beginn``/``ende`` (Öffnungszeit und
Sonderöffnungszeit): ``ende == beginn`` ist ungültig (nicht definierbare
Dauer). ``ende < beginn`` ist hingegen gültig und bedeutet ein Intervall,
das die Mitternacht überschreitet (z. B. 22:00–02:00) – siehe
``opening_hours.py`` für die Berechnung anhand solcher Intervalle.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, time
from typing import Any

from .models import (
    Angebot,
    Bild,
    Hofladen,
    Oeffnungszeit,
    Sonderoeffnungszeit,
    Zahlungsart,
)

_LATITUDE_MIN = -90.0
_LATITUDE_MAX = 90.0
_LONGITUDE_MIN = -180.0
_LONGITUDE_MAX = 180.0
_WOCHENTAG_MIN = 1
_WOCHENTAG_MAX = 7
_BEWERTUNG_MIN = 0
_BEWERTUNG_MAX = 5


class HofladenValidationError(ValueError):
    """Rohdaten für einen Hofladen sind ungültig oder unvollständig."""


def _require_str(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HofladenValidationError(
            f"Pflichtfeld '{field_name}' fehlt oder ist leer."
        )
    return value.strip()


def _optional_str(raw: Mapping[str, Any], field_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HofladenValidationError(
            f"Feld '{field_name}' muss eine Zeichenkette sein."
        )
    stripped = value.strip()
    return stripped or None


def _optional_float(
    raw: Mapping[str, Any], field_name: str, minimum: float, maximum: float
) -> float | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HofladenValidationError(f"Feld '{field_name}' muss eine Zahl sein.")
    number = float(value)
    if not minimum <= number <= maximum:
        raise HofladenValidationError(
            f"Feld '{field_name}' muss zwischen {minimum} und {maximum} liegen."
        )
    return number


def _parse_bewertung(raw: Mapping[str, Any]) -> int:
    """Bewertung (0-5 Sterne) einlesen.

    Bewusst nicht wie ``latitude``/``longitude`` mit einer harten
    Fehlermeldung bei Werten ausserhalb des Bereichs, sondern auf den
    gültigen Bereich **begrenzt** (analog zum Suchradius in
    ``osm_info.py``): Eine Bewertung ist reine Komfort-Metainformation,
    kein sicherheits- oder korrektheitsrelevantes Feld - ein
    geringfügig ausserhalb liegender Wert (z. B. durch eine künftige
    Fremddatenquelle mit 1-10-Skala) soll das Speichern des gesamten
    Hofladens nicht verhindern. Ein fehlender Wert ergibt den Standard
    ``0`` (unbewertet).
    """
    value = raw.get("bewertung", 0)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HofladenValidationError("Feld 'bewertung' muss eine Zahl sein.")
    return max(_BEWERTUNG_MIN, min(_BEWERTUNG_MAX, int(value)))


def _parse_version(raw: Mapping[str, Any]) -> int:
    """Versionsnummer für optimistische Nebenläufigkeitskontrolle einlesen.

    Anders als ``bewertung`` (reine Komfort-Metainformation) ist die
    Version sicherheitsrelevant für die Konflikterkennung beim
    Offline-Sync (siehe ``coordinator.async_save_hofladen``) - ein
    ungültiger Wert wird daher mit einem harten Fehler abgelehnt statt
    stillschweigend begrenzt. Fehlt das Feld (z. B. bei Import/Export
    aus einer Zeit vor Einführung der Versionierung), ergibt sich der
    Standard ``1``.
    """
    value = raw.get("version", 1)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HofladenValidationError("Feld 'version' muss eine ganze Zahl sein.")
    if value < 1:
        raise HofladenValidationError("Feld 'version' muss mindestens 1 sein.")
    return value


def _parse_time(raw_value: Any, context: str, field_name: str) -> time:
    if isinstance(raw_value, time):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return time.fromisoformat(raw_value)
        except ValueError as err:
            raise HofladenValidationError(
                f"{context}: ungültige Uhrzeit in '{field_name}': '{raw_value}'."
            ) from err
    raise HofladenValidationError(
        f"{context}: ungültige Uhrzeit in '{field_name}': {raw_value!r}."
    )


def _parse_date(raw_value: Any, context: str, field_name: str) -> date:
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return date.fromisoformat(raw_value)
        except ValueError as err:
            raise HofladenValidationError(
                f"{context}: ungültiges Datum in '{field_name}': '{raw_value}'."
            ) from err
    raise HofladenValidationError(
        f"{context}: ungültiges Datum in '{field_name}': {raw_value!r}."
    )


def _parse_oeffnungszeit(raw: Any, index: int) -> Oeffnungszeit:
    context = f"Öffnungszeit #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    wochentag = raw.get("wochentag")
    if (
        not isinstance(wochentag, int)
        or isinstance(wochentag, bool)
        or not (_WOCHENTAG_MIN <= wochentag <= _WOCHENTAG_MAX)
    ):
        raise HofladenValidationError(
            f"{context}: 'wochentag' muss zwischen {_WOCHENTAG_MIN} (Montag) "
            f"und {_WOCHENTAG_MAX} (Sonntag) liegen."
        )

    beginn = _parse_time(raw.get("beginn"), context, "beginn")
    ende = _parse_time(raw.get("ende"), context, "ende")
    if ende == beginn:
        raise HofladenValidationError(
            f"{context}: 'ende' darf nicht gleich 'beginn' sein."
        )

    return Oeffnungszeit(wochentag=wochentag, beginn=beginn, ende=ende)


def _parse_sonderoeffnungszeit(raw: Any, index: int) -> Sonderoeffnungszeit:
    context = f"Sonderöffnungszeit #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    datum_von = _parse_date(raw.get("datum_von"), context, "datum_von")
    datum_bis = _parse_date(raw.get("datum_bis"), context, "datum_bis")
    if datum_bis < datum_von:
        raise HofladenValidationError(
            f"{context}: 'datum_bis' darf nicht vor 'datum_von' liegen."
        )

    geschlossen = bool(raw.get("geschlossen", False))

    beginn: time | None = None
    ende: time | None = None
    if not geschlossen:
        if raw.get("beginn") is None or raw.get("ende") is None:
            raise HofladenValidationError(
                f"{context}: 'beginn' und 'ende' sind erforderlich, solange "
                "'geschlossen' nicht gesetzt ist."
            )
        beginn = _parse_time(raw["beginn"], context, "beginn")
        ende = _parse_time(raw["ende"], context, "ende")
        if ende == beginn:
            raise HofladenValidationError(
                f"{context}: 'ende' darf nicht gleich 'beginn' sein."
            )

    return Sonderoeffnungszeit(
        datum_von=datum_von,
        datum_bis=datum_bis,
        geschlossen=geschlossen,
        beginn=beginn,
        ende=ende,
    )


def _parse_lookup(raw: Any, index: int, kind: str, factory: Any) -> Any:
    context = f"{kind} #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    id_value = raw.get("id")
    name_value = raw.get("name")
    if not isinstance(id_value, str) or not id_value.strip():
        raise HofladenValidationError(f"{context}: 'id' fehlt oder ist leer.")
    if not isinstance(name_value, str) or not name_value.strip():
        raise HofladenValidationError(f"{context}: 'name' fehlt oder ist leer.")

    return factory(id=id_value.strip(), name=name_value.strip())


def _parse_angebot(raw: Any, index: int) -> Angebot:
    context = f"Angebot #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    id_value = raw.get("id")
    name_value = raw.get("name")
    if not isinstance(id_value, str) or not id_value.strip():
        raise HofladenValidationError(f"{context}: 'id' fehlt oder ist leer.")
    if not isinstance(name_value, str) or not name_value.strip():
        raise HofladenValidationError(f"{context}: 'name' fehlt oder ist leer.")

    # Ein eventuell noch vorhandenes 'gruppen'-Feld aus älteren, vor der
    # Vereinfachung gespeicherten Rohdaten wird bewusst ignoriert
    # (Angebote sind seit der Vereinfachung eine schlichte Namensliste
    # ohne Gruppierung, siehe models.Angebot) - kein Fehler, kein
    # Absturz; die Gruppen-Information geht dabei inhaltlich verloren.
    return Angebot(id=id_value.strip(), name=name_value.strip())


def _migriere_kategorien_und_produkte_zu_angeboten(
    raw: Mapping[str, Any],
) -> list[Any]:
    """Migriert die frühere, getrennte Struktur (``kategorien``/``produkte``)
    in eine einheitliche, flache Liste von Angebot-Rohdaten.

    **Idempotent:** Ist der Schlüssel ``angebote`` bereits vorhanden
    (neues Format), wird dieser unverändert zurückgegeben – die
    Migration greift ausschliesslich, wenn ausschliesslich die alten
    Schlüssel ``kategorien``/``produkte`` vorhanden sind.

    Angebote sind seit der Vereinfachung eine schlichte Namensliste ohne
    Gruppierung (siehe ``models.Angebot``) – die frühere Unterscheidung
    zwischen „Kategorie“ und „Produkt“ existiert dadurch nicht mehr:
    Sowohl bestehende Kategorien als auch bestehende Produkte werden
    gleichermassen zu flachen Angebot-Einträgen (nur ``id``/``name``).
    Eine eventuelle Produkt-zu-Kategorie-Verknüpfung
    (``kategorie_ids``) wird dabei nicht mehr ausgewertet, da es keine
    Gruppierung mehr gibt, in die sie einfliessen könnte – auch das ist
    ein bewusster, dokumentierter Informationsverlust (siehe CHANGELOG).
    """
    if "angebote" in raw:
        angebote_raw = raw.get("angebote") or []
        return list(angebote_raw) if isinstance(angebote_raw, (list, tuple)) else []

    kategorien_raw = raw.get("kategorien") or []
    produkte_raw = raw.get("produkte") or []
    if not kategorien_raw and not produkte_raw:
        return []

    angebote: list[Any] = []
    for quelle in (produkte_raw, kategorien_raw):
        if not isinstance(quelle, (list, tuple)):
            continue
        for eintrag in quelle:
            if not isinstance(eintrag, Mapping):
                # Ungültig - unverändert weitergeben, _parse_angebot
                # meldet den konkreten Fehler (Fail-Fast bleibt erhalten).
                angebote.append(eintrag)
                continue
            angebote.append({"id": eintrag.get("id"), "name": eintrag.get("name")})

    return angebote


def _parse_bild(raw: Any, index: int) -> Bild:
    context = f"Bild #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        raise HofladenValidationError(f"{context}: 'url' fehlt oder ist leer.")

    beschreibung = raw.get("beschreibung")
    if beschreibung is not None and not isinstance(beschreibung, str):
        raise HofladenValidationError(
            f"{context}: 'beschreibung' muss eine Zeichenkette sein."
        )

    hochgeladen = raw.get("hochgeladen", False)
    if not isinstance(hochgeladen, bool):
        raise HofladenValidationError(f"{context}: 'hochgeladen' muss ein Bool sein.")

    return Bild(
        url=url.strip(),
        beschreibung=(beschreibung.strip() if beschreibung else None) or None,
        hochgeladen=hochgeladen,
    )


def _parse_list(raw: Mapping[str, Any], field_name: str, parse_item: Any) -> tuple:
    items = raw.get(field_name, []) or []
    if not isinstance(items, (list, tuple)):
        raise HofladenValidationError(f"Feld '{field_name}' muss eine Liste sein.")
    return tuple(parse_item(item, i) for i, item in enumerate(items))


def parse_hofladen(raw: Mapping[str, Any]) -> Hofladen:
    """Rohdaten eines Hofladens in das interne, typisierte Modell überführen.

    Erwartet ein Mapping mit mindestens den Pflichtfeldern ``id`` und
    ``name``. Alle übrigen Felder sind optional und werden bei Fehlen
    robust auf ``None`` bzw. eine leere Sammlung abgebildet.

    Wirft :class:`HofladenValidationError`, wenn Pflichtfelder fehlen oder
    Werte fachlich ungültig sind (z. B. Koordinaten ausserhalb des gültigen
    Bereichs, ein Öffnungszeit-Ende vor dem Beginn).
    """
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(
            "Rohdaten eines Hofladens müssen ein Mapping (dict) sein."
        )

    hofladen_id = _require_str(raw, "id")
    name = _require_str(raw, "name")

    beschreibung = _optional_str(raw, "beschreibung")
    bemerkung = _optional_str(raw, "bemerkung")
    adresse = _optional_str(raw, "adresse")
    plz = _optional_str(raw, "plz")
    ort = _optional_str(raw, "ort")
    land = _optional_str(raw, "land")
    website = _optional_str(raw, "website")
    mobilnummer = _optional_str(raw, "mobilnummer")
    email = _optional_str(raw, "email")
    bewertung = _parse_bewertung(raw)
    version = _parse_version(raw)

    latitude = _optional_float(raw, "latitude", _LATITUDE_MIN, _LATITUDE_MAX)
    longitude = _optional_float(raw, "longitude", _LONGITUDE_MIN, _LONGITUDE_MAX)

    oeffnungszeiten = _parse_list(raw, "oeffnungszeiten", _parse_oeffnungszeit)
    sonderoeffnungszeiten = _parse_list(
        raw, "sonderoeffnungszeiten", _parse_sonderoeffnungszeit
    )
    angebote_raw = _migriere_kategorien_und_produkte_zu_angeboten(raw)
    angebote = tuple(
        _parse_angebot(item, i) for i, item in enumerate(angebote_raw)
    )
    zahlungsarten = _parse_list(
        raw,
        "zahlungsarten",
        lambda item, i: _parse_lookup(item, i, "Zahlungsart", Zahlungsart),
    )
    bilder = _parse_list(raw, "bilder", _parse_bild)

    return Hofladen(
        id=hofladen_id,
        name=name,
        beschreibung=beschreibung,
        bemerkung=bemerkung,
        adresse=adresse,
        plz=plz,
        ort=ort,
        land=land,
        website=website,
        mobilnummer=mobilnummer,
        email=email,
        latitude=latitude,
        longitude=longitude,
        oeffnungszeiten=oeffnungszeiten,
        sonderoeffnungszeiten=sonderoeffnungszeiten,
        angebote=angebote,
        zahlungsarten=zahlungsarten,
        bilder=bilder,
        bewertung=bewertung,
        version=version,
    )
