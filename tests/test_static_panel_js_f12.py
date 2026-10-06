"""F12 (Code Review 2026.9.2): Defense in Depth im Panel (``hofkarte-panel.js``).

Reine Hilfsfunktionen (``istSichereBildUrl``, ``istGueltigeEmail``) werden aus
dem Quelltext extrahiert und mit Node ausgeführt (ohne Node übersprungen);
das Escaping und die Import-Limits werden strukturell am Quelltext geprüft
(wie bei den übrigen ``test_static_panel_js*``-Tests).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from custom_components.hofkarte import const

_PANEL_JS = Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
_EIGENER_ORIGIN = "http://192.168.1.50:8123"
_ID = "0123456789abcdef0123456789abcdef"
_NODE = shutil.which("node") is not None


def _quelle() -> str:
    return _PANEL_JS.read_text(encoding="utf-8")


def _helfer_quelltext() -> str:
    quelle = _quelle()
    start = quelle.index("// Befund F12 (Code Review 2026.9.2)")
    ende = quelle.index("function isFullDay(row)")
    return quelle[start:ende]


def _node(ausdruck: str) -> object:
    skript = _helfer_quelltext() + f"\nprocess.stdout.write(JSON.stringify({ausdruck}));"
    ergebnis = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(ergebnis.stdout)


# --- Escaping (strukturell) ---------------------------------------------------


def test_keine_unescapten_id_interpolationen_in_attributen() -> None:
    quelle = _quelle()
    ungeschuetzt = re.findall(
        r'(?:data-[a-z-]+|value)="\$\{(?!this\.escAttr)[^}]*(?:\.id|duplikat_von|beginn|ende|datum_von|datum_bis)[^}]*\}"',
        quelle,
    )
    assert ungeschuetzt == []


def test_zeiten_und_ids_werden_mit_escattr_ausgegeben() -> None:
    quelle = _quelle()
    for muster in (
        'data-view="${this.escAttr(item.id)}"',
        'data-edit="${this.escAttr(item.id)}"',
        'data-delete="${this.escAttr(item.id)}"',
        'data-auswahl="${this.escAttr(item.id)}"',
        'data-import-entscheidung="${this.escAttr(eintrag.duplikat_von)}"',
        'data-edit-from-detail="${this.escAttr(d.id)}"',
        'value="${this.escAttr(x.beginn || "")}"',
        'value="${this.escAttr(x.datum_von || "")}"',
    ):
        assert muster in quelle, muster


def test_externe_bilder_haben_referrerpolicy_no_referrer() -> None:
    quelle = _quelle()
    for treffer in re.findall(r"<img [^>]*src=[^>]*>", quelle):
        assert 'referrerpolicy="no-referrer"' in treffer, treffer


def test_bilder_werden_nur_ueber_die_pruefung_gerendert() -> None:
    quelle = _quelle()
    assert "bildHtml(url, alt, vorschau = false)" in quelle
    assert "istSichereBildUrl(url, window.location.origin)" in quelle
    assert "this.bildHtml(b.url" in quelle and "this.bildHtml(bild.url" in quelle


def test_mailto_nur_bei_validierter_adresse() -> None:
    quelle = _quelle()
    assert "istGueltigeEmail(email)" in quelle
    assert quelle.index("istGueltigeEmail(email)") < quelle.index('href="mailto:')


# --- Import-Limits ---------------------------------------------------------------


def test_import_limits_stimmen_mit_backend_ueberein_und_werden_vor_dem_lesen_geprueft() -> None:
    quelle = _quelle()
    assert f"const IMPORT_MAX_EINTRAEGE = {const.MAX_IMPORT_EINTRAEGE};" in quelle
    assert "const IMPORT_MAX_BYTES = 2 * 1024 * 1024;" in quelle
    assert quelle.index("file.size > IMPORT_MAX_BYTES") < quelle.index("await file.text()")
    assert quelle.index("daten.length > IMPORT_MAX_EINTRAEGE") > quelle.index("JSON.parse(inhalt)")
    assert quelle.index("daten.length > IMPORT_MAX_EINTRAEGE") < quelle.index(
        "hofkarte/management/import_preview"
    )


# --- Funktionen (Node) -----------------------------------------------------------


@pytest.mark.skipif(not _NODE, reason="Node nicht verfügbar")
@pytest.mark.parametrize(
    ("url", "erwartet"),
    [
        ("https://example.com/bild.jpg", True),
        ("http://www.beispiel.ch/a.png", True),
        ("https://Beispiel.CH./a.png", True),
        ("http://8.8.8.8/a.png", True),
        ("http://[2001:4860:4860::8888]/a.png", True),
        (f"{_EIGENER_ORIGIN}/api/image/serve/{_ID}/original", True),  # eigener Upload
        ("javascript:alert(1)", False),
        ("data:image/png;base64,AAAA", False),
        ("file:///etc/passwd", False),
        ("ftp://beispiel.ch/a.png", False),
        ("http://user:pw@beispiel.ch/a.png", False),
        ("http://localhost/a.png", False),
        ("http://foo.localhost/a.png", False),
        ("http://127.0.0.1/a.png", False),
        ("http://127.1/a.png", False),
        ("http://2130706433/a.png", False),
        ("http://0x7f000001/a.png", False),
        ("http://192.168.1.20/relay/0?turn=on", False),
        ("http://10.0.0.1/a.png", False),
        ("http://172.16.0.1/a.png", False),
        ("http://100.64.0.1/a.png", False),
        ("http://169.254.169.254/latest/meta-data", False),
        ("http://homeassistant/a.png", False),
        ("http://homeassistant.local:8123/a.png", False),
        ("http://[::1]/a.png", False),
        ("http://[::ffff:127.0.0.1]/a.png", False),
        ("http://[fe80::1]/a.png", False),
        ("http://192.168.1.99:8123/api/image/serve/" + _ID + "/original", False),  # fremder Host
        (f"{_EIGENER_ORIGIN}/api/image/serve/{_ID}/original?x=1", False),
        ("", False),
        (None, False),
    ],
)
def test_ist_sichere_bild_url(url: object, erwartet: bool) -> None:
    ausdruck = f"istSichereBildUrl({json.dumps(url)}, {json.dumps(_EIGENER_ORIGIN)})"
    assert _node(ausdruck) is erwartet


@pytest.mark.skipif(not _NODE, reason="Node nicht verfügbar")
@pytest.mark.parametrize(
    ("email", "erwartet"),
    [
        ("hof@beispiel.ch", True),
        ("a.b+c@sub.beispiel.ch", True),
        ("a@b.ch?cc=x@y.ch", False),
        ("a@b.ch&body=x", False),
        ("a%40b.ch@c.ch", False),
        ("a b@c.ch", False),
        ("a@@b.ch", False),
        ("a@b.ch,c@d.ch", False),
        ("keine-mail", False),
        ("", False),
    ],
)
def test_ist_gueltige_email(email: str, erwartet: bool) -> None:
    assert _node(f"istGueltigeEmail({json.dumps(email)})") is erwartet
