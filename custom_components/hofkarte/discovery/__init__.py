"""Hofladen-Discovery: automatische Erkennung von Hofläden (Open-Source-Variante).

Phase 1-3 (``2026.10.1``): Kandidaten aus OpenStreetMap (Overpass) für eine
Koordinate ermitteln - ohne KI, ohne Cloud-Dienst, ohne Schlüssel. Das
Ergebnis sind ausschliesslich **Vorschläge zur Überprüfung**; gespeichert
wird nichts (das bleibt wie bei ``osm_info.py`` beim regulären Speichern
über die Verwaltungsoberfläche).

Aufbau:

- ``profile``  - Suchprofile als reine Daten (``farmshop``).
- ``text``     - Namens-Normalisierung und -Ähnlichkeit (``difflib``).
- ``geo``      - Entfernungsberechnung.
- ``scoring``  - Bewertung der Kandidaten (Nähe, Name, Website-Domain).
- ``website``, ``provenance``, ``enrich`` - Anreicherung (robots.txt, Herkunft je Feld).
- ``overpass`` - Query, Antwortprüfung, Kandidaten, Zusammenführung, Abruf.

Alles ausser ``overpass.async_suche`` ist frei von Home-Assistant-Importen
und damit isoliert testbar.
"""
