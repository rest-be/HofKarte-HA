# Beitragen zu HofKarte

Danke für dein Interesse an HofKarte! Dieses Dokument beschreibt, wie du
lokal entwickelst, testest und Änderungen beiträgst.

HofKarte ist ein privates Projekt (siehe `SECURITY.md`); es gibt kein
formelles Contributor-Team, aber Beiträge über Pull Requests sind
willkommen.

## Entwicklungsumgebung einrichten

Voraussetzungen: Python 3.12 oder neuer (siehe von Home Assistant selbst
unterstützte Python-Version), `pip`.

```bash
git clone https://github.com/rest-be/HofKarte.git
cd HofKarte
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements_test.txt
```

Es werden **keine zusätzlichen Python-Pakete für den Betrieb** benötigt
(`manifest.json` → `requirements: []`); `requirements_test.txt` enthält
ausschliesslich Werkzeuge für die Entwicklung/Tests.

## Code-Stil, Linting, Typisierung

- **Sprache:** Der gesamte Code, alle Kommentare, Docstrings,
  Variablennamen, Testbezeichnungen und Fehlermeldungen sind auf
  **Deutsch** (Ausnahme: Python-Schlüsselwörter, Home-Assistant-API-Namen
  und `strings.json`/`translations/en.json`, die auf Englisch bleiben).
- **Konventionen:** `from __future__ import annotations` in jeder Datei,
  durchgängig `async def` für I/O-relevanten Code, `asyncio.Lock` für
  konkurrierende Schreibzugriffe (siehe `data_provider.py`).
- **Keine blockierenden Aufrufe** im Event Loop (kein `time.sleep`, keine
  synchrone Netzwerk-/Dateisystem-I/O ausserhalb eines Executors). Siehe
  `docs/architecture.md`, Abschnitt „Performance“, für ein konkretes
  Beispiel, warum das wichtig ist.

Linting und Typisierung vor jedem Commit prüfen:

```bash
pip install pyflakes mypy
python -m pyflakes custom_components/hofkarte/*.py custom_components/hofkarte/tests/*.py
python -m mypy --ignore-missing-imports custom_components/hofkarte/*.py
```

Beide Prüfungen müssen fehlerfrei durchlaufen (aktueller Stand: 0
Findings in beiden Werkzeugen).

## Tests ausführen

```bash
pytest custom_components/hofkarte/tests
```

Erwartung: alle Tests grün (aktueller Stand: rund 1120 Tests; die JavaScript-Verhaltenstests des Panels laufen mit Node und `jsdom` und werden ohne beides übersprungen). Für neue
Funktionalität gilt:

- Jede neue Fach-/Berechnungslogik (z. B. in `opening_hours.py`,
  `distance.py`, `search.py`) bekommt eigene, isolierte Unit-Tests ohne
  Home-Assistant-Abhängigkeit, wo möglich.
- Jede neue Entity/Plattform bekommt Tests für: `unique_id`-Muster,
  Device-Zuordnung, Verfügbarkeit, sowie einen End-zu-End-Test über
  einen echten `hass.config_entries.async_setup`-Aufruf.
- Jede neue Fehlerbehandlung (z. B. neue Exception-Typen) bekommt einen
  expliziten Test für den Fehlerfall, nicht nur den Erfolgsfall.

## Branch- und Commit-Konventionen

- **Branches:** Die aktive Entwicklung findet auf `develop` statt
  (langlebiger Integrationsbranch); `main` bildet ausschliesslich den
  jeweils zuletzt veröffentlichten, produktiven Releasestand ab und
  wird nur im Rahmen eines Releases aktualisiert (siehe „Release-
  Ablauf“ unten). Feature-/Fix-Branches nach dem Muster
  `feature/kurzbeschreibung` bzw. `fix/kurzbeschreibung` von `develop`
  abzweigen.
- **Entwicklungsversionen:** Während der aktiven Entwicklung eines
  Milestones trägt `manifest.json` die Version
  `<Milestone>-dev.<LAUFNUMMER>` (z. B. `2026.9.1-dev.7`), fortlaufend
  hochgezählt pro abgeschlossener Änderung. Vor der Veröffentlichung
  wird mindestens ein Release Candidate `<Milestone>-rc.<LAUFNUMMER>`
  (z. B. `2026.9.1-rc.1`) erstellt, geprüft und dokumentiert – erst
  danach erfolgt der eigentliche produktive Release unter der reinen
  Milestone-Version (z. B. `2026.9.1`) auf `main`.
- **Commit-Nachrichten:** kurze, aussagekräftige erste Zeile (Deutsch,
  Imperativ, z. B. „Öffnungszeiten-Berechnung um Mitternachtsfall
  ergänzen“), bei Bedarf ausführlichere Beschreibung im Body. Kein
  festes Konventions-Präfix-System (kein Conventional Commits) vorgesehen
  – Klarheit vor Format.

## Pull-Request-Ablauf

1. Von `develop` abzweigen, Änderung umsetzen.
2. Sicherstellen: `pytest`, `pyflakes` und `mypy` laufen fehlerfrei
   (siehe oben).
3. `CHANGELOG.md` unter der aktuellen `<Milestone>-dev.<LAUFNUMMER>`-
   Version um die nutzerrelevante Änderung ergänzen (Format:
   [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)).
4. Pull Request gegen `develop` öffnen mit kurzer Beschreibung von
   **Was** und **Warum**.
5. Nach Review und grünen Checks: Merge durch den/die Projektbetreuer:in.

## Release-Ablauf

Sobald `develop` für einen Milestone funktional abgeschlossen ist:

1. Ein oder mehrere Release Candidates (`<Milestone>-rc.<LAUFNUMMER>`)
   auf `develop` erstellen: Dokumentation konsolidieren/nachführen,
   Release-Metadaten prüfen, offensichtliche Unstimmigkeiten
   bereinigen – ohne funktionale Codeänderung.
2. Nach erfolgreicher Prüfung des Release Candidates: `develop` nach
   `main` mergen, `manifest.json` auf die reine Milestone-Version
   setzen (z. B. `2026.9.1`), `CHANGELOG.md`-Abschnitt entsprechend
   umbenennen/datieren, GitHub Release/Tag auf `main` erstellen.

Es gibt aktuell keine automatisierte CI-Pipeline; Tests/Linting werden
manuell vor Merge und Release ausgeführt.

## Umgang mit Übersetzungen

HofKarte pflegt zwei Sprachen für die Home-Assistant-eigene
Übersetzungsinfrastruktur (Config Flow, Service-Beschreibungen):

- `custom_components/hofkarte/strings.json` – Quelle auf **Englisch**.
- `custom_components/hofkarte/translations/en.json` – identisch zu
  `strings.json` (strukturell, siehe Test
  `test_strings_json_und_englische_uebersetzung_stimmen_strukturell_ueberein`).
- `custom_components/hofkarte/translations/de.json` – deutsche
  Übersetzung, strukturell identisch zu den beiden englischen Dateien.

Beim Hinzufügen eines neuen Config-Flow-Fehlers, Abbruchgrunds oder
Service-Felds **immer alle drei Dateien** synchron aktualisieren. Die
automatisierten Tests in `tests/test_translations.py` prüfen
strukturelle Konsistenz (nicht die sprachliche Qualität – das bleibt
manueller Prüfung vorbehalten).

Entity-Namen (z. B. „Geöffnet“, „Nächste Öffnung“) sind bewusst fest auf
Deutsch gesetzt (`_attr_name`, kein `translation_key`-Mechanismus) – eine
dokumentierte, absichtliche Vereinfachung für die einsprachige
Zielgruppe (siehe `quality_scale.yaml`, Kriterium
`entity-translations`).

## Weiterführende Dokumentation

- `docs/architecture.md` – Architekturüberblick, Zusammenspiel der
  Module, Erweiterungspunkte.
- `docs/handbuch.md` – Anwendungshandbuch für Endanwender:innen.
- `README.md` – Kurzübersicht, Installation, Funktionsumfang.
