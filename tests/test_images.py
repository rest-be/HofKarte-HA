"""Tests für die sichere Bildverarbeitung (images.py)."""

from __future__ import annotations

from custom_components.hofkarte.images import (
    get_additional_images,
    get_main_image_url,
    is_valid_image_url,
)
from custom_components.hofkarte.models import Bild


class TestIsValidImageUrl:
    """Tests für die URL-Validierung."""

    def test_valid_https_url(self) -> None:
        """HTTPS URLs sollten akzeptiert werden."""
        assert is_valid_image_url("https://example.com/image.jpg")

    def test_valid_http_url(self) -> None:
        """HTTP URLs sollten akzeptiert werden."""
        assert is_valid_image_url("http://example.com/image.png")

    def test_https_url_with_path_and_query(self) -> None:
        """HTTPS URLs mit Pfad und Query sollten akzeptiert werden."""
        assert is_valid_image_url(
            "https://cdn.example.com/images/farm/12345/main.jpg?size=large&v=1"
        )

    def test_file_url_rejected(self) -> None:
        """file:// URLs sollten abgelehnt werden (Sicherheit)."""
        assert not is_valid_image_url("file:///etc/passwd")
        assert not is_valid_image_url("file://localhost/path/to/image.jpg")

    def test_data_url_rejected(self) -> None:
        """data: URLs sollten abgelehnt werden."""
        assert not is_valid_image_url("data:image/png;base64,iVBORw0KGgoAAAANS...")

    def test_ftp_url_rejected(self) -> None:
        """FTP und andere Protokolle sollten abgelehnt werden."""
        assert not is_valid_image_url("ftp://example.com/image.jpg")

    def test_empty_string_rejected(self) -> None:
        """Leere Strings sollten abgelehnt werden."""
        assert not is_valid_image_url("")

    def test_whitespace_only_rejected(self) -> None:
        """Nur Whitespace sollte abgelehnt werden."""
        assert not is_valid_image_url("   ")
        assert not is_valid_image_url("\t\n")

    def test_none_rejected(self) -> None:
        """None sollte abgelehnt werden."""
        assert not is_valid_image_url(None)

    def test_non_string_rejected(self) -> None:
        """Nicht-Strings sollten abgelehnt werden."""
        assert not is_valid_image_url(123)  # type: ignore
        assert not is_valid_image_url(["https://example.com"])  # type: ignore
        assert not is_valid_image_url({"url": "https://example.com"})  # type: ignore

    def test_url_without_netloc_rejected(self) -> None:
        """URLs ohne Netzwerk-Location sollten abgelehnt werden."""
        assert not is_valid_image_url("https://")
        assert not is_valid_image_url("http://")

    def test_url_with_leading_whitespace_stripped(self) -> None:
        """URLs mit führendem Whitespace sollten nach dem Trimmen validiert werden."""
        assert is_valid_image_url("  https://example.com/image.jpg")

    def test_url_with_trailing_whitespace_stripped(self) -> None:
        """URLs mit nachfolgendem Whitespace sollten nach dem Trimmen validiert werden."""
        assert is_valid_image_url("https://example.com/image.jpg  ")

    def test_malformed_url(self) -> None:
        """Ungültige URLs sollten abgelehnt werden."""
        assert not is_valid_image_url("not a url")
        assert not is_valid_image_url("ht!tp://example.com")


class TestGetMainImageUrl:
    """Tests für die Ermittlung des Hauptbildes."""

    def test_first_valid_image_is_main(self) -> None:
        """Das erste gültige Bild sollte das Hauptbild sein."""
        bilder = (
            Bild(url="https://example.com/image1.jpg", beschreibung="Bild 1"),
            Bild(url="https://example.com/image2.jpg", beschreibung="Bild 2"),
        )
        assert get_main_image_url(bilder) == "https://example.com/image1.jpg"

    def test_skips_invalid_images(self) -> None:
        """Ungültige Bilder sollten übersprungen werden."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Invalid"),
            Bild(url="https://example.com/valid.jpg", beschreibung="Valid"),
        )
        assert get_main_image_url(bilder) == "https://example.com/valid.jpg"

    def test_empty_tuple_returns_none(self) -> None:
        """Ein leeres Tupel sollte None zurückgeben."""
        assert get_main_image_url(()) is None

    def test_all_invalid_images_returns_none(self) -> None:
        """Wenn alle Bilder ungültig sind, sollte None zurückgeben."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Invalid 1"),
            Bild(url="data:image/png;base64,xxx", beschreibung="Invalid 2"),
            Bild(url="", beschreibung="Empty"),
        )
        assert get_main_image_url(bilder) is None

    def test_single_valid_image(self) -> None:
        """Ein einzelnes gültiges Bild sollte das Hauptbild sein."""
        bilder = (Bild(url="https://example.com/only.jpg", beschreibung="Einzig"),)
        assert get_main_image_url(bilder) == "https://example.com/only.jpg"


class TestGetAdditionalImages:
    """Tests für die Ermittlung weiterer (nicht Haupt-)Bilder."""

    def test_leeres_tupel_ergibt_leere_liste(self) -> None:
        assert get_additional_images(()) == []

    def test_einzelnes_bild_ergibt_leere_liste(self) -> None:
        """Gibt es nur ein Bild, ist es das Hauptbild – keine weiteren."""
        bilder = (Bild(url="https://example.com/only.jpg", beschreibung="Einzig"),)
        assert get_additional_images(bilder) == []

    def test_mehrere_bilder_ohne_hauptbild(self) -> None:
        bilder = (
            Bild(url="https://example.com/1.jpg", beschreibung="Eins"),
            Bild(url="https://example.com/2.jpg", beschreibung="Zwei"),
            Bild(url="https://example.com/3.jpg", beschreibung=None),
        )

        weitere = get_additional_images(bilder)

        assert [eintrag["url"] for eintrag in weitere] == [
            "https://example.com/2.jpg",
            "https://example.com/3.jpg",
        ]
        assert weitere[0]["beschreibung"] == "Zwei"
        assert weitere[1]["beschreibung"] is None

    def test_unsichere_weitere_bilder_werden_gefiltert(self) -> None:
        bilder = (
            Bild(url="https://example.com/1.jpg", beschreibung="Haupt"),
            Bild(url="file:///etc/passwd", beschreibung="Unsicher"),
            Bild(url="https://example.com/2.jpg", beschreibung="Sicher"),
        )

        weitere = get_additional_images(bilder)

        assert [eintrag["url"] for eintrag in weitere] == [
            "https://example.com/2.jpg"
        ]

    def test_unsicheres_erstes_bild_wird_nicht_als_weiteres_gezaehlt(self) -> None:
        """Ein unsicheres erstes Bild ist weder Hauptbild noch 'weiteres
        Bild' – es wird komplett ausgeschlossen."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Unsicher"),
            Bild(url="https://example.com/1.jpg", beschreibung="Haupt"),
            Bild(url="https://example.com/2.jpg", beschreibung="Zwei"),
        )

        assert get_main_image_url(bilder) == "https://example.com/1.jpg"
        weitere = get_additional_images(bilder)
        assert [eintrag["url"] for eintrag in weitere] == [
            "https://example.com/2.jpg"
        ]
