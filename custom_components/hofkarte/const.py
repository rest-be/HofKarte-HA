"""Konstanten für die HofKarte-Integration."""

from datetime import timedelta

DOMAIN = "hofkarte"

# Config Flow / Config Entry
DEFAULT_NAME = "HofKarte"

# Coordinator / Datenabruf
# Befund F6: Kein periodischer Abruf mehr. Die Daten ändern sich nur durch
# Schreibzugriffe über den Coordinator (inkrementelles Update, siehe
# coordinator.py); zeitabhängige Zustände (Geöffnet, Nächste Öffnung/
# Schliessung) aktualisieren sich zeitgenau über async_track_point_in_time
# (siehe entity.py/opening_hours.naechster_statuswechsel). Ein 15-Minuten-
# Raster war ungenau (bis zu 15 Minuten verspätet) und las bei jedem Lauf
# alle Datensätze neu ein.
DEFAULT_UPDATE_INTERVAL: timedelta | None = None
DEFAULT_FETCH_TIMEOUT_SECONDS = 30

# Sortiment und Eigenschaften (User Editierbar):
# Vorschlagswerte für den Fachbereich Zahlungsarten. Nutzer sind nicht auf
# diese Werte beschränkt – jeder beliebige Name ist zulässig (siehe
# parsing.py); dies ist lediglich ein sinnvoller Startkatalog, den z. B.
# ein künftiger Editier-Dialog vorschlagen kann. Die früheren Kataloge
# für „Verkaufsarten“ und „Merkmale“ wurden entfernt, da diese
# Fachbereiche selbst ersatzlos entfernt wurden (siehe CHANGELOG).
STANDARD_ZAHLUNGSARTEN: tuple[str, ...] = (
    "Bargeld",
    "Debitkarte",
    "Kreditkarte",
    "TWINT",
)

# Options Flow ("Einstellungen", Issue Options Flow): dauerhaft
# gespeicherte Vorgabewerte für die Verwaltungsoberfläche, analog zur
# globalen „Einstellungen“-Maske der parallel gepflegten iOS-App. Anders
# als z. B. STANDARD_ZAHLUNGSARTEN sind dies keine fachlichen
# Vorschlagswerte für Hofladen-Daten, sondern Bedienungs-Vorgaben für die
# Übersicht bzw. „Angaben automatisch ermitteln“ selbst.
CONF_LISTEN_SORT_SPALTE = "listen_sort_spalte"
CONF_LISTEN_SORT_RICHTUNG = "listen_sort_richtung"
CONF_OSM_RADIUS_METER = "osm_radius_meter"

DEFAULT_LISTEN_SORT_SPALTE = "name"
DEFAULT_LISTEN_SORT_RICHTUNG = "asc"
# An die iOS-App angeglichener Standardwert (siehe Options Flow) - weicht
# bewusst vom historischen, deutlich kleineren Fallback in osm_info.py
# (STANDARD_RADIUS_METER, weiterhin als harte Absicherung für den Fall
# genutzt, dass keine Config Entry ermittelt werden kann) ab.
DEFAULT_OSM_RADIUS_METER = 200

# Zulässige Werte für das Standard-Sortierfeld der Übersicht - müssen mit
# den in der Listenansicht sortierbaren Spalten in hofkarte-panel.js
# übereinstimmen (Name/Adresse/Status/Bewertung). "geoeffnet" ist dabei
# der dort bereits bestehende interne Spaltenname für "Status" (siehe
# ``sortierteGefilterteItems()``/``listTable()``) - bewusst beibehalten
# statt umbenannt, um die bestehende Sortierlogik nicht unnötig
# anzufassen.
LISTEN_SORT_SPALTEN: tuple[str, ...] = ("name", "adresse", "geoeffnet", "bewertung")
LISTEN_SORT_RICHTUNGEN: tuple[str, ...] = ("asc", "desc")


# --- Längen-/Mengenlimits (Befund F11, Code Review 2026.9.2) -----------------
#
# Obergrenzen für Hofladen-Rohdaten (siehe ``parsing.py``). Sie begrenzen
# den Speicher-/Rechenbedarf (Store, Coordinator-Refresh, Websocket-
# Antworten, Panel-Rendering) gegenüber manipulierten oder versehentlich
# riesigen Datensätzen und liegen deutlich über realen Nutzungswerten.
# Verletzung -> ``HofladenValidationError`` mit klarer Meldung; bestehende,
# zu grosse Datensätze werden beim Einlesen wie andere ungültige Datensätze
# übersprungen und protokolliert (der Coordinator-Lauf bricht nicht ab).
MAX_LAENGE_NAME = 200
MAX_LAENGE_TEXT = 5000  # beschreibung, bemerkung
MAX_LAENGE_ADRESSFELD = 200  # adresse, plz, ort, land
MAX_LAENGE_URL = 2048  # website, Bild-URL
MAX_LAENGE_EMAIL = 254  # RFC 5321
MAX_LAENGE_TELEFON = 40
MAX_ANZAHL_ANGEBOTE = 50
MAX_ANZAHL_ZAHLUNGSARTEN = 30
MAX_ANZAHL_BILDER = 20
MAX_ANZAHL_QUELLEN = 20  # Herkunftsangaben je Hofladen (höchstens eine je übernommenem Feld)
MAX_ANZAHL_OEFFNUNGSZEITEN = 100
MAX_ANZAHL_SONDEROEFFNUNGSZEITEN = 100
MAX_IMPORT_EINTRAEGE = 500  # Datensätze je Import
# Erlaubte IDs: Auto-IDs ``hofladen-<hex>`` bleiben gültig. Die ID landet in
# Entity-/Device-Kennungen sowie (im Panel) in HTML-Attributen.
ID_MUSTER = r"[A-Za-z0-9_-]{1,64}"
