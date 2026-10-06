# HofKarte 2026.10.0

Dieses Release härtet die Integration (Sicherheit, Robustheit),
macht das Panel deutlich schneller, schreibt Daten effizienter und
bringt den Foto-Upload für die Mobile PWA ohne CORS-Konfiguration.
Ein Update wird allen Nutzer:innen empfohlen.

## Neu

- **Foto-Upload für die Mobile PWA ohne CORS:** Der neue
  WebSocket-Befehl `hofkarte/management/upload_image` nimmt Fotos
  (JPEG, PNG, GIF, bis 3 MiB) über die bestehende Verbindung entgegen.
  `cors_allowed_origins` ist dafür nicht mehr nötig. Der Befehl ist
  nur für Administratoren verfügbar.
- **Action `hofkarte.hoflaeden_in_naehe`** (inkl. Filter
  `min_bewertung`) und ein **Automation-Blueprint** „Benachrichtigung
  bei Hofladen in der Nähe“ für die Home Assistant Companion App.
- **Optimistische Versionierung je Hofladen** (Feld `version`):
  Konflikte beim Offline-Sync mehrerer Geräte werden erkannt statt
  stillschweigend überschrieben.
- **README-Abschnitt „Mobile PWA“.**

## Sicherheit

- Das Flag „hochgeladen“ eines Bildes wird serverseitig abgeleitet und
  lässt sich nicht mehr von aussen setzen.
- Gehärtete Prüfung von Website-Adressen (SSRF) inkl. Schutz gegen
  DNS-Rebinding beim Website-Abruf.
- Längen- und Mengenlimits für Eingaben; Härtung des Panels gegen
  eingeschleuste Inhalte.
- **Leaflet wird lokal mitgeliefert** – das Panel lädt keine Skripte
  mehr von einem CDN.

## Verbessert

- **Schnelleres Panel:** deutlich weniger DOM-Knoten und
  Event-Listener, Marker-Clustering ab 200 Hofläden, Vorschaubilder
  (256 × 256) für eigene Uploads.
- **Effizientes Schreiben:** Importe schreiben den Speicher einmalig
  statt je Eintrag; Änderungen aktualisieren die Daten inkrementell.
- **Zeitgenaue Statuswechsel:** „Geöffnet“ und die Zeitstempel-Sensoren
  wechseln exakt zur Öffnungs-/Schliesszeit statt per Abfrageintervall.
- Statische Panel-Dateien mit Cache-Headern; die OpenStreetMap-Suche
  hat ein Zeitbudget und einen kurzen Zwischenspeicher.

## Behoben

- Kein Endlos-Rendern und keine Dauer-Neuladung, wenn die Karte
  nicht geladen werden kann (jetzt Fehlermeldung mit zunehmend
  längeren Wiederholungsabständen).
- Options Flow mit explizitem Konstruktor; Robustheit gegen tief
  verschachteltes JSON-LD und quadratische Regex-Laufzeiten.

## Hinweise zum Update

- Home Assistant nach dem Update **neu starten** (neuer Python-Code).
- Für den Foto-Upload der PWA: PWA auf Version **1.11.0** bringen.
  Bilder über ca. 2.5 MB laufen weiter über den REST-Weg und brauchen
  dort `cors_allowed_origins`.
- Damit hochgeladene Bilder als „hochgeladen“ erkannt werden, muss in
  Home Assistant die interne bzw. externe URL gesetzt sein (z. B. bei
  Zugriff über eine DuckDNS-Domain `external_url`).
