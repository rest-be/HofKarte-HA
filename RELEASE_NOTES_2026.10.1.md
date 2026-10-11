# HofKarte 2026.10.1 (Entwurf)

> **Entwurf.** Noch nicht veröffentlicht: Version, Datum und der Abschnitt zur
> KI-Messung werden beim Release-Candidate festgelegt (siehe unten
> «Offen bis zum Release»).

Dieses Release bringt das **Erfassen neuer Hofläden aus dem Netz**
(Hofladen-Discovery), eine **überarbeitete Verwaltungsoberfläche** und ein
neues App-Icon. Ein Update wird empfohlen.

## Neu

- **Hofladen erfassen** mit drei Wegen: *Ich stehe vor dem Hofladen*
  (Standort, Treffer aus OpenStreetMap in der Nähe, Schnellerfassung mit Foto),
  *Ich habe eine Webseite* (Schritte Webseite → Auslesen → Prüfen mit Vorschau)
  und *Von Hand*. Vor dem Speichern wird geprüft, ob es den Hofladen schon gibt.
- **Angaben ergänzen / aktualisieren:** Ein bestehender Hofladen wird mit
  Webseite und OpenStreetMap verglichen (Aktuell · Gefunden · Status). Lücken
  sind vorgewählt, Abweichungen nie; Angebote und Zahlungsarten werden ergänzt,
  nie ersetzt. Übernommen wird ins Formular, gespeichert wird erst dort.
- **Optionale KI-Auswertung** (Home Assistant «AI Task», z. B. lokal mit
  Ollama): nie vorangekreuzt, mit Datenschutzhinweis. Nur wörtlich im
  Seitentext belegte Angaben gelten als belegt; Vermutungen stehen getrennt und
  sind nie vorausgewählt. Die KI läuft nachträglich, das Vorliegende lässt sich
  vorab prüfen.
- **Herkunft der Angaben** (Webseite, OpenStreetMap, KI-Vermutung) wird je Feld
  gespeichert und im Detail unter «Quellen» angezeigt.
- **Neue Übersicht:** gemeinsame Steuerleiste (Suche, «Nur geöffnet», Sortierung)
  für Kacheln, Liste und Karte; ⋮-Menüs, Auswahlmodus, Kartenliste.
- **Neue Detailansicht und neues Formular** mit sieben gleichen Gruppen
  (Grunddaten, Adresse, Kontakt, Öffnungszeiten, Angebote, Bilder, Herkunft),
  Vollständigkeitsanzeige, «Auf einen Blick» mit Schnellaktionen, Chips für
  Angebote und feste Fussleiste mit «Ungespeichert».
- **Neues App-Icon** (Karotte auf Feldern).

## Verbessert

- Zugänglichkeit: Fokusführung bei Schrittwechseln, Screenreader-Texte für
  Statusmeldungen, Tastaturbedienung der Menüs, «Bewegung reduzieren».
- Server liefert Öffnungsstatus, Hauptbild und nächsten Statuswechsel je
  Hofladen (`geoeffnet`, `hauptbild_url`, `status_wechsel`).

## Datenschutz

- Standort des Geräts nur auf ausdrücklichen Klick und nur über HTTPS.
- Webseiten werden nur gelesen, wenn `robots.txt` es erlaubt (höchstens 4 Seiten
  desselben Hosts, 1 s Pause). OpenStreetMap-Daten: © OpenStreetMap-Mitwirkende
  (ODbL).
- Ohne Auswahl einer KI-Entität ist keine KI beteiligt. Bei Cloud-Anbietern
  verlässt der Seitentext das Netzwerk.

## Hinweise zum Update

- Home Assistant nach dem Update **neu starten** (neuer Python-Code) und das
  Panel im Browser hart neu laden (neue Panel-Version).
- Das Icon erscheint in Home Assistant ab Version mit lokalen Brand-Bildern;
  ältere Versionen zeigen weiterhin das Standard-Symbol.

## Offen bis zum Release

- Test der KI-Auswertung mit Ollama (Discovery Phase 8) und Eintrag der
  Ergebnisse in README/Handbuch.
- Test auf dem iPhone (Kamera, Standortfreigabe, Abläufe «Webseite» und
  «Angaben ergänzen») und in der Mac-App.
- Entscheid: GUI und Discovery gemeinsam als 2026.10.1 oder GUI als 2026.10.2.
- Release-Candidate, Version in `manifest.json`, Tag und Merge.
