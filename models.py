"""Internes, typisiertes Datenmodell für Hofläden.

Dieses Modul enthält ausschliesslich die interne fachliche Darstellung
eines Hofladens. Es kennt keine Rohdatenformate, keine Home-Assistant-
Entities, keine Persistenz und keine Netzwerklogik – das ist bewusst nicht
Aufgabe dieses Moduls. Die Überführung von Rohdaten in dieses Modell erfolgt
getrennt in ``parsing.py``.

Alle Datenstrukturen sind unveränderlich (``frozen``), damit einmal
erzeugte Hofladen-Objekte nicht versehentlich mutiert werden können.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class Zahlungsart:
    """Eine akzeptierte Zahlungsart (z. B. „Bar“, „Twint“)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Angebot:
    """Ein im Hofladen angebotener Artikel bzw. eine angebotene Leistung.

    Ersetzt die früher getrennten Konzepte ``Kategorie`` und ``Produkt``
    (siehe CHANGELOG, Zusammenlegung zu „Angebote“). Bewusst eine
    **schlichte Auflistung ohne Gruppierung**: Ein früherer Versuch,
    Angebote zusätzlich mit frei formulierten Gruppen zu versehen
    (Feld ``gruppen``), wurde nach Rückmeldung wieder entfernt, da der
    Mehrwert der Gruppierung den zusätzlichen Pflegeaufwand nicht
    rechtfertigte. Ein Angebot ist damit strukturell nur noch ``id`` und
    ``name`` – ein reiner Produktname.
    """

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Bild:
    """Ein optionales Bild des Hofladens.

    ``hochgeladen`` unterscheidet über HofKartes geführten Upload
    erzeugte Bilder (Home Assistants eigene ``image_upload``-Komponente,
    URL zeigt auf die eigene Home-Assistant-Instanz) von frei
    eingegebenen externen URLs. Wird für die Sicherheitsprüfung in
    ``images.py`` benötigt: Eine von uns selbst über den offiziellen
    Upload-Weg erzeugte URL ist per Herkunft vertrauenswürdig, auch wenn
    sie auf eine private/interne Adresse der eigenen Home-Assistant-
    Installation zeigt (was für frei eingegebene externe URLs zu Recht
    abgelehnt wird, siehe Moduldoc dort). Standardmässig ``False``
    (bestehende, extern verlinkte Bilder ohne dieses Feld bleiben
    dadurch unverändert als "extern" behandelt).
    """

    url: str
    beschreibung: str | None = None
    hochgeladen: bool = False


@dataclass(frozen=True, slots=True)
class Oeffnungszeit:
    """Eine regelmässige wöchentliche Öffnungszeit (ein Intervall an einem
    Wochentag).

    ``wochentag`` folgt ISO 8601 (1 = Montag ... 7 = Sonntag), analog zu
    ``datetime.date.isoweekday()``. Mehrere Intervalle pro Wochentag sind
    zulässig (z. B. „08:00–12:00“ und „14:00–18:00“) und werden als separate
    ``Oeffnungszeit``-Objekte abgebildet.

    ``beginn``/``ende`` sind bewusst als naive ``datetime.time`` modelliert:
    Es handelt sich um wiederkehrende Uhrzeiten ohne festes Datum, keine
    absoluten Zeitpunkte. Die Auswertung gegen die tatsächliche
    Home-Assistant-Zeitzone (für den berechneten Öffnungsstatus) ist
    Aufgabe von ``opening_hours.py``, nicht dieses Moduls.
    """

    wochentag: int
    beginn: time
    ende: time


@dataclass(frozen=True, slots=True)
class Sonderoeffnungszeit:
    """Eine datumsbezogene Ausnahme von den regulären Öffnungszeiten.

    Deckt sowohl Sonderöffnungen (z. B. verlängerte Zeiten an Feiertagen)
    als auch vollständige Schliessungen (``geschlossen=True``, z. B. Ferien)
    über einen Datumsbereich ab. ``beginn``/``ende`` sind nur gesetzt, wenn
    ``geschlossen`` False ist.
    """

    datum_von: date
    datum_bis: date
    geschlossen: bool
    beginn: time | None = None
    ende: time | None = None


@dataclass(frozen=True, slots=True)
class Hofladen:
    """Interne, vollständig typisierte Darstellung eines Hofladens.

    ``id`` ist die stabile, eindeutige Kennung des Hofladens. Sie wird von
    der Datenquelle vorgegeben (siehe ``parsing.py``) und darf sich über
    die Zeit nicht ändern, da Devices und Entities sich
    darauf verlassen.

    ``bemerkung`` ist ein zusätzliches, von ``beschreibung`` unabhängiges
    Freitextfeld – gedacht für interne Notizen/Hinweise, die sich
    inhaltlich von der (potenziell öffentlich sichtbaren) Beschreibung
    unterscheiden sollen. Auf Hofladen-Ebene angesiedelt statt je Angebot,
    da Angebote seit der Vereinfachung zu einer schlichten Namensliste
    ohne weitere Struktur wurden (siehe ``Angebot``) und ein Bemerkungsfeld
    je Angebot diese bewusste Vereinfachung wieder aufgehoben hätte.
    """

    id: str
    name: str
    beschreibung: str | None = None
    bemerkung: str | None = None
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    website: str | None = None
    mobilnummer: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    oeffnungszeiten: tuple[Oeffnungszeit, ...] = ()
    sonderoeffnungszeiten: tuple[Sonderoeffnungszeit, ...] = ()
    angebote: tuple[Angebot, ...] = ()
    zahlungsarten: tuple[Zahlungsart, ...] = ()
    bilder: tuple[Bild, ...] = ()
    # Bewertung (0-5 Sterne, 0 = unbewertet). Bewusst ein einfacher Integer
    # statt eines eigenen Typs: Der Wertebereich ist klein und fest, eine
    # eigene Klasse würde hier keinen zusätzlichen Nutzen bringen (siehe
    # ``parsing.py`` für die Begrenzung/Validierung auf 0-5 beim Einlesen).
    bewertung: int = 0
    # Optimistische Versionierung für nebenläufige Schreibzugriffe mehrerer
    # Geräte (z. B. zwei Familienmitglieder mit der HofKarte-PWA, einer davon
    # offline). Beginnt bei 1 und wird von
    # ``coordinator.HofKarteUpdateCoordinator.async_save_hofladen`` bei jeder
    # erfolgreichen Aktualisierung um 1 erhöht - niemals direkt von
    # Aufrufern gesetzt. Ein Client, der einen Hofladen ändern möchte,
    # schickt die zuletzt bekannte Version mit; weicht diese von der
    # aktuell gespeicherten ab, wird die Änderung als Versionskonflikt
    # abgelehnt statt die zwischenzeitliche Änderung stillschweigend zu
    # überschreiben (siehe ``coordinator.HofladenVersionConflictError``).
    version: int = 1
