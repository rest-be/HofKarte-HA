"""F1 (Code Review 2026.9.2): Das Panel löscht hochgeladene Bilder nur noch
für URLs des **eigenen Origins** im exakten Upload-Muster.

``eigeneUploadImageId`` ist eine reine Funktion ohne DOM-Bezug; sie wird
hier aus dem Quelltext extrahiert und mit Node ausgeführt (kein
JS-Testframework nötig). Ohne Node werden die Verhaltenstests übersprungen,
der strukturelle Test läuft immer.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_PANEL_JS = Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
_ID = "0123456789abcdef0123456789abcdef"
_ORIGIN = "http://192.168.1.50:8123"


def _funktionsquelltext() -> str:
    quelle = _PANEL_JS.read_text(encoding="utf-8")
    treffer = re.search(r"function eigeneUploadImageId\(.*?\n}\n", quelle, re.DOTALL)
    assert treffer, "eigeneUploadImageId nicht gefunden"
    return treffer.group(0)


def _ausfuehren(url: object, origin: str) -> object:
    skript = (
        _funktionsquelltext()
        + f"\nprocess.stdout.write(JSON.stringify(eigeneUploadImageId("
        f"{json.dumps(url)}, {json.dumps(origin)})));"
    )
    ergebnis = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(ergebnis.stdout)


def test_extract_image_id_nutzt_die_origin_pruefung() -> None:
    quelle = _PANEL_JS.read_text(encoding="utf-8")
    assert "return eigeneUploadImageId(url, window.location.origin);" in quelle
    # Die alte, origin-lose Regex darf nicht zurückkehren.
    assert r"/\/api\/image\/serve\/([^/]+)\//" not in quelle


@pytest.mark.skipif(shutil.which("node") is None, reason="Node nicht verfügbar")
@pytest.mark.parametrize(
    ("url", "erwartet"),
    [
        (f"{_ORIGIN}/api/image/serve/{_ID}/original", _ID),
        (f"{_ORIGIN}/api/image/serve/{_ID}/256x256", _ID),
        (f"http://192.168.1.20:8123/api/image/serve/{_ID}/original", None),
        (f"https://boese.example/api/image/serve/{_ID}/original", None),
        (f"{_ORIGIN}/api/image/serve/{_ID}/original?x=1", None),
        (f"{_ORIGIN}/api/image/serve/abc/original", None),
        (f"{_ORIGIN}/x/api/image/serve/{_ID}/original", None),
        ("/api/image/serve/" + _ID + "/original", None),
        ("kein url", None),
        (None, None),
    ],
)
def test_bild_id_nur_fuer_eigenen_origin(url: object, erwartet: str | None) -> None:
    assert _ausfuehren(url, _ORIGIN) == erwartet


@pytest.mark.skipif(shutil.which("node") is None, reason="Node nicht verfügbar")
def test_ohne_bekannten_origin_wird_nie_geloescht() -> None:
    assert _ausfuehren(f"{_ORIGIN}/api/image/serve/{_ID}/original", "") is None
