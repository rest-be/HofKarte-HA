# Security Policy

## Über dieses Projekt

HofKarte ist ein **privates, lokal betriebenes** Home-Assistant-Custom-Integrationsprojekt.
Es gibt kein kommerzielles Support-Team und keinen 24/7-Sicherheitsdienst –
Rückmeldungen erfolgen nach bestem Aufwand durch den/die Projektbetreuer:in
(siehe `codeowners` in `custom_components/hofkarte/manifest.json`).

## Unterstützte Versionen

Es wird ausschliesslich die **jeweils neueste veröffentlichte Version**
(siehe `CHANGELOG.md` bzw. GitHub Releases) mit Sicherheitskorrekturen
versorgt. Ältere Versionen werden nicht rückwirkend gepatcht – bitte vor
einer Fehlermeldung immer zuerst auf die neueste Version aktualisieren.

| Version         | Unterstützt              |
| ---------------- | -------------------------- |
| Neueste Release  | ✅                          |
| Ältere Versionen | ❌ (bitte aktualisieren)    |

## Meldeweg für Sicherheitsprobleme

Sicherheitsrelevante Probleme (z. B. eine Möglichkeit, über eine
Bild-URL interne Netzwerkressourcen zu erreichen, ein Weg, die
WebSocket-Verwaltungs-API ohne Administratorrechte zu nutzen, oder ein
Leck lokal gespeicherter Hofladen-Daten) bitte **nicht** als öffentliches
GitHub-Issue melden, sondern über den privaten Meldeweg:

- GitHub: [Security Advisory](https://github.com/rest-be/HofKarte/security/advisories/new)
  für dieses Repository erstellen (falls verfügbar), oder
- direkt den/die Codeowner (`@rest-be`) über GitHub kontaktieren.

Bitte folgende Angaben beifügen, soweit bekannt:

- Betroffene HofKarte-Version (`manifest.json` → `version`)
- Home-Assistant-Version
- Schritte zur Reproduktion
- Erwartetes vs. tatsächliches Verhalten
- Falls vorhanden: relevante Auszüge aus dem Home-Assistant-Log
  (**ohne** persönliche Daten oder Zugangsdaten)

## Erwartete Reaktionszeit

Da es sich um ein privates Freizeitprojekt ohne kommerzielle Garantien
handelt, gibt es **keine zugesicherte Reaktionszeit**. Nach bestem
Bemühen wird angestrebt:

- Erstbestätigung des Eingangs: in der Regel innerhalb einiger Tage.
- Einschätzung des Schweregrads und weiteres Vorgehen: nach Verfügbarkeit
  des/der Projektbetreuer:in.

Es besteht kein Anspruch auf eine bestimmte Bearbeitungsfrist.

## Bereich dieser Policy

Diese Policy deckt ausschliesslich Sicherheitsprobleme **im
HofKarte-Quellcode selbst** ab (`custom_components/hofkarte/`).
Sicherheitsprobleme in Home Assistant selbst, in HACS oder in
Drittanbieter-Abhängigkeiten sind an die jeweiligen Projekte zu melden.

## Bekannte, bewusste Sicherheitsentscheidungen

Zur Einordnung – diese Punkte sind bekannt, dokumentiert und keine
offenen Sicherheitslücken:

- Die Bild-URL-Prüfung (`custom_components/hofkarte/images.py`) ist rein
  syntaktisch (Schema, Zugangsdaten, literale private/interne
  IP-Adressen, seit `2026.10.0-dev.5` gehärtet) und führt **keine
  DNS-Auflösung** durch, um den Home-Assistant-Event-Loop nicht zu
  blockieren. Ein Domainname, der erst zur Abrufzeit auf eine private
  Adresse auflöst (DNS-Rebinding), wird dadurch nicht erkannt (der
  Website-Abruf ist dagegen geschützt, siehe unten). Siehe README, Abschnitt „Bekannte
  Einschränkungen“.
- Über den geführten Bilder-Upload erzeugte Bilder (`Bild.hochgeladen =
  True`) sind von der Ablehnung privater/interner IP-Adressen bewusst
  ausgenommen, da ihre URL zwangsläufig auf die eigene
  Home-Assistant-Instanz zeigt. Das Flag wird dabei **ausschliesslich
  serverseitig abgeleitet** (ab `2026.10.0-dev.4`, Befund F1 des Code
  Reviews zu 2026.9.2): Es gilt nur für URLs im exakten Muster des
  eigenen Uploads (`/api/image/serve/<32 Hex-Zeichen>/original|BxH`, ohne
  Query/Fragment) **und** auf einer Origin dieser Home-Assistant-Instanz
  (interne, externe, Cloud- bzw. automatisch erkannte lokale URL). Ein
  in Importdateien, `ws_save`-Anfragen oder Store-Daten behauptetes
  `hochgeladen: true` wird ignoriert und weder gespeichert noch
  exportiert; Schema- und Zugangsdaten-Prüfung gelten unverändert. Wird
  Home Assistant über einen nicht als interne/externe URL
  konfigurierten Hostnamen aufgerufen, gilt ein dort hochgeladenes Bild
  mit privater IP als normale externe URL und wird abgelehnt – dann
  die interne/externe URL unter *Einstellungen → System → Netzwerk*
  konfigurieren. Siehe `docs/architecture.md`, Abschnitt „Geführter
  Bilder-Upload“.
- Die Text-Heuristiken der Website-Auswertung (Adresse, Öffnungszeiten,
  Telefon, E-Mail) sind laufzeitbegrenzt (Befund F2): Eingabelänge und
  Zeilenlänge sind gekappt, alle Muster haben Obergrenzen, und die
  Auswertung läuft im Executor mit Zeitlimit statt in der Event-Loop.
- Der Bilder-Upload selbst nutzt ausschliesslich Home Assistants eigene
  `image_upload`-Komponente (kein eigener Upload-Endpunkt); Format-
  (JPEG/PNG/GIF) und Grössenprüfung (max. 10 MB) erfolgen serverseitig
  durch diese Komponente.
- Die Verwaltungsoberfläche (`frontend.py`, `management.py`) erfordert
  Home-Assistant-Administratorrechte (`require_admin`) – auch für die
  Funktion „🔍 Angaben automatisch ermitteln“, die seit Issue #11 beide
  WebSocket-Befehle `ws_webseite_info` und `ws_osm_info` (siehe unten)
  gemeinsam auslösen kann.
- Es findet keine Kommunikation mit externen Diensten durch HofKarte
  selbst statt (siehe README, Abschnitt „Datenschutz- und
  Standort-Hinweise“) – Ausnahmen: das Laden von Hofladen-Bildern über
  die vom Benutzer hinterlegten externen Bild-Adressen, (seit
  Issue #8) der Abruf einer vom Benutzer im Verwaltungs-Panel
  eingegebenen Website-Adresse, sowie (seit Issue #10, erweitert in
  Issue #11) die Suche über die OpenStreetMap-Overpass-API – beide
  seit Issue #11 gemeinsam über die eine Funktion „🔍 Angaben
  automatisch ermitteln“ auslösbar.

### Funktion „Infos ermitteln“ (`webseite_info.py`, Issue #8)

Diese Funktion ist die **erste eigene ausgehende Netzwerkanfrage im
Backend-Code von HofKarte** – bisher wurde jede Netzwerkkommunikation an
Home-Assistant-Komponenten oder den Browser delegiert. Getroffene
Sicherheitsmassnahmen:

- **Kein externer/Cloud-/KI-Dienst:** Die Extraktion erfolgt
  ausschliesslich lokal und deterministisch (schema.org-JSON-LD,
  `<title>`/Meta-Beschreibung als Fallback). Es wird kein Cloud-Dienst,
  kein LLM und kein Scraping-Dienst eingebunden.
- **SSRF-Schutz über den Standard aus `images.py` hinaus:** Neben der
  syntaktischen Grundprüfung (Schema, Zugangsdaten, „localhost“,
  private/interne IP-Literale – ausgelagert in
  `custom_components/hofkarte/url_sicherheit.py` und von `images.py`
  und `webseite_info.py` gemeinsam genutzt) gelten zusätzlich ein
  Antwortgrössen-Limit (2 MB), eine Content-Type-Prüfung (nur
  HTML-artige Antworten), eine Zeitüberschreitung (10 Sekunden) sowie
  eine manuelle, bei jedem Sprung erneut geprüfte Weiterleitungsauflösung
  (maximal 3 Sprünge) – eine Weiterleitung auf ein privates/internes
  Ziel wird dadurch abgelehnt, statt ihr automatisch zu folgen.
- **Home Assistants verwaltete Client-Session:** Der Abruf verwendet
  `homeassistant.helpers.aiohttp_client.async_get_clientsession`, keine
  eigene, unverwaltete `aiohttp.ClientSession` (siehe
  `custom_components/hofkarte/quality_scale.yaml`, Kriterium
  `inject-websession`).
- **Review vor dem Speichern:** Das Ergebnis ist ausschliesslich ein
  Vorschlag im Bearbeitungsformular – es wird dabei nichts automatisch
  gespeichert; das eigentliche Speichern erfolgt unverändert über den
  bestehenden, administratorpflichtigen `ws_save`-Befehl.
- **DNS-Rebinding-Schutz (ab `2026.10.0-dev.5`, Befund F4):** Der
  Website-Abruf löst jeden Hostnamen (Erstanfrage und jeden
  Weiterleitungssprung) asynchron auf, prüft **alle** A/AAAA-Einträge auf
  öffentliche Erreichbarkeit (`is_global`; gemischte Antworten werden
  abgelehnt) und verbindet sich mit genau den geprüften Adressen. Dafür
  nutzt der Abruf je Anfrage eine eigene, kurzlebige `aiohttp`-Session
  mit eigenem Resolver (statt der geteilten Home-Assistant-Session).
  Zusätzlich wird die URL-Syntax gehärtet (normalisierter Hostname,
  unübliche IPv4-Schreibweisen wie `127.1`/`2130706433`/`0x7f000001`,
  interne Hostnamen wie `*.local`/`*.lan`/Einzel-Label).
- **Grenze der Bild-URL-Prüfung:** Für `image_url` (synchrone
  Entity-Property) findet weiterhin keine Auflösung statt; die
  Prüfung ist dort rein syntaktisch (siehe oben).
- **Eingabelimits (Befund F11):** Längen-/Mengenlimits für alle
  Hofladen-Felder, strikte ID-Regel (`[A-Za-z0-9_-]{1,64}`), einfache
  Format-Prüfung für E-Mail/Telefon und höchstens 500 Datensätze je
  Import (Konstanten in `const.py`). Bestehende Datensätze, die die
  Regeln verletzen (z. B. eine ID mit Leerzeichen), werden beim
  Einlesen übersprungen und im Log gewarnt.
- **Panel-Defense-in-Depth (Befund F12):** Datenwerte in HTML-Attributen
  werden escaped, Bilder nur bei sicherer URL geladen (sonst Platzhalter,
  externe Bilder mit `referrerpolicy="no-referrer"`), `mailto:`-Links nur
  für validierte Adressen, Import-Datei höchstens 2 MB.

### Datenschutz der Kontaktfelder, Last auf externe Dienste (Befund F14)

- **Kontaktdaten:** Mobilnummer und E-Mail liegen **unverschlüsselt** in
  `.storage/hofkarte_hoflaeden` und sind Teil von Home-Assistant-
  Backups. Entities (Attribute) und Diagnostics geben sie nicht aus; wer
  ein Backup oder die Storage-Datei weitergibt, gibt sie mit weiter.
- **Overpass (OpenStreetMap):** Radius höchstens 2 000 m, Gesamtbudget
  40 s über alle Instanzen, 10-Minuten-Cache (höchstens 32 Einträge) gegen
  wiederholte identische Abfragen; es werden nur Koordinaten und Radius
  gesendet, nur auf ausdrücklichen Klick.
- **Statische Dateien:** werden mit langem Cache ausgeliefert; Versionen
  stehen in den URLs (`?v=`), nach einem Update lädt der Browser neu.

### Gebündelte Frontend-Bibliotheken (Befund F7, ab 2026.10.0-dev.6)

Die Kartenansicht nutzt Leaflet `1.9.4` (BSD-2-Clause) und bei mehr als
200 Markern `leaflet.markercluster` `1.5.3` (MIT). Beide liegen
**unverändert im Repository** (`custom_components/hofkarte/static/vendor/`)
und werden von Home Assistant selbst ausgeliefert – es wird **kein
Skript und kein Stylesheet mehr von einem CDN** geladen. Damit entfällt
das Lieferkettenrisiko eines nachträglich veränderten CDN-Inhalts (im
Panel läuft Code mit den Rechten der angemeldeten Home-Assistant-Sitzung).
Herkunft, Lizenzen und SHA-256-Prüfsummen stehen in
`THIRD_PARTY_NOTICES.md`; ein Test gleicht die Prüfsummen mit den Dateien
ab. Die einzige verbleibende Verbindung zu Dritten in der Kartenansicht
sind die OpenStreetMap-Kacheln (siehe Datenschutz-Hinweise). Das Panel
meldet einen Ladefehler der Bibliothek ohne automatische
Wiederholungsschleife (Befund F8).

### Funktion „Ort in der Nähe suchen“ (`osm_info.py`, Issue #10, erweitert in Issue #11)

Diese Funktion führt die **zweite eigene ausgehende Netzwerkanfrage im
Backend-Code von HofKarte** ein – diesmal an die OpenStreetMap-Overpass-
API, einen von HofKarte nicht kontrollierten, aber freien, kostenlosen,
kontofreien OpenStreetMap-Community-Dienst (kein kommerzieller
Cloud-Dienst, kein LLM/KI-Dienst, kein „Scraping-as-a-Service“). Anders
als die rein clientseitig vom Browser geladenen OpenStreetMap-
Kartenkacheln (Issue #2) überträgt diese Funktion **serverseitig
konkrete Koordinaten eines bestimmten Hofladens** an den externen Dienst
– ausschliesslich auf ausdrücklichen Klick auf „📍 Ort in der Nähe
suchen“, nie automatisch oder im Hintergrund. Getroffene
Sicherheitsmassnahmen bzw. bewusste Abgrenzungen:

- **Kein externer/Cloud-/KI-Dienst im Sinne des Kernprinzips:** Die
  Overpass API ist ein reiner OpenStreetMap-Datenabruf (strukturierte
  Kartendaten, kein LLM, kein Konto, keine Nutzungsgebühr) – keine
  Interpretation durch einen Cloud-/KI-Dienst. Die Antwort wird
  ausschliesslich lokal und deterministisch ausgewertet (siehe
  `osm_info.py`, Moduldoc, für die genaue Einordnung dieser bewusst
  begrenzten, zweiten Ausnahme).
- **Mehrere feste Anfrageziele statt eines Einzelpunkts:** Die
  Haupt-Instanz `overpass-api.de` wird von ihren eigenen Betreibern als
  häufig überlastet beschrieben. Statt eines einzelnen, fest verdrahteten
  Endpunkts hinterlegt `osm_info.py` deshalb eine kurze, statische Liste
  bekannter, öffentlicher Overpass-Instanzen (`OVERPASS_URLS`, alle drei
  ebenfalls freie, kostenlose, kontofreie OpenStreetMap-Community-Dienste
  – keine neue Kategorie externer Dienste); schlägt eine Instanz fehl
  (Verbindungsfehler, Zeitüberschreitung, Fehler- oder
  Drosselungs-Status wie HTTP 429), wird automatisch die nächste
  versucht, jeder Fehlversuch wird protokolliert.
- **Erkennbarer `User-Agent`-Header:** Die Overpass-Nutzungsrichtlinien
  verlangen ausdrücklich einen identifizierenden `User-Agent`- oder
  `Referer`-Header; jede Anfrage sendet daher einen festen,
  HofKarte-identifizierenden `User-Agent` mit.
- **Kein SSRF-Schutz à la `url_sicherheit.py` nötig, dafür andere
  Limits:** Anders als bei `webseite_info.py` sind die Anfrageziele hier
  **fest im Code hinterlegt** (`OVERPASS_URLS`) und werden nie durch
  Benutzereingaben beeinflusst – nur Koordinaten und Radius (reine
  Zahlenwerte) fliessen in den Anfragetext ein, eine Prüfung einer
  benutzergesteuerten Ziel-URL entfällt damit. Es gelten dieselben
  allgemeinen Abwehrmassnahmen wie in `webseite_info.py`: ein
  Antwortgrössen-Limit (1 MB) sowie eine Zeitüberschreitung
  (25 Sekunden je Instanz).
- **Seit Issue #11 im Formular einstellbarer Radius, zweifach
  begrenzt:** Der Suchradius ist nicht mehr fest auf
  `STANDARD_RADIUS_METER` (50 m) verdrahtet, sondern im Formular
  einstellbar – bewusst über **zwei unabhängige Schichten** begrenzt,
  damit ein zu grosser oder ungültiger Wert weder eine überdimensionierte
  Anfrage an den externen Dienst erzeugt noch die Anwendung mit einem
  Fehler abbricht: Das WebSocket-Schema von `ws_osm_info` weist einen
  Wert ausserhalb von `MIN_RADIUS_METER`–`MAX_RADIUS_METER` (20–2000 m)
  bereits vor der Verarbeitung mit einem Schema-Fehler zurück; zusätzlich
  klammert `async_ermittle_osm_orte()` selbst jeden übergebenen Radius
  defensiv auf denselben Bereich, unabhängig davon, ob er über den
  regulären WebSocket-Pfad oder – etwa in Tests – direkt an die Funktion
  übergeben wurde.
- **Home Assistants verwaltete Client-Session:** Wie
  `webseite_info.py` verwendet auch dieser Abruf
  `homeassistant.helpers.aiohttp_client.async_get_clientsession`, keine
  eigene, unverwaltete `aiohttp.ClientSession` (siehe
  `custom_components/hofkarte/quality_scale.yaml`, Kriterium
  `inject-websession`).
- **Begrenzter, dokumentierter `opening_hours`-Parser statt
  Freitext-Raten:** OpenStreetMaps `opening_hours`-Tag folgt einer
  eigenen, formal spezifizierten Syntax – dieses Modul unterstützt
  bewusst nur eine gängige Teilmenge davon (siehe `osm_info.py`,
  Moduldoc); nicht unterstützte Syntax (Feiertagsregeln, Datumsbereiche,
  `off`-Ausnahmen u. Ä.) wird komplett übersprungen statt teilweise oder
  falsch interpretiert.
- **Review vor dem Speichern:** Wie bei `webseite_info.py` ist das
  Ergebnis ausschliesslich ein Vorschlag im Bearbeitungsformular – es
  wird dabei nichts automatisch gespeichert; das eigentliche Speichern
  erfolgt unverändert über den bestehenden, administratorpflichtigen
  `ws_save`-Befehl. Bei mehreren Treffern wird zunächst eine
  Trefferauswahl gezeigt, bevor der gewählte Treffer im bereits aus
  Issue #9 bekannten Bestätigungs-Popup zur Prüfung erscheint.

### Funktion „Hofladen finden“ (`discovery/`, ab `2026.10.1`)

Der Dialog „🔎 Hofladen finden“ sucht Hofläden in OpenStreetMap, wertet
auf Wunsch deren Website aus und schlägt die Angaben zur Übernahme in ein
neues Formular vor. Er erweitert die beiden obigen Funktionen um zwei
bewusst begrenzte Ausnahmen; es gibt weiterhin **keinen KI-, Cloud- oder
Scraping-Dienst** (die optionale KI-Anreicherung ist nicht Teil dieser
Version).

- **Ausdrücklicher Klick, nur Administratoren:** Die WebSocket-Befehle
  `hofkarte/management/discover` und `…/enrich` verlangen
  Administratorrechte (`require_admin`). Es läuft nichts im Hintergrund
  oder automatisch; gespeichert wird erst im bestehenden `ws_save`-Pfad
  nach Prüfung im Formular.
- **Overpass (Suche):** Dieselben festen, freien Overpass-Instanzen wie
  bei „Ort in der Nähe suchen“ (`OVERPASS_URLS`), Zielliste nie durch
  Benutzereingaben beeinflusst, Radius serverseitig auf 50 m bis 5 km
  begrenzt (Schema und defensive Klammerung), Antwortgrössen- und
  Zeitlimit, kurzer Zwischenspeicher (10 Minuten, höchstens 32 Einträge).
  Eine HTTP-200-Antwort mit leerer Trefferliste und Overpass-Fehlerhinweis
  (`remark`) wird als Fehler gemeldet, nicht als „keine Treffer“. Dabei
  werden Koordinaten übertragen, die der Benutzer im Dialog gewählt hat.
- **Website-Abruf mit `robots.txt` (neue Ausnahme):** Im Gegensatz zu
  „Infos ermitteln“ (eine vom Benutzer angegebene Seite) liest die
  Anreicherung höchstens **4 Seiten desselben Hosts**: die Startseite und
  Links von ihr (eine Ebene tief, nur Seiten wie Kontakt/Öffnungszeiten/
  Hofladen), nacheinander mit **1 Sekunde Pause**, ohne Dateien (PDF,
  Bilder), ohne Logins, mit Gesamtzeitlimit. Vor dem ersten Abruf wird
  `robots.txt` nach RFC 9309 ausgewertet: `Disallow` für `HofKarte`
  bzw. `*` wird beachtet, 4xx bedeutet „alles erlaubt“, 5xx oder
  Netzwerkfehler bedeuten konservativ „nichts abrufen“. Die Anfragen
  tragen den erkennbaren `User-Agent`
  `HofKarte/HomeAssistant (+https://github.com/rest-be/HofKarte-HA)`.
- **SSRF-Schutz unverändert:** Alle Abrufe laufen über die gehärtete
  Session aus `webseite_info.py` (öffentliche Adressen, DNS-Prüfung mit
  IP-Bindung, Weiterleitungen einzeln geprüft, Grössen-/Typ-/Zeitlimits).
  Links werden nur innerhalb desselben Hosts verfolgt.
- **Herkunftsnachweis (`quellen`):** Jeder übernommene Wert trägt seine
  Quelle (OpenStreetMap oder Website, mit Adresse) und den Status
  `confirmed`/`inferred`. OpenStreetMap-Werte werden mit „©
  OpenStreetMap-Mitwirkende (ODbL)“ gekennzeichnet. Das Feld wird beim
  Einlesen streng bereinigt (bekannte Felder, nur http(s)-URLs, eine
  Quelle je Feld, höchstens 20 Einträge). Beschreibungstexte werden
  **nicht** automatisch übernommen.
- **Standort des Geräts (Browser):** Beim Öffnen des Dialogs fragt der
  Browser (nach Freigabe durch den Benutzer) den aktuellen Gerätestandort
  ab, um die Koordinaten vorzubelegen. Das ist die einzige Verwendung der
  Geolocation-API im Panel; der Wert verlässt das Gerät nur als
  Suchkoordinaten an den eigenen Home-Assistant-Server und von dort an
  Overpass, und wird nicht gespeichert. Ohne sicheren Kontext (HTTPS) oder
  ohne Freigabe fällt der Dialog auf die in Home Assistant konfigurierte
  Position zurück.
- **Panel-Härtung:** Alle Werte aus OpenStreetMap und Websites werden vor
  der Darstellung HTML-escaped (durch einen Test abgesichert), Links nur
  für http(s)-Adressen mit `rel="noopener noreferrer"`.
