# Phase 0 – Messung & Spike (Hofladen-Erkennung)

Ziel (siehe Konzept „Hofladen-Discovery“, Phase 0): **Wie gut findet OpenStreetMap deine Hofläden?** und
**Liefert ein lokales LLM brauchbare, sichere strukturierte Daten?** – bevor Phase 1+ gebaut wird.

Festgelegte Rahmenbedingungen (Entscheide vom 2026-10-06): KI erst nach der Messung; **Radius maximal 5 km**;
Standardbibliothek bevorzugt (`difflib`), Abhängigkeiten nur bei klarem Gewinn; kein automatischer Beschreibungstext.

Alles hier ist **eigenständig** (nur Python ≥ 3.9, keine Installation, kein Home Assistant) und gehört nicht zur
ausgelieferten Integration (`custom_components/` bleibt unberührt).

> Die Overpass-API war aus der Entwicklungs-Sandbox nicht erreichbar. Die Messung selbst wurde **nicht** ausgeführt;
> das Werkzeug ist mit 28 Offline-Tests (gefälschte Antworten) abgesichert. Die Zahlen entstehen bei dir.

## Teil A – OSM-Trefferquote messen (ca. 1–2 Stunden inkl. Testset)

### 1. Testset anlegen
Kopiere `testset.beispiel.json` nach `testset.json` und ersetze die Platzhalter durch **30–50 echte Fälle**:
- **positiv** (≈ 80 %): echte Hofläden – gemischt: Stadtnähe/Land, mit/ohne Website, Selbstbedienung/Automat/bedient,
  solche, von denen du *weisst*, dass sie in OSM stehen, und solche, bei denen du unsicher bist. Name so, wie ein Nutzer
  ihn tippen würde; Koordinaten aus der Karte.
- **negativ** (≈ 20 %): Orte, die **kein** Hofladen sind (Bäckerei, Hof ohne Verkauf) – misst Fehlalarme.

Hilfsmittel zum Finden der Fälle: `scan` listet alle Kandidaten um einen Punkt als CSV (Spalte „ist_hofladen“ von Hand füllen):

```bash
python3 overpass_messung.py scan --lat 46.95 --lon 7.45 --radius 3000 --out scan.csv
```

### 2. Messen
```bash
python3 overpass_messung.py messen --testset testset.json --cache cache --out ergebnis
```
Standard: Variante `erweitert`, Radien 2000/5000 m, Suchpunkt-Versatz 0 und 1500 m (simuliert einen ungenauen
Standort) → bei 40 Einträgen 160 Abfragen, je ≥ 3 s Pause (≈ 10 Minuten). Weitere Varianten vergleichen:

```bash
python3 overpass_messung.py messen --testset testset.json --cache cache --out vergleich \
        --varianten bestand,kern,erweitert --radien 2000 --versatz 0
```
(`bestand` = Abfrage der heutigen Integration – alle `shop=*` – und zeigt, wie teuer/ungenau sie bei grösserem Radius ist.)

Eigene Overpass-Instanz: `--url https://…/api/interpreter`. Jede Antwort landet in `cache/` (Wiederholung und
`--offline` belasten den Dienst nicht; der Cache wird später als Test-Fixture für Phase 1/2 verwendet).

### 3. Ergebnis lesen (`ergebnis.md`)
| Spalte | Bedeutung |
|---|---|
| gefunden | Hofladen steht überhaupt in der Kandidatenliste → **Obergrenze** dessen, was Scoring/KI je leisten können |
| @1 / @3 / @10 | Hofladen unter den ersten N nach naivem Score (0.6 Name + 0.4 Distanz) |
| @3 (nur Distanz) | Vergleich: nur nach Entfernung sortiert → zeigt den Nutzen des Namens-Scorings |
| Fehlalarm | Negativfall mit ähnlich benanntem Kandidaten ≤ 300 m |
| Kand. med/max, Latenz, max KB | Last für Overpass und Wartezeit für die Nutzer |

**Go/No-Go-Vorschlag** (bitte mit dir abstimmen, sobald Zahlen vorliegen):
- *gefunden* ≥ 80 % bei 5 km / Versatz 1500 m und @3 ≥ 90 % von „gefunden“ → Overpass + Scoring reicht, KI ist optional.
- *gefunden* 50–80 % → trotzdem weiter (Fallback: Website-Ermittlung); KI bringt hier wenig, besser Lücken in OSM schliessen.
- *gefunden* < 50 % → Konzept überdenken (andere Quellen).

## Teil B – KI-Spike (nur wenn Ollama verfügbar)

### B1 – Modell direkt prüfen
```bash
python3 ai_spike/ollama_extraktion.py --text ai_spike/beispiel_seite.txt --modell qwen2.5:7b --url http://localhost:11434
```
Gibt JSON-Gültigkeit, Schema-Konformität, Latenz, Tokens/s, **Grounding-Status** (confirmed/inferred je Wert) und
`injection_durchgeschlagen` aus. Der Beispieltext enthält absichtlich eine eingebettete „Anweisung an KI-Systeme“.
Mit 2–3 Modellen und eigenen echten Seitentexten (als `.txt`) wiederholen; Latenz auf der Hardware notieren, auf der
Ollama später läuft.

### B2 – Weg über Home Assistant
`ai_spike/ha_ai_task_beispiel.yaml` in *Entwicklerwerkzeuge → Aktionen (YAML-Modus)* einfügen (`entity_id` anpassen).
Bestätigt, dass `ai_task.generate_data` mit `structure` bei deiner HA-Version und deinem Modell funktioniert
(bekannt: Ollama + `gpt-oss` hatte Probleme, HA-Issue #152337).

**Abnahme Teil B:** gültiges JSON in ≥ 9 von 10 Läufen · Latenz akzeptabel (Vorschlag ≤ 60 s) · Injection ändert
nichts an den als `confirmed` geltenden Werten · ai_task-Aufruf läuft.

## Rückmeldung an mich
Bitte `ergebnis.md` (+ `ergebnis.json`) und die Ausgaben von Teil B einsenden – optional auch den `cache/`-Ordner
(nur öffentliche OSM-Daten). Daraus entstehen der Go/No-Go-Entscheid und die Kalibrierung für Phase 2.

## Tests
```bash
python3 -m pytest -c /dev/null --rootdir=. tools/discovery_phase0/tests -q -p no:cacheprovider
```
(Der Test `test_bestand_variante_entspricht_der_integration` warnt, falls sich die Filter in `osm_info.py` ändern.)
