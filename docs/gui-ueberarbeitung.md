# GUI-Überarbeitung Übersicht (Kacheln · Liste · Karte)

Arbeitsdokument zu Branch `feature/gui-uebersicht` (Basis `feature/discovery-phase-1`, 2026.10.1-dev.9).
Plan: `HofKarte_GUI_Ueberarbeitung_Vorgehensplan.md`; Entwurf: Artifact «HofKarte GUI-Entwurf».

## Entscheide (Phase 0)

1. Löschen: Bestätigungsdialog bleibt; Eintrag im ⋮-Menü ganz unten, rot.
2. Sortierung: ein gemeinsamer Zustand für alle Ansichten; Startwert aus `listen_sort_*`.
3. Entfernung: nur mit Gerätestandort (Browser-Erlaubnis); nicht gespeichert. Bestehendes `data-geraete-entfernung` weiterverwenden.
4. Details: bleibt vorerst der bestehende Detaildialog; neue Details-Seite später.
5. «Nur geöffnet» über serverseitiges `geoeffnet`; bestehendes `data-karte-nur-geoeffnet` (Karte) wird zum gemeinsamen Filter.
6. «Offen bis …»: optionales Server-Feld in `list`; ohne Feld bleibt «Geöffnet/Geschlossen».

## Baseline

`pytest custom_components/hofkarte/tests`: 1121 passed, 4 failed (bekannte Altfehler:
`test_options_flow_rejects_radius_out_of_range`, `test_ws_import_commit_ohne_eingerichtete_integration_sendet_fehler`,
`test_ws_import_commit_ohne_eintraege_sendet_fehler`, `test_ws_osm_info_liefert_ermittelte_orte`).
Die jsdom-Tests laufen nur mit `NODE_PATH` auf ein `node_modules` mit `jsdom`, sonst werden 31 übersprungen.

## Test-Inventar: Selektoren der Übersicht (beizubehalten oder gezielt anpassen)

Übersicht: `data-ansicht` (5), `data-auswahl` (5), `data-auswahl-anzahl`, `data-export`, `data-import-*`,
`data-list-body` (4), `data-listen-filter` (2), `data-view` (2), `data-edit`, `data-delete`, `data-new`,
`data-karte-nur-geoeffnet`, `data-karte-fehler*`, `data-karte-erneut`, `data-geraete-entfernung`, `data-erneut-laden`.
Hofladen finden (unverändert lassen): `data-finden-*` (≈ 110 Verwendungen).

Regel: Selektoren behalten; wo ein Test absichtlich ein neues Verhalten erzwingt (z. B. Checkboxen nur im Auswahlmodus),
wird der Test in derselben Phase angepasst und im CHANGELOG vermerkt.

## Phasen

| Phase | Inhalt | Version |
|---|---|---|
| 1 | Fundament: Kopfzeile, Steuerleiste, Menü, Kontextleiste, gemeinsamer Filter-/Sortierzustand | dev.10 (erledigt) |
| 2 | Kacheln | dev.11 (erledigt) |
| 3 | Liste | dev.12 (erledigt) |
| 4 | Karte | dev.13 (erledigt) |
| 5 | Feinschliff, Zugänglichkeit, Doku | dev.14 (erledigt) |

## Detail & Erfassung (Folgeprojekt)

Umsetzung der überarbeiteten Detailmasken und des Erfassungsprozesses auf
Branch `feature/detail-erfassung` (Plan: `detail-erfassung-umsetzungsplan.md`,
Inventar: `detail-erfassung-inventar.md`).

| Phase | Inhalt | Version |
|---|---|---|
| 1 | Gruppenmodell (7 Gruppen), Akkordeon, Vollständigkeit | dev.16 (erledigt) |
| 2 | Detail neu: «Auf einen Blick», Schnellaktionen, Gruppen | dev.17 (erledigt) |
| 3 | Bearbeiten neu: gleiche Gruppen, Chips, Fussleiste | dev.18 (erledigt) |
| 4 | Einstieg «Hofladen erfassen» (drei Wege) | dev.19 (erledigt) |
| 5 | Szenario 1: Vor Ort / Schnellerfassung | dev.20 (erledigt) |
| 6 | Szenario 2: Von Webseite mit Prüfansicht | dev.21 (erledigt) |
| 7 | Szenario 3: Angaben ergänzen / Abgleich | dev.22 (erledigt) |
| 8 | Zugänglichkeit, Doku, Aufräumen | dev.23 (erledigt) |
| 9 | Release (zusammen mit Discovery Phase 8) | zurückgestellt |

Selektoren der neuen Abläufe: `data-erfassen-*` (Einstieg), `data-vorort-*`
(Schnellerfassung), `data-web-*` (Webseite), `data-erg-*` (Abgleich),
`data-gruppe*` (Akkordeon). Der frühere Suchdialog (`data-finden-*`) bleibt als
«Erweiterte Suche» bestehen.

Zugänglichkeit: Fokus auf die Überschrift bei Schrittwechseln (auch nach
asynchronem Neuzeichnen), `aria-current="step"` in der Schrittanzeige,
`role="status"` für Fortschritt, Statussymbole mit Text für Screenreader
(`.sr-nur`), Beschriftungen an Auswahlfeldern, `prefers-reduced-motion`.
Tests: `test_static_panel_js_a11y.py`.
