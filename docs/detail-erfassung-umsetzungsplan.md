# HofKarte – Detailmasken und Erfassungsprozess
## Umsetzungsplan (HA-Integration)

Stand: 2026-10-11 · Basis: `feature/gui-uebersicht` (2026.10.1-dev.15) · Entwurf: Artifact «HofKarte Detail & Erfassung» (7 Tafeln, klickbar)
Geltungsbereich: nur HA-Panel (`static/hofkarte-panel.js`). PWA später separat. Release 2026.10.1 bleibt zurückgestellt (zusammen mit Discovery Phase 8 / KI-Messung mit Ollama).

## 1. Ziel und Leitplanken

**Ziel:** Das Wesentliche auf einen Blick; grosse Blöcke einklappbar; Detail und Bearbeiten mit identischer Gruppierung und Reihenfolge; ein klarer Erfassungseinstieg für die drei Szenarien.

**Entschiedene Punkte**
- Detail: **Akkordeon (A)**, Block «Auf einen Blick» oben.
- Ein Einstieg **«Hofladen erfassen»** ersetzt die Kopfzeilen-Knöpfe «Hofladen finden» und «Hofladen».
- Szenario 1: **Schnellerfassung vor Ort** (Standort, Treffer in der Nähe, 2 Schritte, danach «Noch offen»).

**Leitplanken (unverändert aus der Übersicht)**
- HA-Theme-Variablen, Hell/Dunkel, keine festen Hex-Farben (ausser Status mit Fallback).
- Keine neuen Abhängigkeiten, keine Build-Pipeline; inline-SVG-Icons; Touch-Ziele ≥ 44 px; Status nie nur über Farbe.
- Nichts wird ohne ausdrückliche Wahl überschrieben. KI-Vermutungen nie vorausgewählt. Escaping/XSS-Regeln, nur http(s)-Links.
- Datenmodell bleibt unverändert; Vollständigkeit wird im Panel nur zur Anzeige berechnet.
- Pro Phase: Tests grün (ausser 4 bekannte Altfehler), `PANEL_BUILD` = Manifest, CHANGELOG, Version `2026.10.1-dev.N`.

## 2. Zielbild

**Gemeinsame Gruppen (gleiche Reihenfolge in Detail und Bearbeiten)**

| # | Gruppe | Inhalt | Standard (Detail / Bearbeiten) |
|---|---|---|---|
| 1 | Grunddaten | Name, Beschreibung, Bewertung, interne Bemerkung | offen / offen |
| 2 | Adresse & Standort | Adresse, PLZ/Ort/Land, Koordinaten, Mein Standort, Minikarte | offen / offen |
| 3 | Kontakt & Webseite | Telefon, Mobil, E-Mail, Webseite (+ «Webseite auslesen») | offen / zu |
| 4 | Öffnungszeiten | Wochentage, Sonderzeiten; Detail: «heute» hervorgehoben | offen / zu |
| 5 | Angebote & Zahlungsarten | Detail: Pills; Bearbeiten: Chips, Zahlungsarten als Schalter | offen / offen |
| 6 | Bilder | Hauptbild, Upload, externe URL | zu / zu |
| 7 | Herkunft der Angaben | Quellen-Tabelle, OSM-Hinweis (ODbL); im Editor nur lesend | zu / zu |

Jede Gruppe: Titel, Kurzzusammenfassung im eingeklappten Zustand, Vollständigkeitspunkt (vollständig / teilweise / leer), «Alle ein-/ausklappen». Zustand pro Sitzung, nicht gespeichert.

**Detail:** Kopf (Zurück, «Angaben ergänzen», «Bearbeiten», ⋮ mit Route/Löschen), Block «Auf einen Blick» (Bild, Status, Sterne, Adresse, Schnellaktionen Route/Anrufen/Webseite/E-Mail, Hinweis «Noch unvollständig: … Jetzt ergänzen»).
**Bearbeiten:** gleiche Gruppen, Assistentenleiste «Angaben automatisch ergänzen», feste Fussleiste (Ungespeichert · Abbrechen · Speichern), Wochentage-Editor mit «Auf Di–Fr kopieren», Sterne mit Zurücksetzen.
**Erfassen:** Einstieg mit drei Karten (Vor Ort · Webseite · Von Hand) und Hinweis auf «Angaben ergänzen» für Bestehendes; Duplikatprüfung vor dem Speichern.

## 3. Technische Entscheide (vor Phase 1 bestätigen, Empfehlung kursiv)

1. **Reihenfolge der Umsetzung:** Gruppenmodell zuerst, dann Detail, dann Editor, dann Erfassung. *Ja, damit Detail/Editor garantiert dieselbe Struktur teilen.*
2. **Gemeinsames Gruppenmodell:** eine Konstante `HOF_GRUPPEN` (id, Titel, Icon) plus Hilfsfunktionen `gruppeHtml(id, summary, punkt, inhalt, offen)` und `vollstaendigkeit(item)`; Detail und Editor rendern über dieselbe Liste. *Ja.*
3. **Vollständigkeit:** im Panel berechnet (Felder pro Gruppe gefüllt/teilweise/leer), nur Anzeige; kein Speichern, kein Backend. *Ja.*
4. **«Offen bis HH:MM»:** optionales Server-Feld in `_serialize_hofladen` (`status_text` oder `oeffnet_bis`); ohne Feld bleibt «Geöffnet/Geschlossen». *Kleine Backend-Ergänzung in Phase 2, mit Test.*
5. **Finden-Dialog:** Logik (`finden`, `data-finden-*`, ca. 110 Testzugriffe) bleibt, wird in neuen Schritten/Stil weiterverwendet statt neu geschrieben. *Ja, Selektoren behalten.*
6. **Popups `webseiteInfoPopup` / `osmOrteAuswahlPopup`:** bleiben bis Phase 6 unverändert; der Editor ruft sie über die Assistentenleiste auf. Danach Abgleich mit Szenario 3.
7. **Foto aufnehmen (mobil):** `<input type="file" accept="image/*" capture="environment">`; Verhalten je nach Companion-App/Browser prüfen, Fallback Dateiwahl. *Ja.*
8. **Branch:** Weiterarbeit auf `feature/gui-uebersicht` oder neuer Branch `feature/detail-erfassung` ab dort. *Neuer Branch, damit die abgenommene Übersicht getrennt bleibt.*
9. **Standortfreigabe:** Geolocation nur auf Klick, nur über sichere Verbindung; Fehlermeldungen verständlich (verweigert / nicht verfügbar).
10. **Dokumentation:** `docs/gui-ueberarbeitung.md` wird um Abschnitt «Detail & Erfassung» ergänzt; README/Handbuch in Phase 7.

## 4. Phasen

### Phase 0 – Vorbereitung (0,5 Tag)
- Branch anlegen, Baseline dokumentieren (1138 grün + 4 Altfehler).
- Inventar: alle `data-*`-Selektoren und Texte in Tests zu `detail()`, `editor()`, `findenDialog()`, Quellen-Abschnitt; Liste, was sich ändert; Ziel: Selektoren behalten.
- Entscheide aus Abschnitt 3 bestätigen.
- **Ergebnis:** Entscheide, Testinventar (`docs/…`).

### Phase 1 – Gruppenmodell und Akkordeon (1 Tag) → dev.16
- `HOF_GRUPPEN`, `gruppeHtml()`, `vollstaendigkeit()`, «Alle ein-/ausklappen».
- Akkordeon auf Basis `<details>`/Button mit `aria-expanded`, Tastatur (Enter/Leertaste), sichtbarer Fokus, Zustand je Sitzung.
- Zusammenfassungszeilen je Gruppe (z. B. «Mo–Fr 08:00–18:30 · Sa bis 16:00»).
- Tests: Auf-/Zuklappen, Zusammenfassung, Vollständigkeitspunkt, Escaping.
- **Ergebnis:** Bausteine vorhanden, noch nicht eingebunden.

### Phase 2 – Detail neu (1,5 Tage) → dev.17
- `detail()` auf 7 Gruppen umstellen; Block «Auf einen Blick» mit Bild, Status, Sternen, Adresse, Schnellaktionen (Route nutzt bestehende Routing-Auswahl, Anrufen `tel:`, E-Mail `mailto:`, Webseite nur http(s)).
- Hinweis «Noch unvollständig» mit Sprung zu «Angaben ergänzen».
- Öffnungszeiten als Tabelle mit «heute»-Markierung; Pills; Quellen-Tabelle wie bisher (`detailQuellenSection`, ODbL-Hinweis).
- Optional Server-Feld «Offen bis …» (Entscheid 4) mit Test in `test_management*`.
- Kopfzeile: Zurück, «Angaben ergänzen» (bis Phase 5 Verweis auf Editor mit Assistent), «Bearbeiten», ⋮ (Route, Löschen).
- Tests: bestehende Detail-Tests anpassen, neue für Gruppen/Schnellaktionen/Unvollständigkeit.

### Phase 3 – Bearbeiten neu (2 Tage) → dev.18
- `editor()` mit denselben Gruppen und derselben Reihenfolge; Standard offen: 1, 2, 5.
- Assistentenleiste ersetzt den grossen Block «Automatisch ausfüllen» (gleiche Funktionen, gleiche Handler `data-auto-info-btn`, OSM-Umkreis).
- Chips für Angebote (Hinzufügen/Entfernen), Schalter für Bargeld/TWINT/Karte; Datenformat der Felder bleibt kompatibel (Textareas werden beim Speichern aus den Chips befüllt).
- Wochentage-Editor mit «Auf Di–Fr kopieren», Sonderzeiten; Sterne mit Zurücksetzen.
- Feste Fussleiste mit Ungespeichert-Anzeige, Abbrechen mit Rückfrage bei Änderungen, Speichern; Fokus auf erstes fehlerhaftes Feld bei Validierung.
- Tests: Formular-Roundtrip (Werte → Speichern → identisches Payload wie vorher), Chips, Zeiten kopieren, Abbrechen-Rückfrage.

### Phase 4 – Einstieg «Hofladen erfassen» (1 Tag) → dev.19
- Kopfzeile: ein Knopf «Hofladen erfassen» statt zwei.
- Einstiegsseite mit drei Karten; URL-Feld aktiviert «Auslesen» nur bei gültiger http(s)-Adresse; «Von Hand» öffnet leeres Formular (Phase 3).
- Hinweisbox «Hofladen schon erfasst?».
- Duplikatprüfung (bestehende `findeBestehenden`) vor dem Speichern auch für den Handweg.
- Tests: Navigation, URL-Validierung, Kopfzeile, Hinweise.

### Phase 5 – Szenario 1: Vor Ort (2 Tage) → dev.20
- Schritt 1: Standort ermitteln (Genauigkeit), Umkreis-Chips 100/250/500 m, Trefferliste «In der Nähe» mit Entfernung, «Wahrscheinlich dieser», «Möglicherweise schon erfasst», «Keiner davon, neu erfassen». Wiederverwendung der Finden-Logik.
- Schritt 2: Schnellerfassung (Name Pflicht, Standort übernommen, Foto aufnehmen, Webseite optional, Speichern).
- Abschluss: «Gespeichert» mit Liste «Noch offen» (Öffnungszeiten, Angebote, Zahlungsarten, Foto) und «Jetzt ergänzen» / «Fertig».
- Mobil zuerst (390 px), Touch-Ziele, Fehlerfälle (Standort verweigert, keine Treffer).
- Tests: Ablauf mit Stubs für Geolocation/Netz, Duplikatwarnung, Pflichtfeld, «Noch offen».

### Phase 6 – Szenario 2: Von Webseite (1,5 Tage) → dev.21
- Schrittanzeige Webseite → Auslesen → Prüfen; KI-Auswertung optional mit Datenschutzhinweis (Text geht an lokales Ollama).
- Fortschritt (Webseite, OSM, KI) mit «Vorliegendes prüfen», KI-Ergebnisse dürfen nachträglich erscheinen.
- Prüfen: Feld für Feld mit Quelle und Abweichungswarnung, Vermutungen der KI getrennt und nie vorausgewählt, Vorschau-Karte rechts (mobil darunter), «In Formular übernehmen» → Editor (Phase 3).
- Tests: Auswahl, Abweichung, Vermutungen nicht vorausgewählt, Übernahme in Formular.

### Phase 7 – Szenario 3: Ergänzen/Aktualisieren (2 Tage) → dev.22
- Vollständigkeitsanzeige, «Verglichen mit» (Webseite, OSM, «Neu abgleichen»).
- Vergleichstabelle Angabe · Aktuell · Gefunden · Status (Lücke / Abweichend / Gleich), Filter «Nur Unterschiede / Alle», «Nur Lücken füllen», «Nichts wählen».
- Regeln: Lücken vorgewählt, Abweichungen nie; Listenfelder (Angebote) werden ergänzt, nie ersetzt; feste Fussleiste «Auswahl übernehmen (n)»; Erfolgsmeldung.
- Einstiege: Detail («Angaben ergänzen», Hinweis «Noch unvollständig»), «Noch offen»-Seite.
- Tests: Vorauswahl, nichts überschrieben ohne Wahl, Listen ergänzen, Abgleich-Fehler.

### Phase 8 – Feinschliff, Zugänglichkeit, Doku (1,5 Tage) → dev.23
- A11y-Durchgang: Tastatur, Fokusführung beim Wechsel der Schritte, Screenreader-Labels, Kontraste Hell/Dunkel, `prefers-reduced-motion`.
- Test auf iPhone, Mac-App, Browser; Cache-Hinweis (`PANEL_BUILD`).
- Doku: README, `docs/handbuch.md` (Kapitel Detail, Erfassen, Ergänzen), `docs/gui-ueberarbeitung.md`, CHANGELOG, CONTRIBUTING (Testanzahl).
- Alte, nicht mehr genutzte Teile des Finden-Dialogs und Editors entfernen (nur wenn ungenutzt und Tests angepasst).

### Phase 9 – Release (später)
- Zusammen mit Discovery Phase 8 (KI-Messung, von dir mit Ollama); RC, Release Notes, Tag/Merge durch dich. Version 2026.10.1 mit Discovery + GUI oder GUI als 2026.10.2 (Entscheid beim Release).

## 5. Aufwand und Reihenfolge

| Phase | Inhalt | Aufwand | Version |
|---|---|---|---|
| 0 | Vorbereitung, Entscheide | 0,5 T | – |
| 1 | Gruppenmodell, Akkordeon | 1 T | dev.16 |
| 2 | Detail neu | 1,5 T | dev.17 |
| 3 | Bearbeiten neu | 2 T | dev.18 |
| 4 | Einstieg «Hofladen erfassen» | 1 T | dev.19 |
| 5 | Szenario 1 Vor Ort | 2 T | dev.20 |
| 6 | Szenario 2 Webseite | 1,5 T | dev.21 |
| 7 | Szenario 3 Ergänzen | 2 T | dev.22 |
| 8 | Feinschliff, Doku | 1,5 T | dev.23 |

Zwischenstände sind lauffähig. Nach jeder Phase ZIP; Abnahme durch dich vor der nächsten. Phasen 2+3 bringen den grössten Nutzen (Detailmasken); 4–7 können einzeln vorgezogen oder gestrichen werden.

## 6. Risiken

| Risiko | Gegenmassnahme |
|---|---|
| Viele Tests hängen an Detail-/Editor-/Finden-DOM | Inventar in Phase 0, Selektoren behalten, Tests je Phase anpassen |
| Editor-Umbau ändert das Speicherformat unbemerkt | Roundtrip-Test: gleiches Payload wie vor dem Umbau |
| Chips/Schalter weichen von bestehendem Textformat ab | Beim Speichern in dasselbe Format zurückschreiben; Altbestände werden korrekt eingelesen |
| Standort/Kamera in HA-Companion-App eingeschränkt | Fallbacks (Koordinaten von Hand, Dateiwahl), früh auf Gerät testen |
| Überschreiben bestehender Daten | Regeln aus Abschnitt 1, expliziter Test pro Feldtyp |
| KI-Aussagen wirken belegt | Getrennte Darstellung, nie vorausgewählt, Quelle immer sichtbar |
| `hofkarte-panel.js` wächst weiter | Bausteine als getrennte Methoden; Aufteilen in Module bewusst nicht Teil dieses Vorhabens |
| Cache zeigt alte Version | `PANEL_BUILD` in Kopfzeile, Hinweis in Release Notes |

## 7. Abnahmekriterien
- Detail und Bearbeiten zeigen dieselben 7 Gruppen in derselben Reihenfolge, Gruppen einklappbar, Wesentliches oben auf einen Blick.
- Alle drei Szenarien über «Hofladen erfassen» bzw. «Angaben ergänzen» erreichbar; Duplikatprüfung vor dem Speichern.
- Keine bestehende Angabe wird ohne ausdrückliche Auswahl verändert; KI-Vermutungen nie vorausgewählt.
- Alle bisherigen Funktionen bleiben erreichbar (Routing, Löschen, Quellen, Bilder, Sonderzeiten, Export/Import).
- Bedienung per Tastatur und Touch, Hell/Dunkel lesbar, mobil nutzbar (Szenario 1 auf 390 px).
- Tests grün (ausser 4 bekannte Altfehler), Doku und CHANGELOG aktuell.

## Umsetzungsstand

Phasen 0–8 sind umgesetzt (dev.16 bis dev.23, Branch `feature/detail-erfassung`). Phase 9 (Release) bleibt zurückgestellt und erfolgt zusammen mit Discovery Phase 8 (KI-Messung mit Ollama). Bewusste Abweichung vom Plan: Der frühere Suchdialog wurde nicht entfernt, sondern bleibt als «Erweiterte Suche» erreichbar.
