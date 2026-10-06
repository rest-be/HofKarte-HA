"""Tests für den gemeinsamen SSRF-Prüfkern (url_sicherheit.py).

Ausgelagert aus ``images.py`` im Zuge von Issue #8 ("Informationen aus
Homepage"), das denselben Prüfkern ein zweites Mal benötigt (siehe
``webseite_info.py``). Bewusst ohne DNS-Mocking, siehe Moduldoc: die
Prüfung ist rein syntaktisch.
"""

import pytest

from custom_components.hofkarte.url_sicherheit import (
    ist_eigene_upload_url,
    ist_oeffentliche_ip,
    ist_sichere_externe_url,
    normalisiere_hostname,
    normalisiere_origin,
    pruefe_aufloesung,
    ist_unsicheres_ip_literal,
)


def test_akzeptiert_gewoehnliche_domain() -> None:
    assert ist_sichere_externe_url("https://www.beispiel-hofladen.ch/")


def test_lehnt_leere_oder_fehlende_url_ab() -> None:
    assert not ist_sichere_externe_url("")
    assert not ist_sichere_externe_url("   ")
    assert not ist_sichere_externe_url(None)


def test_lehnt_unsichere_schemata_ab() -> None:
    assert not ist_sichere_externe_url("file:///etc/passwd")
    assert not ist_sichere_externe_url("ftp://beispiel.example/")
    assert not ist_sichere_externe_url("data:text/html,<script>")


def test_lehnt_zugangsdaten_in_url_ab() -> None:
    assert not ist_sichere_externe_url("http://user:pw@beispiel.example/")


def test_lehnt_localhost_ab() -> None:
    assert not ist_sichere_externe_url("http://localhost/")
    assert not ist_sichere_externe_url("http://LOCALHOST/")


def test_lehnt_private_und_loopback_ip_literale_ab() -> None:
    assert not ist_sichere_externe_url("http://127.0.0.1/")
    assert not ist_sichere_externe_url("http://192.168.1.1/")
    assert not ist_sichere_externe_url("http://10.0.0.5/")
    assert not ist_sichere_externe_url("http://[::1]/")


def test_lehnt_link_local_und_cloud_metadata_ab() -> None:
    assert not ist_sichere_externe_url("http://169.254.169.254/latest/meta-data")


def test_kennt_keine_herkunfts_ausnahme() -> None:
    """Anders als images.is_valid_image_url(hochgeladen=True) - diese
    Funktion ist ausschliesslich für frei eingegebene, nicht
    vertrauenswürdige URLs gedacht."""
    assert not ist_sichere_externe_url("http://192.168.1.50:8123/api/image/serve/x")


def test_ist_unsicheres_ip_literal_liefert_false_fuer_domainnamen() -> None:
    assert ist_unsicheres_ip_literal("example.com") is False


def test_ist_unsicheres_ip_literal_erkennt_private_adresse() -> None:
    assert ist_unsicheres_ip_literal("192.168.0.1") is True


# --- F1 (Code Review 2026.9.2): Herkunft eigener Uploads --------------------

_ORIGIN = "http://192.168.1.50:8123"
_ID = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize(
    ("url", "erwartet"),
    [
        ("HTTP://Beispiel.CH:80/x", "http://beispiel.ch"),
        ("https://beispiel.ch:443/", "https://beispiel.ch"),
        ("https://beispiel.ch:8443/", "https://beispiel.ch:8443"),
        ("http://[::1]:8123/", "http://[::1]:8123"),
        ("ftp://beispiel.ch/", None),
        ("http://user:pw@beispiel.ch/", None),
        ("http://beispiel.ch:abc/", None),
        ("", None),
        (None, None),
    ],
)
def test_normalisiere_origin(url: str | None, erwartet: str | None) -> None:
    assert normalisiere_origin(url) == erwartet


@pytest.mark.parametrize("variante", ["original", "256x256", "1920x1080"])
def test_eigener_upload_wird_erkannt(variante: str) -> None:
    assert ist_eigene_upload_url(f"{_ORIGIN}/api/image/serve/{_ID}/{variante}", [_ORIGIN])


def test_eigener_upload_mit_standardport_und_gross_klein_schreibung() -> None:
    assert ist_eigene_upload_url(
        f"HTTPS://HA.Beispiel.CH:443/api/image/serve/{_ID}/original",
        ["https://ha.beispiel.ch"],
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.20/relay/0?turn=on",  # fremdes Ziel
        f"http://192.168.1.20:8123/api/image/serve/{_ID}/original",  # falscher Host
        f"https://192.168.1.50:8123/api/image/serve/{_ID}/original",  # falsches Schema
        f"{_ORIGIN}/api/image/serve/{_ID}/original?x=1",  # Query
        f"{_ORIGIN}/api/image/serve/{_ID}/original#frag",  # Fragment
        f"{_ORIGIN}/api/image/serve/{_ID[:-1]}/original",  # ID zu kurz
        f"{_ORIGIN}/api/image/serve/{_ID.upper()}/original",  # keine Hex-Kleinschreibung
        f"{_ORIGIN}/api/image/serve/{_ID}/original/../../x",  # Pfad-Trick
        f"{_ORIGIN}/api/image/serve/{_ID}/other",  # unbekannte Variante
        f"{_ORIGIN}/x/api/image/serve/{_ID}/original",  # Präfix
        f"/api/image/serve/{_ID}/original",  # relativ
        f"http://user:pw@192.168.1.50:8123/api/image/serve/{_ID}/original",
        "",
        None,
    ],
)
def test_fremde_oder_manipulierte_urls_sind_kein_eigener_upload(url: str | None) -> None:
    assert not ist_eigene_upload_url(url, [_ORIGIN])


def test_ohne_bekannte_origins_ist_nichts_ein_eigener_upload() -> None:
    assert not ist_eigene_upload_url(f"{_ORIGIN}/api/image/serve/{_ID}/original", [])
    assert not ist_eigene_upload_url(f"{_ORIGIN}/api/image/serve/{_ID}/original", ["ungültig"])


# --- F4 (Code Review 2026.9.2): Härtung der syntaktischen Prüfung -----------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost./",
        "http://foo.localhost/",
        "http://127.1/",
        "http://0/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://017700000001/",
        "http://100.64.0.1/",  # CGNAT
        "http://homeassistant/",  # Einzel-Label
        "http://homeassistant.local:8123/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:7f00:1]/",
        "http://0.0.0.0/",
        "http://224.0.0.1/",  # Multicast
        "http://240.0.0.1/",  # reserviert
        "http://169.254.169.254/",
        "http://[fe80::1]/",
        "http://[64:ff9b::7f00:1]/",  # NAT64 auf 127.0.0.1
        "http://[2002:7f00:1::]/",  # 6to4 auf 127.0.0.1
        "http://nas.lan/",
        "http://drucker.internal/",
        "http://router.home.arpa/",
        "http://hof.local./",
        "http://1.2.3.4.5/",  # numerische Endung
        "http://foo.bar.1/",
        "http://a..b/",
    ],
)
def test_f4_interne_ziele_und_unuebliche_schreibweisen_werden_abgelehnt(url: str) -> None:
    assert not ist_sichere_externe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://www.beispiel.ch/hofladen",
        "https://Beispiel.CH./x",  # abschliessender Punkt, Grossschreibung
        "http://8.8.8.8/",
        "https://münchen.example/",
        "http://[2001:4860:4860::8888]/",
        "https://hof-1.example.com:8443/a?b=1",
    ],
)
def test_f4_oeffentliche_ziele_bleiben_erlaubt(url: str) -> None:
    assert ist_sichere_externe_url(url)


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("Beispiel.CH.", "beispiel.ch"),
        ("MÜNCHEN.example", "xn--mnchen-3ya.example"),
        ("a..b", None),
        ("", None),
        (None, None),
    ],
)
def test_normalisiere_hostname(roh: str | None, erwartet: str | None) -> None:
    assert normalisiere_hostname(roh) == erwartet


@pytest.mark.parametrize(
    ("adresse", "erwartet"),
    [
        ("93.184.216.34", True),
        ("2606:2800:220:1::1", True),
        ("127.0.0.1", False),
        ("10.0.0.1", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.1.1", False),
        ("::ffff:10.0.0.1", False),
        ("::ffff:8.8.8.8", True),
        ("kein-ip", False),
    ],
)
def test_ist_oeffentliche_ip(adresse: str, erwartet: bool) -> None:
    assert ist_oeffentliche_ip(adresse) is erwartet


def test_pruefe_aufloesung_verlangt_ausschliesslich_oeffentliche_adressen() -> None:
    assert pruefe_aufloesung(["93.184.216.34"])
    assert not pruefe_aufloesung([])
    assert not pruefe_aufloesung(["93.184.216.34", "127.0.0.1"])  # gemischt
