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
