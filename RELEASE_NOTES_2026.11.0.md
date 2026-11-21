# HofKarte 2026.11.0

Kleines Update: ein **Menü-Knopf** im Panel für das Smartphone und die
automatische Zuordnung von **Bereich und Label «HofKarte»**.

## Neu

- **Menü-Knopf auf dem iPhone:** Auf schmalen Bildschirmen (Smartphone,
  HA-Companion-App) erscheint oben links ein Menü-Knopf, der die
  Home-Assistant-Seitenleiste öffnet. Bisher kam man aus dem HofKarte-Panel
  nur über eine Kantengeste zurück ins Menü.
- **Bereich und Label «HofKarte»:** Jeder Hofladen wird automatisch dem
  Bereich «HofKarte» zugeordnet und erhält das Label «HofKarte» (am Device und
  an allen Entities). In den Einstellungen lässt sich das abschalten und
  umbenennen. Ein bereits gesetzter anderer Bereich bleibt erhalten, von Hand
  entfernte Zuordnungen kommen nicht ungefragt zurück, bestehende Hofläden
  werden beim ersten Start einmalig nachgezogen.

## Dokumentation

- README: Versionstabelle PWA ↔ Integration um PWA `2.1.0` ergänzt,
  Funktionsumfang der PWA nachgeführt (Stand 2.1.0).

## Hinweise zum Update

- Home Assistant nach dem Update **neu starten** (neuer Python-Code) und das
  Panel im Browser bzw. in der Companion-App neu laden (neue Panel-Version).
- Beim ersten Start entstehen Bereich und Label «HofKarte» und werden den
  vorhandenen Hofläden zugeordnet. Wer das nicht möchte, schaltet die
  Zuordnung unter **Konfigurieren** ab; dann wird nichts angelegt.
- Nutzer der PWA: keine Änderung nötig.

## Bekannte Einschränkungen

- Der Menü-Knopf wurde automatisiert und im iPhone-Format im Browser geprüft,
  aber noch nicht auf einem echten iPhone bzw. in der Companion-App.
- Die Zuordnung von Bereich und Label wurde mit der Home-Assistant-Testumgebung
  geprüft, noch nicht in einer produktiven Instanz.
- Wie bei `2026.10.2`: Die KI-Auswertung wurde noch nicht mit einem lokalen
  Modell im Feld gemessen.
