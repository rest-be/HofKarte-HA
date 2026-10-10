# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

**Versionierung:** Ab dem MVP-Release (`2026.9.0`) folgt HofKarte dem
Versionierungsschema von Home Assistant selbst:
`JAHR.MONAT.LAUFNUMMER` (z. B. `2026.9.0`, `2026.9.1`, `2026.10.0`).
Frühere Versionen (`0.1.0` bis `0.18.1`) folgten während der
Entwicklung, vor der ersten offiziellen Veröffentlichung, einer an
Semantic Versioning angelehnten, fortlaufenden Nummerierung und sind
unten als historische Entwicklungsdokumentation erhalten.

## [Unreleased]

### Geändert (2026.10.1-dev.12) – GUI-Überarbeitung, Phase 3 (Liste)

- Liste: Spalten Auswahl · Name & Adresse · Ort · Status · Bewertung · ⋮-Aktionen; Sortierköpfe mit `aria-sort`, feststehender Tabellenkopf, Hover- und Auswahl-Hervorhebung. Auf schmalen Bildschirmen entfallen Ort und Bewertung.
- Kopf-Checkbox wählt alle sichtbaren (gefilterten) Hofläden, mit Teilzustand.
- Je Zeile dasselbe ⋮-Menü wie in den Kacheln (Route, Bearbeiten, Löschen zuunterst); ein gemeinsamer Aufbau (`aktionenMenueHtml`). Neue Sortieroption «Ort».
- Behoben: Das ⋮-Menü (Kachel, Liste, Kopfzeile) war in manchen HA-Themes durchsichtig; es hat jetzt einen deckenden Hintergrund.

### Geändert (2026.10.1-dev.11) – GUI-Überarbeitung, Phase 2 (Kacheln)

- Kacheln: die ganze Kachel ist klickbar (öffnet die Details); Aktionen Route (Google/Apple Maps), Bearbeiten und Löschen liegen im ⋮-Menü der Kachel (Löschen zuunterst, rot, mit bestehender Rückfrage). Es ist immer nur ein Kachelmenü offen; Schliessen per Klick daneben oder Escape.
- Auswahl: Checkboxen erscheinen nur im neuen «Auswählen»-Modus (Schalter in der Steuerleiste); gewählte Kacheln sind hervorgehoben, die Kontextleiste (Export) bleibt im Modus sichtbar.
- Raster `repeat(auto-fill, minmax(260px, 1fr))`, einheitliche Kopfzeile je Kachel (Name, Adresse, Status, Bewertung, Webseite).
- Tests: Anpassung bestehender Kacheltests, 2 neue Tests.

### Geändert (2026.10.1-dev.10) – GUI-Überarbeitung, Phase 1

- Übersicht (Kacheln, Liste, Karte): gemeinsame **Kopfzeile** („Hofladen finden“,
  „+ Hofladen“, ⋮-Menü mit Import) und gemeinsame **Steuerleiste** mit Suche, Filter
  „Nur geöffnet“, Sortierung (Spalte + Richtung) und Ansichtsumschalter mit Icons.
- Suche, „Nur geöffnet“ und Sortierung gelten jetzt in **allen drei Ansichten** und
  bleiben beim Wechsel der Ansicht erhalten (Karte: filtert die Marker). Der Filter
  „Nur geöffnet“ der Karte ist damit der gemeinsame Filter; die Suche war bisher nur
  in der Liste vorhanden. Standardsortierung ist Name aufsteigend (vorher in der Liste
  unsortiert, solange keine Spalte gewählt war).
- Export: neue **Kontextleiste** („n ausgewählt · Alle auswählen · Auswahl aufheben ·
  Export“), nur sichtbar, wenn etwas gewählt ist; „Alle auswählen“ wählt nur die
  gefilterten Hofläden. Import liegt im ⋮-Menü.
- Zähler („3 von 8 Hofläden“) und Leerzustand „Keine Treffer“ mit „Filter
  zurücksetzen“; Teil-Updates beim Tippen (Fokus bleibt erhalten).
- Touch-Ziele ≥ 44 px, sichtbarer Fokus, ⋮-Menü per Escape/Klick daneben schliessbar.
- Tests: `tests/test_static_panel_js_uebersicht.py` (7 Verhaltenstests).

### Geändert (2026.10.1-dev.9)

- „Hofladen finden“, Schritt 1: Ist keine KI-Entität gewählt, zeigt der
  Dialog statt nichts einen Hinweis, wie die KI-Auswertung aktiviert wird
  (zuvor fehlte das Kästchen dann ohne Erklärung).

### Hinzugefügt (2026.10.1-dev.8, Hofladen-Discovery Phase 4: optionale KI)

- **Optionale KI-Auswertung** in „Hofladen finden“ über Home Assistants
  `ai_task.generate_data` (kein eigenes Provider-System, keine
  Zugangsdaten). Aktivierung zweistufig: Options-Flow-Feld
  **KI-Entität** (leer = aus) und Kästchen „Website-Text mit KI
  auswerten“ je Suche (nie vorangekreuzt, nennt die Entität und den
  Datenabfluss).
- Die KI ergänzt nur Angebote, Zahlungsarten und Öffnungszeiten. **Grounding
  durch HofKarte:** nur wörtlich im Seitentext stehende Werte gelten als
  belegt (`website_ki`, `confirmed`); unbelegte erscheinen getrennt als
  „Vermutungen“, nicht vorausgewählt, und werden als `ki`/`inferred`
  gespeichert. Öffnungszeiten nur mit belegtem Ausschnitt, den der
  bestehende Parser versteht.
- Schutz: festes Schema (drei Felder), Eingabelimits, entschärfter
  Seitentext (6 000/15 000 Zeichen), keine Werkzeuge, 60 s Zeitlimit,
  Ausfall ohne Folgen. Test für Prompt-Injection.
- `ws_enrich` akzeptiert `ki`; `ws_settings` liefert `ki_entitaet`;
  neues Ereignis `ki`.

### Dokumentation (2026.10.1-dev.7, Phase 6)

- `SECURITY.md`: neuer Abschnitt „Hofladen finden“ mit den beiden neuen
  Ausnahmen (mehrseitiger Website-Abruf mit `robots.txt`, Standort des
  Geräts im Browser) und den Schutzmassnahmen.
- `README.md`, `docs/handbuch.md`: Anleitung „Hofladen finden“,
  Datenschutz-Abschnitt (sechs statt vier Ausnahmen), Einschränkungen.
- `docs/architecture.md`: Abschnitt „Hofladen-Discovery“.
- `CONTRIBUTING.md`: Teststand aktualisiert.

### Behoben (2026.10.1-dev.6)

- Dialog „Hofladen finden“, Schritt 2 und 3: Radio-Button bzw. Checkbox
  wurden durch die globale Regel `input{width:100%}` auf volle Breite
  gezogen, der Text rutschte an den rechten Rand und war nicht lesbar.
  Auswahlelemente haben jetzt feste Breite, der Text nutzt die restliche
  Zeile (in Chromium bei 1000 und 380 px Breite geprüft).

### Geändert (2026.10.1-dev.5)

- Die Kopfzeile des Verwaltungs-Panels zeigt die geladene Panel-Fassung
  („Panel 2026.10.1-dev.5“). So lässt sich ohne Entwicklerwerkzeuge
  prüfen, ob der Browser/die App das aktuelle Panel-Skript verwendet
  (veralteter Cache). Neue Versionsnummer erzwingt zugleich eine neue
  Skript-URL (`?v=`).

### Hinzugefügt (2026.10.1-dev.4, Hofladen-Discovery Phase 5: Oberfläche)

- **Dialog „🔎 Hofladen finden“** im Verwaltungs-Panel (Listenansicht,
  neben „+ Neuer Hofladen“), drei Schritte:
  1. *Suchen:* Name und Website optional, Koordinaten, Umkreis (50 m bis
     5 km, Standard 2 km), erweiterte Suche. Beim Öffnen wird der
     **aktuelle Standort des Geräts** übernommen (Browser-Geolocation, mit
     Freigabe-Abfrage); ohne Freigabe/HTTPS bleibt der Standort der
     Home-Assistant-Installation eingetragen. Gesucht wird nie
     automatisch, sondern erst auf „Suchen“.
  2. *Kandidat wählen:* sortiert nach Score mit Konfidenz und Gründen
     (Nähe, Name, Website); Hinweis, wenn der Hofladen schon erfasst sein
     könnte; „Manuell erfassen“ und – bei angegebener Website – „Nur
     Website auswerten“ als Ausweg bei Lücken in OpenStreetMap.
  3. *Angaben prüfen:* Live-Fortschritt der Anreicherung, je Feld Quelle
     (mit Link), Hinweis bei abweichenden Quellen, Auswahl per Häkchen;
     „In Formular übernehmen“ öffnet das normale Bearbeitungsformular.
     Der Dialog speichert nichts.
- **Neues optionales Feld `quellen`** im Hofladen (Herkunft je Feld:
  `feld`, `quelle`, `status`, `url`, `lizenz`), validiert (bekannte
  Felder, nur http(s)-URLs, höchstens eine Angabe je Feld, höchstens 20),
  abwärtskompatibel (leer bei allen bestehenden Hofläden). Das Panel
  behält die Herkunft eines Feldes nur, solange es nach der Übernahme
  nicht von Hand geändert wurde. Die Detailansicht zeigt einen Abschnitt
  „Herkunft der Angaben“ (mit ODbL-Hinweis für OpenStreetMap).
- Geändert: Der Regressionstest `test_panel_js_verwendet_keine_geolocation_api_mehr`
  (Issue #3, Geräte-Entfernung bleibt entfernt) wurde zu
  `…_nur_fuer_den_finden_dialog`: die Browser-Geolocation darf jetzt
  ausschliesslich in `ermittleGeraeteStandort()` vorkommen, inklusive
  ausdrücklicher Prüfung auf einen sicheren Kontext (HTTPS/localhost).

### Hinzugefügt (2026.10.1-dev.3, Hofladen-Discovery Phase 3: Anreicherung)

- **WebSocket-Befehl `hofkarte/management/enrich`** (nur Administratoren,
  Subscription, deterministisch, ohne KI): reichert einen Kandidaten
  (Ergebnis von `discover`) und/oder eine Website-Adresse an. Das
  Ergebnis bestätigt die Subscription, danach folgen Ereignisse
  `osm` → `website` → `fertig`; `fertig` enthält den Vorschlag im
  bestehenden Hofladen-Format mit `quellen` je Feld und `abweichungen`.
  Gespeichert wird nichts. Probleme bei der Website stehen als `status`
  im Ereignis `website` und brechen nichts ab. Fehlercodes `not_ready`,
  `invalid_format`.
- **`discovery/website.py`:** konservativer Mehrseiten-Abruf. `robots.txt`
  wird vor jedem Abruf ausgewertet (RFC 9309: 4xx = erlaubt, 5xx oder
  Netzwerkfehler = nichts abrufen, `Disallow` für `HofKarte`/`*`
  respektiert), eigener User-Agent mit Projekt-URL, höchstens 4 Seiten
  (Startseite plus Kontakt-/Öffnungszeiten-/Laden-Links desselben Hosts,
  eine Ebene), Pause zwischen Seiten, keine Dateien/Logins. SSRF-Schutz
  und Extraktion von `webseite_info.py` werden wiederverwendet.
- **`discovery/provenance.py`:** Zusammenführung von OSM und Website mit
  Quellenpriorität je Feld (OSM-Angaben tragen „© OpenStreetMap-
  Mitwirkende (ODbL)“). Beschreibungstexte werden nicht übernommen.
- `webseite_info._hole_html` akzeptiert optional `headers` und
  `erlaubte_typen`; `WebseiteNichtErreichbarError.status` trägt den
  HTTP-Status. Ohne diese Angaben unverändertes Verhalten.
- Noch nicht enthalten: das persistente Feld `quellen` im gespeicherten
  Hofladen-Modell (folgt als eigener Schritt, zusammen mit der
  Oberfläche).

### Hinzugefügt (2026.10.1-dev.2, Hofladen-Discovery Phase 2: Bewertung)

- **`discovery/scoring.py`:** Kandidaten werden mit einem Score (0..1) und
  einer Konfidenz („hoch“/„mittel“/„niedrig“) bewertet. Signale: Nähe
  (bis 25 m volle Punktzahl, danach glatter Abfall), Namensähnlichkeit
  (nur eines von mehreren Signalen, da OSM-Namen oft vom Betriebsnamen
  abweichen), Website-Domain (stark, namensunabhängig). Bei ≤ 25 m
  mindestens 0,85; unbenannte Kandidaten werden nicht abgewertet.
  Schwellen sind Startwerte, kalibriert an den Messdaten (Phase 0);
  der Name verbessert bei grossem Koordinatenversatz die Trefferlage
  gegenüber reiner Distanz.
- `hofkarte/management/discover` nimmt optional `name` und `website`
  entgegen und liefert pro Kandidat `score`, `konfidenz` und `signale`;
  die Liste ist nach Score sortiert (ohne Angaben: nach Nähe).

### Hinzugefügt (2026.10.1-dev.1, Hofladen-Discovery Phase 1)

- **Hofladen-Discovery (Open-Source-Variante, ohne KI):** neues Paket
  `custom_components/hofkarte/discovery/` ermittelt Hofladen-Kandidaten
  für eine Koordinate aus OpenStreetMap (Overpass) – nur Vorschläge,
  nichts wird gespeichert.
  - `profile.py`: Suchprofil `farmshop` als Daten. Standardfilter ist
    nur `["shop"="farm"]` (in der Messung günstig und mit allen in OSM
    vorhandenen Hofläden); weitere Filter nur über `erweitert=true`
    (nicht gemessen).
  - `overpass.py`: Query, Antwortprüfung, Kandidaten, Cache. Eine
    Antwort mit leerem `elements` und `remark` „runtime error“ gilt als
    Fehler (nicht als „keine Treffer“) und wird nie gecacht. Unbenannte
    Objekte und Namensvarianten (`brand`, `operator`, `alt_name`,
    `name:fr`, …) bleiben Kandidaten. Doppelt erfasste Objekte
    (Gebäude + Punkt, ≤ 30 m, gleicher/ähnlicher Name, gleiche
    Website-Domain oder ein Objekt ohne Namen) werden zu einem Kandidaten
    zusammengeführt.
  - `text.py` (`difflib`, keine neue Abhängigkeit) und `geo.py`.
- **WebSocket-Befehl `hofkarte/management/discover`** (nur Administratoren):
  `latitude`, `longitude`, optional `radius` (Standard 2 000 m, 50–5 000 m)
  und `erweitert`. Fehlercodes `not_ready`, `invalid_coordinates`,
  `unreachable`; keine Treffer ergeben eine leere Liste.
- Der HTTP-Abruf (mehrere Overpass-Instanzen, Gesamtbudget, Grössenlimit)
  wird von `osm_info.py` wiederverwendet und blieb unverändert; die
  Funktion „Ort in der Nähe suchen“ verhält sich wie bisher.

## [2026.10.0] - 2026-10-06

Enthält die in den Entwicklungsversionen `2026.10.0-dev.4` bis `-dev.7`
(Code-Review-Umsetzung, Blöcke A–D) und den bisher unveröffentlichten
Änderungen (Abschnitt „Fortsetzung“ unten) entwickelten und im Release
Candidate `2026.10.0-rc.1` abschliessend geprüften Änderungen; ergänzt
um den Foto-Upload per WebSocket.

### Hinzugefügt

- **WebSocket-Befehl `hofkarte/management/upload_image`
  (Foto-Upload ohne CORS):** Die Mobile PWA (ab 1.11.0) lädt Fotos
  Base64-kodiert über die bereits bestehende WebSocket-Verbindung
  hoch. Dadurch ist für den Foto-Upload **kein
  `cors_allowed_origins`** mehr nötig. Der Befehl ist nur für
  Administratoren zugelassen, nimmt `filename`, `content_type`
  (nur `image/jpeg`, `image/png`, `image/gif`) und `data` entgegen,
  begrenzt die Rohdaten auf 3 MiB (WebSocket-Limit von Home Assistant:
  4 MiB), bereinigt den Dateinamen und legt das Bild über die
  `image_upload`-Komponente von Home Assistant ab (identisch zum
  REST-Upload; Auslieferung via `/api/image/serve/<id>/original`).
  Antwort: `{"id": "<Bild-ID>"}`. Fehlercodes: `invalid_data`,
  `not_ready`, `upload_failed`. Grössere Dateien nutzt die PWA weiter
  über den REST-Weg (dort ist CORS weiterhin nötig).

### Geändert

- Neue Datei `RELEASE_NOTES_2026.10.0.md`.

## [2026.10.0-dev.7] - Entwicklungsversion (develop)

Kein produktiver Release. Setzt Block D der Code-Review-Befunde zu
`2026.9.2` um (F5, F6, Rest von F14).

### Geändert

- **F5 – Batch-Schreiben, inkrementelles Update:** Neue Provider-
  Operation `async_apply_changes` (atomar, ein `Store.async_save`, unter
  dem Lock; auch im `StaticTestDataProvider`). Der Coordinator setzt nach
  `async_save_hofladen`/`async_add_hofladen`/`async_update_hofladen_sortiment`/
  `async_delete_hofladen` den validierten Stand inkrementell in
  `coordinator.data` ein (`async_set_updated_data`), kein
  `async_refresh()` mit Neu-Parsen aller Datensätze mehr. Neu:
  `async_save_many`, `bereite_save_vor`, `async_schreibe_vorbereitete`.
  `ws_import_commit` validiert jeden Eintrag einmal, schreibt dann **einmal**
  und löst **ein** Update aus (vorher je Eintrag ein Schreibvorgang plus
  Refresh, doppeltes Parsen). Die Fail-Fast-Garantie bleibt (auch
  Versionskonflikte werden jetzt vor dem ersten Schreiben erkannt).
  Duplikatsuche beim Import über einen Namensindex (`_DuplikatIndex`,
  Semantik unverändert).
- **F6 – zeitgenaue Statuswechsel:** `update_interval` ist jetzt `None`
  (kein 15-Minuten-Polling). Binary Sensor „Geöffnet“ sowie die Sensoren
  „Nächste Öffnung/Schliessung“ planen mit `async_track_point_in_time`
  den nächsten Statuswechsel (neue hass-freie Funktion
  `opening_hours.naechster_statuswechsel`: nächster Intervallbeginn/-ende
  oder Mitternacht; Zeitzonen-/DST-Logik der bestehenden Intervallbildung),
  planen nach jedem Tick neu, rechnen bei Datenänderung neu und melden
  Timer über `async_on_remove` ab. `async_sync_devices` läuft nur noch bei
  geänderter Menge/geänderten Namen der Hofläden.
- **F14 (Rest):** `cache_headers=True` für die statischen Panel-Dateien
  (URLs tragen `?v=<Version>`). Overpass: Gesamtbudget 40 s (statt bis zu
  75 s) und 10-Minuten-Cache (32 Einträge). README/SECURITY.md um
  Obergrenzen, Kontaktdaten-Datenschutz (unverschlüsselt in
  `.storage/`, Teil von Backups) und die SSRF-Prüfung ergänzt.

## [2026.10.0-dev.6] - Entwicklungsversion (develop)

Kein produktiver Release. Setzt Block C der Code-Review-Befunde zu
`2026.9.2` um (F7, F8, F9, F10, F14 – Panel-Teil).

### Sicherheit

- **F7 – Leaflet lokal gebündelt, kein CDN mehr:** Leaflet `1.9.4`
  (BSD-2-Clause) und `leaflet.markercluster` `1.5.3` (MIT) liegen
  unverändert unter `static/vendor/` und werden von Home Assistant
  ausgeliefert (`/api/hofkarte/static/vendor/…?v=<Version>`). Neu:
  `THIRD_PARTY_NOTICES.md` (Lizenzen, Herkunft, SHA-256); SECURITY.md,
  README und Architekturdokument angepasst.

### Behoben

- **F8 – Kein Render-Loop bei Leaflet-Ladefehler:** Der Fehlerpfad von
  `initKarte()` ruft nicht mehr `render()` auf (vorher: Fehler → Render →
  `initKarte()` → erneuter Ladeversuch → …). Meldung per `textContent`,
  fehlgeschlagenes `<script>` wird entfernt, erneuter Versuch nur über
  „Erneut versuchen“ bzw. ausdrücklichen Wechsel in die Kartenansicht.
- **F9 – Keine Dauer-Neuladung nach Ladefehler:** `_loadFailed` verhindert
  das Neuladen bei jeder `hass`-Änderung; stattdessen Backoff (2 s … max.
  60 s) und Button „Erneut versuchen“. `_loading`-Schutz bleibt.

### Geändert (Performance, F10/F14)

- `<style>` und Leaflet-CSS werden einmalig angelegt; `render()` ersetzt
  nur `<main>`.
- Event-Delegation auf `<main>` statt Listener je Kachel/Zeile/Render.
- Listenfilter entprellt (150 ms) mit Teil-Update von `<tbody>`;
  Auswahl aktualisiert nur Zähler/Export-Knopf/Checkboxen.
- Such-/Sortierschlüssel je Hofladen einmal vorberechnet.
- Karte wird einmal erzeugt; bei Filter-/Datenänderung nur die
  Marker-Ebene getauscht; Abbau nur beim Verlassen der Kartenansicht;
  ein gemeinsamer Popup-Handler; `isConnected`-Prüfung nach dem Laden.
- Clustering ab 200 Markern (`leaflet.markercluster`).
- **F14 (Panel):** Kacheln und Editor laden eigene Uploads als
  256×256-Vorschau (Original nur in der Detailansicht, Rückfall auf das
  Original bei Fehler), `decoding="async"`.
- Messung (jsdom, 500 synthetische Hofläden): Listener-Registrierungen
  bei 5 Filtereingaben 4494 → 0, bei 5 Auswahl-Klicks 4350 → 0, beim
  Öffnen der Liste 1014 → 6; neue DOM-Knoten bei 5 schnellen
  Filtereingaben 29 303 → 5 636 (ein Teil-Update); Kartenansicht beim
  Öffnen 2544 → 50 DOM-Knoten (geclustert).

## [2026.10.0-dev.5] - Entwicklungsversion (develop)

Kein produktiver Release. Setzt Block B der Code-Review-Befunde zu
`2026.9.2` um (F4, F11, F12).

### Sicherheit

- **F4 – SSRF-Prüfung gehärtet (`url_sicherheit.py`):** Hostname wird
  normalisiert (Kleinschreibung, abschliessender Punkt, IDNA). Abgelehnt
  werden jetzt `localhost.`, `*.localhost`, `*.local`, `*.internal`,
  `*.lan`, `*.home.arpa`, Einzel-Label-Hosts (`homeassistant`), unübliche
  IPv4-Schreibweisen (`127.1`, `0`, `2130706433`, `0x7f000001`,
  `017700000001`), IPv4-gemappte/NAT64/6to4-IPv6-Adressen auf interne Ziele
  sowie CGNAT (`100.64.0.0/10`) u. a. – statt der Negativliste gilt die
  Positivprüfung `is_global`.
- **F4 – DNS-Rebinding-Schutz beim Website-Abruf (`webseite_info.py`):**
  Jeder Hostname (Erstanfrage und jeder Weiterleitungssprung) wird
  asynchron aufgelöst, **alle** A/AAAA-Einträge müssen öffentlich sein
  (gemischte Antworten werden abgelehnt, z. B. `127.0.0.1.nip.io`), die
  Verbindung nutzt genau die geprüften Adressen. Fehlerfall wie bisher
  („nicht erlaubtes Ziel“). Dafür nutzt der Abruf eine eigene,
  kurzlebige `aiohttp`-Session statt der geteilten Home-Assistant-Session.
  Die Bild-URL-Prüfung (`image_url`) bleibt syntaktisch; die Grenze ist in
  `images.py` dokumentiert.
- **F11 – Längen-/Mengenlimits (`parsing.py`, `const.py`):** Name ≤ 200,
  Beschreibung/Bemerkung ≤ 5 000, Adressfelder ≤ 200, Website/Bild-URL
  ≤ 2 048, E-Mail ≤ 254, Telefon ≤ 40; ≤ 50 Angebote, ≤ 30 Zahlungsarten,
  ≤ 20 Bilder, ≤ 100 Öffnungs- und ≤ 100 Sonderöffnungszeiten;
  höchstens 500 Datensätze je Import. `id`: `[A-Za-z0-9_-]{1,64}`;
  E-Mail: einfache Formatprüfung (genau ein `@`, kein Leerraum, kein
  `? & % # < > " ' , ;`); Telefon: nur Ziffern, Leerzeichen und `+ - / ( ) .`.
  **Hinweis:** Bestehende Datensätze, die diese Regeln verletzen (z. B.
  eine ID mit Leerzeichen), werden beim Einlesen wie bisher
  übersprungen und im Log gewarnt (der Coordinator-Lauf bricht nicht ab).
- **F12 – Panel-Härtung (`hofkarte-panel.js`):** `escAttr` für alle
  datenbasierten `data-*`-/`value`-Attribute; Bilder werden nur bei
  sicherer URL geladen (`istSichereBildUrl`, sonst Platzhalter) und mit
  `referrerpolicy="no-referrer"`; `mailto:`-Link nur bei validierter
  Adresse; Import-Datei höchstens 2 MB und 500 Einträge (vor dem Lesen/
  Parsen geprüft).

## [2026.10.0-dev.4] - Entwicklungsversion (develop)

Kein produktiver Release. Setzt Block A der Code-Review-Befunde zu
`2026.9.2` um (F3, F1, F2, F13). Die in `[Unreleased]` unten
beschriebenen Änderungen (`dev.1`–`dev.3`) bleiben unverändert gültig.

### Sicherheit

- **F1 – `Bild.hochgeladen` wird serverseitig abgeleitet:** Das Flag, das
  die private-IP-Prüfung für Bild-URLs aussetzt, wurde bisher ungeprüft
  aus Client-/Importdaten übernommen; ein manipulierter Datensatz
  (`{"url": "http://192.168.1.20/relay/0?turn=on", "hochgeladen": true}`)
  umging damit den SSRF-Schutz. Es gilt jetzt nur noch für URLs im
  exakten Muster des eigenen Uploads (`/api/image/serve/<32 Hex>/…`) auf
  einer Origin dieser Home-Assistant-Instanz (neu:
  `url_sicherheit.ist_eigene_upload_url`, `instanz_origin.py`).
  Durchgesetzt in `parse_hofladen` (damit in `ws_save`, Import und beim
  Lesen bestehender Store-Daten); gespeicherte und exportierte Daten
  tragen nie ein behauptetes Flag. Das Panel löscht hochgeladene Bilder
  (`image/delete`) nur noch für URLs des eigenen Origins
  (`eigeneUploadImageId`). Nach dem Start von Home Assistant werden die
  Daten einmal neu eingelesen, damit die automatisch erkannte lokale
  Adresse berücksichtigt ist.
- **F2 – Quadratische Regex-Laufzeit behoben:** Adress- und
  E-Mail-Heuristik der Website-Auswertung konnten die Event-Loop blockieren
  (Messung: ≈ 13 s bei 20 000 Zeichen). Muster begrenzt (Wort-, Local-Part-,
  Domain-Längen, Wortgrenzen-Lookbehind), Eingabe gekappt
  (`MAX_SICHTBARER_TEXT_ZEICHEN`, `MAX_ZEILE_ZEICHEN`), E-Mail-Suche nur bei
  `@`, Auswertung im Executor mit Zeitlimit
  (`EXTRAKTION_TIMEOUT_SEKUNDEN`).

### Behoben

- **F3 – Options Flow:** Expliziter Konstruktor mit
  `self.config_entry = …` entfernt (ab Home Assistant 2025.12 ohne Setter,
  die Einstellungen-Maske wäre dort nicht mehr öffnbar). Die
  Auswahlfelder nutzen jetzt `SelectSelector` mit übersetzten Labels.
  Keine Anhebung der Mindestversion nötig (`hacs.json` ≥ 2025.1.0).
- **F13 – Robustheit:** `RecursionError` bei tief verschachteltem JSON-LD
  abgefangen, `_flatten_json_ld` iterativ; `ws_save` meldet
  `DuplicateHofladenIdError`/`HofladenNotFoundError` als `duplicate_id`
  bzw. `not_found` statt unbehandelt.

## [2026.10.0] - Fortsetzung (vormals „Unveröffentlicht“)

### Hinzugefügt

- **Action `hofkarte.hoflaeden_in_naehe`:** Liefert Hofläden innerhalb
  eines Radius um einen beliebigen, mitgegebenen Standort
  (`latitude`/`longitude`/`radius_meter`), sortiert nach Entfernung,
  optional nur aktuell geöffnete (`nur_geoeffnet`). Anders als der
  bestehende `Entfernung`-Sensor und die Action `hoflaeden_suchen`
  (beide gegen die fixe, konfigurierte Home-Assistant-Position) prüft
  diese Action gegen einen beliebigen Standort, der bei jedem Aufruf
  frisch übergeben wird – Grundlage für Nähe-Benachrichtigungen anhand
  des tatsächlichen, aktuellen Gerätestandorts (z. B. aus einer
  `person`-/`device_tracker`-Entity der Home Assistant Companion App).
  Es werden weiterhin keine Standortdaten durch die Integration
  gespeichert oder verfolgt.
- **Automation-Blueprint „HofKarte – Benachrichtigung bei Hofladen in
  der Nähe“** (`blueprints/automation/hofkarte/naehe_benachrichtigung.yaml`):
  nutzt die neue Action, um bei jeder Standortänderung einer Person
  oder eines Geräts zu prüfen, ob ein Hofladen in der Nähe liegt, und
  löst dafür eine frei wählbare Benachrichtigungs-Aktion aus.
- **README-Abschnitt „Mobile PWA“:** Hinweis auf die unabhängig
  entwickelte, unter `rest-be/HofKarte-PWA` gepflegte Progressive Web
  App, die HofKarte als Client dieser Integration nutzt (eigener
  Admin-Benutzer, CORS-Einstellung, HTTPS/DuckDNS).
- **Parameter `min_bewertung` für `hofkarte.hoflaeden_in_naehe`:**
  filtert optional auf Hofläden mit mindestens dieser Bewertung (0–5)
  – ein einfacher „nur Favoriten“-Filter, der das bestehende, geteilte
  `bewertung`-Feld wiederverwendet statt ein eigenes Favoriten-Feld
  einzuführen. Die Service-Antwort liefert neu auch die Bewertung pro
  Treffer. Das Automation-Blueprint „Benachrichtigung bei Hofladen in
  der Nähe“ bekommt dafür den neuen Eingabeparameter „Mindestbewertung
  (nur Favoriten)“ sowie die `bewertung`-Vorlagenvariable für die
  Benachrichtigungs-Aktion. Dazu eine neue Schritt-für-Schritt-
  Einrichtungsanleitung im README für die Nähe-Benachrichtigung über
  die Home Assistant Companion App.
- **Optimistische Versionierung je Hofladen (neues Feld `version`):**
  jeder Hofladen trägt neu eine fortlaufende Versionsnummer (Start
  bei 1, wird bei jeder Aktualisierung um 1 erhöht). Grundlage für
  verlässlichen Offline-Sync mehrerer Geräte (siehe HofKarte-PWA,
  Vorgehensplan Phase 8b): Schickt ein Aufrufer beim Aktualisieren
  eines Hofladens über die WebSocket-Action
  `hofkarte/management/save` eine `version` mit, die nicht mehr mit
  der aktuell gespeicherten übereinstimmt (ein anderes Gerät hat
  zwischenzeitlich bereits synchronisiert), wird die Änderung
  **nicht** stillschweigend überschrieben, sondern als Ergebnis mit
  `"konflikt": true` und dem aktuellen Serverstand zurückgemeldet.
  Fehlt `version` (ältere Aufrufer, Import), wird wie bisher ohne
  Prüfung gespeichert – vollständig abwärtskompatibel. Die
  mitgelieferte Verwaltungsoberfläche (`hofkarte-panel.js`) nutzt dies
  automatisch mit, da sie den zuletzt geladenen Hofladen-Datensatz
  (inkl. `version`) beim Speichern unverändert zurückschickt.

## [2026.9.2] - 2026-09-30

Enthält die in den sieben Entwicklungsversionen `2026.9.2-dev.1` bis
`-dev.7` (Issues #8–#11) entwickelten Änderungen. Für diesen Release
gab es – anders als bei `2026.9.1` – keinen eigenen Release-Candidate-
Schritt; die Konsolidierung erfolgte direkt auf Basis von `dev.7`.

### Hinzugefügt

- **Automatische Ermittlung von Website-Angaben (Issue #8/#9):** Im
  Bearbeitungsformular ruft der Button „🔎 Infos ermitteln“ (Abschnitt
  „Kontakt & Webseite“) auf ausdrücklichen Klick die dort eingetragene
  Website-Adresse ab und wertet ausschliesslich strukturierte, von der
  Seite selbst veröffentlichte Daten (schema.org-JSON-LD, ergänzend
  `<title>`/Meta-Beschreibung sowie – falls kein JSON-LD vorliegt –
  dokumentierte Text-Heuristiken für Adresse und Öffnungszeiten) aus,
  um Name, Adresse, Beschreibung, Öffnungszeiten, Angebote und
  Zahlungsarten als Vorschlag zu ermitteln. Rein lokale, deterministische
  Extraktion – kein externer/Cloud-/KI-Dienst. Ermittelte Angaben
  erscheinen in einem Bestätigungs-Popup zur Prüfung; erst ein Klick auf
  „Übernehmen“ überträgt sie ins Formular, „Abbrechen“ verwirft sie
  vollständig – es wird dabei nie automatisch gespeichert.
- **„Ort in der Nähe suchen“ über OpenStreetMap (Issue #10):** Zweite
  Datenquelle über die freie, kostenlose, kontofreie
  OpenStreetMap-Overpass-API: sucht anhand der im Formular eingetragenen
  Koordinaten nach benannten, hofladenartigen Orten in der Nähe und
  bietet sie, bei mehreren Treffern über eine Trefferauswahl, zur
  Übernahme über dasselbe Bestätigungs-Popup an. Gehärtet über mehrere
  bekannte Overpass-Instanzen als automatischen Fallback
  (`overpass-api.de`, `overpass.private.coffee`, `overpass.osm.ch`)
  sowie ausführliche Fehlerprotokollierung, falls eine Instanz
  fehlschlägt.
- **Eine gemeinsame Aktion „🔍 Angaben automatisch ermitteln“
  (Issue #11):** Die bis dahin getrennten Funktionen „Infos ermitteln“
  (Website) und „Ort in der Nähe suchen“ (OpenStreetMap) wurden zu einer
  einzigen Aktion zusammengelegt, die – je nach im Formular vorhandener
  Website-Adresse und/oder Koordinaten – wahlweise beide Quellen
  parallel abfragt und die Ergebnisse in einem gemeinsamen Vorschlag
  zusammenführt (je Feld mit Herkunftskennzeichnung Website/
  OpenStreetMap). Der Suchradius für die OpenStreetMap-Suche ist dabei
  im Formular einstellbar. Die OpenStreetMap-Suche wurde ausserdem um
  den Tag `amenity=marketplace` sowie eine Namens-Heuristik für
  untertaggte Hofgelände (`landuse=farmyard`/`building=farm` mit
  passendem Namen) erweitert.
- **Kontaktfelder Mobilnummer und E-Mail:** Neue, optionale Felder im
  Datenmodell, durchgängig berücksichtigt im Bearbeitungsformular
  (Abschnitt „Kontakt & Webseite“), in der Detailansicht (anklickbare
  Telefon-/E-Mail-Links), bei Export/Import sowie bei der automatischen
  Ermittlung (Website-Analyse und OpenStreetMap-Suche liefern jetzt
  ebenfalls Telefon/E-Mail, sofern verfügbar).
- **Bewertung (0–5 Sterne):** Neues Bewertungsfeld je Hofladen mit
  interaktiver Sterne-Auswahl im Bearbeitungsformular, Anzeige in der
  Detailansicht, eigenem, sortierbarem Sensor je Hofladen-Device sowie
  als zusätzliche, sortierbare Spalte in der Listenansicht bzw. kleiner
  Anzeige neben dem Status-Badge in der Kachelansicht.
- **Neue „Einstellungen“-Maske (Options Flow):** Über die Integration
  erreichbare, dauerhaft gespeicherte Voreinstellungen für die
  Übersicht (Standard-Sortierfeld und -richtung) sowie für „Angaben
  automatisch ermitteln“ (dauerhaft gespeicherter Standard-Suchradius,
  Bereich jetzt 20–2000 m, Standard 200 m – zuvor nur pro
  Formularsitzung flüchtig, 10–500 m, Standard 50 m).
- **Kartenmarker nach Öffnungsstatus eingefärbt:** Marker in der
  eingebetteten Kartenansicht sind jetzt grün (geöffnet) bzw. grau
  (geschlossen) eingefärbt statt einheitlich in der
  HA-Theme-Primärfarbe, analog zur bereits bestehenden Statusfarbgebung
  in Kacheln-/Listenansicht.

### Behoben

- **Datenverlust im Bearbeitungsformular nach „Infos ermitteln“
  (Issue #9):** Ein Klick auf „Infos ermitteln“ liess zuvor jeden
  bereits im Formular eingetragenen, aber noch nicht gespeicherten Wert
  verschwinden, da der abschliessende Re-Render das Formular
  ausschliesslich aus dem internen Bearbeitungszustand neu aufbaute.
  Behoben durch eine vollständige Erfassung des Formularzustands vor
  jedem mit der automatischen Ermittlung verbundenen Re-Render.
- **„Die Overpass API (OpenStreetMap) konnte nicht erreicht werden.“**
  bei „Ort in der Nähe suchen“: verbesserte Fehlerprotokollierung sowie
  mehrere Overpass-Instanzen als Fallback (siehe oben), ein
  identifizierender `User-Agent`-Header, der kombinierte
  `nwr`-Selektor sowie angepasste Timeouts adressieren die
  dokumentierten, wahrscheinlichsten Ursachen (Überlastung der
  Haupt-Instanz, fehlender `User-Agent`). Aus dieser
  Entwicklungsumgebung heraus ohne Netzwerkzugriff auf die
  Overpass-Instanzen nicht direkt reproduzierbar gewesen.

### Tests

- 572 Tests insgesamt (zuvor 366 bei `2026.9.1`), `pyflakes`/`mypy`/
  `node --check` durchgehend fehlerfrei.

## [2026.9.1] - 2026-09-19

Enthält die in den sieben Entwicklungsversionen `2026.9.1-dev.1` bis
`-dev.7` (Issues #1–#6) entwickelten und im Release Candidate
`2026.9.1-rc.1` abschliessend geprüften Änderungen.

### Hinzugefügt

- **Übersicht als Kacheln oder Liste (Issue #1):** Neuer Umschalter
  „🔲 Kacheln“/„📋 Liste“ oberhalb der Hofladen-Übersicht.
  - **Kacheln:** erweitert um Hauptbild (mit neutralem Platzhalter ohne
    gültiges Bild), klickbaren Namen (öffnet die Detailansicht,
    zusätzlich zum bestehenden „Details“-Button), anklickbare Webseite,
    Öffnungsstatus-Badge und einen Karten-Button bei hinterlegten
    Koordinaten (letzterer mit Issue #3 durch die Routing-Auswahl
    ersetzt, siehe unten).
  - **Liste (neu):** sortierbare Tabelle (Name, Adresse, Status – jede
    Spalte einzeln, beide Richtungen), Freitextfilter über Name/Adresse,
    Karten-Button je Zeile. Vollständig clientseitig, kein neuer
    Backend-Endpunkt für Sortierung/Filterung nötig.
  - `management.py` liefert seither zwei neue, serverseitig berechnete
    Felder über `ws_list`/`ws_save` (`geoeffnet`, `hauptbild_url`), um
    Duplikation sicherheitsrelevanter bzw. zeitzonenabhängiger Logik in
    JavaScript zu vermeiden – keine Breaking Changes an bestehenden
    WebSocket-Verträgen. 8 neue Backend-Tests (`test_management.py`).
- **Übersicht als Karte (Issue #2):** Dritte Umschalter-Option
  „🗺️ Karte“ – Marker je Hofladen mit gültigen Koordinaten, Popup mit
  Name und Button „Zur Detailansicht“, automatische Kartenausschnitt-
  Anpassung (`fitBounds`), Checkbox „Nur aktuell geöffnete Hofläden
  anzeigen“ (unbekannter Status gilt konsequent **nicht** als
  geöffnet), klare Fehlermeldung statt leerer Fläche bei
  nicht ladbarer Kartenbibliothek. **Neue, bewusst dokumentierte
  Abhängigkeit:** [Leaflet](https://leafletjs.com/) `1.9.4`
  (BSD-2-Clause) mit OpenStreetMap-Kartenkacheln, ausschliesslich per
  `<script>`/`<link>` von einem CDN mit fest gepinnter Version
  nachgeladen (kein „latest“, keine Paketverwaltung, keine
  Build-Pipeline), erst beim ersten Öffnen der Kartenansicht geladen.
  Begründung und geprüfte Alternativen siehe `docs/architecture.md`.
- **Export/Import von Hofläden (Issue #5):** In Kachel- und Listenansicht
  können einzelne Hofläden per Checkbox ausgewählt und über einen
  „Export“-Button als eine JSON-Datei (Liste von Hofladen-Objekten,
  identisch zum internen Datenmodell) heruntergeladen werden. Ein
  „Import“-Button erlaubt die Auswahl einer solchen JSON-Datei; die
  Struktur wird serverseitig validiert (neuer WebSocket-Befehl
  `hofkarte/management/import_preview`) und mit einer klaren
  Fehlermeldung abgelehnt, falls sie ungültig ist – ohne jeden
  Teil-Import. Erkennt die Vorschau ein mögliches Duplikat (Name
  **und**, sofern beide Datensätze eine Adresse besitzen, auch die
  Adresse stimmen überein), erscheint ein Konfliktdialog mit einer
  farblich hervorgehobenen Gegenüberstellung von bestehendem und
  importiertem Datensatz; pro Duplikat kann „Aktualisieren“ oder
  „Beibehalten“ gewählt werden (zusätzlich als Komfortfunktion: „Alle
  aktualisieren“/„Alle beibehalten“). Unentschiedene Duplikate bleiben
  beim Abschluss des Imports sicher erhalten statt stillschweigend
  überschrieben zu werden. Der tatsächliche Import (neuer
  WebSocket-Befehl `hofkarte/management/import_commit`) validiert und
  schreibt in zwei Phasen (erst alle Einträge vollständig prüfen, dann
  erst schreiben), damit ein ungültiger Einzeleintrag nie zu einem
  beschädigten oder teilweise übernommenen Bestand führt. Eine in der
  Importdatei enthaltene, von einer anderen HofKarte-Installation
  stammende `id` wird für neu angelegte Hofläden verworfen und durch
  eine frisch vergebene, lokale ID ersetzt. 28 neue Tests: 19 in
  `test_management.py`, 9 strukturelle Tests in
  `test_static_panel_js_export_import.py`.

### Geändert

- **Navigation zum Hofladen (Issue #3):** Der bisherige einzelne
  Kartenlink „🗺️ Auf Google Maps anzeigen“ (zeigte nur einen
  Standort-Pin, keine Route) wird in Kacheln-, Listen- und
  Detailansicht durch eine kompakte Routing-Auswahl mit zwei
  Icon-Buttons ersetzt: 🗺️ öffnet eine echte Wegbeschreibung in Google
  Maps, 🧭 dieselbe Wegbeschreibung in Apple Maps – jeweils ausgehend
  vom aktuellen Standort. Ist eine Adresse hinterlegt, hat sie beim
  Routing Vorrang vor Koordinaten; ohne Adresse und ohne gültige
  Koordinaten sind beide Buttons deaktiviert. Das Bearbeitungsformular
  behält seinen bisherigen, einzelnen Google-Maps-Link zur
  Koordinatenkontrolle unverändert (dort ist Adress-Routing nicht
  sinnvoll, da ggf. noch keine gespeicherte, konsistente Adresse
  vorliegt). 11 neue Tests (`test_static_panel_js_routing.py`):
  Routing-URL-Schemata, Adress-Priorität vor Koordinaten, deaktivierter
  Zustand ohne Ziel.

### Behoben

- **Panel zeigte nach einem Update weiterhin den alten Stand** (z. B.
  fehlende Kacheln-/Listen-/Kartenansicht aus Issue #1/#2, obwohl der
  Code selbst korrekt aktualisiert war): `frontend.py` übergab
  `hofkarte-panel.js` bislang unter einer über alle Versionen hinweg
  identischen URL – Browser (teils auch Home Assistants eigenes
  Frontend) cachen per Custom-Panel geladenes JavaScript anhand dieser
  URL, nicht anhand des Dateiinhalts, und lieferten dadurch nach einem
  Update weiterhin eine bereits zwischengespeicherte ältere Fassung
  aus. Behoben durch einen neuen, sich pro Integrationsversion
  ändernden Query-Parameter (`?v=<version>`, aus `manifest.json`
  gelesen) an `js_url` – siehe `docs/architecture.md`. **Einmalig**
  konnte beim Wechsel auf diese Version noch ein harter Neuladen der
  Seite nötig sein; künftige Updates lösen das Problem seither
  automatisch. 2 neue Tests (`test_frontend.py`).
- **Kartenansicht (Issue #2) zeigte statt eines Standortmarkers ein
  defektes Bild-Icon ("?") an** (Issue #4): Leaflets eigene, bild-
  basierte Standard-Icon-Erkennung (`Icon.Default._detectIconPath`)
  erzeugt ein Sondierungselement im echten, globalen `document.body`
  und fragt andernfalls `document.querySelector('link[href$="leaflet.css"]')`
  ab. Beides findet das `<link rel="stylesheet">` nicht, das
  `karteAnsicht()` innerhalb des Shadow DOM des `<hofkarte-panel>`-
  Elements einbindet – Shadow-DOM-Grenzen werden dabei weder für die
  Style-Zuordnung noch für `querySelector()` durchquert. Dadurch blieb
  `Icon.Default.imagePath` leer und das erzeugte Marker-`<img>` zeigte
  ein defektes Bild. Behoben, indem Marker nun ein eigenes, reines
  Inline-SVG-Icon über `L.divIcon()` erhalten (neue Funktion
  `erzeugeKarteMarkerIcon()` in `hofkarte-panel.js`) – ohne zusätzliche
  Bildressource, ohne weiteren Netzwerk-Request und unabhängig von
  Leaflets Shadow-DOM-inkompatibler Pfaderkennung. Marker-Position,
  Popup-Inhalt/-Navigation und der Filter „nur aktuell geöffnete
  Hofläden“ bleiben unverändert. 6 neue Tests (`test_static_panel_js.py`).
- **Öffnungszeiten-Intervalle verdoppelten sich bei jedem Klick auf
  „+ weiteres Intervall“, zusätzlich entstanden beim Speichern
  doppelte, inhaltlich identische Hofladen-Einträge (Issue #6):**
  `bind()` registriert Event-Listener, ohne zuvor bestehende zu
  entfernen. Das ist unproblematisch, solange `bind()` ausschliesslich
  einmalig nach einem vollständigen `innerHTML`-Ersatz in `render()`
  läuft. Die Handler für „+ weiteres Intervall“ und „+ Sonderzeit
  hinzufügen“ fügten eine neue Zeile jedoch gezielt per DOM-Insert ein
  (bewusst ohne vollständigen Re-Render, um den restlichen
  Formularzustand/Fokus zu erhalten) und riefen danach erneut
  `this.bind()` auf demselben, unverändert bestehenden DOM auf – dabei
  erhielten bereits vorhandene Elemente (u. a. der Button selbst sowie
  der Formular-`submit`-Handler) bei jedem weiteren Klick einen
  zusätzlichen, doppelten Listener obendrauf. Dadurch verdoppelte sich
  die Anzahl neu eingefügter Zeilen pro Klick näherungsweise, und beim
  Abschicken des Formulars löste der mehrfach gebundene
  `submit`-Handler `this.save()` mehrfach aus – da ein neuer, noch
  ungespeicherter Hofladen zu diesem Zeitpunkt keine `id` besitzt,
  vergab `ws_save` bei jedem dieser parallelen Aufrufe eine neue,
  eigene ID, wodurch mehrere identische Hofladen-Einträge entstanden.
  Behoben, indem beide Handler `bind()` nicht mehr erneut aufrufen,
  sondern gezielt nur den „entfernen“-Button der jeweils neu
  eingefügten Zeile direkt verkabeln. 5 neue Tests
  (`test_static_panel_js_formular_listener.py`).

### Entfernt

- **„Entfernung von diesem Gerät berechnen“ (Issue #3):** Der optionale
  Button in der Detailansicht, der rein clientseitig über die
  Browser-Geolocation-API die Luftlinien-Entfernung vom aktuell
  verwendeten Gerät berechnete, wurde vollständig entfernt (Code und
  Dokumentation) – laut Issue nicht mehr benötigt. Der unabhängige,
  serverseitige Entfernungs-Sensor (`distance.py`, Entfernung zur in
  Home Assistant konfigurierten Position) ist davon **nicht** betroffen
  und bleibt unverändert bestehen. 11 neue Tests
  (`test_static_panel_js_routing.py`, siehe „Geändert“ oben) decken
  zusätzlich die vollständige Entfernung aus dem Quelltext ab.

### Ausdrücklich unverändert

- Detailansicht, Bearbeitungsansicht, Bilder-Upload,
  Zahlungsarten-Logik sowie alle bestehenden WebSocket-Verträge und
  Actions über die gesamte `dev.1`–`dev.7`-Reihe hinweg: keine
  Breaking Changes.

### Tests

- 60 neue Tests seit `2026.9.0` (306 → 366), `pyflakes`/`mypy`/
  `node --check` durchgehend fehlerfrei.

## [2026.9.0] - 2026-09-17

### Erstes offizielles Release (MVP)

- HofKarte wird mit dieser Version erstmals offiziell veröffentlicht.
  Alle bisherigen Versionen (`0.1.0`–`0.18.1`, siehe unten) waren
  interne Entwicklungsstände ohne offizielle Veröffentlichung.
- **Neue Versionierung:** Umstellung von einer an Semantic Versioning
  angelehnten Zählung auf das Home-Assistant-eigene Kalenderschema
  `JAHR.MONAT.LAUFNUMMER` (siehe Hinweis oben).
- **Dokumentation vollständig überarbeitet:** Referenzen auf interne
  Entwicklungs-„Einheiten“ (Bauabschnitte aus dem ursprünglichen,
  internen Umsetzungsplan) vollständig aus Code-Kommentaren,
  Docstrings, README, CHANGELOG, `docs/handbuch.md`,
  `docs/architecture.md` und `quality_scale.yaml` entfernt und durch
  beschreibende, auf den tatsächlichen Code bezogene Erklärungen
  ersetzt. `docs/handbuch.md` und `docs/architecture.md` wurden gegen
  den aktuellen Code verifiziert; dabei ein fehlendes Feld ergänzt
  (Kapitel 4 des Handbuchs nannte „Bemerkung“ nicht in der Liste der
  beim Anlegen eines Hofladens verfügbaren Felder).
- **Testinfrastruktur-Korrektur:** Der Vergleich der Manifest-Version
  gegen den neuesten CHANGELOG-Eintrag
  (`test_manifest_und_hacs.py`) verglich Versionen bisher als reine
  Zeichenketten. Das wäre mit dem neuen Kalenderschema ab einem
  zweistelligen Monat falsch gewesen (`"2026.10.0" >= "2026.9.0"` ist
  als Stringvergleich **falsch**, da `"1" < "9"`). Behoben durch einen
  numerischen Tupel-Vergleich, mit eigenem Regressionstest
  (`test_version_tuple_vergleicht_numerisch_nicht_lexikografisch`).
- Alle 306 automatisierten Tests grün, `pyflakes`/`mypy` sauber (siehe
  Testbericht in der Auslieferung dieser Version). Keine funktionalen
  Änderungen an der Integration selbst in diesem Release – ausschliesslich
  Dokumentation, Versionierung und die oben genannte Testkorrektur.

## [0.18.1] - Unveröffentlicht

### Geändert

- **Ansicht „Hofladen bearbeiten“ neu geordnet und gestaltet** – rein
  visuell, keine funktionalen oder datenbezogenen Änderungen:
  - Reihenfolge der Gruppierungen angepasst: Allgemeine Informationen →
    Adresse → Standort/Koordinaten → Kontakt & Webseite →
    Öffnungszeiten → Angebote und Zahlungsarten → Bilder (Standort/
    Koordinaten steht jetzt vor Kontakt & Webseite statt danach).
  - Sektion „Angebote und Eigenschaften“ in **„Angebote und
    Zahlungsarten“** umbenannt (passend zum tatsächlichen Inhalt, seit
    Verkaufsarten/Merkmale entfernt wurden); Handbuch-Kapitel 8
    entsprechend mitbenannt.
  - Feld „Bemerkung“ ist jetzt ein Textfeld mit derselben Höhe wie
    „Angebote“/„Zahlungsarten“ (zuvor ein einzeiliges Eingabefeld).
  - Die Zeitfelder „Von“/„Bis“ (Öffnungszeiten) sowie „Beginn“/„Ende“
    (Sonderöffnungszeiten) sind schmaler gestaltet (`max-width: 140px`)
    statt die volle verfügbare Breite auszufüllen.
  - Sichtbarer Abstand zwischen den Gruppierungen ergänzt, analog zur
    bereits bestehenden Detailansicht (`margin-bottom: 20px`).

## [0.18.0] - Unveröffentlicht

### Behoben

- **Kritischer Bug – Geolocation-Button meldete fälschlich
  „Standortzugriff wurde verweigert“:** Browser gewähren
  Geolocation-Zugriff ausschliesslich in einem sicheren Kontext (HTTPS
  oder `localhost`). Wird Home Assistant wie im Heimnetz üblich über
  einfaches `http://` aufgerufen (z. B. `http://192.168.1.50:8123`),
  lehnt der Browser den Zugriff automatisch als `PERMISSION_DENIED` ab
  – **ohne jemals einen Freigabe-Dialog anzuzeigen**. Das erschien
  fälschlich als tatsächliche Ablehnung, obwohl die Nutzerin/der
  Nutzer nie gefragt wurde. Behoben durch eine explizite
  `window.isSecureContext`-Prüfung in `ermittleGeraeteEntfernung()`
  (`hofkarte-panel.js`) **vor** dem eigentlichen Geolocation-Aufruf,
  mit eigener, klar unterscheidbarer Fehlermeldung („Standortermittlung
  erfordert eine sichere Verbindung (HTTPS) oder den Aufruf über
  localhost.“).

### Geändert

- **„Angebote“ ohne Gruppen:** Das erst kürzlich eingeführte
  `gruppen`-Feld an `models.Angebot` wurde wieder entfernt – ein
  Angebot ist jetzt wieder ausschliesslich `id`/`name`, eine schlichte
  Namensliste ohne Gruppierung. Betrifft `models.py`, `parsing.py`
  (Migration vereinfacht: Kategorien und Produkte werden seit dieser
  Änderung gleichermassen zu flachen Angebot-Einträgen, eine
  `kategorie_ids`-Auflösung findet nicht mehr statt), `attributes.py`
  (Attribut `angebote` jetzt eine einfache Namensliste),
  `hofkarte-panel.js` (Editor-Feld ohne `Name|Gruppe`-Syntax,
  Detailansicht als flache Liste statt Gruppierung). Bereits
  gespeicherte Angebote mit `gruppen`-Feld werden beim Einlesen
  fehlerfrei verarbeitet, das Feld aber ignoriert (kein Fehler, kein
  Absturz, die Information geht bewusst verloren).
- **„Verkaufsarten“ und „Merkmale“ ersatzlos entfernt:** Die
  Fachbereiche `Verkaufsart` und `Merkmal` existieren nicht mehr.
  Betrifft `models.py`, `parsing.py`, `attributes.py`, `search.py`
  (Filter-Parameter `verkaufsart`/`merkmal` entfernt), `services.py` +
  `strings.json`/`translations/{en,de}.json`/`services.yaml`
  (Action-Parameter der `hofkarte.hoflaeden_suchen`-Action entfernt –
  bewusste, dokumentierte Ausnahme von „keine Breaking Changes“),
  `coordinator.py` (`async_update_hofladen_sortiment`: Parameter
  entfernt), `const.py`/`sortiment_katalog.py` (Vorschlagskataloge
  entfernt; `STANDARD_ZAHLUNGSARTEN` bleibt unverändert bestehen),
  `hofkarte-panel.js` (Editor-Felder und Detailansicht-Abschnitte
  entfernt). Bereits gespeicherte Daten mit diesen Feldern werden beim
  Einlesen fehlerfrei verarbeitet, die Felder aber nicht mehr
  ausgewertet.

### Hinzugefügt

- **Neues Feld „Bemerkung“** (`models.Hofladen.bemerkung`): optionales
  Freitextfeld auf Hofladen-Ebene, unabhängig von `beschreibung` –
  gedacht für interne Notizen. Editierbar im Bearbeitungsformular
  (Sektion „Allgemeine Informationen“), sichtbar in der Detailansicht
  in einem eigenen Abschnitt (kein leerer Bereich, wenn nicht gesetzt).
  Bewusst auf Hofladen-Ebene angesiedelt statt je Angebot, da Angebote
  seit obiger Vereinfachung keine weitere Struktur mehr tragen.

### Ausdrücklich unverändert

- Bilder-Upload, serverseitige Entfernungs-Entity, Zahlungsarten,
  Öffnungszeiten, WebSocket-Vertrag der Verwaltungsoberfläche
  (`hofkarte/management/*`): keine Änderungen.

## [0.17.0] - Unveröffentlicht

### Hinzugefügt

- **Entfernung vom aktuellen Gerät:** Neuer Button „📍 Entfernung von
  diesem Gerät berechnen“ in der Detailansicht (`hofkarte-panel.js`),
  nutzt die Browser-Geolocation-API rein clientseitig. Ergänzt die
  bestehende, serverseitige Entfernungs-Entity, ersetzt sie **nicht**
  (eine Home-Assistant-Entity kann nur einen Zustand für alle
  Betrachter:innen haben). Haversine-Formel als dokumentiertes
  JS-Duplikat von `distance.haversine_distance_km` implementiert und
  numerisch gegen die Python-Referenz verifiziert. Klare Fehlermeldungen
  bei verweigerter/nicht unterstützter/zeitüberschreitender
  Standortabfrage. Gerätestandort wird nicht gespeichert und nicht an
  das Backend übertragen.

### Geändert

- **„Kategorien“ und „Produkte“ zu „Angebote“ zusammengelegt:**
  `models.Angebot(id, name, gruppen)` ersetzt die früher getrennten
  `Kategorie`/`Produkt`. Betroffen: `models.py`, `parsing.py`,
  `attributes.py`, `coordinator.py` (`async_update_hofladen_sortiment`:
  Parameter `kategorien`/`produkte` → `angebote`), `search.py`
  (`find_hoflaeden`: Parameter `kategorie`/`produkt` → `angebot`,
  prüft Name **oder** Gruppe), `services.py` +
  `strings.json`/`translations/{en,de}.json`/`services.yaml`
  (Action-Parameter der `hofkarte.hoflaeden_suchen`-Action angepasst –
  bewusste, dokumentierte Ausnahme von „keine Breaking Changes“).
  JS-Panel: die beiden getrennten Editor-Textfelder „Kategorien“ und
  „Produkte“ sind einem einzigen Feld „Angebote“ gewichen (Syntax
  `Name` bzw. `Name|Gruppe1,Gruppe2`); die Detailansicht zeigt Angebote
  nach Gruppen zusammengefasst statt in zwei getrennten Abschnitten.
- **Bestehende Daten werden automatisch migriert:** Neue, verbindliche
  Migrationsfunktion `parsing._migriere_kategorien_und_produkte_zu_angeboten`
  – idempotent (bereits migrierte bzw. neu angelegte Daten im
  `angebote`-Format bleiben unverändert), verlustfrei (jedes Produkt
  wird zu einem Angebot mit aufgelösten Gruppennamen; Kategorien ohne
  zugeordnete Produkte bleiben als eigenständige Angebote mit leeren
  Gruppen erhalten statt zu verschwinden). Keine manuelle Nutzeraktion
  nötig.

### Behoben

- **Zeiten ohne Sekunden (hh:mm statt hh:mm:ss):** `management.py`s
  `_json_value` rief `time.isoformat()` ohne `timespec` auf, was
  standardmässig Sekunden liefert. Die Detailansicht der
  Öffnungszeiten zeigte dadurch z. B. „08:00:00–12:00:00 Uhr“ statt
  „08:00–12:00 Uhr“. Behoben durch `timespec="minutes"` speziell für
  `time`-Objekte (nicht für `date`-Objekte, die weiterhin
  `YYYY-MM-DD` liefern). Betrifft ausschliesslich die Darstellung,
  keine Änderung an Speicherung oder Berechnung.

### Tests

- 9 dedizierte Migrationstests (`test_migration_kategorien_produkte_zu_angebote.py`):
  Produkt mit einer/mehreren Kategorien, Produkt ohne Kategorie,
  verwaiste Kategorie, gemischter Fall, Idempotenz (isoliert und über
  den vollen `parse_hofladen`-Pfad), leere Eingabe.
- Bestehende Tests in `test_models.py`, `test_attributes.py`,
  `test_search.py`, `test_parsing.py`, `test_binary_sensor.py`,
  `test_coordinator.py`, `test_services.py`, `test_end_to_end.py` auf
  das neue `Angebot`-Modell umgestellt.
- Neuer Regressionstest für den Sekunden-Bug in `test_management.py`.

### Ausdrücklich unverändert

- `image.py`, `distance.py`, `data_provider.py`, `frontend.py`,
  WebSocket-Vertrag der Verwaltungsoberfläche
  (`hofkarte/management/*`): keine Änderungen.

## [0.16.2] - Unveröffentlicht

### Behoben

- **Kritischer Bug – Bilder-Upload schlug immer fehl:** Der
  Upload-Aufruf (`fetch("/api/image/upload", ...)`) sendete keine
  Home-Assistant-Authentifizierung mit. Home Assistants `/api/*`-
  Endpunkte erfordern einen `Authorization: Bearer <token>`-Header
  (kein Cookie-basiertes Login) – `ImageUploadView` verlangt zudem
  explizit Authentifizierung (im Unterschied zur Auslieferung über
  `ImageServeView`, die bewusst ohne Auth auskommt). Ohne den Header
  schlug jeder Upload-Versuch fehl und Home Assistant protokollierte
  „Login attempt failed“/„invalid authentication“, obwohl die
  Benutzerin/der Benutzer regulär angemeldet war. Behoben durch
  Ergänzen des Headers mit `this.hass.auth.accessToken`
  (`hofkarte-panel.js`, `uploadBild`). Zusätzlich wird ein `401`-Fehler
  jetzt mit einer eigenen, verständlichen Meldung („Anmeldung
  abgelaufen“) statt eines generischen Fehlers angezeigt.
- WebSocket-Befehle (`image/delete`, alle `hofkarte/management/*`)
  waren von diesem Bug **nicht** betroffen, da die WebSocket-Verbindung
  bereits beim Verbindungsaufbau authentifiziert wird – nur der
  einzelne, separate HTTP-`fetch()`-Aufruf für den eigentlichen
  Datei-Upload war betroffen.

## [0.16.1] - Unveröffentlicht

### Geändert

- **Start-Button für den Bilder-Upload:** Der bisherige Einstiegspunkt
  (ein als Button gestaltetes `<label>`, das ein verstecktes
  `input[type=file]` auslöste) wurde durch einen echten
  `<button type="button">` ersetzt, der dasselbe Datei-Feld
  programmatisch öffnet (`input.click()`). Rein visuelle/semantische
  Verbesserung des Einstiegspunkts – der dahinterliegende Upload-Ablauf
  (Validierung, Anbindung an Home Assistants `image_upload`-Komponente,
  Erfolgs-/Fehlermeldung, Einreihung in die Bilderliste) ist
  unverändert.
- Neuer, eigenständiger Button-Stil (`.upload-start-btn`, grün über
  `--success-color`) statt der bisherigen, optisch mit `.secondary`-
  Buttons verwechselbaren Gestaltung – klar als eigene Aktion erkennbar
  und von der primären „Speichern“-Aktion sowie den `.map-btn`/
  `.info-btn`-Stilen unterscheidbar.
- Nebeneffekt (Verbesserung): ein echtes `<button>`-Element ist für
  assistive Technologien zuverlässiger als Aktion erkennbar als ein
  Label, das auf ein verstecktes Datei-Feld zeigt; zusätzlich
  `aria-label` ergänzt.
- `type="button"` explizit gesetzt, damit der Button innerhalb des
  Formulars kein versehentliches Absenden (Speichern) auslöst.

### Ausdrücklich unverändert

- Upload-Validierung, Backend-Anbindung (`image_upload`-Komponente),
  Datenmodell (`Bild.hochgeladen`), externe-URL-Eingabe, Hauptbild-Logik,
  Entfernen von Bildern: keine Änderungen. Reine Anpassung des
  Auslöse-Elements in `hofkarte-panel.js`.

## [0.16.0] - Unveröffentlicht

### Hinzugefügt

- **Geführter Bilder-Upload** in der Verwaltungsoberfläche
  (`hofkarte-panel.js`): Bild direkt hochladen (JPEG/PNG/GIF, max.
  10 MB) statt nur externe Bild-Adressen manuell einzutragen – beide
  Wege sind kombinierbar. Direktes Feedback bei Erfolg/Fehler, Vorschau
  je Bild, optionale Beschreibung, Entfernen sowie „Als Hauptbild
  festlegen“ (verschiebt an den Anfang der Liste, bestehende
  Hauptbild-Konvention unverändert).
- Nutzt **ausschliesslich Home Assistants eigene `image_upload`-
  Komponente** (`POST /api/image/upload`, Auslieferung über
  `/api/image/serve/{id}/original`, Löschen über den bestehenden
  WebSocket-Befehl `image/delete`) – kein eigener Upload-Endpunkt,
  keine neue Python-Abhängigkeit. `manifest.json` deklariert
  `image_upload` neu als Abhängigkeit (analog zu `http`).
- `models.Bild`: neues Feld `hochgeladen: bool = False` (Default
  erhält bestehende, extern verlinkte Bilder unverändert). Wird von
  `parsing.py` validiert.
- `images.py`: `is_valid_image_url` akzeptiert einen neuen
  `hochgeladen`-Parameter. Über den Upload erzeugte Bilder sind gezielt
  von der Ablehnung privater/interner IP-Adressen ausgenommen (die
  Upload-URL zeigt zwangsläufig auf die eigene, meist private
  Home-Assistant-Instanz) – Vertrauensbasis ist die Herkunft, nicht der
  Adressbereich; Schema-/Zugangsdaten-Prüfung bleiben unverändert auch
  für hochgeladene Bilder in Kraft.
- Beim Entfernen eines hochgeladenen Bildes wird die zugrunde liegende
  Datei über `image/delete` mitgelöscht – keine verwaisten Dateien.
- Tests: 5 neue Fälle in `test_images_security.py` (Ausnahme für
  `hochgeladen=True`, weiterhin geltende Schema-/Zugangsdaten-Prüfung,
  Behandlung je Bild statt global), 3 neue Fälle in `test_parsing.py`
  (Default, Übernahme, Typprüfung des neuen Felds), 1 neuer Test für
  die `image_upload`-Manifest-Abhängigkeit.

### Geändert

- README, `docs/handbuch.md` (neuer Abschnitt „Bilder hochladen“ in
  Kapitel 4), `docs/architecture.md` (neuer Abschnitt „Geführter
  Bilder-Upload“) und `SECURITY.md` um den Upload-Mechanismus und die
  `hochgeladen`-Sicherheitsausnahme ergänzt. Veraltete Formulierungen
  („HofKarte lädt und speichert keine Bilddateien selbst“) korrigiert,
  da dies mit dem neuen Upload nicht mehr zutrifft.

### Ausdrücklich unverändert

- `image.py`, `distance.py`, `coordinator.py`, `data_provider.py`,
  WebSocket-Vertrag für Hofladen-Verwaltung (`hofkarte/management/*`):
  keine Änderungen. Bestehende, extern verlinkte Bilder funktionieren
  unverändert (Feld `hochgeladen` defaultet auf `False`).

### Bewusst nicht implementiert

- WebP-Unterstützung: Home Assistants `image_upload`-Komponente
  unterstützt nur JPEG/PNG/GIF; da kein eigener Upload-Mechanismus
  gebaut wird (siehe oben), gilt dieselbe Einschränkung für HofKarte.

## [0.15.1] - Unveröffentlicht

### Geändert

- **Koordinaten von LV95 auf WGS84 umgestellt:** Die Verwaltungsoberfläche
  erfasst und zeigt Koordinaten jetzt direkt als WGS84-Dezimalgrad
  (Latitude/Longitude) – identisch zum Speicherformat
  (`Hofladen.latitude`/`longitude`). Es findet keine
  Koordinatentransformation mehr statt (Eingabe-, Speicher- und
  Anzeigeformat sind durchgehend gleich).
- **Karten-Button öffnet jetzt Google Maps** statt map.geo.admin.ch,
  anhand der gespeicherten WGS84-Koordinaten
  (`https://www.google.com/maps/search/?api=1&query={lat},{lon}`,
  offizielles Google-Maps-URL-Schema). Identisches Verhalten in
  „Bearbeiten“ und „Details“ über eine gemeinsame Funktion
  (`googleMapsUrl`/`mapButton`), unverändert deaktiviert ohne gültige
  Koordinaten.
- Infobutton-Text von einer LV95-Erklärung auf eine
  Latitude/Longitude-Erklärung umgestellt.

### Entfernt

- `lv95.py` und `tests/test_lv95.py`: durch die Umstellung auf WGS84
  entfällt die Koordinatenumrechnung vollständig; das Modul wurde zu
  totem Code (von keiner anderen Datei mehr referenziert, verifiziert)
  und entsprechend entfernt statt belassen.

### Behoben

- **Bug in der neuen Kartenlogik:** `Number("")` ergibt in JavaScript
  `0`, nicht `NaN`. Ohne gesonderte Prüfung hätte der Karten-Button bei
  fehlenden Koordinaten fälschlich als aktiv gegolten und auf
  Koordinate (0, 0) verwiesen. Durch einen expliziten
  Leerstring-Check vor der Zahlkonvertierung behoben und per Test
  verifiziert.

### Ausdrücklich unverändert

- Backend (`management.py`, `coordinator.py`, `models.py`,
  `parsing.py`, `distance.py`), WebSocket-Vertrag, Datenmodell,
  gespeichertes Datenformat: keine Änderungen. Bestehende
  Hofladen-Daten (bereits WGS84) sind ohne jede Migration weiterhin
  gültig. Übrige GUI (Liste, Öffnungszeiten-Editor, Sortiment,
  Gruppierung, Info-Button-Styling) unverändert.

## [0.15.0] - Unveröffentlicht

### Hinzugefügt

- **Karten-Button** neben den LV95-Koordinaten, identisch in
  „Bearbeiten“ und „Details“ verfügbar (Button „🗺️ Auf Karte anzeigen“,
  öffnet [map.geo.admin.ch](https://map.geo.admin.ch) in neuem Tab).
  Gemeinsame Implementierung (`mapUrl`/`mapButton` in
  `hofkarte-panel.js`) für beide Ansichten – kein Code-Duplikat. LV95
  wird nativ über den dokumentierten URL-Parameter `center` an
  map.geo.admin.ch übergeben, **keine** Umrechnung nach WGS84 nötig
  (map.geo.admin.ch akzeptiert LV95 direkt). Button ist deaktiviert
  ohne gültige Koordinaten (`is_valid_lv95`), öffnet ausschliesslich
  einen rein lesenden externen Link, keine neue Abhängigkeit.

### Geändert

- **LV95-Infobutton visuell hervorgehoben:** blau hinterlegt (nutzt die
  Home-Assistant-Theme-Farbe `--info-color`, passt sich hellen wie
  dunklen Themes an), mit Hover-/Fokus-Zustand und `aria-label` für
  Barrierefreiheit. Bleibt eindeutig von der primären
  „Speichern“-Aktion und den `.secondary`/`.danger`-Buttons
  unterscheidbar.
- **Gruppierung in „Bearbeiten“ überarbeitet:** die bisherige
  „Stammdaten“-Sektion wurde in vier eigenständige, konsistent mit der
  Detailansicht benannte Abschnitte aufgeteilt: „Allgemeine
  Informationen“ (Name, Beschreibung), „Adresse“ (Adresse, PLZ, Ort,
  Land), „Kontakt & Webseite“ (Webseite), „Standort / Koordinaten“
  (LV95-Felder, Infobutton, Karten-Button). Keine Änderung an
  Feldnamen, Validierung oder Speicherlogik – rein strukturelle/visuelle
  Gruppierung.
- Detailansicht: „Adresse“ und „Standort / Koordinaten“ sind jetzt zwei
  getrennte Abschnitte (vorher gemeinsam dargestellt) – konsistent mit
  der neuen Gruppierung in „Bearbeiten“.

### Ausdrücklich unverändert

- Backend (`management.py`, `coordinator.py`, `models.py`,
  `parsing.py`, `distance.py`, `lv95.py`), WebSocket-Vertrag,
  Datenmodell: keine Änderungen. Rein clientseitige
  GUI-Verfeinerung ohne Breaking Changes.

## [0.14.0] - Unveröffentlicht

### Hinzugefügt

- **Read-only Detailansicht** je Hofladen in der Verwaltungsoberfläche
  (`static/hofkarte-panel.js`): zeigt Stammdaten, Adresse, Koordinaten,
  Öffnungszeiten, Sortiment und Bilder kompakt an, ohne editierbare
  Felder – erreichbar über einen neuen „Details“-Button in der Liste.
  Kein neuer Backend-Endpunkt nötig (nutzt die bereits über
  `hofkarte/management/list` geladenen Daten).
- **Koordinaten-Eingabe im Schweizer System LV95/EPSG:2056**
  (`custom_components/hofkarte/lv95.py`, referenzimplementierte und
  gegen einen amtlichen swisstopo-Referenzpunkt verifizierte
  Näherungsformeln; identische Formeln clientseitig in
  `hofkarte-panel.js`). Ein Infobutton (ⓘ) neben den Koordinatenfeldern
  erklärt LV95 direkt im Formular. **Keine Datenmodell-Änderung und
  keine Migration nötig:** intern wird weiterhin WGS84 gespeichert
  (siehe Architekturentscheid in `lv95.py`/`docs/architecture.md`);
  bestehende Koordinaten werden beim Öffnen der Bearbeitungsansicht
  automatisch als LV95 angezeigt.
- **Öffnungszeiten-Editor überarbeitet:** pro Wochentag ein
  übersichtlicher Block mit den Modi „Geschlossen“ / „24 Stunden
  geöffnet“ / „Zeiten festlegen“ (mit beliebig vielen Intervallen je
  Tag), statt eines `prompt()`-Dialogs zum Hinzufügen neuer Intervalle.
  „24 Stunden geöffnet“ wird als Intervall 00:00–23:59 gespeichert
  (bereits zuvor an anderer Stelle im Projekt verwendete Konvention,
  keine neue Datenmodell-Änderung).
- **Webseite als anklickbarer Link** in der Detailansicht: wird nur
  angezeigt, wenn eine plausible `http(s)`-Adresse hinterlegt ist
  (kein leerer UI-Bereich bei fehlender Webseite; ungültige Adressen
  werden als Text mit Hinweis statt als Link angezeigt).
- Validierung in der Verwaltungsoberfläche erweitert: LV95-Koordinaten
  werden auf Plausibilität geprüft (grobe Bounding Box
  Schweiz/Liechtenstein) und Webseiten-Eingaben auf ein gültiges
  `http(s)`-Format.
- Tests: `tests/test_lv95.py` (10 Tests: amtlicher Referenzpunkt,
  Rundreise-Konsistenz, Plausibilitätsprüfung, End-zu-End-Test über den
  echten Coordinator, der exakt den Workflow des Panels nachbildet).

### Geändert

- `static/hofkarte-panel.js`: vollständig überarbeitet (Detailansicht,
  LV95-Koordinatenfelder, neuer Öffnungszeiten-Editor). Bestehende
  Funktionen (Liste, Erstellen, Bearbeiten, Löschen, Sortiment-Textfelder,
  Sonderöffnungszeiten-Editor) unverändert erhalten.

### Ausdrücklich unverändert (keine Architekturänderung)

- `models.py`, `parsing.py`, `distance.py`, `data_provider.py`,
  `coordinator.py`, `management.py`: keine Änderungen. Der
  WebSocket-Vertrag (`hofkarte/management/list|save|delete`) und das
  gespeicherte Datenformat sind identisch zu vorher – bestehende
  Hofladen-Daten funktionieren ohne jede Migration unverändert weiter.

## [0.13.3] - Unveröffentlicht

### Hinzugefügt

- `CONTRIBUTING.md`: Entwicklungsumgebung, Code-Stil/Linting/Typisierung,
  Tests ausführen, Branch-/Commit-Konventionen, Pull-Request-Ablauf,
  Umgang mit Übersetzungen.
- `SECURITY.md`: unterstützte Versionen, privater Meldeweg für
  Sicherheitsprobleme, erwartete Reaktionszeit, bekannte/bewusste
  Sicherheitsentscheidungen.
- `docs/architecture.md`: Architekturüberblick, Zusammenspiel von Config
  Flow/ConfigEntry/Coordinator/Devices/Entities, Datenmodell und
  Datenquelle, Öffnungszeiten-/Geo-/Sortimentslogik, Erweiterungspunkte.
- `docs/handbuch.md`: vollständiges Anwendungshandbuch für
  Endanwender:innen mit allen 15 im Umsetzungsplan geforderten
  Kapiteln (Installation, Ersteinrichtung, Konfiguration,
  HofKarte-Geräte, Entities, Öffnungszeiten, Standort/Entfernung,
  Produkte/Eigenschaften, Actions/Automationen mit lauffähigen
  YAML-Beispielen, zwei Dashboard-Beispiele mit reinen
  Home-Assistant-Bordmitteln, Fehlerbehebung, Updates, Deinstallation,
  Datenschutz, Support).
- README: Verweis auf Anwendungshandbuch/Architekturdokumentation/
  CONTRIBUTING/SECURITY, Support-Abschnitt ergänzt.

### Geprüft, keine Änderung nötig

- Secrets/Tokens/API-Schlüssel/Passwörter: keine gefunden.
- Persönliche Daten (Namen, E-Mail-Adressen, private Koordinaten):
  keine gefunden. Auftretende IP-Adressen (`127.0.0.1`,
  `169.254.169.254`) sind Standard-Sicherheitsbeispiele in
  `images.py`, keine echten Daten.
- Veraltete Architekturhinweise (React, FastAPI, Uvicorn, SQLite,
  Alembic, Docker, eigene REST-API): alle Fundstellen sind korrekte
  Verneinungen abgelehnter Architekturentscheidungen, keine
  tatsächlichen Altlasten.
- `LICENSE`: Jahr, Rechteinhaber (`@rest-be`) konsistent mit
  `manifest.json` (`codeowners`) und README.
- Alle Beispiel-YAMLs (README + Handbuch) gegen echte Entity-Namen,
  Action-Namen und Parameter aus dem Code geprüft und als YAML
  validiert.
- Keine Code-Änderungen nötig; Tests unverändert grün (292/292).

## [0.13.2] - Unveröffentlicht

### Behoben

- **Kritisch – Testsuite komplett ausgefallen:** Zwei verwaiste
  Testdateien (`tests/test_camera.py`, `tests/test_camera_fetch.py`)
  referenzierten das bereits entfernte `camera.py`-Modul und liessen die
  gesamte Testsammlung mit `Interrupted: 2 errors during collection`
  abbrechen (0 von 271 Tests liefen). Entfernt.
- `distance.py`: mypy-Fund behoben – nach `is_valid_home_position(...)`
  konnte statische Typprüfung nicht erkennen, dass die Koordinaten nicht
  mehr `None` sind (`TypeGuard` kann zwei unabhängige Parameter nicht
  gemeinsam verengen). Durch explizite `assert`-Anweisungen behoben.
- `opening_hours.py`: mypy-Fund behoben – interne Hilfsfunktionen
  typisierten den `tzinfo`-Parameter als `object` statt
  `datetime.tzinfo | None`.

### Hinzugefügt

- `quality_scale.yaml`: ehrliche Selbsteinschätzung gegen die
  Home-Assistant-Integration-Quality-Scale (52 Kriterien: 36 erfüllt,
  8 fachlich nicht zutreffend/„exempt“, 8 offen mit dokumentiertem
  technischen Grund statt Scheinimplementierung).
- `PARALLEL_UPDATES = 0` in allen drei Entity-Plattformen
  (`binary_sensor.py`, `sensor.py`, `image.py`) ergänzt – Konvention für
  coordinator-basierte Plattformen ohne pro-Entity-Netzwerkzugriffe.
- README: Abschnitt „Deinstallation“ ergänzt (fehlte bisher vollständig).
- Tests: `test_end_to_end.py` (vollständiges Szenario mit zwei
  gleichzeitigen Hofläden: Devices, Öffnungsstatus, Sortiment,
  Entfernung, Action, zweifacher Reload als Neustart-Ersatz,
  Stabilität von Entity-/Unique-IDs), `test_translations.py`
  (JSON-Validität, DE/EN-Strukturgleichheit, Vollständigkeit der
  Config-Flow- und Service-Feld-Übersetzungen), `test_manifest_und_hacs.py`
  (Manifest-Pflichtfelder, SemVer, `http`-Dependency, `hacs.json`,
  Versionskonsistenz mit CHANGELOG, HACS-Pflichtdateien).

### Geprüft, keine Änderung nötig

- `pyflakes`, `vulture` (Dead-Code-Scan, 80 % Konfidenz): keine Funde in
  Produktionscode.
- Mehrfacher Config-Entry-Reload, Entity-/Unique-ID-Stabilität über
  Reloads hinweg: durch Tests bestätigt.
- Mehrere Config Entries: nicht vorgesehen (Single-Instance-Architektur,
  siehe `config_flow.py`); dokumentiert statt implementiert.

## [0.13.1] - Unveröffentlicht

### Geändert

- **README komplett neu strukturiert** für Benutzer statt nur
  Entwickler: neue Abschnitte „Voraussetzungen“, „Konfiguration“,
  „Beispiele für Automationen“, „Fehlerbehebung“ und „Datenschutz- und
  Standort-Hinweise“ ergänzt (vorher gar nicht bzw. nur verstreut
  vorhanden). Reihenfolge der Abschnitte an den typischen
  Benutzerpfad angepasst (Installation → Einrichtung → Nutzung →
  technische Details → Fehlerbehebung). Technisch-detaillierte Inhalte
  (Internes Datenmodell, Coordinator, Data Provider) in einen
  eigenen Abschnitt „Unter der Haube“ verschoben, damit sie normale
  Benutzer:innen nicht von den eigentlichen Bedienungsinformationen
  ablenken.
- `hacs.json`: minimale unterstützte Home-Assistant-Version
  (`"homeassistant": "2025.1.0"`) ergänzt, entsprechend der Version, gegen
  die die Testsuite tatsächlich läuft.

### Behoben

- **CHANGELOG-Konsistenz:** Mehrere strukturelle Fehler bereinigt, die
  durch frühere, teils externe Bearbeitungen entstanden waren: ein
  Eintrag stand oberhalb der eigentlichen Dateiüberschrift (Änderungen
  am Stammdatenformular/`website`-Feld, jetzt in `[0.10.3]`
  zusammengeführt); ein weiterer Eintrag (`[0.10.0]`, native
  Seitenleiste/WebSocket-API) stand fälschlich nach `[0.1.0]` statt in
  chronologischer Reihenfolge – Inhalt ebenfalls verlustfrei in
  `[0.10.3]` zusammengeführt. Die Versionsliste ist jetzt durchgehend
  absteigend sortiert ohne Duplikate oder verwaiste Einträge.
- `camera.py` (inkl. zugehöriger Tests) erneut entfernt – wiederholt
  aufgetauchte, unverdrahtete Implementierung, die der getroffenen
  Architekturentscheidung (natives `image`-Entity) widerspricht.
- Fehlendes `.gitignore` am Repository-Root ergänzt (bisher gelangten
  `__pycache__`-Ordner ins Repository).

### Hinweis zur Dokumentation

- Das neu im Datenmodell vorhandene Feld `Hofladen.website` (bislang nur
  in einem verwaisten CHANGELOG-Eintrag erwähnt) ist jetzt auch im
  README dokumentiert.

## [0.13.0] - Unveröffentlicht

### Hinzugefügt

- `diagnostics.py`: `async_get_config_entry_diagnostics` liefert Status
  des letzten Datenabrufs, Zeitpunkt der letzten erfolgreichen
  Aktualisierung, konfiguriertes Update-Intervall, Typ des Data
  Providers und dessen Schreibfähigkeit sowie die Anzahl verwalteter
  Hofläden. Bewusst keine Hofladen-Inhalte oder Standortdaten (durch
  Test explizit abgesichert).
- `coordinator.py`: neue öffentliche Properties
  `letzte_erfolgreiche_aktualisierung`, `provider_type_name`,
  `provider_unterstuetzt_schreibzugriffe` sowie zwei neue
  Schreibmethoden `async_save_hofladen` (beliebige Felder, für die
  Verwaltungsoberfläche) und `async_delete_hofladen`.
- Debug-Logging für Device-Entfernung (`device.py`) sowie
  Hofladen-Hinzufügen/-Aktualisieren/-Löschen/-Speichern
  (`coordinator.py`).
- Tests: `test_diagnostics.py` (neu), weitere Tests für die neuen
  Coordinator-Properties/-Methoden, Reload/Unload-Robustheit
  (Panel-Entfernung bei Unload, keine Duplikate über mehrere
  Reload-Zyklen hinweg), sowie Fehlerbehandlungstests für
  `management.py` (`not_ready`-Fehlercode, korrekte Trennung von
  `invalid_data`/`not_supported`).

### Geändert

- `coordinator.py`: `config_entry` wird jetzt explizit an
  `DataUpdateCoordinator` übergeben (siehe „Behoben“ unten).
- `management.py`: `ws_save`/`ws_delete` delegieren jetzt vollständig an
  `coordinator.async_save_hofladen`/`async_delete_hofladen` statt direkt
  auf `coordinator._provider` zuzugreifen. Alle drei WebSocket-Handler
  behandeln jetzt eine nicht eingerichtete Integration sauber
  (`not_ready`) statt eine unbehandelte `ValueError` durchzureichen.

### Behoben

- **Zukunftsrelevanter Bug in `coordinator.py`:** Ohne explizite
  Übergabe von `config_entry` ermittelt `DataUpdateCoordinator` die
  Config Entry über einen von Home Assistant selbst als veraltet
  markierten Kontextvariablen-Fallback
  (`config_entries.current_entry`), der laut Warnhinweis im
  Home-Assistant-Kern **ab Version 2025.11 nicht mehr unterstützt
  wird**. Behoben durch expliziten `config_entry`-Parameter im
  Coordinator-Konstruktor.
- **Kapselungsbruch und Fehlerbehandlung in `management.py`:**
  Direkter Zugriff auf `coordinator._provider` (private Attribute) von
  aussen; `ValueError` aus `_get_coordinator` konnte unbehandelt aus
  `ws_save`/`ws_delete` entkommen; ein nicht schreibfähiger Data
  Provider wurde in `ws_save` fälschlich als `"invalid_data"` statt als
  eigener Fehlerfall (`"not_supported"`) gemeldet. Alle drei Punkte
  behoben.

### Entfernt

- `camera.py` (inkl. `test_camera.py`, `test_camera_fetch.py`): erneut
  aufgetauchte, unverdrahtete Implementierung, die der bereits
  getroffenen Architekturentscheidung (natives `image`-Entity)
  widerspricht.

### Bewusst geprüft und nicht umgesetzt

- `always_update=False` am Coordinator (würde State-Updates bei
  unveränderten Rohdaten unterdrücken): abgelehnt, da „Geöffnet“ und
  „Entfernung“ dynamisch aus der aktuellen Uhrzeit berechnet werden –
  ohne Zustandsaktualisierung bei jedem Coordinator-Update würde der
  Öffnungsstatus nicht zur richtigen Zeit umschalten, selbst wenn sich
  die Hofladen-Daten nicht geändert haben.
- Zeitpunktgenaue, zusätzliche Status-Aktualisierung exakt bei
  Öffnungs-/Schliesszeitpunkten (statt nur alle 15 Minuten): wäre neue
  Funktionalität ohne klaren Bedarf (Grundsatz: „Keine neue
  Funktionalität ohne Bedarf“); das bestehende, konfigurierbare
  Update-Intervall gilt als angemessen für diesen Anwendungsfall.

## [0.12.0] - Unveröffentlicht

### Hinzugefügt

- Image Entity „Hauptbild“ (`image.py`, `HofKarteHauptbildImage`) pro
  Hofladen: nutzt Home Assistants native `image`-Entity-Plattform
  (`homeassistant.components.image.ImageEntity`) – die plattformgerechte
  Lösung für Bild-URLs, da nur echte `image`-Entities von
  Home-Assistant-Dashboards (z. B. Picture-Entity-Cards) automatisch als
  Bild dargestellt werden. Home Assistant übernimmt Abruf und
  Zwischenspeicherung selbst; keine eigene Download-/Thumbnail-Pipeline.
- `images.py`: reine, testbare Fachfunktionen `is_valid_image_url`
  (nur `http`/`https`, keine Zugangsdaten, keine literale
  private/interne IP-Adresse), `get_main_image_url` (erstes Bild mit
  sicherer URL = Hauptbild, Reihenfolge in `Hofladen.bilder` bestimmt
  die Priorität – bewusst kein zusätzliches „ist Hauptbild“-Feld im
  Datenmodell) und `get_additional_images` (alle sicheren Bilder ausser
  dem Hauptbild als einfache, JSON-taugliche Liste).
- „Weitere Bilder“ (über das Hauptbild hinaus) werden als
  `extra_state_attributes` (`weitere_bilder`) an derselben Image-Entity
  bereitgestellt statt als eigene Entities oder Galerie (Grenzen dieser
  Grundsatz: „Keine React-Galerie“) – analog zum bestehenden
  Sortiment-Attribute-Muster.
- Cache-Invalidierung bei Bildänderung: Ändert sich die Hauptbild-URL
  eines Hofladens (z. B. über das Verwaltungspanel), wird Home
  Assistants interner Bild-Cache (`ImageEntity._cached_image`)
  zurückgesetzt und `image_last_updated` erneuert – sonst würde
  weiterhin das alte, bereits abgerufene Bild ausgeliefert.
- Umfangreiche Tests: `images.py` (gültige/ungültige Schemata,
  Zugangsdaten, private/reservierte/Loopback-/Link-Local-IP-Literale,
  fehlende Bilder, JSON-Serialisierbarkeit) und `image.py`
  (`unique_id`-Muster, Hauptbild-Ermittlung inkl. Überspringen
  unsicherer Bilder, Verhalten ohne Bilder, Attribute, Cache-
  Invalidierung bei URL-Änderung, Device-Zuordnung, dynamische
  Entity-Erzeugung für neu hinzugefügte Hofläden).

### Geändert

- `__init__.py`: `PLATFORMS` umfasst nun zusätzlich `image`.

### Entfernt

- `camera.py`: eine unvollständige, nicht verdrahtete und ungetestete
  alternative Implementierung über die `camera`-Plattform (eigener
  `aiohttp`-Bildabruf statt Home Assistants `image`-Entity-Mechanismus).
  Stand im Widerspruch zur hier getroffenen Architekturentscheidung
  (natives `image`-Entity) und wurde entfernt, um keinen toten,
  widersprüchlichen Code im Repository zu belassen.

### Architekturentscheid: Bilddarstellung

- Für Hofladen-Bilder wird Home Assistants natives `image`-Entity
  verwendet statt einer reinen Attribut-Lösung oder der
  `camera`-Plattform. Begründung: Nur echte `image`-Entities werden von
  Standard-Lovelace-Karten automatisch als Bild gerendert; ein
  beliebiges Attribut mit einer URL-Zeichenkette wird das nicht.

### Behoben (während der Implementierung)

- **Blockierender Aufruf in `images.py`:** Eine frühere Fassung der
  URL-Sicherheitsprüfung löste den Hostnamen über das blockierende,
  synchrone `socket.getaddrinfo` auf, um private/interne IP-Adressen
  auch hinter einem Domainnamen zu erkennen. Da diese Prüfung aus einer
  Entity-Property (`image_url`) heraus aufgerufen wird, hätte dies den
  Home-Assistant-Event-Loop blockiert (Regeln: „keine blockierenden
  Aufrufe“). Behoben durch eine rein syntaktische Prüfung ohne
  DNS-Auflösung (nur IP-Literale werden gegen bekannte
  private/reservierte Bereiche geprüft); die bewusste Grenze dieser
  vereinfachten Prüfung ist im Moduldoc von `images.py` dokumentiert.
- Ein Testfehler in `test_image.py` (`_FakeProvider` unterstützt keine
  Schreibzugriffe, ein Test rief dennoch `async_update_hofladen_sortiment`
  auf) wurde behoben, indem die Testdaten direkt manipuliert und ein
  regulärer Refresh angestossen werden.

### Bewusst nicht implementiert

- Optionale Diagnostics/Zusatzinformationen (im Plan als „optional“
  genannt): Gegenstand eines eigenen, späteren Arbeitsschritts
  „Diagnostics, Fehlerbehandlung, Performance und Qualität“.

## [0.11.0] - Unveröffentlicht

### Hinzugefügt

- Home-Assistant-Action `hofkarte.hoflaeden_suchen`
  (`services.py`, Fachlogik in `search.py`): durchsucht und filtert die
  verwalteten Hofläden. Parameter (alle optional, UND-verknüpft):
  `suchbegriff` (Freitext über Name/Beschreibung/Ort, Teilstring),
  `kategorie`, `produkt`, `verkaufsart`, `zahlungsart`, `merkmal`
  (jeweils exakter, case-insensitiver Namensabgleich), `nur_geoeffnet`
  (nutzt `opening_hours.is_open`, keine eigene Berechnungslogik). Liefert
  Rückgabedaten (`SupportsResponse.ONLY`): Trefferanzahl sowie je
  Treffer eine knappe Auswahl (`id`, `name`, `geoeffnet`).
- `search.py`: reine, testbare Fachfunktion `find_hoflaeden` ohne
  Home-Assistant-Abhängigkeit (analog zu `opening_hours.py`,
  `distance.py`, `attributes.py`).
- `services.yaml` sowie `strings.json`/`translations/{en,de}.json`:
  Feldbeschreibungen für die Action (Titel, Beschreibung je Parameter),
  sichtbar in Entwicklerwerkzeuge → Aktionen.
- Umfangreiche Tests: `search.py` (Freitext, alle fünf Filterdimensionen
  einzeln und kombiniert, `nur_geoeffnet` inkl. unbekanntem
  Öffnungsstatus, Reihenfolge/Unveränderlichkeit der Eingabe) sowie
  `services.py` (Registrierung, Rückgabedaten für verschiedene
  Filterkombinationen, Schema-Validierung ungültiger Datentypen und
  unbekannter Felder).

### Geändert

- `__init__.py`: `async_setup` registriert die neue Action zusätzlich zu
  WebSocket-Befehlen und Frontend-Assets (Domain-Ebene, analog zum
  bestehenden Muster – Actions sind nicht an eine einzelne Config Entry
  gebunden).

### Behoben (während der Implementierung)

- **Bug in `services.py`:** Der Service-Handler war ursprünglich als
  `lambda call: _async_hoflaeden_suchen(hass, call)` registriert. Eine
  `lambda`-Hülle um eine `async def`-Funktion liefert beim Aufruf eine
  nicht ausgeführte Coroutine zurück; Home Assistant erkennt eine
  `lambda` nicht als Koroutinenfunktion und awaitet sie nicht,
  wodurch die Coroutine selbst (statt eines Dicts) als Rückgabewert
  ankam und `homeassistant.exceptions.HomeAssistantError:
  service_reponse_invalid` auslöste. Behoben durch eine eigene
  `async def _service_handler(call)`-Funktion. Durch die eigene
  Testsuite gefunden und sofort behoben.

### Bewusst nicht implementiert

- Eigene „Hofladen-Daten aktualisieren“-Action: Home Assistants
  eingebaute Action `homeassistant.update_entity` deckt dies für alle
  HofKarte-Entities (basierend auf `CoordinatorEntity`) bereits ab –
  eine eigene Action würde dies nur duplizieren.
- Separate Actions je Filterdimension: eine einzige Such-Action mit
  mehreren optionalen Parametern deckt alle geforderten Fälle ab.
- Keine proprietäre REST-API, keine globale Suche über andere
  Home-Assistant-Integrationen hinweg.

## [0.10.3] - Unveröffentlicht

### Hinzugefügt

- Natives Home-Assistant-Sidebar-Panel „HofKarte“ zur grafischen
  Verwaltung der Hofläden (`frontend.py`, `management.py`): Hofläden
  können über die Oberfläche neu erstellt, bearbeitet und dauerhaft
  gelöscht werden. Stammdaten, Koordinaten, reguläre und
  Sonderöffnungszeiten sowie Sortiment und Eigenschaften sind grafisch
  editierbar. Änderungen werden ohne Neustart über den bestehenden
  Storage-Provider und Coordinator in Devices und Entities übernommen.
  Nur für Home-Assistant-Administratoren sichtbar/nutzbar.
- Stammdatenformular um die Felder Name, Beschreibung, Adresse, PLZ/Ort,
  Land, Koordinaten und **Webseite** (`Hofladen.website`, neu im
  Datenmodell und in `parsing.py`) vervollständigt.
- Tests für das Sidebar-Panel (`tests/test_frontend.py`): statische
  Asset-Registrierung, Panel-Registrierung inkl. Konfiguration
  (Sidebar-Titel, `require_admin`, JS-URL), Idempotenz bei
  Doppelregistrierung, korrektes Entfernen beim Entladen sowie
  No-Op-Verhalten, wenn kein Panel registriert ist.
- Tests für die WebSocket-Verwaltungs-API (`tests/test_management.py`):
  JSON-Serialisierung verschachtelter Hofladen-Daten (Zeiten, Tupel),
  Fehlerfall ohne eingerichtete Integration, Auflisten, Erstellen (mit
  automatisch generierter ID), Aktualisieren, Ablehnen ungültiger Daten,
  Löschen, Fehler bei unbekannter ID sowie bei einem nicht
  schreibfähigen Data Provider, und Registrierung aller drei
  WebSocket-Befehle.

### Behoben

- **Kritischer Bug in `frontend.py`:** `manifest.json` deklarierte keine
  Abhängigkeit zu `http`. Dadurch war `hass.http` zum Zeitpunkt von
  `async_setup_frontend_assets` nicht zuverlässig initialisiert (`None`)
  und der Aufruf von `hass.http.async_register_static_paths(...)` konnte
  mit `AttributeError` fehlschlagen – was den Start der **gesamten**
  HofKarte-Integration verhindert hätte, nicht nur des Panels. Behoben
  durch `"dependencies": ["http"]` in `manifest.json`.
- `frontend.py`: ungenutzten Import (`const.DOMAIN`) entfernt
  (pyflakes-Fund).

### Sicherheit

- Verwaltungsoberfläche und alle Schreiboperationen erfordern
  Home-Assistant-Administratorrechte (`require_admin`).
- Keine externe Datenquelle, keine externe API und keine
  Standortübertragung durch die Verwaltungsoberfläche.

### Architekturentscheid: eigene grafische Verwaltungsoberfläche

- Bestätigt und beibehalten: Abweichend vom ursprünglichen Plan
  („Keine eigene UI“, „Keine proprietäre REST-API“) verwaltet
  HofKarte Hofläden über ein eigenes Sidebar-Panel mit
  WebSocket-Backend (`frontend.py`, `management.py`) statt über
  Home-Assistant-Actions/Services. Diese Abweichung ist bewusst und
  dokumentiert (siehe README, Abschnitt „Grafische
  Hofladenverwaltung“).

### Architekturentscheid: Datenquelle final festgelegt

- Löst eine zuvor offene Architekturentscheidung: Home Assistant
  ist sowohl Laufzeitumgebung als auch Verwaltungsoberfläche für
  HofKarte. Die vom Benutzer gepflegten Hofläden werden in einem
  integrationsinternen, persistenten Store gehalten (Home Assistants
  `helpers.storage.Store`) – keine externe Datenbank, kein externer
  Dienst, keine eigene REST-API. Der `HofladenDataProvider` kapselt
  diesen Store; Coordinator und Entities greifen ausschliesslich über
  diese Abstraktion darauf zu.
- `data_provider.py`: neue produktive Implementierung
  `StorageHofladenDataProvider`. Startet leer (keine erfundenen
  Beispieldaten), lädt Daten einmalig (Lazy Load, In-Memory-Cache) und
  schreibt bei jeder Mutation sowohl in den Cache als auch persistent in
  den Store. Ein `asyncio.Lock` schützt vor verlorenen Schreibzugriffen
  bei gleichzeitigen Änderungen.
- Tests für `StorageHofladenDataProvider`: leerer Start, Kopie bei
  `fetch`, Hinzufügen/Abrufen, doppelte ID abgelehnt, Update mit
  Feld-Merge, unbekannte ID abgelehnt, sowie zwei Tests, die *echte*
  Persistenz über eine neue Provider-Instanz hinweg verifizieren
  (simuliert einen Neustart/Reload).
- `test_init.py`: neuer Test, der bestätigt, dass ein frischer Eintrag
  ohne Hofläden startet, sowie ein End-zu-End-Test, der einen echten
  Reload durchführt und bestätigt, dass ein zuvor hinzugefügter Hofladen
  diesen übersteht.

### Weitere Korrekturen

- Veraltete Dokumentation im Config Flow und Parsing zum inzwischen
  festgelegten Data Provider entfernt.
- Verhalten bei entfernten Hofläden dokumentiert: Das Device wird
  entfernt, bereits registrierte Entities bleiben mit stabiler
  `unique_id` bestehen und werden `unavailable`.
- Home-Assistant-Position für den Distance Sensor plausibilisiert: Das
  Standardpaar `0.0/0.0` wird als unbekannt behandelt; gültige einzelne
  `0.0`-Koordinaten bleiben zulässig. Tests dafür ergänzt.

### Geändert

- `__init__.py`: `async_setup_entry` verwendet nun
  `StorageHofladenDataProvider(hass)` statt `StaticTestDataProvider()`.
  `StaticTestDataProvider` bleibt unverändert als reiner
  Testdaten-Provider für die Testsuite bestehen.
- `data_provider.py`: Moduldokumentation und Docstring von
  `StaticTestDataProvider` aktualisiert (nicht mehr „offene
  Architekturentscheidung“, sondern klar als testspezifisch markiert).
- Vier bestehende End-zu-End-Tests (`test_device.py`, `test_sensor.py`,
  `test_binary_sensor.py`), die implizit auf den bisherigen
  Standard-Platzhalter-Hofladen des alten `StaticTestDataProvider` in
  der Produktion angewiesen waren, wurden angepasst: Sie fügen den
  Testdatensatz jetzt explizit über `coordinator.async_add_hofladen`
  hinzu, da ein frischer Store ohne vorbelegte Daten startet.

## [0.9.1] - Unveröffentlicht

### Hinzugefügt

- Sortiment und Eigenschaften eines **bestehenden**
  Hofladens sind jetzt nutzereditierbar.
- `data_provider.py`: `MutableHofladenDataProvider.async_update_raw_hofladen`
  (teilweise Aktualisierung eines bestehenden Rohdatensatzes), neue
  `HofladenNotFoundError`. Implementiert in `StaticTestDataProvider`.
- `coordinator.py`: `HofKarteUpdateCoordinator.async_update_hofladen_sortiment`
  – bewusst auf genau die fünf Fachbereiche beschränkt (Kategorien,
  Produkte, Zahlungsarten, Verkaufsarten, Merkmale); andere Felder
  (Name, Adresse, Öffnungszeiten, ...) bleiben unangetastet. Fail-Fast
  wie bei `async_add_hofladen`: Validierung vor jedem Schreibzugriff,
  Refresh danach für konsistente `coordinator.data` und Entities.
- `const.py`: `STANDARD_ZAHLUNGSARTEN` (Bargeld, Debitkarte, Kreditkarte,
  TWINT), `STANDARD_VERKAUFSARTEN` (Hofladen, Selbstbedienung,
  Verkaufsautomat, Ab-Hof-Verkauf), `STANDARD_MERKMALE` (Bio, eigener
  Anbau, Parkplatz, barrierefrei) als Vorschlagswerte.
- Neues Modul `sortiment_katalog.py`: erzeugt aus den Standardwerten
  direkt verwendbare, gültige Rohdaten (`{"id": ..., "name": ...}`) inkl.
  deterministischer ID-Ableitung (`slug`).
- Tests für Provider-Update (Feld-Merge, unbekannte ID), Coordinator-
  Update (einzelnes Feld, mehrere Felder gleichzeitig, explizites Leeren
  via `[]`, kein Parameter = keine Änderung, unbekannte ID, ungültige
  Daten ändern nichts, nicht unterstützt bei read-only Provider),
  Standardkatalog (Namen, Slug-Determinismus, Round-Trip-Gültigkeit über
  `parse_hofladen`) sowie ein End-zu-End-Test, der bestätigt, dass eine
  Sortiment-Änderung sich ohne Reload in den State-Attributen
  niederschlägt.

### Hinweis

- Wie beim Hinzufügen keine Home-Assistant-Oberfläche (Service/UI) –
  reine Python-Ebene.
- Der Standardkatalog ist ein Vorschlag; Nutzer sind auf keine
  bestimmten Werte beschränkt (siehe `parsing.py`: jeder nicht-leere
  Name ist gültig).

## [0.9.0] - Unveröffentlicht

### Hinzugefügt

- Entfernungsberechnung als reine, testbare Fachfunktionen in
  `distance.py`: `haversine_distance_km` (Grosskreisdistanz, korrekt auch
  über die Datumsgrenze hinweg), `calculate_distance_km` (liefert `None`
  bei fehlender Home- oder Hofladen-Position) und `round_distance_km`
  (Rundung für die Anzeige, standardmässig 1 Nachkommastelle).
- Sensor „Entfernung“ (`HofKarteEntfernungSensor` in `sensor.py`) pro
  Hofladen: Device Class `distance`, Einheit Kilometer,
  `state_class: measurement`, `suggested_display_precision: 1`. Nutzt
  ausschliesslich `hass.config.latitude`/`longitude` als Referenzpunkt.
- Tests für bekannte Koordinaten, identische Koordinaten (0 km),
  Symmetrie, Antipoden (halber Erdumfang), Datumsgrenze, Rundung,
  fehlende Home-Position, fehlende Hofladen-Koordinaten sowie
  End-zu-End-Tests über den tatsächlichen Home-Assistant-State.

### Geändert

- `sensor.py`: `async_setup_entry` registriert zusätzlich
  `HofKarteEntfernungSensor` über den bestehenden
  `async_setup_hofladen_entities`-Mechanismus (automatische Erzeugung
  auch für später hinzugefügte Hofläden, kein Reload nötig).

### Eingehaltene Grenzen

- Keine Speicherung der Home-Assistant-Position durch die Integration –
  `hass.config.latitude`/`longitude` wird bei jeder Berechnung live
  gelesen, nie zwischengespeichert.
- Keine Standortübertragung an externe Dienste – die Berechnung erfolgt
  vollständig lokal (reine Mathematik, kein Netzwerkzugriff).
- Keine eigene Kartenkomponente.

## [0.8.0] - Unveröffentlicht

### Hinzugefügt

- Sortiment und Eigenschaften (Kategorien, Produkte, Zahlungsarten,
  Verkaufsarten, Merkmale) als `extra_state_attributes` am Binary Sensor
  „Geöffnet“ (`attributes.py`, `build_sortiment_attributes`). Bewusst
  keine zusätzlichen Sensoren erstellt (Regeln: „Keine künstlichen
  Messwerte“, „Keine unnötigen Entities“).
- Produkte enthalten die aufgelösten Namen ihrer zugeordneten Kategorien
  (Fallback auf die rohe Kategorie-ID, falls diese im Hofladen nicht
  existiert).
- Fehlende Sammlungen ergeben stets eine leere Liste statt `None` oder
  einem fehlenden Schlüssel (stabile Attributstruktur).
- Namen werden für eine deterministische Darstellung sortiert
  (`str.casefold`, Unicode-Codepoint-Reihenfolge).
- Tests für vollständiges Mapping, fehlende Werte, Kategorie-Auflösung
  (inkl. unbekannter IDs), Sortierverhalten sowie End-zu-End-Tests über
  den tatsächlichen Home-Assistant-State.

### Geändert

- `binary_sensor.py`: `HofKarteGeoeffnetBinarySensor` liefert nun
  `extra_state_attributes` über `attributes.build_sortiment_attributes`.

### Bewusst nicht dupliziert

- Die Sensoren „Nächste Öffnung“/„Nächste Schliessung“ tragen diese
  Attribute nicht (Grundsatz: grosse Datenmengen nicht bei
  jeder State-Änderung duplizieren) – durch einen expliziten Test
  abgesichert.

## [0.7.0] - Unveröffentlicht

### Hinzugefügt

- Vollständige, deterministische Öffnungszeiten-Berechnung in
  `opening_hours.py`: `is_open`, `get_next_opening`, `get_next_closing`.
  Unterstützt mehrere Intervalle pro Tag, Sonderöffnungszeiten
  (inkl. Sonder-Schliessung über einen Datumsbereich),
  Mitternachtsüberschreitung, Wochenwechsel und die Zeitzone des
  Home-Assistant-Systems (zeitzonenbewusste Berechnung statt naiver
  Datums-/Uhrzeit-Arithmetik).
- Binary Sensor „Geöffnet“ sowie die Sensoren „Nächste Öffnung“ und
  „Nächste Schliessung“ liefern nun echte berechnete Werte statt des
  bisherigen Platzhalter-Zustands „unbekannt“.
- Umfangreiche Tests für alle geforderten Mindestfälle:
  offen innerhalb eines Intervalls, geschlossen vor Öffnung, geschlossen
  nach Schliessung, zwei Intervalle am selben Tag, Mitternacht (vor/nach/
  nach Ende), Sonderöffnung, Sonder-Schliessung (Einzeltag und
  Datumsbereich), Wochenwechsel sowie Zeitzonen-/Sommerzeit-Grenzfälle.

### Geändert

- `parsing.py`: Validierungsregel für `beginn`/`ende` (Öffnungszeit und
  Sonderöffnungszeit) gelockert. Bisher wurde `ende <= beginn`
  grundsätzlich abgelehnt; nun ist nur noch `ende == beginn` ungültig.
  `ende < beginn` ist gültig und wird als Mitternachtsüberschreitung
  interpretiert. Diese Änderung war notwendig, um die geforderte
  Mitternachtsüberschreitung überhaupt abbilden zu können
  (Grenzen: „Keine Änderung der Entitätsarchitektur außer soweit für
  korrekte Zustände notwendig“).
- Bestehende Parsing-Tests entsprechend angepasst: der bisherige Test
  „Ende vor Beginn wird abgelehnt“ wurde durch einen Test ersetzt, der
  bestätigt, dass dies nun gültig ist (Mitternachtsüberschreitung); ein
  neuer Test deckt weiterhin `ende == beginn` als ungültig ab.

### Bekannte Grenze

- Uhrzeiten, die exakt in eine Sommerzeit-Umstellungslücke fallen oder im
  doppelt vorkommenden Bereich beim Zurückstellen liegen, werden mit der
  von Python/`zoneinfo` standardmässig gewählten Auflösung berechnet
  (kein explizites Disambiguieren dieser seltenen Grenzfälle).

## [0.6.0] - Unveröffentlicht

### Hinzugefügt

- Binary Sensor „Geöffnet“ (`binary_sensor.py`) pro Hofladen. Bewusst
  ohne Device Class, da keine Home-Assistant-Device-Class für „Geschäft
  geöffnet“ passt.
- Sensoren „Nächste Öffnung“ und „Nächste Schliessung“ (`sensor.py`) pro
  Hofladen, Device Class `timestamp`.
- Gemeinsame Entity-Basisklasse `HofKarteEntity` (`entity.py`) mit
  Device-Zuordnung und Verfügbarkeit (abhängig vom letzten
  Coordinator-Abruf und der Existenz des Hofladens in den Daten).
- `async_setup_hofladen_entities`-Helper (`entity.py`): legt Entities für
  alle aktuellen und künftig über den Coordinator hinzukommenden
  Hofläden an, ohne dass ein Reload nötig ist.
- Vorgesehenes Berechnungsmodul `opening_hours.py` (zu diesem
  Zeitpunkt noch als Stub, liefert `None`; die robuste Implementierung
  folgt in einer späteren Version).
- Tests für Entity-Erzeugung, `unique_id`-Muster, Device-Zuordnung,
  fehlende Device Class beim Binary Sensor, Verfügbarkeit, sowie die
  dynamische Entity-Erzeugung bei neu hinzugefügten Hofläden.

### Geändert

- `__init__.py`: `PLATFORMS` umfasst nun `binary_sensor` und `sensor`.

### Behoben

- `data_provider.py`: `StaticTestDataProvider()` ohne explizite Testdaten
  referenzierte bisher die geteilte Default-Liste direkt statt einer
  Kopie. `async_add_raw_hofladen` konnte dadurch globalen, über
  Testläufe hinweg geteilten Zustand verändern. Behoben, indem der
  Konstruktor in jedem Fall eine Kopie anlegt.

## [0.5.1] - Unveröffentlicht

### Hinzugefügt

- `MutableHofladenDataProvider`-Schnittstelle in `data_provider.py` für
  Provider mit Schreibzugriff, implementiert von `StaticTestDataProvider`
  (`async_add_raw_hofladen`, lehnt doppelte IDs mit
  `DuplicateHofladenIdError` ab).
- `HofKarteUpdateCoordinator.async_add_hofladen(raw_hofladen)`: validiert
  neue Hofladen-Rohdaten (Fail-Fast), reicht sie an den Provider weiter
  und stösst einen Refresh an, sodass Daten und Device Registry
  automatisch konsistent bleiben.
- Tests für erfolgreiches Hinzufügen, ungültige Rohdaten, doppelte IDs,
  nicht unterstützende (rein lesende) Provider sowie einen
  End-zu-End-Test, der bestätigt, dass ein neuer Hofladen automatisch ein
  Device erhält.

## [0.5.0] - Unveröffentlicht

### Hinzugefügt

- Device-Repräsentation für Hofläden (`device.py`): stabile
  `identifiers`, die ausschliesslich auf `Hofladen.id` basieren, sowie
  Synchronisation mit der Device Registry.
- `async_sync_devices` erzeugt bzw. aktualisiert für jeden Hofladen ein
  Device und entfernt Devices von Hofläden, die nicht mehr in den
  Coordinator-Daten enthalten sind.
- Devices werden beim Einrichten der Config Entry und bei jedem weiteren
  Coordinator-Update synchronisiert (`coordinator.async_add_listener`).
- Tests für Identifier-Stabilität, keine Hersteller-/Modellangaben,
  Erstellung mehrerer sauber getrennter Devices, Idempotenz bei Reload,
  Aktualisierung bei Namensänderung, Entfernen verschwundener Hofläden
  sowie einen End-zu-End-Test über `async_setup_entry`.

### Geändert

- `__init__.py`: ruft nach dem initialen Datenabruf `async_sync_devices`
  auf und hält die Device Registry über einen Coordinator-Listener aktuell.

## [0.4.0] - Unveröffentlicht

### Hinzugefügt

- Zentraler `HofKarteUpdateCoordinator` (`coordinator.py`) für den
  asynchronen Abruf, die Validierung und Bereitstellung der
  Hofladen-Daten als `dict[str, Hofladen]`.
- Data-Provider-Abstraktion (`data_provider.py`) mit
  `HofladenDataProvider`-Schnittstelle und einer Testdaten-Implementierung
  (`StaticTestDataProvider`), solange die tatsächliche Datenquelle nicht
  feststeht.
- Konfigurierbares Update-Intervall (Standard 15 Minuten) und
  Abruf-Timeout (Standard 30 Sekunden) als Coordinator-Parameter.
- Initialer Datenabruf beim Einrichten der Config Entry über
  `async_config_entry_first_refresh` (inkl. automatischem Retry via
  `ConfigEntryNotReady` bei Fehlschlag).
- Tests für erfolgreichen Abruf, Zeitüberschreitung, Datenquellenfehler,
  einzelne ungültige Datensätze, leere Datenquelle und Verhalten bei
  einem Fehlversuch nach vorherigem Erfolg.

### Geändert

- `__init__.py`: `async_setup_entry` erstellt und startet nun den
  Coordinator und legt ihn (statt eines leeren Platzhalter-Dicts) unter
  `hass.data[DOMAIN][entry.entry_id]` ab.
- `const.py`: `DEFAULT_UPDATE_INTERVAL` und
  `DEFAULT_FETCH_TIMEOUT_SECONDS` ergänzt.

### Offene Architekturentscheidung

- Die konkrete Datenquelle für Hofladen-Rohdaten steht weiterhin nicht
  fest. Der Coordinator nutzt bewusst einen Testdaten-Provider
  (`StaticTestDataProvider`) statt einer erfundenen externen API.

## [0.3.0] - Unveröffentlicht

### Hinzugefügt

- Internes, typisiertes Datenmodell für Hofläden (`models.py`): Stammdaten,
  Öffnungszeiten, Sonderöffnungszeiten, Produkte, Kategorien,
  Zahlungsarten, Verkaufsarten, Merkmale, optionale Bilder. Alle
  Datenstrukturen sind unveränderlich (frozen dataclasses).
- Parsing/Validierung roher Hofladen-Daten in das interne Modell
  (`parsing.py`) inkl. `HofladenValidationError` bei ungültigen oder
  unvollständigen Pflichtdaten.
- Umfangreiche Tests für vollständige und unvollständige Datensätze sowie
  für einzelne Validierungsregeln (Koordinatenbereich, Zeitformate,
  Öffnungszeit-Reihenfolge, Sonderöffnungszeit-Regeln).

## [0.2.0] - Unveröffentlicht

### Hinzugefügt

- Config Flow (`config_flow.py`) zur Einrichtung über die
  Home-Assistant-Oberfläche.
- Config-Entry-Lifecycle (`async_setup_entry` / `async_unload_entry`) in
  `__init__.py`.
- Übersetzungsgrundlage (`strings.json`) sowie Übersetzungen für Englisch
  (`translations/en.json`) und Deutsch (`translations/de.json`).
- Tests für erfolgreichen Flow, ungültige Eingaben und doppelte Einrichtung.
- Tests für Setup/Unload einer Config Entry.

### Geändert

- `manifest.json`: `config_flow` auf `true` gesetzt.
- YAML-basiertes `async_setup` entfernt zugunsten von Config Entries
  (siehe Globale Konventionen: keine YAML-Konfiguration parallel zum
  Config Flow).

## [0.1.0] - Unveröffentlicht

### Hinzugefügt

- Minimales, ladbares Home-Assistant-Integrationsgrundgerüst (Domain `hofkarte`).
- Grundlegende HACS-kompatible Repository-Struktur (`hacs.json`).
- README mit Installations- und Entwicklungsgrundlagen.
- Minimale Teststruktur (pytest + Home-Assistant-Testwerkzeuge).
