# Detail & Erfassung – Phase 0: Entscheide und Testinventar

Stand: 2026-10-11 · Branch `feature/detail-erfassung` (ab `feature/gui-uebersicht`, 2026.10.1-dev.15)
Plan: `docs/detail-erfassung-umsetzungsplan.md`

## 1. Entscheide (Abschnitt 3 des Plans)

| # | Entscheid | Stand |
|---|---|---|
| 1 | Reihenfolge: Gruppenmodell → Detail → Editor → Erfassung | übernommen |
| 2 | Gemeinsames Gruppenmodell `HOF_GRUPPEN` + `gruppeHtml()` + `vollstaendigkeit()` | übernommen |
| 3 | Vollständigkeit nur im Panel, nur Anzeige | übernommen |
| 4 | «Offen bis HH:MM»: optionales Server-Feld, Fallback «Geöffnet/Geschlossen» | Phase 2 |
| 5 | Finden-Dialog: Logik und `data-finden-*` bleiben | übernommen |
| 6 | Popups `webseiteInfoPopup`/`osmOrteAuswahlPopup` bleiben bis Phase 6/7 | übernommen |
| 7 | Foto: `input type=file accept=image/* capture=environment`, Fallback Dateiwahl | Phase 5 |
| 8 | Neuer Branch `feature/detail-erfassung` | erledigt |

## 2. Code-Bereiche (hofkarte-panel.js, 3685 Zeilen)

| Methode | Zeile | Phase |
|---|---|---|
| `kopfzeileHtml()` (Knöpfe `data-finden-open`, `data-new`) | ~1669 | 4 |
| `detail()` + `detailQuellenSection/KontaktSection/OpeningHours/SpecialHours/PillSection/AngeboteSection` | 2270–2434 | 2 |
| `editor()` | 2435–2563 | 3 |
| `webseiteInfoPopup()`, `osmOrteAuswahlPopup()` | 2564, 2615 | bleiben |
| `bindDelegiert()`, `bind()` | 2827, 2936 | 2–4 |
| `oeffneFinden()`, `findenDialog()`, `bindFindenDelegiert()` | 3150, 3482, 3599 | 4–6 |
| `save()` liest `f.elements[name]`, `lines()` für Angebote/Zahlungsarten, Tage via `day_mode_*`, Sonderzeiten via `[data-special]` | ~1020–1120 | 3 |

## 3. Selektoren, die erhalten bleiben müssen

Editor/Formular: `form` (submit → `save()`), Feldnamen `latitude`, `longitude`, `osm_radius`, `angebote`, `zahlungsarten`, `day_mode_<tag>`, `beginn`, `ende`, `datum_von`, `datum_bis`, `geschlossen`; `data-add-interval`, `data-remove-interval`, `data-day-block`, `data-day-intervals`, `data-add-special`, `data-remove-special`, `data-special`, `data-bewertung-stern`, `data-bild-*`, `data-start-upload`, `data-upload-status`, `data-add-external-url`, `data-external-url`, `data-toggle-coord-info`, `data-auto-info-btn`, `data-auto-info-status`, `data-cancel`, `bild-upload-input`.
Detail: `data-back`, `data-edit-from-detail`, `data-view`, `data-edit`, `data-delete`.
Finden: alle `data-finden-*` (ca. 110 Testzugriffe in `test_static_panel_js_finden.py`), `data-webseite-info-*`, `data-osm-orte-*`.
Übersicht (unberührt): `data-auswahl*`, `data-kachel-menue*`, `data-sort*`, `data-karte-*`, `data-listen-filter`, `data-list-body`.

**Regel für Chips (Phase 3):** Das Textarea `angebote`/`zahlungsarten` bleibt als verstecktes Feld bestehen; Chips/Schalter schreiben dorthin, `save()` bleibt unverändert.

## 4. Betroffene Testdateien

| Datei | Zeilen | Bezug | Erwartete Anpassung |
|---|---|---|---|
| `test_static_panel_js_finden.py` | 527 | hoch (105 Treffer) | Phase 4–6: Einstieg/Schritte; Selektoren bleiben |
| `test_static_panel_js_auto_ermittlung.py` | 235 | 17 | Phase 3: Assistentenleiste (`data-auto-info-btn` bleibt) |
| `test_static_panel_js_osm_info.py` | 237 | 17 | Phase 3/7 |
| `test_static_panel_js_webseite_info.py` | 224 | 12 | Phase 3/7 |
| `test_static_panel_js_uebersicht.py` | 526 | 9 | Phase 4: Kopfzeile (zwei Knöpfe → einer) |
| `test_static_panel_js_block_c.py` | 362 | 4 | Phase 2: Detail-Texte |
| `test_static_panel_js_routing.py` | 196 | 2 | Phase 2: Route im Detail (`routingAuswahl(` genau 1× im Detail) |
| `test_static_panel_js_formular_listener.py` | 98 | Intervalle/Sonderzeiten | Phase 3: Listener-Anzahl nach Umbau prüfen |
| `test_static_panel_js_f12.py`, `_upload_origin.py`, `_export_import.py`, `test_static_panel_js.py` | – | gering | Phase 8 Gegenprüfung |
| `test_quellen.py` | – | `PANEL_BUILD` = Manifest; Quellen-Anzeige | jede Phase |

Textabhängigkeiten (Überschriften «Allgemeine Informationen», «Automatisch ausfüllen», «Angebote und Zahlungsarten», «Standort/Koordinaten») werden in Phase 2/3 mit den neuen Gruppentiteln angepasst.

## 5. Baseline
Siehe Abschnitt unten (nach Testlauf ergänzt).

Testlauf 2026-10-11 auf `feature/detail-erfassung` (= dev.15): **1138 bestanden, 4 bekannte Altfehler** (`test_options_flow_rejects_radius_out_of_range`, `test_ws_import_commit_ohne_eingerichtete_integration_sendet_fehler`, `test_ws_import_commit_ohne_eintraege_sendet_fehler`, `test_ws_osm_info_liefert_ermittelte_orte`). Dauer ca. 2 Minuten.
