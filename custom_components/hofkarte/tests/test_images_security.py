"""Tests für die syntaktische Sicherheitsprüfung in images.py.

Bewusst ohne DNS-Mocking: Die Prüfung erfolgt seit dem Bugfix rein
syntaktisch (kein blockierender socket.getaddrinfo-Aufruf mehr, siehe
images.py-Moduldoc).
"""

from custom_components.hofkarte import images
from custom_components.hofkarte.models import Bild


def test_rejects_loopback_ip_literal() -> None:
    assert not images.is_valid_image_url("http://127.0.0.1/img.jpg")


def test_rejects_private_ipv4_literal() -> None:
    assert not images.is_valid_image_url("http://192.168.1.1/img.jpg")


def test_rejects_localhost_hostname() -> None:
    assert not images.is_valid_image_url("http://localhost/img.jpg")


def test_rejects_ipv6_loopback_literal() -> None:
    assert not images.is_valid_image_url("http://[::1]/img.jpg")


def test_rejects_link_local_literal() -> None:
    assert not images.is_valid_image_url("http://169.254.169.254/meta")


def test_accepts_public_domain_host() -> None:
    """Ein gewöhnlicher Domainname wird akzeptiert (keine DNS-Auflösung,
    siehe Moduldoc zu den bewussten Grenzen dieser Prüfung)."""
    assert images.is_valid_image_url("https://example.com/pic.jpg")


def test_rejects_credentials_in_url() -> None:
    assert not images.is_valid_image_url("http://user:pw@example.com/a.jpg")


def test_get_additional_images_excludes_hauptbild_and_unsafe_entries() -> None:
    """Das Hauptbild fehlt in der Liste; unsichere Einträge (IP-Literal,
    privat) werden ebenfalls gefiltert."""
    images_list = (
        Bild(url="https://example.com/1.jpg", beschreibung="one"),
        Bild(url="http://127.0.0.1/x.png", beschreibung="local"),
        Bild(url="https://example.com/2.jpg", beschreibung=None),
    )

    hauptbild = images.get_main_image_url(images_list)
    weitere = images.get_additional_images(images_list)

    assert hauptbild == "https://example.com/1.jpg"
    urls = [eintrag["url"] for eintrag in weitere]
    assert urls == ["https://example.com/2.jpg"]
    assert "http://127.0.0.1/x.png" not in urls
    assert "https://example.com/1.jpg" not in urls


# ---------------------------------------------------------------------------
# hochgeladen=True: Ausnahme für über den geführten Upload erzeugte Bilder
# ---------------------------------------------------------------------------


def test_rejects_private_ip_when_not_hochgeladen() -> None:
    """Ohne hochgeladen=True gilt weiterhin die normale Ablehnung
    (Referenzverhalten, unverändert)."""
    assert not images.is_valid_image_url("http://192.168.1.50:8123/x.jpg")


def test_accepts_private_ip_when_hochgeladen() -> None:
    """Eine private/interne IP-Adresse (typisch für die eigene
    Home-Assistant-Instanz im Heimnetz) muss bei hochgeladen=True
    akzeptiert werden – die Vertrauensbasis ist hier die Herkunft (von
    HofKarte selbst über Home Assistants offiziellen Upload-Weg
    erzeugt), nicht der Adressbereich."""
    url = "http://192.168.1.50:8123/api/image/serve/abc123/original"
    assert images.is_valid_image_url(url, hochgeladen=True)


def test_accepts_localhost_when_hochgeladen() -> None:
    assert images.is_valid_image_url(
        "http://localhost:8123/api/image/serve/abc123/original", hochgeladen=True
    )


def test_hochgeladen_still_rejects_invalid_scheme() -> None:
    """Die Ausnahme betrifft ausschliesslich die Adressbereichs-Prüfung –
    Schema- und Zugangsdaten-Prüfung gelten unverändert auch für
    hochgeladene Bilder (Defense in Depth)."""
    assert not images.is_valid_image_url(
        "file:///etc/passwd", hochgeladen=True
    )
    assert not images.is_valid_image_url(
        "http://user:pw@192.168.1.50/x.jpg", hochgeladen=True
    )


def test_hochgeladen_still_rejects_empty_url() -> None:
    assert not images.is_valid_image_url(None, hochgeladen=True)
    assert not images.is_valid_image_url("", hochgeladen=True)


def test_get_main_image_url_beruecksichtigt_hochgeladen_flag_pro_bild() -> None:
    """get_main_image_url/get_additional_images müssen das hochgeladen-Flag
    JE BILD berücksichtigen (nicht global) – ein extern verlinktes
    Bild mit privater IP bleibt unsicher, auch wenn ein anderes Bild im
    selben Hofladen hochgeladen wurde."""
    images_list = (
        Bild(
            url="http://192.168.1.50:8123/api/image/serve/abc/original",
            hochgeladen=True,
        ),
        Bild(url="http://192.168.1.99/nicht-hochgeladen.jpg", hochgeladen=False),
    )

    hauptbild = images.get_main_image_url(images_list)
    weitere = images.get_additional_images(images_list)

    assert hauptbild == "http://192.168.1.50:8123/api/image/serve/abc/original"
    assert weitere == []  # das zweite, nicht hochgeladene Bild bleibt unsicher


def test_manipuliertes_hochgeladen_flag_umgeht_die_private_ip_pruefung_nicht() -> None:
    """F1 (Regression, Ende-zu-Ende ohne Home Assistant): Rohdaten mit
    ``hochgeladen: true`` auf ein internes Ziel ergeben kein Hauptbild."""
    from custom_components.hofkarte.parsing import parse_hofladen

    hofladen = parse_hofladen(
        {
            "id": "h1",
            "name": "Hof",
            "bilder": [
                {"url": "http://192.168.1.20/relay/0?turn=on", "hochgeladen": True}
            ],
        },
        eigene_origins=["http://192.168.1.50:8123"],
    )

    assert images.get_main_image_url(hofladen.bilder) is None


def test_eigener_upload_bleibt_trotz_privater_ip_ein_gueltiges_hauptbild() -> None:
    from custom_components.hofkarte.parsing import parse_hofladen

    url = "http://192.168.1.50:8123/api/image/serve/0123456789abcdef0123456789abcdef/original"
    hofladen = parse_hofladen(
        {"id": "h1", "name": "Hof", "bilder": [{"url": url}]},
        eigene_origins=["http://192.168.1.50:8123"],
    )

    assert images.get_main_image_url(hofladen.bilder) == url
