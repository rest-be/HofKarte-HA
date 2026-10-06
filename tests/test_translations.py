"""Automatisiert prüfbare Konsistenz von Übersetzungen.

Deckt genau das ab, was ohne menschliche Sprachprüfung automatisiert
verifizierbar ist: valides JSON, strukturelle Übereinstimmung zwischen
Deutsch/Englisch, sowie dass alle im Code tatsächlich verwendeten
Übersetzungsschlüssel (Config-Flow-Fehler/Abbrüche, Service-Felder)
auch in ``strings.json`` und beiden ``translations/*.json`` vorhanden
sind. Inhaltliche/sprachliche Qualität der Übersetzung selbst ist nicht
automatisiert prüfbar und bleibt manueller Kontrolle vorbehalten.
"""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.hofkarte.services import (
    SERVICE_HOFLAEDEN_SUCHEN,
    _SERVICE_HOFLAEDEN_SUCHEN_SCHEMA,
)

_HOFKARTE_DIR = Path(__file__).resolve().parent.parent


def _load_json(relativer_pfad: str) -> dict:
    pfad = _HOFKARTE_DIR / relativer_pfad
    with pfad.open(encoding="utf-8") as datei:
        return json.load(datei)


def _alle_schluesselpfade(daten: dict, praefix: str = "") -> set[str]:
    """Alle verschachtelten Schlüsselpfade eines JSON-Objekts als Set.

    Beispiel: {"a": {"b": "x"}} -> {"a", "a.b"}.
    """
    pfade: set[str] = set()
    for schluessel, wert in daten.items():
        aktueller_pfad = f"{praefix}.{schluessel}" if praefix else schluessel
        pfade.add(aktueller_pfad)
        if isinstance(wert, dict):
            pfade |= _alle_schluesselpfade(wert, aktueller_pfad)
    return pfade


def test_strings_json_ist_gueltiges_json() -> None:
    _load_json("strings.json")


def test_translations_de_ist_gueltiges_json() -> None:
    _load_json("translations/de.json")


def test_translations_en_ist_gueltiges_json() -> None:
    _load_json("translations/en.json")


def test_deutsche_und_englische_uebersetzung_haben_dieselbe_struktur() -> None:
    """Es dürfen keine Schlüssel in einer Sprache fehlen oder zusätzlich
    vorhanden sein – sonst fehlt in einer Sprache eine Übersetzung oder
    es gibt einen verwaisten Text, der nirgends verwendet wird."""
    de_pfade = _alle_schluesselpfade(_load_json("translations/de.json"))
    en_pfade = _alle_schluesselpfade(_load_json("translations/en.json"))

    nur_in_de = de_pfade - en_pfade
    nur_in_en = en_pfade - de_pfade

    assert not nur_in_de, f"Nur in Deutsch vorhanden: {sorted(nur_in_de)}"
    assert not nur_in_en, f"Nur in Englisch vorhanden: {sorted(nur_in_en)}"


def test_strings_json_und_englische_uebersetzung_stimmen_strukturell_ueberein() -> None:
    """``strings.json`` ist die Quelle für die automatische
    Übersetzungsinfrastruktur; ``translations/en.json`` sollte dieselbe
    Struktur wie ``strings.json`` haben (beides Englisch)."""
    strings_pfade = _alle_schluesselpfade(_load_json("strings.json"))
    en_pfade = _alle_schluesselpfade(_load_json("translations/en.json"))

    assert strings_pfade == en_pfade


def test_config_flow_fehlercodes_sind_in_allen_uebersetzungen_vorhanden() -> None:
    """Jeder im Code tatsächlich verwendete Config-Flow-Fehler-/Abbruch-Code
    muss in strings.json und beiden Übersetzungen vorhanden sein –
    sonst zeigt Home Assistant nur den rohen internen Code an."""
    verwendete_error_codes = {"invalid_name"}
    verwendete_abort_reasons = {"single_instance_allowed"}

    for pfad in ("strings.json", "translations/de.json", "translations/en.json"):
        daten = _load_json(pfad)
        config = daten.get("config", {})

        vorhandene_errors = set(config.get("error", {}).keys())
        vorhandene_aborts = set(config.get("abort", {}).keys())

        fehlende_errors = verwendete_error_codes - vorhandene_errors
        fehlende_aborts = verwendete_abort_reasons - vorhandene_aborts

        assert not fehlende_errors, f"{pfad}: fehlende error-Keys {fehlende_errors}"
        assert not fehlende_aborts, f"{pfad}: fehlende abort-Keys {fehlende_aborts}"


def test_service_felder_sind_in_allen_uebersetzungen_dokumentiert() -> None:
    """Jedes in ``services.py`` definierte Service-Feld muss in
    strings.json und beiden Übersetzungen einen name/description-Eintrag
    haben, sonst zeigt Home Assistant in Entwicklerwerkzeuge → Aktionen
    nur den rohen Feldnamen ohne Erklärung an."""
    erwartete_felder = {
        str(schluessel.schema if hasattr(schluessel, "schema") else schluessel)
        for schluessel in _SERVICE_HOFLAEDEN_SUCHEN_SCHEMA.schema
    }

    for pfad in ("strings.json", "translations/de.json", "translations/en.json"):
        daten = _load_json(pfad)
        service_eintrag = daten["services"][SERVICE_HOFLAEDEN_SUCHEN]

        assert "name" in service_eintrag
        assert "description" in service_eintrag

        dokumentierte_felder = set(service_eintrag.get("fields", {}).keys())
        fehlende_felder = erwartete_felder - dokumentierte_felder

        assert not fehlende_felder, f"{pfad}: fehlende Feld-Dokumentation {fehlende_felder}"


def test_services_yaml_ist_gueltiges_yaml() -> None:
    import yaml

    pfad = _HOFKARTE_DIR / "services.yaml"
    with pfad.open(encoding="utf-8") as datei:
        daten = yaml.safe_load(datei)

    assert "hoflaeden_suchen" in daten


def test_options_selector_uebersetzungen_decken_alle_auswahlwerte_ab() -> None:
    """F3: Die ``SelectSelector``-Dropdowns des Options Flows beziehen ihre
    Bezeichnungen aus ``selector.<schlüssel>.options.<wert>`` - fehlt ein
    Wert, zeigt Home Assistant nur den rohen technischen Wert."""
    from custom_components.hofkarte.const import (
        CONF_LISTEN_SORT_RICHTUNG,
        CONF_LISTEN_SORT_SPALTE,
        LISTEN_SORT_RICHTUNGEN,
        LISTEN_SORT_SPALTEN,
    )

    erwartet = {
        CONF_LISTEN_SORT_SPALTE: set(LISTEN_SORT_SPALTEN),
        CONF_LISTEN_SORT_RICHTUNG: set(LISTEN_SORT_RICHTUNGEN),
    }
    for pfad in ("strings.json", "translations/de.json", "translations/en.json"):
        selector = _load_json(pfad)["selector"]
        for schluessel, werte in erwartet.items():
            assert set(selector[schluessel]["options"]) == werte, pfad
