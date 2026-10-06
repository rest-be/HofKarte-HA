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

import re
from collections.abc import Iterable, Mapping
from datetime import date, time
from typing import Any

from .const import (
    ID_MUSTER,
    MAX_ANZAHL_ANGEBOTE,
    MAX_ANZAHL_BILDER,
    MAX_ANZAHL_OEFFNUNGSZEITEN,
    MAX_ANZAHL_SONDEROEFFNUNGSZEITEN,
    MAX_ANZAHL_ZAHLUNGSARTEN,
    MAX_LAENGE_ADRESSFELD,
    MAX_LAENGE_EMAIL,
    MAX_LAENGE_NAME,
    MAX_LAENGE_TELEFON,
    MAX_LAENGE_TEXT,
    MAX_LAENGE_URL,
)

from .models import (
    Angebot,
    Bild,
    Hofladen,
    Oeffnungszeit,
    Sonderoeffnungszeit,
    Zahlungsart,
)
from .url_sicherheit import ist_eigene_upload_url

_LATITUDE_MIN = -90.0
_LATITUDE_MAX = 90.0
_LONGITUDE_MIN = -180.0
_LONGITUDE_MAX = 180.0
_WOCHENTAG_MIN = 1
_WOCHENTAG_MAX = 7
_BEWERTUNG_MIN = 0
_BEWERTUNG_MAX = 5


_ID_REGEX = re.compile(ID_MUSTER)
# Telefonnummer: nur Ziffern, Leerzeichen und + - / ( ) . (Befund F11).
_TELEFON_REGEX = re.compile(r"[0-9+\-/(). ]+")
# E-Mail: bewusst einfach (kein vollständiges RFC 5322): Genau ein "@", nichts
# davor/danach leer, kein Leerraum, keine Zeichen, die in ``mailto:``-Links
# zusätzliche Parameter einschleusen (``?``, ``&``, ``%``, ``#``, ``<``, ``>``,
# Anführungszeichen, Komma, Semikolon).
_EMAIL_REGEX = re.compile(r"[^@\s?&%#<>\"',;]+@[^@\s?&%#<>\"',;]+")

# Obergrenzen je Textfeld (Konstanten in ``const.py``).
_MAX_LAENGE_JE_FELD = {
    "name": MAX_LAENGE_NAME,
    "beschreibung": MAX_LAENGE_TEXT,
    "bemerkung": MAX_LAENGE_TEXT,
    "adresse": MAX_LAENGE_ADRESSFELD,
    "plz": MAX_LAENGE_ADRESSFELD,
    "ort": MAX_LAENGE_ADRESSFELD,
    "land": MAX_LAENGE_ADRESSFELD,
    "website": MAX_LAENGE_URL,
    "mobilnummer": MAX_LAENGE_TELEFON,
    "email": MAX_LAENGE_EMAIL,
}


class HofladenValidationError(ValueError):
    """Rohdaten für einen Hofladen sind ungültig oder unvollständig."""


def _pruefe_laenge(text: str, field_name: str, maximum: int) -> None:
    if len(text) > maximum:
        raise HofladenValidationError(
            f"Feld '{field_name}' darf höchstens {maximum} Zeichen lang sein "
            f"(aktuell {len(text)})."
        )


def _require_str(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HofladenValidationError(
            f"Pflichtfeld '{field_name}' fehlt oder ist leer."
        )
    stripped = value.strip()
    maximum = _MAX_LAENGE_JE_FELD.get(field_name)
    if maximum is not None:
        _pruefe_laenge(stripped, field_name, maximum)
    return stripped


def _optional_str(raw: Mapping[str, Any], field_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HofladenValidationError(
            f"Feld '{field_name}' muss eine Zeichenkette sein."
        )
    stripped = value.strip()
    maximum = _MAX_LAENGE_JE_FELD.get(field_name)
    if maximum is not None:
        _pruefe_laenge(stripped, field_name, maximum)
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


def _parse_bild(
    raw: Any, index: int, eigene_origins: Iterable[str] = ()
) -> Bild:
    context = f"Bild #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        raise HofladenValidationError(f"{context}: 'url' fehlt oder ist leer.")
    if len(url.strip()) > MAX_LAENGE_URL:
        raise HofladenValidationError(
            f"{context}: 'url' darf höchstens {MAX_LAENGE_URL} Zeichen lang sein."
        )

    beschreibung = raw.get("beschreibung")
    if beschreibung is not None and not isinstance(beschreibung, str):
        raise HofladenValidationError(
            f"{context}: 'beschreibung' muss eine Zeichenkette sein."
        )

    # Befund F1 (Code Review 2026.9.2): Das Flag wird **nicht** aus den
    # Rohdaten übernommen, sondern serverseitig aus der URL abgeleitet (nur
    # eigener Upload-Pfad + Origin dieser HA-Instanz, siehe
    # ``url_sicherheit.ist_eigene_upload_url``). Ein mitgeschicktes
    # ``hochgeladen`` wird nur noch auf den Typ geprüft (Format-
    # Kompatibilität), sein Wert aber ignoriert - sonst könnte ein
    # manipulierter Datensatz die private-IP-Prüfung (SSRF) umgehen.
    hochgeladen_roh = raw.get("hochgeladen", False)
    if not isinstance(hochgeladen_roh, bool):
        raise HofladenValidationError(f"{context}: 'hochgeladen' muss ein Bool sein.")
    bild_url = url.strip()

    return Bild(
        url=bild_url,
        beschreibung=(beschreibung.strip() if beschreibung else None) or None,
        hochgeladen=ist_eigene_upload_url(bild_url, eigene_origins),
    )


def _pruefe_anzahl(items: Any, field_name: str, maximum: int) -> None:
    if isinstance(items, (list, tuple)) and len(items) > maximum:
        raise HofladenValidationError(
            f"Feld '{field_name}' darf höchstens {maximum} Einträge enthalten "
            f"(aktuell {len(items)})."
        )


def _parse_list(
    raw: Mapping[str, Any],
    field_name: str,
    parse_item: Any,
    maximum: int | None = None,
) -> tuple:
    items = raw.get(field_name, []) or []
    if not isinstance(items, (list, tuple)):
        raise HofladenValidationError(f"Feld '{field_name}' muss eine Liste sein.")
    if maximum is not None:
        _pruefe_anzahl(items, field_name, maximum)
    return tuple(parse_item(item, i) for i, item in enumerate(items))


def bilder_mit_serverseitigem_flag(
    raw: Mapping[str, Any], hofladen: Hofladen
) -> list[Any] | None:
    """Die Bilder-Rohdaten mit dem **serverseitig abgeleiteten**
    ``hochgeladen``-Flag liefern (Befund F1).

    ``hofladen`` muss das Ergebnis von ``parse_hofladen(raw, ...)`` sein.
    Damit wird auch im Store/Export nie ein vom Client behauptetes Flag
    persistiert. ``None``, falls ``raw`` keine Bilder enthält (dann ist
    nichts zu ersetzen).
    """
    bilder_raw = raw.get("bilder")
    if not bilder_raw:
        return None
    return [
        {**dict(eintrag), "hochgeladen": bild.hochgeladen}
        for eintrag, bild in zip(bilder_raw, hofladen.bilder, strict=True)
    ]


def parse_hofladen(
    raw: Mapping[str, Any], *, eigene_origins: Iterable[str] = ()
) -> Hofladen:
    """Rohdaten eines Hofladens in das interne, typisierte Modell überführen.

    ``eigene_origins`` sind die Origins dieser Home-Assistant-Instanz (siehe
    ``instanz_origin.ermittle_eigene_origins``); nur Bild-URLs im Muster des
    eigenen Uploads auf einer dieser Origins erhalten ``Bild.hochgeladen``
    (Befund F1). Ohne Angabe ist das Flag immer ``False`` (fail-closed).

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
    if not _ID_REGEX.fullmatch(hofladen_id):
        raise HofladenValidationError(
            "Feld 'id' darf nur Buchstaben, Ziffern, '-' und '_' enthalten "
            "und höchstens 64 Zeichen lang sein."
        )
    name = _require_str(raw, "name")

    beschreibung = _optional_str(raw, "beschreibung")
    bemerkung = _optional_str(raw, "bemerkung")
    adresse = _optional_str(raw, "adresse")
    plz = _optional_str(raw, "plz")
    ort = _optional_str(raw, "ort")
    land = _optional_str(raw, "land")
    website = _optional_str(raw, "website")
    mobilnummer = _optional_str(raw, "mobilnummer")
    if mobilnummer is not None and not _TELEFON_REGEX.fullmatch(mobilnummer):
        raise HofladenValidationError(
            "Feld 'mobilnummer' darf nur Ziffern, Leerzeichen und die "
            "Zeichen + - / ( ) . enthalten."
        )
    email = _optional_str(raw, "email")
    if email is not None and not _EMAIL_REGEX.fullmatch(email):
        raise HofladenValidationError(
            "Feld 'email' ist keine gültige E-Mail-Adresse (genau ein '@', "
            "keine Leerzeichen und keines der Zeichen ? & % # < > \" ' , ;)."
        )
    bewertung = _parse_bewertung(raw)
    version = _parse_version(raw)

    latitude = _optional_float(raw, "latitude", _LATITUDE_MIN, _LATITUDE_MAX)
    longitude = _optional_float(raw, "longitude", _LONGITUDE_MIN, _LONGITUDE_MAX)

    oeffnungszeiten = _parse_list(
        raw, "oeffnungszeiten", _parse_oeffnungszeit, MAX_ANZAHL_OEFFNUNGSZEITEN
    )
    sonderoeffnungszeiten = _parse_list(
        raw,
        "sonderoeffnungszeiten",
        _parse_sonderoeffnungszeit,
        MAX_ANZAHL_SONDEROEFFNUNGSZEITEN,
    )
    angebote_raw = _migriere_kategorien_und_produkte_zu_angeboten(raw)
    _pruefe_anzahl(angebote_raw, "angebote", MAX_ANZAHL_ANGEBOTE)
    angebote = tuple(
        _parse_angebot(item, i) for i, item in enumerate(angebote_raw)
    )
    zahlungsarten = _parse_list(
        raw,
        "zahlungsarten",
        lambda item, i: _parse_lookup(item, i, "Zahlungsart", Zahlungsart),
        MAX_ANZAHL_ZAHLUNGSARTEN,
    )
    bilder = _parse_list(
        raw,
        "bilder",
        lambda item, i: _parse_bild(item, i, eigene_origins),
        MAX_ANZAHL_BILDER,
    )

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
