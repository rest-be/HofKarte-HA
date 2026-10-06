"""Automatisiert prüfbare HACS-/Manifest-Korrektheit.

Prüft strukturelle Anforderungen an ``manifest.json`` und ``hacs.json``,
die vor einem Release automatisiert verifizierbar sind. Ersetzt keine
echte HACS-Installation (nicht automatisiert simulierbar), stellt aber
sicher, dass die dafür nötigen Grundlagen (gültiges JSON, Pflichtfelder,
konsistente Version, erreichbare Domain) stimmen.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_HOFKARTE_DIR = _REPO_ROOT / "custom_components" / "hofkarte"

# Erlaubt sowohl reguläre Releases (JAHR.MONAT.LAUFNUMMER, z. B.
# "2026.9.0") als auch Entwicklungsversionen (JAHR.MONAT.LAUFNUMMER-dev.
# FORTLAUFENDE_NUMMER, z. B. "2026.9.1-dev.1") und Release Candidates
# (JAHR.MONAT.LAUFNUMMER-rc.FORTLAUFENDE_NUMMER, z. B. "2026.9.1-rc.1")
# auf dem `develop`-Zweig - siehe CONTRIBUTING.md, Abschnitt
# „Branch- und Commit-Konventionen“.
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-(dev|rc)\.\d+)?$")

# Reihenfolge der Release-Stufen innerhalb desselben JAHR.MONAT.LAUFNUMMER
# -Kerns: Entwicklungsversionen kommen vor Release Candidates, die
# wiederum vor dem regulären, suffixlosen Release kommen.
_STUFEN_RANG = {"dev": 0, "rc": 1, None: 2}


def _version_tuple(version: str) -> tuple[float, ...]:
    """Eine Versionszeichenkette für einen korrekten *numerischen*
    Vergleich in ein Tupel überführen. Ein reiner Stringvergleich wäre
    für das seit dem MVP-Release verwendete Home-Assistant-Versionsschema
    (JAHR.MONAT.LAUFNUMMER, z. B. "2026.10.0") falsch: lexikografisch
    wäre "2026.10.0" < "2026.9.0", da "1" < "9" als erstes abweichendes
    Zeichen - numerisch ist Oktober aber später als September.

    Eine Entwicklungs- oder Release-Candidate-Version (```-dev.N```- bzw.
    ```-rc.N```-Suffix) muss dabei stets vor dem zugehörigen, noch
    ausstehenden regulären Release einsortiert werden, und innerhalb
    desselben Kerns kommt ``-dev.N`` stets vor ``-rc.N``:
    ``2026.9.1-dev.1`` < ``2026.9.1-dev.2`` < ``2026.9.1-rc.1`` <
    ``2026.9.1``. Ein regulärer Release ohne Suffix erhält dafür
    ``math.inf`` als vierte Vergleichsstelle.
    """
    match = re.match(r"^(?P<kern>\d+\.\d+\.\d+)(-(?P<stufe>dev|rc)\.(?P<nummer>\d+))?$", version)
    assert match, f"Unbekanntes Versionsformat: '{version}'."
    zahlen = tuple(int(teil) for teil in match.group("kern").split("."))
    stufe = match.group("stufe")
    nummer = int(match.group("nummer")) if match.group("nummer") else math.inf
    return zahlen + (_STUFEN_RANG[stufe], nummer)


def _load_manifest() -> dict:
    with (_HOFKARTE_DIR / "manifest.json").open(encoding="utf-8") as datei:
        return json.load(datei)


def _load_hacs() -> dict:
    with (_REPO_ROOT / "hacs.json").open(encoding="utf-8") as datei:
        return json.load(datei)


def test_manifest_ist_gueltiges_json() -> None:
    _load_manifest()


def test_manifest_enthaelt_alle_pflichtfelder() -> None:
    manifest = _load_manifest()
    pflichtfelder = {
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "documentation",
        "issue_tracker",
        "iot_class",
        "requirements",
        "version",
    }
    fehlende_felder = pflichtfelder - set(manifest.keys())
    assert not fehlende_felder, f"Fehlende Pflichtfelder: {fehlende_felder}"


def test_manifest_domain_stimmt_mit_ordnername_ueberein() -> None:
    manifest = _load_manifest()
    assert manifest["domain"] == "hofkarte"
    assert manifest["domain"] == _HOFKARTE_DIR.name


def test_manifest_version_folgt_kalenderversionierung() -> None:
    """Seit dem MVP-Release folgt HofKarte dem Home-Assistant-eigenen
    Versionierungsschema JAHR.MONAT.LAUFNUMMER (z. B. "2026.9.0") statt
    Semantic Versioning. Das Format ist syntaktisch identisch zu
    MAJOR.MINOR.PATCH (drei durch Punkte getrennte Zahlen) - die
    Bedeutung der Teile hat sich aber geändert, siehe CHANGELOG."""
    manifest = _load_manifest()
    assert _VERSION_PATTERN.match(manifest["version"]), (
        f"Version '{manifest['version']}' entspricht nicht "
        "JAHR.MONAT.LAUFNUMMER (drei durch Punkte getrennte Zahlen)."
    )


def test_version_tuple_vergleicht_numerisch_nicht_lexikografisch() -> None:
    """Regressionstest für den Grund, warum _version_tuple() statt eines
    reinen Stringvergleichs nötig ist: Oktober (zweistelliger Monat) muss
    numerisch nach September kommen, auch wenn "10" lexikografisch vor
    "9" steht."""
    assert _version_tuple("2026.10.0") > _version_tuple("2026.9.0")
    assert not ("2026.10.0" > "2026.9.0")  # zur Verdeutlichung: String-Vergleich wäre falsch


def test_version_tuple_ordnet_dev_versionen_vor_dem_release_ein() -> None:
    """Eine Entwicklungsversion (-dev.N) muss stets vor dem zugehörigen,
    noch ausstehenden Release Candidate bzw. regulären Release liegen,
    und ein Release Candidate (-rc.N) stets vor dem regulären Release."""
    assert _version_tuple("2026.9.1-dev.1") < _version_tuple("2026.9.1-dev.2")
    assert _version_tuple("2026.9.1-dev.2") < _version_tuple("2026.9.1-rc.1")
    assert _version_tuple("2026.9.1-rc.1") < _version_tuple("2026.9.1-rc.2")
    assert _version_tuple("2026.9.1-rc.2") < _version_tuple("2026.9.1")



    """HofKarte wird ausschliesslich über den Config Flow eingerichtet
    (keine YAML-Konfiguration, siehe config_flow.py)."""
    manifest = _load_manifest()
    assert manifest["config_flow"] is True


def test_manifest_hat_keine_unerwarteten_python_abhaengigkeiten() -> None:
    """HofKarte benötigt ausser Home Assistant selbst keine zusätzlichen
    Python-Pakete (siehe README, Abschnitt „Voraussetzungen“)."""
    manifest = _load_manifest()
    assert manifest["requirements"] == []


def test_manifest_deklariert_http_abhaengigkeit() -> None:
    """Ohne diese Abhängigkeit ist ``hass.http`` beim Setup nicht
    zuverlässig verfügbar (siehe CHANGELOG, behobener Bug)."""
    manifest = _load_manifest()
    assert "http" in manifest.get("dependencies", [])


def test_manifest_deklariert_image_upload_abhaengigkeit() -> None:
    """Der geführte Bilder-Upload nutzt Home Assistants eigene
    ``image_upload``-Komponente (Upload-/Serve-Endpunkte,
    WebSocket-Befehle ``image/list|update|delete``). Ohne diese
    Abhängigkeit ist nicht garantiert, dass die Komponente beim Setup
    von HofKarte bereits initialisiert ist."""
    manifest = _load_manifest()
    assert "image_upload" in manifest.get("dependencies", [])


def test_hacs_json_ist_gueltiges_json() -> None:
    _load_hacs()


def test_hacs_json_enthaelt_name_und_render_readme() -> None:
    hacs = _load_hacs()
    assert hacs.get("name") == "HofKarte"
    assert hacs.get("render_readme") is True


def test_hacs_json_deklariert_minimale_ha_version() -> None:
    hacs = _load_hacs()
    assert "homeassistant" in hacs


def test_manifest_version_stimmt_mit_neuestem_changelog_eintrag_ueberein() -> None:
    """Die Manifest-Version muss der zuletzt dokumentierten Version im
    CHANGELOG entsprechen (Versionierung konsistent halten)."""
    manifest = _load_manifest()
    changelog = (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    versions_in_changelog = re.findall(
        r"^## \[(\d+\.\d+\.\d+(?:-(?:dev|rc)\.\d+)?)\]", changelog, re.MULTILINE
    )
    assert versions_in_changelog, "Keine Versionseinträge im CHANGELOG gefunden."

    neueste_dokumentierte_version = versions_in_changelog[0]
    # Die Manifest-Version darf entweder der neuesten dokumentierten
    # Version entsprechen (bereits im CHANGELOG nachgezogen) oder um genau
    # eine Version "voraus" sein (Änderung gerade erst vorgenommen, der
    # zugehörige CHANGELOG-Eintrag steht noch unter "[Unveröffentlicht]").
    # Numerischer Vergleich (nicht String-Vergleich!) ist beim seit dem
    # MVP-Release verwendeten Schema JAHR.MONAT.LAUFNUMMER zwingend
    # nötig, siehe _version_tuple().
    assert _version_tuple(manifest["version"]) >= _version_tuple(
        neueste_dokumentierte_version
    ), (
        f"manifest.json ({manifest['version']}) liegt hinter dem "
        f"CHANGELOG ({neueste_dokumentierte_version}) zurück."
    )


def test_repository_struktur_enthaelt_alle_hacs_pflichtdateien() -> None:
    """Minimale Dateistruktur, die HACS für ein Integrations-Repository
    voraussetzt."""
    pflichtdateien = [
        _REPO_ROOT / "hacs.json",
        _REPO_ROOT / "README.md",
        _REPO_ROOT / "CHANGELOG.md",
        _REPO_ROOT / "LICENSE",
        _HOFKARTE_DIR / "manifest.json",
        _HOFKARTE_DIR / "__init__.py",
    ]
    fehlende_dateien = [str(p) for p in pflichtdateien if not p.is_file()]
    assert not fehlende_dateien, f"Fehlende Pflichtdateien: {fehlende_dateien}"
