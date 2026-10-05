# Drittanbieter-Software (Third-Party Notices)

HofKarte bündelt für die Kartenansicht des Panels zwei JavaScript-Bibliotheken
**unverändert** im Repository (`custom_components/hofkarte/static/vendor/`).
Sie werden von Home Assistant selbst ausgeliefert
(`/api/hofkarte/static/vendor/…`) – es gibt **kein CDN** und keinen
Nachladevorgang von Drittseiten zur Laufzeit (Befund F7 des Code Reviews zu
2026.9.2). Die Kartenkacheln stammen weiterhin von OpenStreetMap
(siehe README/Handbuch, Datenschutz).

| Bibliothek | Version | Lizenz | Urheber | Quelle |
|---|---|---|---|---|
| [Leaflet](https://leafletjs.com) | 1.9.4 | BSD-2-Clause | © 2010–2023 Vladimir Agafonkin, © 2010–2011 CloudMade | npm-Paket `leaflet@1.9.4` (`dist/`) |
| [leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) | 1.5.3 | MIT | © 2012 David Leaver | npm-Paket `leaflet.markercluster@1.5.3` (`dist/`) |

Die vollständigen Lizenztexte liegen neben den Dateien:
`static/vendor/leaflet/LICENSE` und `static/vendor/leaflet.markercluster/LICENSE`.

## Herkunft und Prüfsummen

Die Dateien sind byte-identisch mit dem Inhalt der npm-Pakete
(`npm pack leaflet@1.9.4`, `npm pack leaflet.markercluster@1.5.3`):

| Paketdatei (npm pack) | SHA-256 |
|---|---|
| `leaflet-1.9.4.tgz` | `84c65a256e50657896f54c33bd857b6849ebe94c817803be818bf32a3dde0b77` |
| `leaflet.markercluster-1.5.3.tgz` | `fc6b0b1d00b6c708ae54e43ee4a11ac345e41660e19f0a570190bb35babb1a1c` |

| Datei im Repository | SHA-256 |
|---|---|
| `static/vendor/leaflet/leaflet.js` | `db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a` |
| `static/vendor/leaflet/leaflet.css` | `a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6` |
| `static/vendor/leaflet/images/layers.png` | `1dbbe9d028e292f36fcba8f8b3a28d5e8932754fc2215b9ac69e4cdecf5107c6` |
| `static/vendor/leaflet/images/layers-2x.png` | `066daca850d8ffbef007af00b06eac0015728dee279c51f3cb6c716df7c42edf` |
| `static/vendor/leaflet/images/marker-icon.png` | `574c3a5cca85f4114085b6841596d62f00d7c892c7b03f28cbfa301deb1dc437` |
| `static/vendor/leaflet/images/marker-icon-2x.png` | `00179c4c1ee830d3a108412ae0d294f55776cfeb085c60129a39aa6fc4ae2528` |
| `static/vendor/leaflet/images/marker-shadow.png` | `264f5c640339f042dd729062cfc04c17f8ea0f29882b538e3848ed8f10edb4da` |
| `static/vendor/leaflet.markercluster/leaflet.markercluster.js` | `1e4e1d22972a3926f48598e0caf14e3fe7049835d428a344fed4f9e3665b3508` |
| `static/vendor/leaflet.markercluster/MarkerCluster.css` | `614dea0a98ff3f4ead74f04918f6b1d1b9ba435c25b5fc23b21a394d1e3e4d87` |
| `static/vendor/leaflet.markercluster/MarkerCluster.Default.css` | `61258232d98d64dc2a7b1e02130d67421bc5b9bda5994eef70228ff97570c170` |

## Aktualisieren

1. Neue Version per `npm pack <paket>@<version>` beziehen und die Dateien
   **unverändert** aus `dist/` übernehmen (inkl. Lizenzdatei).
2. Versionen in `static/hofkarte-panel.js` (`LEAFLET_VERSION`,
   `MARKERCLUSTER_VERSION` – sie dienen zugleich als Cache-Busting-Parameter
   `?v=`), die Tabellen oben und das CHANGELOG anpassen.
3. Den Test `test_third_party_notices_nennen_bibliotheken_und_pruefsummen`
   prüft, dass die hier genannten Prüfsummen zu den Dateien passen.
