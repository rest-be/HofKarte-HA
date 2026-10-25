# HofKarte 2026.10.2

Kleines Funktions-Update: Selbstbedienungs-Automaten, die rund um die Uhr
zugänglich sind, lassen sich jetzt als **24h-Automat** kennzeichnen. Dazu
passend gibt es die neue **mobile App HofKarte-PWA 2.0.0**, die diese Version
für den Schalter «24h-Automat» benötigt.

## Neu

- **24h-Automat:** Checkbox bei den Öffnungszeiten im Verwaltungs-Panel.
  Ein 24h-Automat gilt immer als geöffnet, hat keine «nächste Schliessung»
  und wird nur durch eine Sonder-Schliessung (z. B. Betriebsferien)
  unterbrochen. Detailansicht und Kurzinfo zeigen «24h-Automat – rund um die
  Uhr zugänglich».
- Bestehende Hofläden bleiben unverändert («kein Automat»). Alte
  Exportdateien lassen sich weiter importieren.

## Dokumentation

- Handbuch, README und Architektur-Dokumentation sind nachgeführt, unter
  anderem mit dem Abschnitt «Mobile PWA» (Voraussetzungen und welche
  PWA-Version zu welcher Integrationsversion passt).

## Hinweise zum Update

- Home Assistant nach dem Update **neu starten** (neuer Python-Code) und das
  Panel im Browser hart neu laden (neue Panel-Version).
- Bei manueller Installation den Ordner `custom_components/hofkarte/` ersetzen; über HACS wie gewohnt aktualisieren.
- Nutzer der PWA: erst die Integration aktualisieren, dann die PWA.

## Bekannte Einschränkungen

- Wie bei `2026.10.1`: Die optionale KI-Auswertung wurde noch nicht mit einem
  lokalen Modell (Ollama) im Feld gemessen; die Abläufe «Webseite» und
  «Angaben ergänzen» sind auf dem iPhone und in der Mac-App noch nicht
  ausdrücklich getestet.
- Die Bedienung des 24h-Automaten im Panel wurde automatisiert geprüft,
  aber noch nicht auf einem Mobilgerät im Feld.
