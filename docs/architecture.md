# Architektur

Technischer Überblick über HofKarte für Entwickler:innen und
Beitragende. Für die Endanwender-Perspektive siehe
[`docs/handbuch.md`](handbuch.md); für Installation/Kurzübersicht siehe
[`README.md`](../README.md).

## Grundprinzip

Home Assistant ist sowohl **Laufzeitumgebung als auch
Verwaltungsoberfläche** für HofKarte (Architekturentscheid, siehe
CHANGELOG). Es gibt:

- keine eigenständige Webanwendung,
- kein externes Backend,
- keine externe Datenbank,
- keine externe API, die HofKarte selbst aufruft (Ausnahme: das Laden
  vom Benutzer hinterlegter Hofladen-Bild-URLs).

Alle Daten liegen ausschliesslich lokal im
Home-Assistant-eigenen Storage.

## Zusammenspiel der Kernkomponenten

```text
┌─────────────────┐     ┌───────────────────────┐     ┌──────────────────┐
│   Config Flow    │────▶│      ConfigEntry       │────▶│  async_setup_entry │
│ (config_flow.py) │     │  (Anzeigename, Single-  │     │   (__init__.py)    │
└─────────────────┘     │   Instance erzwungen)   │     └────────┬──────────┘
                         └───────────────────────┘              │
                                                                  ▼
┌──────────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ StorageHofladen-  │◀───▶│ HofKarteUpdateCoordinator│────▶│  device.py        │
│ DataProvider      │     │   (coordinator.py)       │     │ (Device Registry)  │
│ (data_provider.py)│     └────────────┬─────────────┘     └──────────────────┘
└──────────────────┘                  │
                                        ▼
                         ┌──────────────────────────────┐
                         │ Entities (binary_sensor.py,   │
                         │ sensor.py, image.py)          │
                         │ – lesen ausschliesslich aus    │
                         │   coordinator.data             │
                         └──────────────────────────────┘
```

### Config Flow → ConfigEntry

`config_flow.py` fragt genau **ein** Feld ab (Anzeigename,
`CONF_NAME`). HofKarte ist als Single-Instance-Integration ausgelegt:
`self._async_current_entries()` verhindert eine zweite Einrichtung
(Abbruchgrund `single_instance_allowed`). Es gibt **keinen Options
Flow** (siehe `quality_scale.yaml`, Kriterium `reconfiguration-flow`).

### ConfigEntry → Setup

`__init__.py` unterscheidet zwei Setup-Ebenen:

- **`async_setup(hass, config)`** – läuft einmalig beim Laden der
  Domain (unabhängig von einer konkreten ConfigEntry): registriert die
  WebSocket-Verwaltungsbefehle (`management.py`), die statischen
  Frontend-Assets (`frontend.py`) und die Home-Assistant-Action
  (`services.py`).
- **`async_setup_entry(hass, entry)`** – läuft je ConfigEntry: erstellt
  `StorageHofladenDataProvider` und `HofKarteUpdateCoordinator`, führt
  den initialen Datenabruf durch, synchronisiert die Device Registry
  und leitet an die Entity-Plattformen weiter
  (`Platform.BINARY_SENSOR`, `Platform.SENSOR`, `Platform.IMAGE`).

### Coordinator → Data Provider

`HofKarteUpdateCoordinator` (`coordinator.py`, Subclass von
`DataUpdateCoordinator`) kennt nur die abstrakte Schnittstelle
`HofladenDataProvider`/`MutableHofladenDataProvider`
(`data_provider.py`) – nicht deren konkrete Implementierung. Produktiv
kommt `StorageHofladenDataProvider` zum Einsatz (kapselt Home
Assistants `helpers.storage.Store`, JSON-Datei unter `.storage/`);
`StaticTestDataProvider` ist eine reine In-Memory-Variante für die
Testsuite.

Der Coordinator bietet öffentliche Schreibmethoden
(`async_add_hofladen`, `async_update_hofladen_sortiment`,
`async_save_hofladen`, `async_delete_hofladen`) – **alle**
Schreibzugriffe (Verwaltungsoberfläche, künftige eigene Skripte) laufen
über diese Methoden, nie direkt über den Data Provider. Jede Methode
validiert Fail-Fast über `parsing.parse_hofladen`, bevor irgendetwas
geschrieben wird, und setzt danach den bereits validierten Stand
**inkrementell** in `coordinator.data` ein (`async_set_updated_data`,
kein `async_refresh()` mit erneutem Parsen aller Datensätze; Befund F5).
`async_save_many`/`async_schreibe_vorbereitete` speichern mehrere
Datensätze in **einem** Schreibvorgang (`async_apply_changes` des
Providers, atomar) und lösen **ein** Update aus.

### Coordinator → Devices/Entities

`device.py` (`async_sync_devices`) gleicht die Device Registry bei
jedem Coordinator-Update mit den aktuellen Hofladen-Daten ab: neue
Hofläden erhalten ein Device, entfernte Hofläden verlieren ihres
(idempotent, keine Duplikate bei Reload).

Entities (`binary_sensor.py`, `sensor.py`, `image.py`) erben von der
gemeinsamen Basisklasse `HofKarteEntity` (`entity.py`,
`CoordinatorEntity`-Subklasse) und lesen **ausschliesslich** aus
`coordinator.data` – keine eigenen Netzwerk- oder Datenzugriffe pro
Entity. `entity.async_setup_hofladen_entities` legt beim Setup Entities
für alle bekannten Hofläden an und reagiert über einen
Coordinator-Listener automatisch auf später hinzukommende Hofläden
(kein Reload nötig).

## Datenmodell und Datenquelle

`models.py` definiert das interne, unveränderliche (`frozen`
Dataclasses) Datenmodell (`Hofladen`, `Oeffnungszeit`,
`Sonderoeffnungszeit`, `Angebot`, `Zahlungsart`, `Bild`). `parsing.py`
überführt rohe, JSON-kompatible `dict`-Daten in dieses Modell und
validiert dabei (`HofladenValidationError` bei ungültigen
Pflichtfeldern).

**Architekturentscheid – Angebote statt Kategorien/Produkte, ohne
Gruppierung:** Die früher getrennten Konzepte `Kategorie` (eigene, über
IDs referenzierte Liste) und `Produkt` (referenziert Kategorien über
`kategorie_ids`) wurden zunächst zu einem gemeinsamen `Angebot`
zusammengelegt und danach – nach weiterer Vereinfachung – auf
`Angebot(id, name)` reduziert: **keine Gruppierung mehr**. Ein
zwischenzeitlich eingeführtes Feld `gruppen` (frei formulierte
Textbezeichnungen direkt am Angebot) wurde wieder entfernt, da der
Mehrwert der Gruppierung den zusätzlichen Pflegeaufwand nicht
rechtfertigte (siehe CHANGELOG).

`parsing.py` enthält weiterhin `_migriere_kategorien_und_produkte_zu_angeboten`:
eine Migration, die beim Einlesen alter Rohdaten (Schlüssel
`kategorien`/`produkte`) automatisch greift, sobald der Schlüssel
`angebote` fehlt. Seit der Vereinfachung werden sowohl Kategorien als
auch Produkte gleichermassen zu flachen Angebot-Einträgen (nur
`id`/`name`) – eine `kategorie_ids`-Auflösung findet nicht mehr statt,
da es keine Gruppierung mehr gibt, in die sie einfliessen könnte. Liegt
bereits das neue Format vor (`angebote`-Schlüssel vorhanden), greift
die Migration nicht (Idempotenz, siehe
`tests/test_migration_kategorien_produkte_zu_angebote.py`). Ein
eventuell noch vorhandenes `gruppen`-Feld an einzelnen Angeboten wird
beim Einlesen ignoriert, nicht übernommen.

**Ebenfalls entfernt:** Die Fachbereiche `Verkaufsart` und `Merkmal`
wurden ersatzlos aus dem Datenmodell entfernt (siehe CHANGELOG).
Bestehende Rohdaten mit diesen Feldern werden beim Einlesen weiterhin
fehlerfrei verarbeitet (die Felder werden schlicht nicht mehr
ausgewertet).

**Neu: `Hofladen.bemerkung`** – ein von `beschreibung` unabhängiges,
optionales Freitextfeld auf Hofladen-Ebene (nicht je Angebot, da
Angebote seit der Vereinfachung bewusst keine weitere Struktur mehr
tragen).

Die Datenquelle ist final festgelegt (siehe CHANGELOG,
„Architekturentscheid: Datenquelle final festgelegt“): ein
integrationsinterner, persistenter Store
(`StorageHofladenDataProvider`), gepflegt über die grafische
Verwaltungsoberfläche. Keine externe Datenbank, kein externer Dienst.

## Öffnungszeiten-Logik

`opening_hours.py` ist die **alleinige** Stelle für die
Öffnungsstatus-Berechnung (`is_open`, `get_next_opening`,
`get_next_closing`). Statt Wochentage modular zu vergleichen, werden
für ein Zeitfenster rund um den Berechnungszeitpunkt konkrete,
zeitzonenbewusste Datum-Uhrzeit-Intervalle erzeugt
(`datetime.combine(datum, uhrzeit, tzinfo=...)` statt naiver
`timedelta`-Arithmetik). Das macht Mitternachtsüberschreitung und
Wochenwechsel zu Spezialfällen der allgemeinen Logik statt zu eigenem
Sonderfall-Code. Sonderöffnungszeiten überschreiben reguläre
Öffnungszeiten vollständig für ihr Datum.

## Geo-/Entfernungslogik

`distance.py` berechnet die Luftlinien-Entfernung
(Haversine-Formel) zwischen der konfigurierten
Home-Assistant-Position (`hass.config.latitude`/`longitude`) und den
Koordinaten eines Hofladens. Reine, HA-unabhängige Fachfunktionen;
`is_valid_home_position` behandelt das Standardpaar `0.0/0.0` einer
unkonfigurierten Installation als unbekannt.

### Koordinaten und Kartenanzeige (Google Maps)

Koordinaten werden in der Verwaltungsoberfläche als WGS84-Dezimalgrad
erfasst und angezeigt – identisch zum internen Datenmodell
(`models.Hofladen.latitude`/`longitude`). Es findet **keine
Koordinatentransformation** statt: Eingabe-, Speicher- und
Anzeigeformat sind durchgehend dasselbe.

Das Bearbeitungsformular bietet weiterhin einen Button, der den anhand
der gerade eingegebenen Koordinaten ermittelten Standort auf Google
Maps öffnet (`hofkarte-panel.js`, Funktionen `googleMapsUrl`/
`mapButton`). Die WGS84-Koordinaten werden direkt in Google Maps'
offiziell dokumentiertes URL-Schema für einen Standort-Pin übernommen
(`https://www.google.com/maps/search/?api=1&query={lat},{lon}`) – keine
Umrechnung nötig. Der Button ist deaktiviert, wenn keine gültigen
Koordinaten vorliegen (`isValidWgs84`); die Kartenansicht ist ein rein
lesender externer Link ohne neue Abhängigkeit. Dieser Button dient
ausschliesslich der Kontrolle der gerade eingegebenen Koordinaten,
nicht der Navigation zum Hofladen (dafür siehe „Routing-Auswahl“
unten) – im Bearbeitungsformular liegt ggf. noch keine gespeicherte,
konsistente Adresse vor, ein Adress-Routing wäre dort nicht sinnvoll.

### Routing-Auswahl: Google Maps und Apple Maps (Issue #3)

Kacheln-, Listen- und Detailansicht ersetzen den bisherigen einzelnen
Kartenlink durch eine kompakte Routing-Auswahl (`routingAuswahl(item)`
in `hofkarte-panel.js`), die eine echte Wegbeschreibung zum Hofladen
öffnet statt nur eines Standort-Pins – der bisherige Anwendungsfall
(Standort auf einer Karte betrachten) bleibt im Bearbeitungsformular
über `mapButton` erhalten (siehe oben), hier geht es um Navigation.

**Zielbestimmung (`ermittleRoutingZiel`):** Ist eine nicht-leere
zusammengesetzte Adresse (`adresse`, `plz`, `ort`, `land`) hinterlegt,
hat sie Vorrang als Routenziel – eine Adresse ist für eine echte
Wegbeschreibung i. d. R. präziser als ein einzelner Koordinatenpunkt
und wird von beiden Kartendiensten direkt als Freitext akzeptiert
(kein eigener Geocoding-Schritt in HofKarte nötig). Nur wenn keine
Adresse, aber gültige WGS84-Koordinaten (`isValidWgs84`) vorhanden
sind, werden diese als `lat,lon` verwendet. Fehlen beide, gibt es kein
Routing-Ziel – die Auswahl wird dann deaktiviert dargestellt (kein
funktionsloser Link).

**URL-Schemata:**

- Google Maps (offiziell dokumentiert, Directions-Action):
  `https://www.google.com/maps/dir/?api=1&destination={ziel}&travelmode=driving`
- Apple Maps (offiziell dokumentiertes Maps-Link-Schema):
  `https://maps.apple.com/?daddr={ziel}&dirflg=d`

`{ziel}` ist dabei entweder die URL-kodierte Adresse oder
`{lat},{lon}` – `encodeURIComponent` stellt sicher, dass Kommas/
Leerzeichen in Adressen keine ungültige URL erzeugen.

**UI-Entscheidung:** Zwei sehr kompakte, icon-only Buttons (🗺️/🧭)
statt eines einzelnen Buttons mit ausklappbarem Auswahlmenü. Das
vermeidet zusätzlichen Interaktions-/Zustands-Code (kein Öffnen/
Schliessen-Zustand, kein Klick-ausserhalb-Handling) und ist trotzdem
schmaler als der bisherige einzelne Textbutton (`.map-btn`, feste
Höhe mit Text) – wichtig insbesondere in der Tabellenspalte der
Listenansicht (eigenes `.route-btn`/`.route-actions`-CSS, quadratische
34×34px-Buttons statt eines breiten Textbuttons).

### Eingebettete Mehrfach-Marker-Karte (Issue #2, Architekturabweichung)

Der bestehende, rein externe Kartenlink (siehe oben) zeigt bewusst
**einen** Standort bzw. eine Route in einem neuen Tab – für eine
**eingebettete** Karte, die **alle** Hofläden gleichzeitig als Marker
zeigt (Issue #2), ist das technisch etwas anderes und nicht
ausreichend.

**Geprüfte Optionen:**

- Eine native, für Custom Panels vorgesehene Home-Assistant-Karten-
  komponente mit beliebigen eigenen Markern existiert nicht – die
  eingebaute Kartenkarte ist an Lovelace-Dashboards gebunden, nicht an
  eigenständige Sidebar-Panels wie das von HofKarte.
- Eine reine Eigenimplementierung (z. B. ein einfaches, selbst
  gezeichnetes Koordinatenraster ohne echtes Kartenmaterial) hätte den
  eigentlichen Zweck (Wiedererkennung realer Orte/Strassen) verfehlt.
- Eine schlanke JavaScript-Kartenbibliothek mit OpenStreetMap-Kacheln,
  als unveränderte Distributionsdatei im Repository gebündelt (seit
  `2026.10.0-dev.6`, Befund F7) – **ohne** Build-Pipeline, npm-
  Abhängigkeit oder CDN zur Laufzeit.

**Entscheid: [Leaflet](https://leafletjs.com/) `1.9.4` (BSD-2-Clause) +
OpenStreetMap-Kacheln.** Begründung:

- kein API-Schlüssel und kein Kartendienst-Konto nötig
  (OpenStreetMap-Kacheln sind ohne Registrierung nutzbar) – im
  Unterschied zu den meisten kommerziellen Kartendiensten;
- keine Build-Pipeline/npm-Abhängigkeit nötig: die **fest gepinnte**
  Version liegt unverändert unter `static/vendor/leaflet/` und wird von
  Home Assistant ausgeliefert (`/api/hofkarte/static/vendor/…?v=<Version>`);
  **kein CDN** – keine Lieferketten-Abhängigkeit zur Laufzeit, kein
  Verbindungsaufbau zu Dritten ausser den OSM-Kacheln. Herkunft, Lizenz
  (BSD-2-Clause) und SHA-256-Prüfsummen: `THIRD_PARTY_NOTICES.md`;
- seit vielen Jahren aktiv gewartet, sehr verbreitet (u. a. in
  zahlreichen Home-Assistant-HACS-Karten bereits im Einsatz), kompakt
  (~40 KB gzip für JS und CSS zusammen).

Dies ist eine **bewusste, dokumentierte Ausnahme** vom Projektgrundsatz
„keine neuen Abhängigkeiten“ – begrenzt auf genau diese eine, schlanke
Bibliothek für genau diese eine Funktion, nicht Teil einer
Build-Pipeline und nicht in `manifest.json` deklariert (es ist eine
reine Frontend-/Browser-Abhängigkeit, keine Python-Abhängigkeit der
Integration selbst).

**Lazy Loading und Fehlerbehandlung:** `ladeLeaflet()` in
`hofkarte-panel.js` lädt das lokale `<script>` **erst beim ersten
Öffnen** der Kartenansicht, nicht beim Start des Panels – wer die
Kartenansicht nie öffnet, löst auch nie eine Verbindung zum
OpenStreetMap-Kachel-Server aus (siehe Datenschutz-Hinweise im
Handbuch). Das Promise wird je Skript zwischengespeichert. Schlägt das
Laden fehl, wird das fehlerhafte `<script>`-Element wieder entfernt, das
Promise verworfen und die Meldung per `textContent` angezeigt – **ohne**
`render()` (Befund F8: sonst würde `render()` → `initKarte()` →
`ladeLeaflet()` eine Endlosschleife bilden). Ein neuer Versuch erfolgt
nur über „Erneut versuchen“ bzw. beim ausdrücklichen Wechsel in die
Kartenansicht. Analog sperrt `_loadFailed` (Befund F9) das automatische
Laden der Hofladen-Liste bei jeder `hass`-Änderung nach einem
Fehlschlag; stattdessen gibt es einen Backoff-Timer (2 s, 4 s, … max.
60 s) und den Button „Erneut versuchen“. Der `_loading`-Schutz bleibt.

**Clustering:** Ab 200 Markern (`KARTE_CLUSTER_AB`) wird das ebenfalls
lokal gebündelte `leaflet.markercluster` (MIT) nachgeladen. Begründung
gegenüber `preferCanvas`: Die Marker sind DOM-basierte `divIcon`s, ein
Canvas-Renderer greift für sie nicht; Clustering senkt Knotenzahl und
Zeichenlast tatsächlich. Fehlt die Bibliothek, werden die Marker einzeln
dargestellt.

**Rendering innerhalb des Shadow-DOM-Custom-Elements (seit
`2026.10.0-dev.6`, Befund F10):** `<style>` und die Leaflet-
Stylesheets (`<link>`) stehen **dauerhaft** im Shadow Root, `render()`
ersetzt nur noch den Inhalt von `<main>`. Die Karte lebt, solange die
Kartenansicht offen ist: `initKarte()` erzeugt sie **einmal** und hängt
bei weiteren Renders lediglich ihren Container (`_karteHost`) in den
neuen Platzhalter um; bei Filter-/Datenänderung wird nur die
Marker-Ebene getauscht (`aktualisiereMarker()`, mit Signaturvergleich).
`teardownKarte()` (`map.remove()`) läuft nur beim Verlassen der
Kartenansicht bzw. in `disconnectedCallback()`. Es gibt genau einen
`popupopen`-Handler pro Karte. Listen-/Kartenaktionen laufen über eine
einmalig gebundene Event-Delegation auf `<main>`; der Listenfilter ist
mit ~150 ms entprellt und ersetzt nur `<tbody>`; Such-/Sortierschlüssel
werden je Hofladen einmal vorberechnet.

Die Kartengrössenberechnung (`L.map()`) erfolgt, nachdem der Container
bereits über `innerHTML` ins DOM eingefügt wurde (Layout ist zu diesem
Zeitpunkt bereits berechnet); zusätzlich sichert ein
`window.addEventListener("resize", …)` sowie ein einmaliges
`setTimeout(() => map.invalidateSize())` gegen nachträgliche
Layoutänderungen (z. B. eine noch laufende Sidebar-Animation) ab. Der
Resize-Handler wird in `teardownKarte()` wieder entfernt, um keine
Listener über die Lebensdauer der jeweiligen Karteninstanz hinaus
anzusammeln.

**Marker, Popup und Detailansicht-Navigation:** Für jeden Hofladen mit
gültigen Koordinaten (`isValidWgs84`, wiederverwendet aus der
bestehenden Google-Maps-Logik) wird ein `L.marker` gesetzt, dessen
Popup einen Button „Zur Detailansicht“ enthält. Da Leaflet-Popups
ausserhalb des von `render()`/`bind()` erzeugten Markups liegen (sie
werden von Leaflet selbst zur Laufzeit in den Kartencontainer
eingefügt), wird der Klick-Handler **nicht** über die generische
`bind()`-Delegation (`data-view`-Attribute wie bei Kacheln/Liste)
registriert, sondern direkt über das Leaflet-eigene `popupopen`-Event
an `this.view(item)` gebunden – dieselbe Methode, die auch die
`data-view`-Buttons in Kacheln und Liste aufrufen, sodass sich die
Detailansicht selbst nicht unterscheidet.

**Marker-Icon (eigenes Inline-SVG statt Leaflets Standardbild, Issue
#4):** Leaflet bestimmt den Bildpfad seines Standard-Icons zur Laufzeit
automatisch (`Icon.Default._detectIconPath`): Es erzeugt ein
Sondierungselement im echten, globalen `document.body` und liest dessen
berechnete `background-image`-Eigenschaft; findet es dort nichts,
befragt es ersatzweise `document.querySelector('link[href$="leaflet.css"]')`.
Beide Wege scheitern innerhalb dieses Panels: Die weiter oben
beschriebene `leaflet.css`-Einbindung liegt im Shadow DOM von
`<hofkarte-panel>`, ist also für ein Element im globalen `document.body`
stilistisch nicht wirksam (Shadow-DOM-Style-Isolation), und der
`document.querySelector`-Fallback durchquert ebenfalls keine
Shadow-DOM-Grenze, findet das dort liegende `<link>` also nicht. In der
Folge blieb `Icon.Default.imagePath` leer und das von Leaflet erzeugte
Marker-`<img>` zeigte ein defektes Bild (in Home Assistant sichtbar als
„?“-Platzhalter).

Statt Leaflets bild-basiertes Standard-Icon zu reparieren (z. B. über
einen expliziten, absoluten CDN-Bildpfad via
`L.Icon.Default.mergeOptions`), erzeugt `erzeugeKarteMarkerIcon()` ein
eigenes Icon über `L.divIcon()`: reines, selbst geschriebenes Inline-SVG
(Pin-Form mit einem Ladensymbol, angelehnt an das bereits im Panel
verwendete Symbolkonzept, vgl. Sidebar-Icon `mdi:store-edit`) statt
eines `<img>`. Das dabei erzeugte Markup landet als Kind des
Karten-Containers und damit **innerhalb desselben Shadow Roots** wie
die restlichen Panel-Styles – die in `styles()` definierten
`.karte-marker-*`-Regeln greifen daher zuverlässig, ohne auf eine der
beiden (hier nicht funktionierenden) automatischen Pfaderkennungen
angewiesen zu sein. Vorteile gegenüber einer absoluten CDN-Bild-URL:
kein zusätzlicher Netzwerk-Request, keine Abhängigkeit vom Fortbestand
eines bestimmten CDN-Pfads für Bilddateien, und ein Icon, das sich
optisch am übrigen Panel orientiert statt an Leaflets generischem
Tropfen-Symbol. Marker-Position, Popup-Verhalten und die
Detailansicht-Navigation (siehe oben) sind von dieser Änderung nicht
betroffen – es wird ausschliesslich die `icon:`-Option beim Erzeugen
des `L.marker(...)`-Aufrufs ergänzt.

**Geöffnet-Filter:** Die Checkbox „Nur aktuell geöffnete Hofläden
anzeigen“ (`karteNurGeoeffnet`) filtert rein clientseitig auf dem
bereits vorhandenen, serverseitig berechneten Feld `geoeffnet` (siehe
Abschnitt oben) – keine neue Backend-Logik. Ein Wert von `null`
(„unbekannt“) gilt bei aktiviertem Filter konsequent **nicht** als
geöffnet, entsprechend der Anforderung „kein unbestätigter
Optimismus“.

**Kein initiales Nachladen ohne Koordinaten:** Gibt es keinen einzigen
Hofladen mit gültigen Koordinaten, zeigt `karteAnsicht()` direkt eine
Meldung, **ohne** überhaupt zu versuchen, Leaflet nachzuladen oder
einen Kartencontainer zu erzeugen – vermeidet unnötige Netzwerkzugriffe
und eine leere/kaputt wirkende Fläche.

## Sortiment-Logik

`attributes.py` überführt Angebote und Zahlungsarten eines Hofladens in
eine stabile, JSON-taugliche Attributstruktur (jeweils eine schlichte
Namensliste) für den Binary Sensor „Geöffnet“ (siehe Handbuch,
Kapitel 8). `sortiment_katalog.py` bietet einen optionalen
Vorschlagskatalog gängiger Werte (nur für Zahlungsarten – nicht für
Angebote, da diese frei formuliert werden).

## Bilder

`images.py` validiert Bild-URLs (nur `http`/`https`, keine
eingebetteten Zugangsdaten, keine literale private/interne IP-Adresse
– rein syntaktisch, keine DNS-Auflösung, siehe `SECURITY.md`).
`image.py` nutzt Home Assistants natives `image`-Entity und dessen
eigenen Bild-Proxy/Cache – HofKarte implementiert keine eigene
Bildabruf-Pipeline.

### Geführter Bilder-Upload

Der Upload in der Verwaltungsoberfläche (`hofkarte-panel.js`)
implementiert **keinen eigenen** Upload-Endpunkt, sondern nutzt Home
Assistants eingebaute `image_upload`-Komponente vollständig:

- **Upload:** `POST /api/image/upload` (Multipart-Formular), liefert
  eine `image_id` zurück. **Erfordert Authentifizierung**
  (`ImageUploadView.requires_auth` ist nicht überschrieben, erbt also
  `True` von `HomeAssistantView`) – im Unterschied zur Auslieferung
  unten. Der clientseitige `fetch()`-Aufruf muss deshalb explizit einen
  `Authorization: Bearer <token>`-Header mit `this.hass.auth.accessToken`
  setzen; ohne diesen Header schlägt der Upload mit „Login attempt
  failed“/„invalid authentication“ im Home-Assistant-Log fehl, obwohl
  man in der Oberfläche angemeldet ist (behobener Bug, siehe
  CHANGELOG). WebSocket-Befehle (z. B. `image/delete`, `this.call()`)
  sind davon nicht betroffen, da die WebSocket-Verbindung bereits beim
  Verbindungsaufbau authentifiziert wird.
- **Auslieferung:** `GET /api/image/serve/{image_id}/original`
  (`requires_auth = False` in dieser Home-Assistant-Komponente – exakt
  passend zur bestehenden `image.py`-Entity, die eine öffentlich ohne
  zusätzliche Authentifizierung abrufbare Bild-URL erwartet).
- **Löschen:** WebSocket-Befehl `image/delete` (Teil der
  `image_upload`-Komponente, nicht von HofKarte selbst implementiert).
- Deklariert als `manifest.json`-Abhängigkeit (`image_upload`), analog
  zur bestehenden `http`-Abhängigkeit – ohne diese ist nicht garantiert,
  dass die Komponente beim Setup von HofKarte bereits initialisiert ist.

Die vom Upload erzeugte, absolute URL wird clientseitig aus
`window.location.origin` gebildet (der Browser kennt die tatsächlich
erreichbare Basis-URL der aktuellen Sitzung). **Bekannte Grenze:**
Läuft Home Assistant hinter einem Reverse Proxy mit unterschiedlichen
intern/extern erreichbaren Adressen, kann die vom Browser gebildete
URL für den serverseitigen Bildabruf (`ImageEntity._fetch_url`, siehe
oben) u. U. nicht erreichbar sein, obwohl sie im Browser selbst
funktioniert.

**Sicherheitsentscheid – `Bild.hochgeladen`:** Eine über den Upload
erzeugte URL zeigt zwangsläufig auf die eigene Home-Assistant-Instanz –
bei den meisten Installationen eine private LAN-Adresse. Die in
`images.py` beschriebene Ablehnung privater/interner IP-Adressen dient
dem Schutz vor SSRF über frei eingegebene, nicht vertrauenswürdige
externe URLs; sie ist bei einer von HofKarte selbst über den
offiziellen Upload-Weg erzeugten URL das falsche Kriterium. Das
Datenmodell (`models.Bild`) trägt daher ein explizites
`hochgeladen: bool`-Feld; `is_valid_image_url` überspringt bei
`hochgeladen=True` gezielt nur die Adressbereichs-Prüfung, nicht die
Schema-/Zugangsdaten-Prüfung (Defense in Depth). Die Vertrauensbasis
ist damit die **Herkunft** (von HofKarte selbst erzeugt), nicht der
Adressbereich – eine bewusste, im Modul dokumentierte Ausnahme statt
einer fragilen Erkennung anhand des URL-Musters.

## Informationen aus Homepage (Issue #8, Korrektur/Erweiterung in Issue #9)

`webseite_info.py` implementiert die **erste eigene, ausgehende
HTTP-Anfrage im Backend-Code von HofKarte** – bisher delegierte
HofKarte jede Netzwerkkommunikation entweder an Home Assistants eigene
`image`-Entity-Infrastruktur (siehe Kapitel „Bilder“ oben) oder an den
Browser (Leaflet/OpenStreetMap, siehe „Eingebettete Kartenansicht“
weiter unten). Architektonisch bewusst als eigenständiges Modul
umgesetzt, nicht innerhalb von `management.py`, analog zur bestehenden
Trennung `images.py`/`opening_hours.py`/`search.py`.

**Datenfluss:**

1. Verwaltungsoberfläche (`hofkarte-panel.js`): Klick auf „🔎 Infos
   ermitteln“ im Bearbeitungsformular (Abschnitt „Kontakt & Webseite“)
   ruft `ermittleWebseiteInfo()` auf, das den WebSocket-Befehl
   `hofkarte/management/webseite_info` mit der aktuell im Formular
   eingetragenen Website-Adresse sendet.
2. `management.ws_webseite_info` (administratorpflichtig, wie alle
   Verwaltungsbefehle) delegiert an
   `webseite_info.async_ermittle_webseite_info(hass, website)`.
3. `webseite_info.py` prüft die Adresse syntaktisch (siehe
   „Sicherheitsmodell“ unten), ruft sie über Home Assistants verwaltete
   Client-Session ab, extrahiert strukturierte Daten und liefert ein
   `WebseiteInfo`-Objekt (oder wirft einen der drei unten beschriebenen
   Fehler) zurück.
4. `ws_webseite_info` bildet die Fehlerfälle auf eigene WebSocket-
   Fehlercodes ab (`invalid_url`/`unreachable`/`not_found`) bzw.
   serialisiert das Ergebnis (`_json_value`, dieselbe Hilfsfunktion wie
   für `Hofladen`-Objekte).
5. `hofkarte-panel.js` speichert das Ergebnis seit Issue #9 zunächst nur
   als Vorschlag (`this.webseiteInfoVorschlag`) und zeigt es in einem
   Bestätigungs-Popup (`webseiteInfoPopup()`) zur Prüfung an. Erst ein
   Klick auf „Übernehmen“ (`uebernehmeWebseiteInfoVorschlag()`) überträgt
   es über die unverändert bestehende `uebernehmeWebseiteInfo()` in
   `this.editing` (den Bearbeitungszustand des offenen Formulars);
   „Abbrechen“ (`abbrechenWebseiteInfo()`) verwirft es. **Es wird dabei
   nie automatisch gespeichert** – das eigentliche Speichern erfolgt
   unverändert über den bestehenden `ws_save`-Befehl, nachdem die
   Benutzerin/der Benutzer die übernommenen Werte geprüft und ggf.
   angepasst hat.

**Datenverlust-Fix (Issue #9):** `ermittleWebseiteInfo()` sicherte vor
Issue #9 nur implizit den zuletzt gespeicherten Formularzustand; das
abschliessende `render()` (Rückmeldung anzeigen) baute das gesamte
Formular-HTML ausschliesslich aus `this.editing` neu auf und liess
dabei jeden inzwischen live eingetippten, aber noch nicht dorthin
übernommenen Wert optisch verschwinden. Behoben durch
`erfasseFormularZustand()`, das denselben Erfassungsmechanismus wie
`formData()`/„Speichern“ (den gemeinsamen Helfer `leseEinfacheFelder()`)
nutzt und konsequent vor jedem mit „Infos ermitteln“ verbundenen
`render()`-Aufruf ausgeführt wird – unabhängig vom Ausgang der
Ermittlung oder davon, ob das Popup per „Abbrechen“ geschlossen wird.

**Vertiefte Text-Heuristik (Issue #9):** Liefert JSON-LD keine Adresse
bzw. keine `openingHoursSpecification`, wertet `webseite_info.py`
zusätzlich den über `_SeitenParser.sichtbarer_text()` extrahierten,
sichtbaren Seitentext mit dokumentierten Regex-Mustern aus
(`_extrahiere_adresse_aus_text`/`_extrahiere_oeffnungszeiten_aus_text`)
– weiterhin ohne externen/Cloud-/KI-Dienst, rein lokal und
deterministisch. Diese Erweiterung wird durch das neue
Bestätigungs-Popup gerechtfertigt (menschliche Prüfung vor jeder
Übernahme, siehe oben) und bleibt dem Prinzip „lieber nichts als
falsch“ verpflichtet: mehrdeutige oder widersprüchliche Fundstellen
liefern bewusst keinen Vorschlag. Siehe `webseite_info.py`, Moduldoc
„Vertiefte Text-Heuristik“, für die im Detail dokumentierten Grenzen
dieses Ansatzes.

**Extraktionsstrategie (kein externer/Cloud-/KI-Dienst):**
Ausschliesslich lokale, deterministische Auswertung mit der
Python-Standardbibliothek (`html.parser`, `json` – keine neue
Abhängigkeit). Primär schema.org-konforme JSON-LD-Daten
(`<script type="application/ld+json">`, aufgelöst inkl. `@graph` und
Objekt-Listen; ein Objekt gilt als Hofladen-Kandidat, wenn es einen
`name` sowie mindestens ein typisches Geschäfts-Feld – `address`,
`openingHours(Specification)`, `telephone`, `priceRange`,
`paymentAccepted` oder `makesOffer` – trägt). Ergänzend, nur zur
Lückenfüllung: `<title>` (unverfälschter Namens-Fallback) und
`<meta name="description">` (Beschreibungs-Fallback). Öffnungszeiten
werden ausschliesslich aus dem vollständig strukturierten
`openingHoursSpecification` übernommen – das kompakte schema.org-
Kurzformat (`openingHours`, z. B. `"Mo-Fr 08:00-18:00"`) wird bewusst
**nicht** geparst (Tagesbereich-Interpretation wäre eine zusätzliche,
fehleranfällige Heuristik-Schicht). Nicht zuverlässig ermittelbare
Felder bleiben leer statt geraten zu werden („lieber nichts als
falsch“ – siehe Moduldoc in `webseite_info.py`).

**Sicherheitsmodell:** Der gemeinsame syntaktische Prüfkern
(`url_sicherheit.py`, aus `images.py` herausgelöst und von beiden
Modulen genutzt – Schema-Whitelist, keine Zugangsdaten, kein
„localhost“, keine privaten/internen IP-Literale, keine DNS-Auflösung;
seit `2026.10.0-dev.5` mit normalisiertem Hostnamen, `inet_aton`-
Schreibweisen, `is_global`-Positivprüfung und internen Hostnamen wie
`*.local`/`*.lan`/Einzel-Label)
wird hier um Massnahmen erweitert, die speziell für den tatsächlichen
Abruf und die Verarbeitung des Antwortinhalts nötig sind: ein
Antwortgrössen-Limit (2 MB), eine Content-Type-Prüfung (nur HTML-artige
Antworten), eine Zeitüberschreitung (10 Sekunden) sowie eine manuelle,
bei jedem Sprung erneut gegen denselben Prüfkern validierte
Weiterleitungsauflösung (maximal 3 Sprünge – verhindert, dass eine
zunächst sichere URL über einen `Location`-Header stillschweigend auf
ein privates/internes Ziel umgeleitet wird). Der HTTP-Abruf verwendet
`homeassistant.helpers.aiohttp_client.async_get_clientsession` statt
einer eigenen, unverwalteten `aiohttp.ClientSession` (siehe
`quality_scale.yaml`, Kriterium `inject-websession`, seit diesem Issue
`done` statt `exempt`). Ausführliche Begründung siehe `SECURITY.md`,
Abschnitt „Funktion ‚Infos ermitteln‘“.

## Ort in der Nähe suchen (Issue #10, Erweiterung von Issue #8)

`osm_info.py` führt die **zweite eigene, ausgehende HTTP-Anfrage im
Backend-Code von HofKarte** ein – diesmal an die
OpenStreetMap-Overpass-API, einen von HofKarte nicht kontrollierten, aber
freien, kostenlosen, kontofreien OpenStreetMap-Community-Dienst. Wie
`webseite_info.py` bewusst als eigenständiges Modul umgesetzt, nicht
innerhalb von `management.py`.

**Mehrere Instanzen statt eines Einzelpunkts:** Die Haupt-Instanz
`overpass-api.de` beschreibt sich selbst als häufig überlastet. Statt
eines einzelnen, fest verdrahteten Endpunkts hinterlegt `osm_info.py`
deshalb eine kurze, statische Liste bekannter, öffentlicher
Overpass-Instanzen (`OVERPASS_URLS`: `overpass-api.de` als Haupt-Instanz,
`overpass.private.coffee` sowie die für Schweizer Nutzung naheliegende
Regional-Instanz `overpass.osm.ch`). `_rufe_overpass_ab()` versucht sie
der Reihe nach; schlägt eine Instanz fehl (Verbindungsfehler,
Zeitüberschreitung, Fehler- oder Drosselungs-Status wie HTTP 429), wird
automatisch die nächste versucht, jeder Fehlversuch wird protokolliert
(`_LOGGER.warning`) – erst wenn alle konfigurierten Instanzen
fehlschlagen, wirft die Funktion `OsmNichtErreichbarError`. Jede Anfrage
sendet zudem einen identifizierenden `User-Agent`-Header, wie von den
Overpass-Nutzungsrichtlinien verlangt. Die eigentliche Overpass-QL-Anfrage
nutzt den kombinierten `nwr`-Selektor (statt separater `node`-/
`way`-Anweisungen) und deckt damit auch als Relation gemappte Läden ab.

**Architektonische Einordnung:** Eine zweite, bewusst eng begrenzte
Ausnahme vom Grundsatz „kein externer/Cloud-/KI-Dienst“, analog zur
bereits bestehenden Ausnahme für die clientseitig geladenen
Leaflet/OpenStreetMap-Kartenkacheln (siehe „Eingebettete Kartenansicht“
unten) – kein kommerzieller Cloud-Dienst, kein LLM/KI-Dienst, kein
„Scraping-as-a-Service“. Anders als die Kartenkacheln (nur generische
Kachel-/Ausschnittkoordinaten, keine Hofladendaten) überträgt dieses
Modul **serverseitig konkrete Koordinaten eines bestimmten Hofladens**
– ausschliesslich auf ausdrücklichen Klick, nie automatisch. Siehe
`osm_info.py`, Moduldoc, sowie `SECURITY.md`, Abschnitt „Funktion ‚Ort
in der Nähe suchen‘“, für die ausführliche Begründung.

**Datenfluss (Stand nach Issue #11, siehe eigener Abschnitt unten für
die Änderungen im Detail):**

1. Verwaltungsoberfläche (`hofkarte-panel.js`): Klick auf „🔍 Angaben
   automatisch ermitteln“ im Bearbeitungsformular (Abschnitt
   „Automatisch ausfüllen“) ruft `ermittleAutomatisch()` auf; ist ein
   gültiges WGS84-Koordinatenpaar eingetragen (siehe `isValidWgs84()`),
   ruft diese Funktion u. a. `holeOsmOrte(latitude, longitude,
   this.osmRadius)` auf, das den WebSocket-Befehl
   `hofkarte/management/osm_info` mit den aktuell im Formular
   eingetragenen Koordinaten und dem einstellbaren Suchradius sendet.
2. `management.ws_osm_info` (administratorpflichtig, wie alle
   Verwaltungsbefehle) delegiert an
   `osm_info.async_ermittle_osm_orte(hass, latitude, longitude,
   radius_meter=...)`.
3. `osm_info.py` validiert die Koordinaten, klammert den Radius serverseitig
   auf `MIN_RADIUS_METER`–`MAX_RADIUS_METER`, baut eine Overpass-QL-Anfrage
   (siehe Moduldoc „Tag-Auswahl“ sowie den Abschnitt „Erweiterung (Issue
   #11)“ unten), ruft sie über Home Assistants verwaltete Client-Session
   ab, klassifiziert jeden Treffer über `_klassifiziere_herkunft()`,
   verwirft unbenannte oder nicht zuordenbare Treffer und liefert eine
   nach Entfernung sortierte Liste von `OsmOrt`-Objekten (oder wirft
   einen der drei Fehler) zurück.
4. `ws_osm_info` bildet die Fehlerfälle auf eigene WebSocket-Fehlercodes
   ab (`invalid_coordinates`/`unreachable`/`not_found`) bzw. serialisiert
   das Ergebnis (`_json_value`, derselbe generische Serialisierer wie für
   `Hofladen`- und `WebseiteInfo`-Objekte).
5. `hofkarte-panel.js`: Bei genau einem Treffer (bzw. keinem parallel
   laufenden Website-Ergebnis, das noch auf eine Auswahl wartet) wird die
   Trefferauswahl übersprungen; bei mehreren Treffern zeigt
   `osmOrteAuswahlPopup()` zunächst eine Auswahlliste (Name, Adresse,
   Entfernung, inkl. Kennzeichnung von Namens-Heuristik-Treffern), aus
   der `waehleOsmOrt()` den gewählten Treffer übernimmt. Anschliessend
   führt `mischeAutoVorschlaege()` das OSM-Ergebnis mit einem eventuell
   parallel ermittelten Website-Ergebnis zusammen und `zeigeAutoErgebnis()`
   öffnet dasselbe Bestätigungs-Popup wie bei einer reinen Website-Suche
   (`webseiteInfoPopup()`, inkl. Quellen-Kennzeichnung je Feld), dieselbe
   Übernahme-Funktion (`uebernehmeWebseiteInfo()`) – bewusst wiederverwendet
   statt für die zweite Datenquelle dupliziert. Es wird nie automatisch
   gespeichert.

**`opening_hours`-Parser:** OpenStreetMaps `opening_hours`-Tag folgt
einer eigenen, formal spezifizierten Syntax
(https://wiki.openstreetmap.org/wiki/Key:opening_hours) – kein Fliesstext
wie bei der Text-Heuristik aus Issue #9. `osm_info.py` unterstützt
bewusst nur eine gängige Teilmenge (Semikolon-getrennte Regeln,
englische Zwei-Buchstaben-Wochentagskürzel, Wochentag-/Zeitbereiche
inkl. mehrerer Zeitintervalle pro Tag, `24/7`); nicht unterstützte Syntax
(Feiertagsregeln, Datumsbereiche, `off`-Ausnahmen u. Ä.) wird komplett
übersprungen statt teilweise interpretiert. Wie bei der Text-Heuristik
aus Issue #9 gilt zusätzlich: Liefern mehrere Regeln unterschiedliche,
widersprüchliche Zeiten für denselben Wochentag, gibt es für diesen Tag
keinen Vorschlag; mehrere Zeitintervalle **derselben** Regel für denselben
Tag (z. B. eine Mittagspause) sind dagegen kein Widerspruch.

**Bewusst nicht umgesetzt (Scope-Abgrenzung):** Reine Koordinatensuche,
keine Freitext-/Adresssuche – eine solche würde einen dritten externen
Dienst (z. B. Nominatim-Geocoding) erfordern und wurde bewusst nicht
eingeführt, um den Umfang dieser Erweiterung nicht unnötig auszuweiten.

## Vereinfachung der automatischen Ermittlung (Issue #11)

Ausgangspunkt war ein Vorschlag, den bisherigen Tag-Filter um konkrete
`shop`-Werte wie `shop=farm`/`shop=greengrocer` zu „erweitern“. Eine
Prüfung der Overpass-QL-Semantik (siehe Moduldoc in `osm_info.py`,
Abschnitt „Erweiterung (Issue #11)“) ergab: `["shop"]` ist in Overpass
QL ein reiner **Schlüssel-Existenz-Filter**, kein Wertevergleich – er
matcht bereits jeden `shop=*`-Wert, `shop=farm` und `shop=greengrocer`
eingeschlossen. Eine solche „Erweiterung“ wäre ein No-Op gewesen. Statt
der wörtlichen Vorgabe zu folgen, wurde die tatsächliche Absicht des
Issues – mehr, aber weiterhin korrekte Treffer für untertaggte
Hofläden – mit zwei echten, wiki-verifizierten Ergänzungen umgesetzt:

- **`amenity=marketplace`** als zusätzlicher, dokumentierter Tag (ein
  von Issue-Seite vorgeschlagener Subtag `marketplace=farmers`
  existiert auf OpenStreetMap nicht und wurde deshalb nicht übernommen).
- Eine zweite, unabhängige Filtergruppe für Hofgelände ohne
  Laden-/Markt-Tag (`landuse=farmyard`, `building=farm`), kombiniert
  mit einer **Namens-Heuristik**: Nur wenn der Name eines solchen
  Objekts einen der Begriffe „hof“, „bauernhof“, „hofladen“ oder „laden“
  enthält (case-insensitiv), wird es überhaupt vorgeschlagen –
  ungetaggte Hofgelände ohne passenden Namen werden weiterhin verworfen
  („lieber nichts als falsch“).

`_klassifiziere_herkunft(tags, name)` trennt beide Fälle serverseitig
scharf und liefert `"tag"`, `"name"` oder `None` (verwerfen); `OsmOrt`
trägt das Ergebnis als `via_namen_heuristik: bool` weiter bis in die
Trefferauswahl der Oberfläche, wo Namens-Treffer ausdrücklich als
solche gekennzeichnet werden – nie stillschweigend mit echten
Tag-Treffern gleichgesetzt.

**Einstellbarer Suchradius:** Der bisher fest verdrahtete
`STANDARD_RADIUS_METER` (50 m) bleibt als harte Absicherung bestehen,
falls keine Config Entry ermittelt werden kann, ist im Formular aber
neu überschreibbar. Seit dem in einem späteren Schritt ergänzten
Options Flow (siehe „Kontakt, Bewertung, Einstellungen und
Kartenmarker“ unten) ist der tatsächlich vorgeschlagene Vorgabewert
stattdessen der dort dauerhaft gespeicherte, standardmässig auf 200 m
angehobene `DEFAULT_OSM_RADIUS_METER`. Zwei unabhängige Schichten
sichern den zulässigen Wertebereich (`MIN_RADIUS_METER`–
`MAX_RADIUS_METER`, mittlerweile 20–2000 m) ab:
clientseitig/schemaseitig über `vol.Range(min=MIN_RADIUS_METER,
max=MAX_RADIUS_METER)` in `ws_osm_info`s WebSocket-Schema (weist einen
Wert ausserhalb des Bereichs mit einem Schema-Fehler zurück), und
zusätzlich, unabhängig davon, ein defensiver serverseitiger Clamp
direkt in `async_ermittle_osm_orte()` (`max(MIN_RADIUS_METER,
min(MAX_RADIUS_METER, radius))`), der nie einen Fehler wirft, sondern
einen ausserhalb des Bereichs liegenden Wert stillschweigend
begrenzt. Diese Redundanz ist bewusst: Tests, die `ws_osm_info` direkt
mit einem rohen `dict` aufrufen (ohne Durchlauf durch die
`vol`-Schema-Anwendung), sollen sich weiterhin auf einen sicheren
Wertebereich verlassen können, ohne von der Schema-Validierung
abhängig zu sein.

**Zusammenlegung der Oberfläche:** Die beiden bisher unabhängigen
Aktionen „🔎 Infos ermitteln“ (Website) und „📍 Ort in der Nähe suchen“
(OpenStreetMap) wurden zu einer einzigen Aktion „🔍 Angaben automatisch
ermitteln“ (`ermittleAutomatisch()`) zusammengelegt. Statt zwei
unabhängiger `async`-Methoden mit eigener Status-/Popup-Steuerung gibt
es nun zwei reine, seiteneffektfreie Abruf-Helfer
(`holeWebseiteVorschlag()`/`holeOsmOrte()`, jeweils `{ ok, ... }` bzw.
`{ ok: false, meldung }` zurückgebend) sowie einen Orchestrator, der
beide **parallel** über `Promise.all` abfragt – je nachdem, ob eine
Website-Adresse bzw. gültige Koordinaten überhaupt eingetragen sind –
und eine Merge-Funktion (`mischeAutoVorschlaege()`), die die Ergebnisse
feldweise zusammenführt. Bei einem Konflikt (beide Quellen liefern
unterschiedliche Werte für dasselbe Feld) gewinnt die Website als in
der Regel vom Betreiber selbst gepflegte, autoritativere Quelle – der
abweichende OSM-Wert wird dabei aber **nicht verworfen**, sondern über
die Quellen-Kennzeichnung `"website+osm"` im Bestätigungs-Popup
nachvollziehbar gehalten (wieder „lieber nichts als falsch“, hier auf
Datenverlust beim automatischen Zusammenführen angewendet). Liefert die
Koordinatensuche mehrere Treffer, muss die Auswahl abgewartet werden,
ohne ein bereits vorliegendes Website-Ergebnis zu verwerfen – gelöst
über ein Zwischenspeicherfeld (`_wartendesWebseiteErgebnis`), das sowohl
bei Auswahl eines Treffers als auch bei Abbruch der Auswahl wieder mit
eingemischt wird.

## Kontakt, Bewertung, Einstellungen und Kartenmarker (`dev.7`)

Vier fachlich unabhängige, aber im selben Entwicklungsschritt
umgesetzte Erweiterungen des Datenmodells und der Verwaltungsoberfläche
ohne neue externe Abhängigkeiten oder zusätzliche ausgehende
HTTP-Anfragen:

- **Kontaktfelder (`models.Hofladen.mobilnummer`/`email`):** Optionale
  Felder, durchgängig berücksichtigt in `parsing.py`, der
  Serialisierung für die Verwaltungsoberfläche, dem
  WebSocket-Save-Pfad sowie Export/Import. Im Bearbeitungsformular im
  Abschnitt „Kontakt & Webseite“ (vor „Webseite“), in der
  Detailansicht als eigener Abschnitt „Kontakt“ mit `tel:`-/
  `mailto:`-Links. `webseite_info.py` und `osm_info.py` liefern beide
  Felder seither zusätzlich als Teil ihrer jeweiligen Ermittlung mit.
- **Bewertung (`models.Hofladen.bewertung`, 0–5, Standard 0):** Neue
  Sensor-Plattform-Entity `HofKarteBewertungSensor`
  (`custom_components/hofkarte/sensor.py`) analog zu den bestehenden
  Entfernungs-/Zeitpunkt-Sensoren, `unique_id`-Muster
  `{DOMAIN}_{hofladen_id}_bewertung`, keine eigene Device Class (es
  gibt keine passende für eine einfache Sterne-Bewertung), aber
  `SensorStateClass.MEASUREMENT` für Statistik-/Verlaufsfähigkeit. Der
  Wert wird beim Einlesen auf den gültigen Bereich begrenzt. In der
  Listenansicht als zusätzliche, über `LISTEN_SORT_SPALTEN` (siehe
  unten) sortierbare Spalte, in der Kachelansicht kompakt neben dem
  Status-Badge.
- **Options Flow („Einstellungen“, `config_flow.HofKarteOptionsFlow`):**
  Eine einzige `async_step_init`-Maske mit drei Feldern
  (`CONF_LISTEN_SORT_SPALTE`, `CONF_LISTEN_SORT_RICHTUNG`,
  `CONF_OSM_RADIUS_METER`, alle in `const.py` definiert) – dauerhaft in
  der Config Entry gespeicherte Vorgabewerte für die Übersicht bzw. für
  „Angaben automatisch ermitteln“, analog zur globalen
  „Einstellungen“-Maske der parallel gepflegten iOS-App. Seit
  `2026.10.0-dev.4` (Befund F3) hat `HofKarteOptionsFlow` **keinen**
  eigenen Konstruktor mehr: `self.config_entry` stellt Home Assistant
  selbst bereit (Property seit 2024.11, ab 2025.12 ohne Setter – eine
  explizite Zuweisung würde dort einen `AttributeError` auslösen). Die
  beiden Auswahlfelder sind `SelectSelector`-Dropdowns mit
  übersetzten Optionsbezeichnungen (`selector.<schlüssel>.options.<wert>`
  in `strings.json`/`translations`). Die Verwaltungsoberfläche liest
  diese Werte beim Laden über den neuen, administratorpflichtigen
  WebSocket-Befehl `hofkarte/management/settings` und verwendet sie als
  Vorgabewerte statt wie bisher rein pro Formularsitzung flüchtiger
  Werte. `DEFAULT_OSM_RADIUS_METER` wurde dabei zugleich von 50 auf
  200 m angehoben (an die iOS-App angeglichen), der zulässige Bereich
  `MIN_RADIUS_METER`–`MAX_RADIUS_METER` von 10–500 m auf 20–2000 m.
- **Kartenmarker nach Status eingefärbt:** `erzeugeKarteMarkerIcon()`
  (`hofkarte-panel.js`, siehe „Eingebettete Kartenansicht“ oben)
  erhält eigene CSS-Klassen für „geöffnet“ (grün) und „geschlossen“
  (grau, bewusst nicht Rot – auf einer Karte sonst leicht mit einem
  Fehlerhinweis verwechselbar) statt durchgängig derselben
  HA-Theme-Primärfarbe; unbekannter Status behält die bisherige
  Standardfarbe. Eigene CSS-Klassen statt Wiederverwendung der
  Kacheln-/Listen-Statusfarbgebung, da die beiden Kontexte (SVG-Marker
  vs. HTML-Badge) unterschiedliche Selektoren benötigen.

## Suche/Filter

`search.py` (`find_hoflaeden`) ist eine reine, HA-unabhängige
Fachfunktion für die UND-verknüpfte Filterung. Der Parameter `angebot`
gleicht den Namen eines Angebots ab (ersetzt die früher getrennten
Parameter `kategorie`/`produkt`, siehe CHANGELOG; eine zwischenzeitliche
Erweiterung auf Gruppen-Abgleich wurde mit der Vereinfachung von
Angeboten wieder zurückgenommen). Die Parameter `verkaufsart` und
`merkmal` wurden ersatzlos entfernt, da die zugrunde liegenden
Fachbereiche selbst entfallen sind. `services.py` bindet die Funktion
als Home-Assistant-Action (`hofkarte.hoflaeden_suchen`) an.

## Grafische Verwaltungsoberfläche (Architekturabweichung)

`frontend.py` (Sidebar-Panel-Registrierung) und `management.py`
(WebSocket-Befehle `hofkarte/management/list|save|delete`) bilden eine
**bewusste Abweichung** vom ursprünglichen Umsetzungsplan (der für
Suche/Filter/Actions keine eigene UI vorsah). Begründung: Da Home
Assistant sowohl Laufzeit- als auch Verwaltungsoberfläche ist, ist eine
native, in HA integrierte Verwaltungsseite konsistent mit diesem
Prinzip. Alle Schreibzugriffe der Oberfläche laufen über die
öffentlichen Coordinator-Methoden (siehe oben), nicht über eine eigene
Datenhaltung.

Das Panel (`static/hofkarte-panel.js`) trennt drei Ansichten
(client-seitiger Zustand, kein serverseitiges Routing): Liste,
Bearbeiten und eine reine **Detailansicht** (read-only). Die
Detailansicht benötigt keinen eigenen WebSocket-Befehl – sie zeigt die
bereits über `hofkarte/management/list` geladenen Daten an, ohne
Bearbeitungsmöglichkeit.

### Behobener Bug: `js_url` ohne Cache-Busting (`2026.9.1-dev.3`)

`async_register_frontend` (`frontend.py`) übergibt Home Assistant die
URL von `hofkarte-panel.js` als `js_url` einmalig beim Setup der
Integration; der Browser lädt diese Datei anschliessend selbst,
anhand ihrer URL. Bis `2026.9.1-dev.2` war diese URL für **jede**
Integrationsversion identisch (`/api/hofkarte/static/hofkarte-panel.js`).
Browser (teilweise auch Home Assistants eigenes Frontend) cachen
per Custom-Panel geladenes JavaScript anhand genau dieser URL, nicht
anhand des tatsächlichen Dateiinhalts – nach einem Update von HofKarte
wurde deshalb trotz korrekt aktualisierter Datei auf der Festplatte
teils weiterhin eine ältere, bereits im Browser zwischengespeicherte
Fassung ausgeliefert (z. B. fehlende Kacheln-/Listen-/Kartenansicht
aus Issue #1/#2, obwohl der Code auf `develop`/im Release korrekt war
– beobachtetes Symptom, das zu diesem Fund führte).

**Behoben** durch `_integration_version()`: liest die Version direkt
aus `manifest.json` (keine zusätzliche Home-Assistant-API-Abhängigkeit
nötig) und hängt sie als Query-Parameter an `js_url` an
(`?v=<version>`). Ändert sich die Version, ändert sich die URL – der
Browser behandelt sie als neue, ihm unbekannte Ressource und lädt sie
zwingend neu, unabhängig von zuvor gesetzten Cache-Headern. Schlägt das
Lesen von `manifest.json` aus irgendeinem Grund fehl, liefert
`_integration_version()` einen festen Platzhalter (`"0"`) – die
Cache-Invalidierung entfällt dann für diesen Einzelfall, das Panel
selbst bleibt aber funktionsfähig (bewusst fehlertolerant, kein
Hard-Fail beim Setup wegen eines reinen Anzeige-Optimierungsmerkmals).

### Event-Listener-Bindung: `bind()` nur nach vollständigem Re-Render (`2026.9.1-dev.6`)

`bind()` registriert sämtliche Event-Listener des Panels ausschliesslich
additiv über `addEventListener` – ohne zuvor bestehende Listener zu
entfernen (kein `removeEventListener`, kein Klonen der Knoten, kein
„bereits gebunden“-Flag). Das ist unproblematisch, solange `bind()`
**ausschliesslich** einmalig direkt nach einem vollständigen
`innerHTML`-Ersatz in `render()` aufgerufen wird: Die zuvor
existierenden Elemente samt ihrer Listener sind zu diesem Zeitpunkt
bereits aus dem DOM entfernt.

Die Handler für „+ weiteres Intervall“ und „+ Sonderzeit hinzufügen“
weichen aus gutem Grund von `render()` ab: Sie fügen eine neue Zeile
gezielt per `insertBefore`/`append` in den bestehenden DOM ein, statt
den gesamten Shadow-DOM-Inhalt neu aufzubauen – ein vollständiger
Re-Render würde sonst z. B. den Eingabefokus in anderen Formularfeldern
verwerfen. Bis `2026.9.1-dev.5` riefen beide Handler danach jedoch
erneut `this.bind()` auf demselben, unverändert bestehenden DOM auf.
Da `bind()` keine bestehenden Listener entfernt, erhielten dabei
**alle** bereits vorhandenen Elemente – u. a. der jeweilige Button
selbst sowie der Formular-`submit`-Handler – bei jedem Klick einen
weiteren, zusätzlichen Listener obendrauf. Ergebnis: Die Anzahl neu
eingefügter Zeilen verdoppelte sich näherungsweise mit jedem Klick,
und der mehrfach gebundene `submit`-Handler löste beim Abschicken des
Formulars `this.save()` mehrfach aus – bei einem neuen, noch
ungespeicherten Hofladen (ohne `id`) vergab `ws_save` dadurch je
Aufruf eine eigene, neue ID, wodurch mehrere identische Hofladen-
Einträge entstanden (Issue #6).

**Behoben**, indem beide Handler `bind()` nicht mehr erneut aufrufen,
sondern gezielt nur den „entfernen“-Button der jeweils neu eingefügten
Zeile direkt per `addEventListener` verkabeln. Dieses Muster – bei
einem gezielten, nicht vollständigen DOM-Insert ausserhalb von
`render()` werden ausschliesslich die neu erzeugten Elemente selbst
gebunden, niemals erneut `bind()` über den gesamten Shadow DOM – gilt
verbindlich für jede künftige, ähnlich gebaute Stelle im Panel.

### Übersicht: Kacheln/Liste, serverseitig berechnete Anzeigefelder

Die Listenansicht selbst bietet zwei Darstellungen (`uebersichtsAnsicht`,
rein clientseitiger Zustand, kein Backend-Unterschied): eine
Kachel-Ansicht (`listGrid`/`listCard`) und eine sortierbare
Tabellenansicht (`listTable`). Sortierung und Freitextfilter
(`sortierteGefilterteItems`) laufen vollständig clientseitig über die
bereits geladenen Daten – kein neuer WebSocket-Befehl nötig.

Für zwei Anzeigefelder wäre eine korrekte clientseitige Berechnung nur
durch Duplikation bereits bestehender, teils sicherheitsrelevanter
Backend-Logik möglich gewesen; stattdessen liefert
`management._serialize_hofladen` sie serverseitig vorberechnet mit:

- **`geoeffnet`** (`true`/`false`/`null`): über `opening_hours.is_open`
  – exakt dieselbe Funktion wie beim Binary Sensor „Geöffnet“
  (`binary_sensor.py`). `now` wird einmal pro WebSocket-Antwort ermittelt
  (`dt_util.now()`), nicht pro Hofladen, damit alle Hofläden einer
  Antwort konsistent gegen denselben Zeitpunkt bewertet werden.
- **`hauptbild_url`** (`str | None`): über `images.get_main_image_url`
  – exakt dieselbe Funktion (inkl. Sicherheitsprüfung gegen
  private/interne IP-Literale, siehe `SECURITY.md`) wie beim
  `image`-Entity für das tatsächliche Hauptbild (`image.py`).

Beide Felder werden von `ws_list` **und** `ws_save` mitgeliefert, damit
die Oberfläche nach dem Speichern eines einzelnen Hofladens dessen
Kachel/Zeile aktualisieren kann, ohne einen vollständigen `list`-Aufruf
zu benötigen.

### Export/Import (Issue #5)

Mehrfachauswahl (`this.auswahl`, eine `Set<hofladen_id>`) ergänzt
Kachel- und Listenansicht um eine Checkbox je Hofladen; die
Kartenansicht bleibt bewusst aussen vor, da dort kein sinnvoller
Anwendungsfall für eine Auswahl besteht.

**Export** läuft vollständig clientseitig: Die ausgewählten Hofläden
werden aus dem bereits geladenen `this.items` gefiltert, um die beiden
serverseitig berechneten, nicht zum internen Datenmodell gehörenden
Felder `geoeffnet`/`hauptbild_url` bereinigt (`bereinigtFuerExport`,
siehe oben) und als **eine** JSON-Datei (Liste von Objekten, kein ZIP)
über einen `Blob`/`<a download>`-Mechanismus heruntergeladen. Kein
neuer Server-Endpunkt nötig.

**Import** ist bewusst zweistufig und delegiert jede Fachlogik
serverseitig an `management.py`, um bestehende Validierungslogik
(`parsing.parse_hofladen`) nicht ein zweites Mal in JavaScript
nachzubauen:

1. **Vorschau** (`hofkarte/management/import_preview`, rein lesend):
   Validiert jeden Datensatz der ausgewählten Datei fail-fast über
   `parse_hofladen` – ist auch nur einer ungültig, wird die *gesamte*
   Vorschau mit einer Fehlermeldung abgelehnt (kein Teil-Ergebnis).
   Für jeden gültigen Datensatz ermittelt `_finde_duplikat` ein
   mögliches Duplikat im aktuellen Bestand: Übereinstimmung im Namen
   (`_normalisiert` – Gross-/Kleinschreibung und
   Leerzeichen werden ignoriert) und, sofern **beide** Datensätze eine
   Adresse besitzen, zusätzlich in der Adresse. Fehlt einem der beiden
   Datensätze die Adresse, entscheidet allein der Name. Bewusst keine
   Fuzzy-Logik (Tippfehlertoleranz) – das Risiko einer fälschlichen
   Zusammenführung wiegt schwerer als der Komfortgewinn.
2. **Konfliktlösung** (rein clientseitig, `this.importDialog`): Für
   jeden erkannten Duplikat-Kandidaten zeigt das Panel bestehenden und
   importierten Datensatz nebeneinander mit farblich hervorgehobenen
   Unterschieden (`diffFelder`, rot/grün analog zu den bestehenden
   Statusfarben `--error-color`/`--success-color`); pro Duplikat wird
   „Aktualisieren“ oder „Beibehalten“ gewählt (zusätzlich als
   Komfortfunktion: „Alle aktualisieren“/„Alle beibehalten“ für alle
   Duplikate gleichzeitig). Gibt es keine Duplikate, wird dieser
   Schritt automatisch übersprungen. Ein beim Abschluss noch
   unentschiedenes Duplikat wird sicher **beibehalten**, nie
   stillschweigend überschrieben (kein Datenverlust ohne explizite
   Bestätigung).
3. **Commit** (`hofkarte/management/import_commit`): Erhält je
   Eintrag eine Aktion (`"neu"`, `"aktualisieren"` oder
   `"ueberspringen"`) und – bei `"aktualisieren"` – die Ziel-ID des
   bestehenden Hofladens. Auch hier zweiphasig fail-fast: Zunächst
   werden *alle* Einträge vollständig validiert (gültige Aktion,
   bei „aktualisieren“ eine tatsächlich noch vorhandene
   `bestehende_id`, sowie die Rohdaten selbst über `parse_hofladen`);
   erst wenn diese Prüfung für sämtliche Einträge erfolgreich war,
   erfolgen die eigentlichen Schreibzugriffe über
   `coordinator.async_save_hofladen` (dieselbe Methode wie beim
   regulären Speichern über die Verwaltungsoberfläche). Eine in der
   Importdatei enthaltene, von einer fremden Installation stammende
   `id` wird für neu angelegte Hofläden verworfen und durch eine
   frisch vergebene, lokale ID (`hofladen-<uuid4>`) ersetzt – nur bei
   „aktualisieren“ wird gezielt die ID des tatsächlich zu
   überschreibenden, bestehenden Hofladens verwendet.

Es gibt bewusst keine echte Transaktionalität über mehrere
Schreibzugriffe hinweg (Home-Assistants `helpers.storage.Store` bietet
das nicht, und kein anderer Teil dieser Integration benötigt sie
bisher) – die vorgelagerte, vollständige Validierung aller Einträge
*vor* dem ersten Schreibzugriff verhindert aber, dass ein einzelner
ungültiger oder inzwischen ungültig gewordener Eintrag (z. B. ein
zwischenzeitlich gelöschter Hofladen bei „aktualisieren“) zu einem
unvollständig durchgeführten Import führt.

## Diagnostics

`diagnostics.py` liefert eine technische Übersicht (Status des letzten
Abrufs, Update-Intervall, Provider-Typ, Anzahl Hofläden) **ohne**
Hofladen-Inhalte oder Standortdaten (siehe README, Abschnitt
„Datenschutz“).

## Performance

- Ein gemeinsamer Coordinator verhindert Mehrfachabfragen einzelner
  Entities.
- **Kein periodischer Abruf (Befund F6):** `DEFAULT_UPDATE_INTERVAL` ist
  `None`. Daten ändern sich nur durch Schreibzugriffe (inkrementelles
  Update); zeitabhängige Zustände aktualisieren sich zeitgenau:
  `HofKarteZeitgesteuerteEntity` (Binary Sensor „Geöffnet“, Sensoren
  „Nächste Öffnung/Schliessung“) plant mit `async_track_point_in_time` den
  Zeitpunkt aus `opening_hours.naechster_statuswechsel` (nächster
  Intervallbeginn/-ende oder lokale Mitternacht, hass-frei und
  zeitzonen-/DST-korrekt über die vorhandene Intervalllogik), plant nach
  jedem Tick neu, rechnet bei jedem Coordinator-Update neu und meldet den
  Timer über `async_on_remove` ab. Hofläden ohne Öffnungszeiten brauchen
  keinen Timer. `async_sync_devices` läuft nur noch, wenn sich die Menge
  oder die Namen der Hofläden ändern. Begründung gegenüber „seltener
  pollen“: ein Raster bleibt ungenau, ein Poll liest alle Datensätze neu.
- Duplikaterkennung beim Import (`_DuplikatIndex`) nutzt einen
  Namensindex statt eines Durchlaufs je Eintrag (gleiche Semantik).
- `frontend.py`: `cache_headers=True` für `/api/hofkarte/static`; die
  versionierten Einstiegs-URLs (`?v=<Version>`) erzwingen nach Updates
  neu geladene Dateien (Befund F14).
- `osm_info.py`: Gesamtbudget 40 s für alle Overpass-Instanzen und
  10-Minuten-Cache (max. 32 Einträge, gerundete Koordinaten + Radius,
  nur erfolgreiche Antworten) gegen wiederholte identische Abfragen.
- `PARALLEL_UPDATES = 0` in allen drei Entity-Plattformen (keine
  pro-Entity-Netzwerkzugriffe, die gedrosselt werden müssten).
- Keine blockierenden Aufrufe im Event Loop – konkretes Beispiel: Die
  ursprüngliche Bild-URL-Sicherheitsprüfung nutzte testweise
  `socket.getaddrinfo` (blockierende DNS-Auflösung) und wurde durch
  eine rein syntaktische, nicht-blockierende Prüfung ersetzt (siehe
  CHANGELOG).

## Hofladen-Discovery (`2026.10.1`)

Paket `custom_components/hofkarte/discovery/`, bewusst frei von Home-Assistant-
Abhängigkeiten (nur `overpass.async_suche` und die Website-Abrufe greifen auf
`hass` zu), damit die Logik testbar und für die PWA wiederverwendbar bleibt.

| Modul | Aufgabe |
|---|---|
| `profile.py` | `Profil` (Overpass-Filter je Objektart); `FARMSHOP` mit Kernfilter `shop=farm` |
| `overpass.py` | Query, Antwortprüfung (200 + `remark` = Fehler), Parsen, Zusammenführen von Duplikaten (≤ 30 m), Cache, `async_suche` (nutzt `osm_info._rufe_overpass_ab`) |
| `scoring.py` | Score aus Distanz, Namensähnlichkeit (`difflib`, tokensortiert), Website-Domain; Konfidenz hoch ≥ 0,75, mittel ≥ 0,45 |
| `website.py` | `robots.txt` (RFC 9309), Linkauswahl, Abruf von höchstens 4 Seiten desselben Hosts mit Pause |
| `provenance.py` | Zusammenführen mit Priorität je Feld, `Vorschlag` mit `quellen` und `abweichungen` |
| `enrich.py` | Ablauf OSM → Website → fertig mit Fortschrittsereignissen |

WebSocket (`management.py`, beide `require_admin`): `hofkarte/management/discover`
(Antwort `{radius, kandidaten}`) und `hofkarte/management/enrich`
(Subscription: Bestätigung, dann Ereignisse `osm`, `website`, `fertig`).

**Datenmodell:** `Hofladen.quellen: tuple[Quelle, ...]` (`feld`, `quelle`,
`status`, `url`, `lizenz`), beim Einlesen in `parsing.py` bereinigt.

**Priorität der Quellen:** Name, Adresse, Telefon, E-Mail: OSM vor Website;
Webseite: OSM vor Eingabe; Öffnungszeiten: Website vor OSM; Angebote und
Zahlungsarten: nur Website; Koordinaten: OSM; Beschreibung: nie automatisch.

**Panel:** Dialog in `hofkarte-panel.js` (`findenDialog`, drei Schritte, per
Ereignisdelegation auf `<main>`); Gerätestandort über
`navigator.geolocation` nur in `ermittleGeraeteStandort()` mit
Secure-Context-Prüfung und Rückfall auf `hass.config`. Auswahlelemente
brauchen eigene Breitenregeln, weil das Panel `input{width:100%}` global setzt.
Die Kopfzeile zeigt `PANEL_BUILD` (muss zu `manifest.json` passen, Test).

**Offen:** optionale KI-Anreicherung (`ai_task.generate_data`), PWA.

## Erweiterungspunkte

Für Beitragende, die HofKarte erweitern möchten:

- **Neue Fachlogik** (z. B. weitere Filterkriterien): eigenes,
  HA-unabhängiges Modul nach dem Muster von `opening_hours.py`/
  `distance.py`/`search.py` – reine Funktionen, kein `hass`-Zugriff,
  isoliert testbar.
- **Neue Entity:** eigene Plattform-Datei, `HofKarteEntity` als Basis,
  Registrierung über `entity.async_setup_hofladen_entities` für
  automatische Erzeugung bei neuen Hofläden.
- **Neuer Data Provider** (z. B. für eine andere Datenquelle):
  `MutableHofladenDataProvider` implementieren; Coordinator und
  Entities benötigen keine Änderung, da sie nur die abstrakte
  Schnittstelle kennen.
- **Neue Schreiboperation:** als öffentliche Methode auf
  `HofKarteUpdateCoordinator` ergänzen (Fail-Fast-Validierung +
  Refresh-Muster wie bei den bestehenden Methoden), nicht direkt am
  Data Provider vorbei.

Siehe auch `quality_scale.yaml` für offene, bewusst zurückgestellte
Verbesserungspunkte (z. B. `runtime-data`-Migration, Repair-Issues).


## Eingabelimits, DNS-Prüfung und Panel-Härtung (`dev.5`)

- **F4 – DNS-Prüfung mit IP-Bindung:** `webseite_info._OeffentlichAufloeser`
  (ein `aiohttp.abc.AbstractResolver`) löst Hostnamen auf, verlangt für
  **alle** Adressen `url_sicherheit.ist_oeffentliche_ip` und gibt genau
  diese an den Verbindungsaufbau zurück (kein Rebinding zwischen Prüfung
  und Abruf). Genutzt über `_sichere_session()` (eigene, je Abruf
  erzeugte Session, `force_close`). Die synchrone Bild-URL-Prüfung bleibt
  syntaktisch.
- **F11 – Limits (`parsing.py`, Konstanten in `const.py`):** Längen je Feld,
  Anzahl Angebote/Zahlungsarten/Bilder/Zeiten, ID-Regel, E-Mail-/
  Telefonformat, höchstens 500 Datensätze je Import (`ws_import_*`).
- **F12 – Panel:** `escAttr` für alle datenbasierten Attribute,
  `istSichereBildUrl` (Bilder), `istGueltigeEmail` (`mailto:`), Import-
  Limits vor `file.text()`/`JSON.parse`.
