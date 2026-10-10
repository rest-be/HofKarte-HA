# HofKarte – Anwendungshandbuch

Vollständiges Handbuch für Endanwender:innen. Aktuell nur auf Deutsch
verfügbar; die Kapitelstruktur ist so angelegt, dass weitere Sprachen
(z. B. `handbuch.en.md`) ergänzt werden können, ohne die Gliederung zu
ändern.

Für eine technische Kurzübersicht siehe [`README.md`](../README.md),
für die Entwickler-/Architekturdokumentation siehe
[`architecture.md`](architecture.md).

## Inhalt

1. [Installation über HACS](#1-installation-über-hacs)
2. [Ersteinrichtung](#2-ersteinrichtung)
3. [Konfiguration](#3-konfiguration)
4. [HofKarte-Geräte](#4-hofkarte-geräte)
5. [Entities](#5-entities)
6. [Öffnungszeiten](#6-öffnungszeiten)
7. [Standort und Entfernung](#7-standort-und-entfernung)
8. [Angebote und Zahlungsarten](#8-angebote-und-zahlungsarten)
9. [Actions und Automationen](#9-actions-und-automationen)
10. [Dashboard-Beispiele](#10-dashboard-beispiele)
11. [Fehlerbehebung](#11-fehlerbehebung)
12. [Updates](#12-updates)
13. [Deinstallation](#13-deinstallation)
14. [Datenschutz](#14-datenschutz)
15. [Support](#15-support)

---

## 1. Installation über HACS

1. HACS öffnen (Seitenmenü in Home Assistant).
2. Über das Drei-Punkte-Menü (oben rechts) **Benutzerdefinierte
   Repositories** wählen.
3. Repository-URL `https://github.com/rest-be/HofKarte` eintragen,
   Kategorie **Integration** wählen, hinzufügen.
4. Im HACS-Suchfeld „HofKarte“ eingeben, öffnen, **Herunterladen**
   wählen.
5. Home Assistant vollständig neu starten (**Entwicklerwerkzeuge →
   YAML** reicht **nicht** – ein echter Neustart ist nötig, damit die
   neue Integration erkannt wird).

*Hinweis: Solange HofKarte nicht im HACS-Default-Store gelistet ist,
sind Schritt 2–3 (benutzerdefiniertes Repository) erforderlich.*

Alternative: manuelle Installation (siehe README, Abschnitt
„Installation“) – nur empfohlen, wenn HACS nicht zur Verfügung steht.

## 2. Ersteinrichtung

Nach dem Neustart:

1. **Einstellungen → Geräte & Dienste** öffnen.
2. **Integration hinzufügen** (unten rechts) wählen.
3. „HofKarte“ suchen und auswählen.
4. Im Einrichtungsdialog erscheint genau **ein Eingabefeld**:
   **Anzeigename** (z. B. „HofKarte“ – frei wählbar, wird als Titel der
   Integration in der Übersicht angezeigt). Bestätigen.
5. HofKarte ist eingerichtet. Es erscheint noch kein Hofladen – das
   Hinzufügen von Hofläden geschieht über die grafische
   Verwaltungsoberfläche (siehe Kapitel 4).

**Wichtig – Single-Instance:** HofKarte kann nur **einmal** pro
Home-Assistant-Installation eingerichtet werden. Ein zweiter Versuch
über „Integration hinzufügen“ wird mit der Meldung „HofKarte ist bereits
eingerichtet“ abgelehnt. Das ist kein Fehler, sondern beabsichtigt: Eine
Instanz verwaltet zentral **alle** Hofläden.

## 3. Konfiguration

Über **Einstellungen → Geräte & Dienste → HofKarte → Konfigurieren**
steht eine „Einstellungen“-Maske (Options Flow) zur Verfügung:

- **Standard-Sortierung der Übersicht:** Sortierfeld (Name, Adresse,
  Status oder Bewertung) und -richtung, die die Listenansicht beim
  Öffnen vorgibt.
- **Standard-Suchradius für „🔍 Angaben automatisch ermitteln“:**
  dauerhaft gespeicherter Vorgabewert für die OpenStreetMap-Suche
  (20–2000 m, voreingestellt 200 m) – wird beim Öffnen des
  Bearbeitungsformulars als Vorschlag übernommen, im Formular selbst
  aber weiterhin pro Aufruf überschreibbar.

Davon unabhängig, weiterhin nur auf Code-Ebene änderbar:

- **Aktualisierungsintervall:** fest auf 15 Minuten
  (`const.DEFAULT_UPDATE_INTERVAL` im Quellcode).
- **Abruf-Timeout:** fest auf 30 Sekunden.

Das ist eine bekannte, dokumentierte Einschränkung (siehe
`quality_scale.yaml`, README „Bekannte Einschränkungen“) – keine
fehlende Dokumentation, sondern der tatsächliche, vollständige
Funktionsumfang.

Was sich **wohl** ändern lässt, sind die eigentlichen Hofladen-Daten
(Name, Adresse, Öffnungszeiten, Sortiment, Bilder, Kontaktdaten,
Bewertung, ...) – das geschieht nicht über „Konfigurieren“, sondern
über die grafische Verwaltungsoberfläche, siehe Kapitel 4.

## 4. HofKarte-Geräte

Nach der Einrichtung erscheint im Home-Assistant-Seitenmenü ein neuer
Eintrag **HofKarte** (nur für Administrator:innen-Konten sichtbar). Dort
können Hofläden verwaltet werden:

### Übersicht: Kacheln, Liste oder Karte

Die Übersicht hat in allen drei Ansichten dieselbe **Kopf- und
Steuerleiste**:

- **Kopfzeile:** „Hofladen finden“, „Hofladen“ (neu anlegen) und ein
  ⋮-Menü mit dem Import (JSON).
- **Suche** nach Name oder Ort, der Filter **„Nur geöffnet“** (fehlende
  Öffnungszeiten zählen dabei **nicht** als geöffnet), die **Sortierung**
  (Name, Adresse, Ort, Status, Bewertung; Pfeil kehrt die Richtung um)
  und der Umschalter **Kacheln / Liste / Karte**. Suche, Filter und
  Sortierung gelten gemeinsam für alle drei Ansichten und bleiben beim
  Wechsel erhalten. Darunter zeigt ein Zähler „x von y Hofläden“ das
  Ergebnis; ohne Treffer erscheint ein Hinweis mit „Filter
  zurücksetzen“.

Die drei Ansichten:

- **Kacheln** (Standardansicht): eine Kachel pro Hofladen mit Hauptbild
  (oder neutralem Platzhalter), Name, Adresse, Öffnungsstatus
  („🟢 Geöffnet“/„🔴 Geschlossen“/„Unbekannt“), Sterne-Bewertung und
  anklickbarer Webseite. **Die ganze Kachel ist anklickbar** und öffnet
  die Detailansicht. Das **⋮-Menü** der Kachel enthält Route (Google
  Maps / Apple Maps), Bearbeiten und – zuunterst, rot – Löschen (mit
  Rückfrage). Checkboxen erscheinen nur im **Auswahlmodus** („Auswählen“
  in der Steuerleiste, Beenden mit „Auswahl beenden“).
- **Liste:** eine Tabelle mit Auswahl-Checkbox, Name (mit Adresse
  darunter), Ort, Status, Bewertung und ⋮-Menü (gleiche Einträge wie
  bei den Kacheln). Die Spaltenköpfe sind sortierbar (Klick, erneuter
  Klick kehrt um); die Kopf-Checkbox wählt alle sichtbaren Zeilen. Auf
  schmalen Bildschirmen entfallen Ort und Bewertung. Welches Feld beim
  Öffnen vorausgewählt ist, lässt sich über den Options Flow vorgeben
  (siehe Kapitel 3).
- **Karte:** links eine Liste aller Treffer, rechts die eingebettete
  Karte (auf Mobilgeräten Karte oben, Liste darunter) mit einer
  Stecknadel je Hofladen mit hinterlegten Koordinaten. Die Farben (grün
  geöffnet, grau geschlossen, sonst Standardfarbe) erklärt eine Legende
  unter der Karte. Ein Klick auf einen Listeneintrag zentriert die Karte
  und öffnet die Info-Karte (Name, Adresse, Status, Bewertung,
  „Details“, „Route“); umgekehrt hebt ein Klick auf eine Stecknadel den
  Eintrag in der Liste hervor. Hofläden ohne Koordinaten stehen in der
  Liste („keine Koordinaten“), erscheinen aber nicht auf der Karte. Sind
  für keinen Hofladen Koordinaten hinterlegt, erscheint statt der Karte
  ein Hinweis. Die Kartenkacheln werden von OpenStreetMap geladen, sobald
  diese Ansicht zum ersten Mal geöffnet wird (siehe Kapitel 14,
  Datenschutz).

**Tastatur:** Das ⋮-Menü öffnet sich per Enter/Leertaste mit Fokus auf dem
ersten Eintrag; Pfeil hoch/runter, Pos1 und Ende bewegen den Fokus,
Escape schliesst das Menü und setzt den Fokus auf den Knopf zurück.

Der Öffnungsstatus wird serverseitig berechnet und stimmt daher stets
mit der Entity „Geöffnet“ (Kapitel 5) überein.

- **Neuer Hofladen:** über die Verwaltungsseite anlegen (Name,
  Beschreibung, Bemerkung, Adresse, PLZ/Ort, Land, Koordinaten,
  Webseite, Öffnungszeiten, Sortiment, Bilder).
- **Bearbeiten:** bestehenden Hofladen in der Liste auswählen, Felder
  ändern, speichern.
- **Details ansehen:** über den Button „Details“ eine **reine
  Anzeigeansicht** öffnen – übersichtlich strukturiert, ohne
  editierbare Felder. Gedacht für den schnellen Überblick, ohne
  versehentlich etwas zu verändern. Über den Button „Bearbeiten“ in der
  Detailansicht gelangt man bei Bedarf gezielt in den Bearbeitungsmodus.
- **Löschen:** Hofladen kontrolliert entfernen (inklusive des
  zugehörigen Geräts und aller Entities in Home Assistant).

### Hofläden exportieren und importieren

In der Ansicht „Liste“ steht in jeder Zeile eine Auswahl-Checkbox, in
den „Kacheln“ erscheinen die Checkboxen nach Klick auf „Auswählen“. Sobald
etwas gewählt ist (bzw. im Auswahlmodus), zeigt eine Leiste die Anzahl
und die Buttons „Alle auswählen“ (nur die gerade sichtbaren Treffer),
„Auswahl aufheben“ und „Export“. Der Import (JSON) liegt im ⋮-Menü der
Kopfzeile:

- **Export:** Mindestens einen Hofladen auswählen und auf „⬇️ Export“
  klicken – der Browser lädt eine einzelne JSON-Datei mit allen
  ausgewählten Hofläden herunter (Dateiname
  `hoflaeden-export-<Zeitstempel>.json`). Diese Datei enthält
  ausschliesslich die gespeicherten Daten (keine berechneten Werte wie
  den aktuellen Öffnungsstatus) und lässt sich als Sicherung
  aufbewahren oder an andere HofKarte-Nutzer:innen weitergeben.
- **Import:** Auf „⬆️ Import“ klicken und eine zuvor exportierte
  JSON-Datei auswählen. Ist die Datei fehlerhaft (kein gültiges JSON,
  falsche Struktur, ungültige Werte), erscheint eine klare
  Fehlermeldung und **nichts** wird verändert.
  - Erkennt HofKarte für einen zu importierenden Hofladen einen
    bereits vorhandenen mit demselben Namen (und, sofern beide eine
    Adresse besitzen, auch derselben Adresse), öffnet sich ein
    Konfliktdialog: Bestehender und importierter Datensatz werden
    nebeneinander mit farblich hervorgehobenen Unterschieden
    (abweichende Felder rot/grün markiert) angezeigt. Für jedes
    Duplikat wird „Aktualisieren“ (bestehenden Hofladen mit den
    importierten Daten überschreiben) oder „Beibehalten“ (bestehenden
    Hofladen unverändert lassen, importierte Version verwerfen)
    gewählt. Über „Alle aktualisieren“/„Alle beibehalten“ lässt sich
    dieselbe Entscheidung auf einen Schlag für alle gefundenen
    Duplikate treffen. Ohne getroffene Entscheidung wird ein Duplikat
    beim Abschluss automatisch **beibehalten** – ein Import kann so
    nichts versehentlich überschreiben.
  - Hofläden ohne erkanntes Duplikat werden ohne Rückfrage als neue
    Hofläden angelegt.
  - Nach Abschluss zeigt eine Meldung, wie viele Hofläden neu
    angelegt, aktualisiert bzw. beibehalten (übersprungen) wurden.

### Bilder hochladen

Im Bearbeitungsformular steht im Bereich „Bilder“ ein geführter
Upload zur Verfügung:

1. Auf den Button „📤 Bild hochladen“ klicken – dieser öffnet die
   Dateiauswahl des Betriebssystems (unterstützte Formate: JPEG, PNG,
   GIF; maximal 10 MB).
2. Der Upload startet sofort; Erfolg oder ein Fehler (z. B. falsches
   Format oder Datei zu gross) wird direkt darunter angezeigt.
3. Das hochgeladene Bild erscheint danach in der Bilderliste. Dort kann
   optional eine Beschreibung ergänzt, das Bild per Stern-Symbol als
   Hauptbild festgelegt oder wieder entfernt werden.
4. Alternativ lässt sich weiterhin eine externe Bild-Adresse manuell
   eintragen („Oder externe Bild-Adresse manuell hinzufügen“) – beide
   Wege können auch kombiniert werden.

> **Hinweis (Mobile PWA):** Die PWA ab Version 1.11.0 lädt Fotos über
> den WebSocket-Befehl `hofkarte/management/upload_image` hoch (nur
> Admin; JPEG, PNG, GIF bis 3 MiB). Dafür ist keine
> `cors_allowed_origins`-Einstellung nötig. Nur sehr grosse Fotos
> (über ca. 2.5 MB) laufen über den REST-Upload, der CORS braucht.

Das **erste Bild in der Liste** ist stets das Hauptbild und erscheint
als `image`-Entity des Hofladens (siehe Kapitel 5). Wird ein
hochgeladenes Bild entfernt, wird die zugrunde liegende Datei ebenfalls
gelöscht – es bleiben keine verwaisten Dateien zurück.

Sobald ein Hofladen angelegt wird, erstellt HofKarte **automatisch**
(ohne Neustart) ein **logisches Gerät** dafür unter **Einstellungen →
Geräte & Dienste → HofKarte → Geräte**. Dieses Gerät ist **kein
physisches Gerät** – es hat bewusst keinen Hersteller und kein Modell,
da ein Hofladen fachlich beides nicht hat. Unter diesem Gerät finden
sich alle in Kapitel 5 beschriebenen Entities für genau diesen Hofladen.

Wird ein Hofladen gelöscht, verschwindet auch sein Gerät. Die bereits
erzeugten Entities bleiben als „nicht verfügbar“ in der Entity-Liste
bestehen (stabile Entity-ID), statt automatisch entfernt zu werden –
das ist eine bekannte, bewusste Einschränkung.

### Angaben automatisch ermitteln

Im Bearbeitungsformular steht im Bereich „Automatisch ausfüllen“ der
Button „🔍 Angaben automatisch ermitteln“ zur Verfügung. Diese eine
Aktion fasst seit Issue #11 zwei zuvor getrennte Funktionen zusammen
und fragt – je nachdem, was im Formular bereits eingetragen ist –
wahlweise beide Quellen **parallel** ab:

1. Ist im Feld „Webseite“ (Abschnitt „Kontakt & Webseite“) eine
   Adresse eingetragen, ruft HofKarte diese Seite ab und wertet – rein
   lokal, ohne einen externen Cloud- oder KI-Dienst – strukturierte,
   von der Seite selbst veröffentlichte Informationen aus (sofern
   vorhanden): Name, Adresse, Beschreibung, Öffnungszeiten, Angebote,
   Zahlungsarten sowie Mobilnummer und E-Mail. Fehlen strukturierte
   Daten für Adresse oder
   Öffnungszeiten, versucht HofKarte zusätzlich, diese anhand gängiger
   deutschsprachiger Formulierungen im sichtbaren Seitentext zu
   erkennen (z. B. „Musterweg 1, 3000 Bern“ oder „Mo–Fr 08:00–18:00
   Uhr“) – weiterhin ohne externen Dienst und weiterhin: im Zweifel
   kein Vorschlag statt eines unsicheren.
2. Sind gültige Koordinaten (Latitude/Longitude) eingetragen, fragt
   HofKarte eine freie, kostenlose OpenStreetMap-Overpass-Instanz nach
   benannten Orten im nahen Umkreis der eingetragenen Koordinaten ab –
   im einstellbaren Suchradius direkt unterhalb des Buttons (20–2000 m,
   voreingestellt 200 m – der Vorgabewert lässt sich dauerhaft über
   **Einstellungen → Geräte & Dienste → HofKarte → Konfigurieren**
   ändern, siehe Kapitel 3). Ist die zuerst versuchte Instanz überlastet
   oder nicht erreichbar, probiert HofKarte automatisch der Reihe nach
   weitere bekannte, freie Instanzen (siehe Kapitel 14, „Datenschutz“).
   **Dabei werden die Koordinaten dieses Hofladens an diesen externen
   Dienst übermittelt** (siehe Kapitel 14, „Datenschutz“). Gesucht wird
   sowohl nach Orten, die auf OpenStreetMap direkt als Laden/Hof/
   Marktplatz getaggt sind, als auch – seit Issue #11 – nach
   Hofgeländen ohne passenden Tag, deren Name auf einen Hofladen
   hindeutet (z. B. „Hof“, „Bauernhof“, „Hofladen“, „Laden“ im Namen).
3. Ist **weder** eine Website-Adresse **noch** ein gültiges
   Koordinatenpaar eingetragen, meldet HofKarte dies und ruft keine der
   beiden Quellen ab.
4. Liefert die Koordinatensuche **genau einen** Treffer (oder liefert
   nur die Website ein Ergebnis), öffnet sich direkt das gemeinsame
   Bestätigungs-Popup. Liefert die Koordinatensuche **mehrere**
   Treffer, wird zunächst eine Liste zur Auswahl angezeigt (Name,
   Adresse, Entfernung) – Treffer, die nur anhand ihres Namens gefunden
   wurden (kein Hofladen-Tag), sind dort ausdrücklich als „anhand des
   Namens gefunden, kein Hofladen-Tag auf OpenStreetMap“ gekennzeichnet.
   Ein bereits vorliegendes Website-Ergebnis bleibt dabei erhalten und
   wird nach der Auswahl mit dem gewählten Ort zusammengeführt.
5. Im Bestätigungs-Popup sind alle Vorschläge zusätzlich mit ihrer
   Herkunft markiert (Website und/oder OpenStreetMap) – liefern beide
   Quellen für dasselbe Feld unterschiedliche Werte, wird der
   Website-Wert vorgeschlagen, der abweichende OpenStreetMap-Wert aber
   nicht verworfen, sondern in der Kennzeichnung sichtbar gehalten.
   Nicht gefundene Felder sind klar als solche gekennzeichnet. Erst ein
   Klick auf **„Übernehmen“** trägt die angezeigten Vorschläge in die
   entsprechenden Formularfelder ein; **„Abbrechen“** verwirft sie
   vollständig, das Formular bleibt dabei unverändert (auch das Popup
   lässt sich per Escape-Taste schliessen, was wie „Abbrechen“ wirkt).
   In beiden Fällen wird **nichts automatisch gespeichert** – auch nach
   „Übernehmen“ bitte die übernommenen Werte vor dem Speichern prüfen
   und bei Bedarf anpassen, bevor regulär auf „Speichern“ geklickt
   wird.

Mögliche Rückmeldungen:

- **„Bitte zuerst eine Website-Adresse oder gültige Latitude-/
  Longitude-Werte eintragen.“** – weder das Feld „Webseite“ noch die
  Koordinatenfelder enthalten verwertbare Angaben.
- **„Die Website konnte nicht erreicht oder nicht gelesen werden.“** –
  die Seite war zum Zeitpunkt des Abrufs nicht erreichbar (z. B.
  Zeitüberschreitung oder Fehlerstatus) oder ihre Antwort liess sich
  nicht als Webseite verarbeiten.
- **„Auf der Website wurden keine verwertbaren Informationen
  gefunden.“** – die Seite war erreichbar, enthielt aber keine der
  gesuchten Angaben in auswertbarer Form.
- **„Die Overpass API (OpenStreetMap) konnte nicht erreicht
  werden.“** – keine der der Reihe nach versuchten Overpass-Instanzen
  war zum Zeitpunkt der Suche erreichbar (z. B. Zeitüberschreitung
  oder Fehlerstatus bei allen Instanzen). Details zu den einzelnen
  Fehlversuchen stehen im Home-Assistant-Protokoll (Einstellungen →
  System → Protokolle).
- **„Im Umkreis wurden keine Orte gefunden.“** – im Suchradius sind auf
  OpenStreetMap keine benannten, passenden Orte hinterlegt.

Schlagen beide Quellen gleichzeitig fehl, werden beide Meldungen
gemeinsam in der Statusanzeige ausgewiesen; liefert nur eine der
beiden Quellen ein Ergebnis, öffnet sich trotzdem das
Bestätigungs-Popup mit den Angaben der erfolgreichen Quelle.

### Hofladen finden

Der Button **„🔎 Hofladen finden“** oben in der Übersicht (neben „+ Neuer
Hofladen“) sucht einen Hofladen und füllt ein neues Formular vor.

**Schritt 1 – Suchen.** Name und Website sind optional und verbessern die
Trefferqualität. Beim Öffnen werden die Koordinaten vom **aktuellen
Standort deines Geräts** übernommen; dein Browser fragt dabei um Freigabe.
Das funktioniert nur über HTTPS; sonst (oder ohne Freigabe) wird die in
Home Assistant eingestellte Position verwendet, und du kannst die
Koordinaten von Hand ändern. Mit „📍 Mein Standort“ holst du den Standort
erneut. Der Umkreis lässt sich von 50 m bis 5 km einstellen (Standard
2 km). Die „erweiterte Suche“ berücksichtigt mehr OpenStreetMap-Tags, ist
langsamer und noch wenig getestet.

**Schritt 2 – Treffer wählen.** Die Treffer sind nach Übereinstimmung
sortiert. „Hohe Sicherheit“ heisst: nah am Standort und/oder passender
Name bzw. Website. Ein Hinweis „Möglicherweise schon erfasst“ warnt vor
Doppelerfassung. Ohne Treffer kannst du „Manuell erfassen“ wählen oder,
wenn eine Website eingetragen ist, „Nur Website auswerten“.

**Schritt 3 – Angaben prüfen.** HofKarte liest die OpenStreetMap-Angaben
und, falls vorhanden, die Website. Pro Angabe (Name, Adresse, Webseite,
Telefon, E-Mail, Öffnungszeiten, Angebote, Zahlungsarten) siehst du die
Quelle und kannst sie abwählen. Weichen die Quellen voneinander ab, steht
ein Hinweis dabei. „In Formular übernehmen“ öffnet ein **neues Formular**;
erst dort speicherst du. Eine Beschreibung wird nie automatisch erzeugt.

**Optional: KI-Auswertung.** Unter Einstellungen → Geräte & Dienste →
HofKarte → Konfigurieren kannst du eine „AI Task“-Entität wählen (leer =
aus). Danach erscheint in Schritt 1 das Kästchen „Website-Text mit KI
auswerten“. Es ist nie vorangekreuzt, und der Dialog nennt die Entität:
Der Text der Website wird dorthin gesendet und verlässt je nach Anbieter
dein Netzwerk (bei lokalen Modellen wie Ollama nicht). In Schritt 3 steht
die KI-Auswertung im Fortschritt. Was die KI nennt und **wörtlich auf der
Seite steht**, erscheint bei den normalen Angaben mit dem Vermerk „Website
(KI-gestützt)“. Was sie nennt, aber nicht belegt ist, steht getrennt unter
„Vermutungen der KI (nicht belegt)“, ist **nicht vorausgewählt** und wird,
wenn du es übernimmst, als „vermutet“ vermerkt. Antwortet die KI nicht,
zu langsam oder unbrauchbar, bleibt das Ergebnis ohne KI.

**Hinweise.** Die Website wird nur gelesen, wenn ihre `robots.txt` das
erlaubt (höchstens 4 Seiten, mit Pause). Die Quellen der übernommenen
Angaben stehen später in der Detailansicht unter „Quellen“.
OpenStreetMap-Angaben stammen von © OpenStreetMap-Mitwirkenden (ODbL).
Fehlermeldungen („Dienst nicht erreichbar“, „robots.txt sperrt“) erscheinen
im Dialog; dann hilft ein späterer Versuch oder die manuelle Erfassung.

## 5. Entities

Für **jeden** Hofladen legt HofKarte automatisch folgende sechs
Entities an:

| Entity (Name) | Plattform | Device Class | Einheit | Bedeutung |
|---|---|---|---|---|
| **Geöffnet** | `binary_sensor` | – | – | Ist der Hofladen gerade geöffnet? `An`/`Aus`, oder „Unbekannt“, wenn keine Öffnungszeiten hinterlegt sind. |
| **Nächste Öffnung** | `sensor` | Zeitstempel | – | Zeitpunkt, zu dem der Hofladen als Nächstes öffnet. |
| **Nächste Schliessung** | `sensor` | Zeitstempel | – | Zeitpunkt, zu dem der Hofladen als Nächstes schliesst. |
| **Entfernung** | `sensor` | Entfernung | Kilometer | Luftlinien-Entfernung zur konfigurierten Home-Assistant-Position. |
| **Bewertung** | `sensor` | – | – | Vergebene Sterne-Bewertung (0–5), siehe Kapitel 8. |
| **Hauptbild** | `image` | – | – | Zeigt das erste hinterlegte Bild mit gültiger, sicherer URL. |

Die Entity-IDs folgen dem Muster `<plattform>.<hofladen_name>_<funktion>`
(z. B. `binary_sensor.hofladen_mueller_geoeffnet`) – der genaue Name
hängt vom vergebenen Hofladen-Namen ab und ist in **Einstellungen →
Geräte & Dienste → HofKarte → Entities** einsehbar.

### Attribute

- **Geöffnet** trägt zusätzlich die Attribute `angebote` und
  `zahlungsarten` (siehe Kapitel 8) – diese
  Informationen erscheinen **nicht** auf den anderen Entities, um
  Daten nicht mehrfach zu duplizieren.
- **Hauptbild** trägt das Attribut `weitere_bilder` (Liste weiterer
  hinterlegter Bilder mit URL und Beschreibung, siehe Kapitel 8/README
  „Bilder“).

### Zustände

Alle fünf Entities werden „nicht verfügbar“, sobald der letzte
Datenabruf fehlgeschlagen ist **oder** der zugehörige Hofladen aus den
Daten verschwunden ist (siehe Kapitel 4). Solange Daten vorhanden sind,
aber ein Wert (noch) nicht berechenbar ist (z. B. keine Öffnungszeiten
hinterlegt), zeigen die Entities „Unbekannt“ – nicht „nicht verfügbar“
und nicht einen erfundenen Wert.

## 6. Öffnungszeiten

HofKarte unterscheidet **reguläre Öffnungszeiten** und
**Sonderöffnungszeiten**:

- **Reguläre Öffnungszeiten:** pro Wochentag (Montag–Sonntag) beliebig
  viele Zeitintervalle (z. B. „Montag 08:00–12:00“ und „Montag
  14:00–18:00“ für eine Mittagspause).
- **Sonderöffnungszeiten:** ein Datumsbereich (Start- und Enddatum) mit
  entweder eigenen Uhrzeiten (z. B. verlängerte Öffnung an einem
  Feiertag) oder als „geschlossen“ markiert (z. B. Betriebsferien).
  **Sonderöffnungszeiten überschreiben reguläre Zeiten für ihren
  Zeitraum vollständig.**

Beide werden über die Verwaltungsoberfläche gepflegt (Kapitel 4). Für
reguläre Öffnungszeiten wählt man pro Wochentag einen von drei Modi:

- **Geschlossen** – kein Intervall für diesen Tag.
- **24 Stunden geöffnet** – ganztägig geöffnet.
- **Zeiten festlegen** – ein oder mehrere „Von–Bis“-Intervalle, über
  „+ weiteres Intervall“ erweiterbar (z. B. für eine Mittagspause).

In der Detailansicht (Kapitel 4) werden die Wochentage stets in fester
Reihenfolge Montag–Sonntag angezeigt, mit „Geschlossen“, „24 Stunden
geöffnet“ oder den konkreten Zeiten je nach hinterlegtem Modus.

**Mitternachtsüberschreitung:** Ein Intervall, dessen Ende vor seinem
Beginn liegt (z. B. „22:00–02:00“), wird korrekt als über Mitternacht
hinausreichend behandelt.

**Nächste Öffnung/Schliessung:** Ist der Hofladen aktuell geöffnet,
zeigt „Nächste Öffnung“ den Beginn der **darauffolgenden**
Öffnungsphase (nicht die laufende); „Nächste Schliessung“ zeigt das
Ende der laufenden Phase. Ist der Hofladen aktuell geschlossen, zeigen
beide Sensoren die als Nächstes anstehende Öffnungsphase.

**Zeitzonenverhalten:** Die Berechnung erfolgt in der in Home Assistant
konfigurierten Zeitzone (**Einstellungen → System → Allgemein**), nicht
in UTC oder einer festen Zeitzone. Bekannte Grenze: Bei Uhrzeiten genau
in einer Sommerzeit-Umstellungslücke oder im doppelt vorkommenden
Bereich beim Zurückstellen der Uhr wird keine explizite
Mehrdeutigkeits-Auflösung vorgenommen (seltener Grenzfall).

## 7. Standort und Entfernung

### Koordinaten eingeben (WGS84)

In der Verwaltungsoberfläche werden Hofladen-Koordinaten als
**WGS84-Dezimalgrad** erfasst (Latitude/Longitude) – demselben Format,
in dem Home Assistant selbst Standorte angibt und in dem HofKarte die
Koordinaten speichert. Ein deutlich sichtbarer, blau hinterlegter
Infobutton (ⓘ) neben den Feldern zeigt eine kurze Erklärung direkt im
Formular.

**Standort beim Bearbeiten ansehen:** Im Bearbeitungsformular steht
neben den Koordinatenfeldern weiterhin ein Button „🗺️ Auf Google Maps
anzeigen“ zur Verfügung. Ein Klick öffnet den Standort anhand der
gerade eingegebenen WGS84-Koordinaten in einem neuen Browser-Tab auf
Google Maps (als Pin, ohne Route) – so lässt sich die Eingabe vor dem
Speichern kontrollieren. Der Button ist ausgegraut/deaktiviert, solange
keine gültigen Koordinaten eingegeben sind. Die Kartenansicht ist rein
informativ – es lassen sich dort keine Daten verändern.

**Route zum Hofladen öffnen:** In den Kacheln und der Liste liegt die Route
im ⋮-Menü des Hofladens („Route (Google Maps)“ / „Route (Apple Maps)“), in
der Detailansicht stehen statt des Kartenlinks zwei Icon-Buttons zur
Verfügung:

- 🗺️ öffnet eine Wegbeschreibung zum Hofladen in **Google Maps**.
- 🧭 öffnet dieselbe Wegbeschreibung in **Apple Maps**.

Beide öffnen in einem neuen Browser-Tab eine echte Route ausgehend vom
aktuellen Standort – nicht nur einen Pin. Ist beim Hofladen eine
Adresse hinterlegt, wird sie als Ziel verwendet; nur wenn keine Adresse,
aber gültige Koordinaten vorhanden sind, dienen diese als Ziel. Sind
weder Adresse noch gültige Koordinaten hinterlegt, sind beide Buttons
deaktiviert. Es findet dabei keine Kommunikation mit einem
zusätzlichen Geodienst statt – Adresse bzw. Koordinaten werden direkt
als Linkparameter an Google/Apple Maps übergeben.

**Woher bekomme ich die Koordinaten eines Hofladens?** Auf Google Maps
oder einem anderen Kartendienst den gewünschten Ort suchen, mit der
rechten Maustaste auf den genauen Standort klicken – die angezeigten
Zahlen sind Latitude, Longitude und können direkt übernommen werden.

### Entfernung berechnen

Der Sensor „Entfernung“ berechnet die **Luftlinien-Entfernung**
(nicht die Strassenentfernung) zwischen der in Home Assistant
konfigurierten Position (**Einstellungen → System → Allgemein**, Latitude/
Longitude) und den beim Hofladen hinterlegten Koordinaten, über die
Haversine-Formel (Grosskreisdistanz auf einer Kugel).

**Genauigkeit:** Die Berechnung ist mathematisch präzise für die
angegebenen Koordinaten, berücksichtigt aber **keine** Strassen,
Höhenunterschiede oder Reisezeit – es ist eine reine Luftlinie.

**Grenzen:**

- Ohne hinterlegte Koordinaten am Hofladen zeigt der Sensor „Unbekannt“.
- Ist die Home-Assistant-Position nicht sinnvoll konfiguriert (das
  Standardpaar `0.0/0.0` einer frischen Installation), zeigt der Sensor
  ebenfalls „Unbekannt“ statt einer irreführenden Entfernung.
- Es wird **keine Standortverfolgung** durchgeführt (kein
  `device_tracker`, keine Personen-/Geräteverfolgung) – nur die
  statische, einmal konfigurierte Home-Position wird gelesen (siehe
  Kapitel 14, Datenschutz).

## 8. Angebote und Zahlungsarten

Jeder Hofladen kann in zwei Fachbereichen gepflegt werden (über die
Verwaltungsoberfläche, Kapitel 4):

- **Angebote** – eine schlichte Liste konkreter Artikel bzw.
  Leistungen, z. B. „Kartoffeln“, „Honig“. In der Verwaltungsoberfläche
  als ein Eintrag pro Zeile erfasst – jede Zeile ist einfach der Name
  des Angebots, ohne weitere Struktur oder Gruppierung.
- **Zahlungsarten** – z. B. „Bargeld“, „TWINT“, „Debitkarte“,
  „Kreditkarte“.

Für Zahlungsarten bietet HofKarte einen **Vorschlagskatalog** gängiger
Werte (siehe README, Abschnitt „Unter der Haube“) – eigene, frei
gewählte Bezeichnungen sind jederzeit ebenso zulässig. Für Angebote
gibt es bewusst keinen Vorschlagskatalog, da es sich um frei formulierte
Produktnamen ohne sinnvolle Standardwerte handelt.

Diese Informationen erscheinen **nicht** als eigene Sensoren (das wären
zu viele, fachlich nicht als Messwert geeignete Entities), sondern als
**Attribute der Entity „Geöffnet“** (siehe Kapitel 5). Sie lassen sich
in Automationen/Vorlagen über `state_attr(...)` auslesen, z. B.:

```jinja
{{ state_attr('binary_sensor.hofladen_mueller_geoeffnet', 'angebote') }}
```

**Hinweis für bestehende Installationen:** Waren „Kategorien“ und
„Produkte“ vorher als getrennte Fachbereiche gepflegt, werden diese
beim nächsten Öffnen automatisch in schlichte „Angebote“
zusammengeführt (sowohl frühere Kategorienamen als auch Produktnamen
werden dabei als eigenständige Angebote übernommen). Waren zuvor
„Verkaufsarten“ oder „Merkmale“ gepflegt, sind diese Fachbereiche seit
dieser Version **entfallen** – die bestehenden Daten gehen beim
Einlesen keinen Fehler, die Informationen werden aber nicht mehr
angezeigt. Ebenso wurde eine zwischenzeitlich eingeführte
Gruppen-Zuordnung bei Angeboten wieder entfernt (kein Fehler beim
Einlesen, die Zuordnung wird schlicht ignoriert).

### Bemerkung

Zusätzlich zur „Beschreibung“ (Kapitel 4) steht ein eigenständiges,
optionales Feld **„Bemerkung“** zur Verfügung – gedacht für interne
Notizen oder Hinweise, die sich inhaltlich von der Beschreibung
unterscheiden sollen (z. B. „Nur nach telefonischer Anmeldung“). Wird
im Bearbeitungsformular unter „Allgemeine Informationen“ erfasst und
erscheint, sofern gesetzt, in der Detailansicht in einem eigenen
Abschnitt.

### Kontakt und Bewertung

- **Mobilnummer/E-Mail:** Optionale Felder im Bearbeitungsformular,
  Abschnitt „Kontakt & Webseite“ (vor „Webseite“). In der Detailansicht
  erscheinen sie im Abschnitt „Kontakt“ als anklickbare Telefon-/
  E-Mail-Links (öffnen die Telefon-App bzw. das Standard-Mailprogramm).
  Beide Felder werden auch von „🔍 Angaben automatisch ermitteln“
  (siehe oben) mit ermittelt, sofern auf der Website bzw. auf
  OpenStreetMap hinterlegt.
- **Bewertung:** Eine optionale Sterne-Bewertung von 0 (keine Bewertung)
  bis 5. Im Bearbeitungsformular ganz unten über eine interaktive
  Sterne-Auswahl gesetzt – ein erneuter Klick auf das zuletzt gefüllte
  Symbol setzt sie wieder auf 0 zurück. In der Detailansicht nur zur
  Ansicht dargestellt. In der Listenansicht als zusätzliche,
  sortierbare Spalte, in der Kachelansicht klein neben dem
  Status-Badge. Steht zusätzlich als eigener Sensor „Bewertung“ zur
  Verfügung (siehe Kapitel 5) und lässt sich als Standard-Sortierfeld
  der Übersicht über den Options Flow vorgeben (siehe Kapitel 3).

## 9. Actions und Automationen

HofKarte stellt eine Home-Assistant-Action bereit:

### `hofkarte.hoflaeden_suchen`

Durchsucht und filtert die verwalteten Hofläden. **Alle** Parameter
sind optional und werden **UND-verknüpft** (je mehr gesetzt sind, desto
enger die Suche).

| Parameter | Typ | Bedeutung |
|---|---|---|
| `suchbegriff` | Text | Freitextsuche (Gross-/Kleinschreibung egal, Teilstring-Treffer) über Name, Beschreibung, Ort. |
| `angebot` | Text | Exakter Name eines Angebots. |
| `zahlungsart` | Text | Exakter Name einer Zahlungsart. |
| `nur_geoeffnet` | Ja/Nein | Nur aktuell geöffnete Hofläden. |

**Rückgabe** (per `response_variable` in Skripten/Automationen
nutzbar): `anzahl_treffer` (Zahl) sowie `hoflaeden` (Liste mit je `id`,
`name`, `geoeffnet`).

**Beispiel 1 – einfacher Aufruf in Entwicklerwerkzeuge → Aktionen:**

```yaml
action: hofkarte.hoflaeden_suchen
data:
  angebot: Gemüse
  nur_geoeffnet: true
```

**Beispiel 2 – vollständige Automation mit Benachrichtigung:**

```yaml
alias: "Hofladen Müller ist offen"
trigger:
  - trigger: state
    entity_id: binary_sensor.hofladen_mueller_geoeffnet
    to: "on"
action:
  - action: notify.mobile_app
    data:
      message: "Hofladen Müller hat gerade geöffnet."
```

**Beispiel 3 – Skript mit Rückgabedaten (`response_variable`):**

```yaml
alias: "Kartoffel-Hofläden Abendübersicht"
trigger:
  - trigger: time
    at: "17:30:00"
action:
  - action: hofkarte.hoflaeden_suchen
    data:
      angebot: Kartoffeln
      nur_geoeffnet: true
    response_variable: treffer
  - action: notify.mobile_app
    data:
      message: >-
        {% if treffer.anzahl_treffer > 0 %}
          {{ treffer.anzahl_treffer }} Hofladen/-läden mit Kartoffeln noch geöffnet:
          {{ treffer.hoflaeden | map(attribute='name') | join(', ') }}
        {% else %}
          Aktuell ist kein Hofladen mit Kartoffeln geöffnet.
        {% endif %}
```

**Nicht vorhanden:** eine eigene „Daten aktualisieren“-Action (dafür
die eingebaute Home-Assistant-Action `homeassistant.update_entity`
verwenden), separate Actions je Filterkriterium, jede Art von
REST-API.

## 10. Dashboard-Beispiele

Beide Beispiele verwenden ausschliesslich in Home Assistant eingebaute
Karten (keine zusätzlichen Frontend-Ressourcen/Custom Cards nötig).
Entity-IDs anpassen (siehe Kapitel 5, wie die tatsächlichen IDs zu
finden sind).

**Beispiel 1 – Entities-Karte mit allen Werten eines Hofladens:**

```yaml
type: entities
title: Hofladen Müller
entities:
  - entity: binary_sensor.hofladen_mueller_geoeffnet
    name: Geöffnet
  - entity: sensor.hofladen_mueller_naechste_oeffnung
    name: Nächste Öffnung
  - entity: sensor.hofladen_mueller_naechste_schliessung
    name: Nächste Schliessung
  - entity: sensor.hofladen_mueller_entfernung
    name: Entfernung
```

**Beispiel 2 – Picture-Entity-Karte mit dem Hauptbild:**

```yaml
type: picture-entity
entity: image.hofladen_mueller_hauptbild
name: Hofladen Müller
show_state: false
show_name: true
tap_action:
  action: more-info
```

**Kombiniert als Dashboard-Ansicht (mehrere Karten untereinander):**

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: image.hofladen_mueller_hauptbild
    name: Hofladen Müller
  - type: entities
    entities:
      - binary_sensor.hofladen_mueller_geoeffnet
      - sensor.hofladen_mueller_naechste_oeffnung
      - sensor.hofladen_mueller_entfernung
```

## 11. Fehlerbehebung

**Die Integration erscheint nicht unter „Integration hinzufügen“:**
Home Assistant vollständig neu starten (nicht nur YAML neu laden); bei
manueller Installation den Pfad `custom_components/hofkarte/` prüfen.

**„HofKarte ist bereits eingerichtet“:** Erwartetes Verhalten, siehe
Kapitel 2 (Single-Instance). Die bestehende Instanz unter
**Einstellungen → Geräte & Dienste** verwenden.

**Das Verwaltungs-Panel „HofKarte“ erscheint nicht im Seitenmenü:** Nur
sichtbar für Administrator:innen-Konten.

**Nach einem Update zeigt das Panel weiterhin den alten Stand** (z. B.
fehlende Kacheln-/Listen-/Kartenansicht): Behobener Bug (ab
`2026.9.1-dev.3`) – die Panel-Adresse enthält seit dieser Version einen
sich pro Version ändernden Query-Parameter, der einen erneuten Abruf
beim Browser erzwingt, statt eine bereits zwischengespeicherte, ältere
Fassung unbegrenzt weiterzuverwenden. Ab dieser Version löst sich das
Problem bei künftigen Updates automatisch; beim Wechsel auf diese
Version selbst kann noch ein einmaliger harter Neuladen der Seite
(<kbd>Strg</kbd>/<kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>) nötig
sein.

**Entity „Geöffnet“ zeigt dauerhaft „Unbekannt“:** Für den Hofladen sind
keine Öffnungszeiten hinterlegt – über die Verwaltungsoberfläche
ergänzen (Kapitel 4/6).

**Sensor „Entfernung“ zeigt „Unbekannt“:** Entweder fehlen dem Hofladen
Koordinaten, oder die Home-Assistant-Position ist nicht konfiguriert
(**Einstellungen → System → Allgemein**), siehe Kapitel 7.

**Hauptbild wird nicht angezeigt:** Bei einem hochgeladenen Bild die
Fehlermeldung im Upload-Bereich prüfen (z. B. falsches Format oder zu
gross). Bei einer manuell eingetragenen externen Bild-Adresse: Diese
ist entweder leer, kein gültiger `http(s)`-Link, oder zeigt aus
Sicherheitsgründen abgelehnt auf eine private/interne IP-Adresse –
Adresse in der Verwaltungsoberfläche prüfen.

**Logging aktivieren:** Für detailliertere Fehlersuche unter
**Einstellungen → System → Logs** das Logging für
`custom_components.hofkarte` auf „Debug“ stellen (oder in
`configuration.yaml`):

```yaml
logger:
  default: warning
  logs:
    custom_components.hofkarte: debug
```

**Diagnostics exportieren:** Unter **Einstellungen → Geräte & Dienste →
HofKarte → Diagnose herunterladen** steht eine technische Übersicht zur
Fehlersuche zur Verfügung (Status des letzten Datenabrufs, Zeitpunkt der
letzten erfolgreichen Aktualisierung, Update-Intervall, Typ der
Datenquelle, Anzahl Hofläden). Diese Datei enthält **bewusst keine**
Hofladen-Inhalte oder Standortdaten und kann daher bei einer
Fehlermeldung gefahrlos angehängt werden.

## 12. Updates

**Update über HACS:** HACS zeigt verfügbare Updates automatisch an
(Badge im Seitenmenü). Update in HACS auswählen, herunterladen, Home
Assistant **vollständig neu starten**, damit die neue Version geladen
wird.

**Breaking Changes:** Nutzerrelevante Änderungen werden in
[`CHANGELOG.md`](../CHANGELOG.md) dokumentiert. Vor einem Update bei
grösserem Versionssprung (geänderte `MAJOR`-Version nach [Semantic
Versioning](https://semver.org/lang/de/)) den Changelog-Eintrag prüfen.

**Reload vs. Neustart:** Ein reines **Reload** der Integration
(Drei-Punkte-Menü bei HofKarte → **Neu laden**) reicht für die meisten
Änderungen aus und ist schneller als ein voller Neustart. Nach einer
HACS-Aktualisierung des Codes ist jedoch ein **vollständiger
Home-Assistant-Neustart** nötig, damit der neue Python-Code tatsächlich
geladen wird – ein reines Reload lädt keinen neuen Code nach.

Hofladen-Daten (Storage) überstehen sowohl Reload als auch Neustart
unverändert (siehe Kapitel 14).

## 13. Deinstallation

1. Unter **Einstellungen → Geräte & Dienste** die HofKarte-Integration
   entfernen (Drei-Punkte-Menü → **Löschen**). Dabei werden alle
   Devices und Entities automatisch entfernt.
2. Die gespeicherten Hofladen-Daten liegen als Datei
   `.storage/hofkarte_hoflaeden` im
   Home-Assistant-Konfigurationsverzeichnis und werden **nicht**
   automatisch mitgelöscht – bei Bedarf manuell entfernen (z. B. über
   den Dateizugriff des Home-Assistant-Hosts).
3. In HACS die Integration deinstallieren (Drei-Punkte-Menü bei
   HofKarte in HACS → **Entfernen**). Bei manueller Installation
   stattdessen den Ordner `custom_components/hofkarte/` löschen.
4. Home Assistant neu starten.

## 14. Datenschutz

- **Keine Cloud, kein externer Dienst:** HofKarte kommuniziert nicht mit
  externen Servern – mit sieben Ausnahmen (drei davon betreffen „Hofladen finden“, siehe unten): Wird für einen Hofladen ein
  Hauptbild über eine externe URL hinterlegt, ruft Home Assistant diese
  URL beim Anzeigen des Bildes ab (siehe Kapitel 5, „Hauptbild“); und
  öffnet man in der Übersicht die Kartenansicht „🗺️ Karte“, lädt der
  Browser die Kartenbibliothek Leaflet sowie die eigentlichen
  Kartenkacheln von OpenStreetMap (siehe Kapitel 4, „Übersicht“) –
  beides ausschliesslich beim tatsächlichen Öffnen dieser Ansicht,
  nicht beim Start des Panels. Dabei werden ausschliesslich die für die
  Kartendarstellung nötigen Ausschnitts-/Kachelkoordinaten übertragen,
  keine Hofladen- oder Standortdaten im Klartext an OpenStreetMap.
  Klickt man im Bearbeitungsformular auf „🔍 Angaben automatisch
  ermitteln“ (Kapitel 4, „Angaben automatisch ermitteln“), ruft
  HofKarte **nur auf diesen ausdrücklichen Klick hin** – je nachdem,
  was im Formular eingetragen ist – die dort eingetragene
  Website-Adresse ab und wertet sie rein lokal aus, und/oder
  übermittelt die im Formular eingetragenen Koordinaten dieses
  Hofladens an eine von mehreren bekannten, freien, kostenlosen
  OpenStreetMap-Overpass-Instanzen (probiert der Reihe nach mehrere
  Instanzen, falls die erste überlastet oder nicht erreichbar ist) –
  ohne einen externen Cloud- oder KI-Dienst einzubinden. Anders als
  bei den Kartenkacheln werden bei der Koordinatensuche tatsächlich
  hofladenspezifische Standortdaten an einen externen Dienst
  übertragen (weiterhin kein kommerzieller Cloud- oder KI-Dienst).
  Beim Dialog „🔎 Hofladen finden“ (Kapitel 4, nur auf ausdrücklichen
  Klick, nur Administratoren) werden die gewählten Suchkoordinaten an die
  freien OpenStreetMap-Overpass-Instanzen gesendet, und die Website des
  gewählten Hofladens wird – unter Beachtung ihrer `robots.txt` –
  gelesen. Dein **Browser** fragt dafür nach Freigabe den Gerätestandort
  ab; er wird nicht gespeichert. Nur wenn du eine KI-Entität gewählt und
  die Option im Dialog angekreuzt hast, wird der Website-Text zusätzlich an
  diese Entität gesendet (je nach Anbieter ausserhalb deines Netzwerks).
  Ausserhalb dieser sieben Fälle findet keine Telemetrie und keine
  Datenübertragung an Dritte statt.
- **Standort (Home-Assistant-Server):** Der Entfernungs-Sensor
  (Kapitel 7) liest ausschliesslich die statische, in Home Assistant
  konfigurierte Position – kein `device_tracker`, keine Personen- oder
  Geräteverfolgung. Diese Position wird von HofKarte nicht separat
  gespeichert und nicht an externe Dienste übertragen.
- **Routing-Auswahl (Google Maps/Apple Maps):** Die Buttons „🗺️“/„🧭“
  (Kapitel 4/7) öffnen erst nach einem bewussten Klick einen neuen
  Browser-Tab bei Google bzw. Apple; dabei werden Adresse oder
  Koordinaten des jeweiligen Hofladens als Link-Parameter an den
  externen Kartendienst übertragen (kein eigener Geocoding-Aufruf
  durch HofKarte selbst, keine Übertragung im Hintergrund ohne Klick).
- **Speicherort aller Daten:** Alle Hofladen-Daten (Name, Adresse,
  Koordinaten, Öffnungszeiten, Sortiment, Bild-Adressen) liegen
  ausschliesslich lokal im Home-Assistant-Storage
  (`.storage/hofkarte_hoflaeden`) – keine Cloud-Synchronisation, keine
  externe Datenbank. Hochgeladene Bilddateien selbst liegen im
  Home-Assistant-Konfigurationsverzeichnis unter `image/` (verwaltet
  durch Home Assistants eigene `image_upload`-Komponente, nicht durch
  HofKarte) und werden beim Entfernen eines Bildes gelöscht. Beim
  Deinstallieren von HofKarte (Kapitel 13) werden diese Dateien –
  analog zu den übrigen Hofladen-Daten – nicht automatisch entfernt.
- **Diagnostics:** Die über Home Assistant herunterladbare Diagnose
  (Kapitel 11) enthält bewusst keine Hofladen-Inhalte und keine
  Standortdaten.
- **Zugriffsschutz:** Die grafische Verwaltungsoberfläche, der Bilder-
  Upload und alle Schreibzugriffe erfordern
  Home-Assistant-Administratorrechte.

## 15. Support

Bei Problemen oder Fragen:

1. Zunächst **Kapitel 11 (Fehlerbehebung)** prüfen sowie
   [`README.md`](../README.md), Abschnitt „Bekannte Einschränkungen“.
2. Sicherheitsrelevante Probleme **nicht** öffentlich melden – siehe
   [`SECURITY.md`](../SECURITY.md) für den privaten Meldeweg.
3. Für alle übrigen Fehlermeldungen: Issue im Repository
   `https://github.com/rest-be/HofKarte` erstellen.

**Für einen hilfreichen Fehlerbericht bitte angeben:**

- HofKarte-Version (**Einstellungen → Geräte & Dienste → HofKarte** oder
  `manifest.json` → `version`)
- Home-Assistant-Version
- Installationsart (HACS oder manuell)
- Schritte zur Reproduktion
- Erwartetes vs. tatsächliches Verhalten
- Nach Möglichkeit: die in Kapitel 11 beschriebene Diagnose-Datei
  (enthält keine persönlichen Daten, siehe Kapitel 14) sowie relevante
  Log-Auszüge **ohne** eigene Zugangsdaten oder persönliche Angaben.

Es handelt sich um ein privates Freizeitprojekt – siehe
[`SECURITY.md`](../SECURITY.md) für Hinweise zur erwarteten
Reaktionszeit.
