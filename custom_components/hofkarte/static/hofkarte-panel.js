/**
 * HofKarte-Verwaltungspanel.
 *
 * Drei Ansichten: Liste (list), Bearbeiten (editor), Details (detail,
 * read-only). Kommuniziert ausschliesslich über die bestehenden
 * WebSocket-Befehle hofkarte/management/list|save|delete – keine neuen
 * Backend-Endpunkte nötig (die Detailansicht liest nur bereits
 * geladene Daten).
 *
 * Koordinaten: Eingabe/Anzeige erfolgt direkt im selben Format, in dem
 * das Backend/Datenmodell speichert (WGS84-Dezimalgrad,
 * ``Hofladen.latitude``/``longitude``) – keine Umrechnung nötig.
 */

function isValidWgs84(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

// Suchradius für die automatische Ermittlung über OpenStreetMap (Issue
// #11) - Werte müssen mit osm_info.py (STANDARD_RADIUS_METER,
// MIN_RADIUS_METER, MAX_RADIUS_METER) übereinstimmen; das Backend
// begrenzt den tatsächlich verwendeten Wert ohnehin serverseitig noch
// einmal (siehe management.ws_osm_info), diese Konstanten steuern nur
// die Eingabegrenzen im Formular.
// An die iOS-App angeglichene Vorgabewerte (Options Flow, siehe
// const.py: DEFAULT_OSM_RADIUS_METER sowie die dortigen
// MIN_RADIUS_METER/MAX_RADIUS_METER in osm_info.py) - der tatsächlich
// dauerhaft gespeicherte Vorgabewert wird beim Laden des Panels über
// "hofkarte/management/settings" ermittelt und ersetzt
// OSM_STANDARD_RADIUS_METER dann als Ausgangswert (siehe load()); diese
// Konstante bleibt als Absicherung, solange die Einstellungen noch nicht
// geladen wurden.
const OSM_STANDARD_RADIUS_METER = 200;
const OSM_MIN_RADIUS_METER = 20;
const OSM_MAX_RADIUS_METER = 2000;

// Umkreis des Dialogs "Hofladen finden" (Discovery) - Werte wie in
// discovery/overpass.py (STANDARD_/MIN_/MAX_RADIUS_METER); das Backend
// begrenzt serverseitig zusätzlich.
// Build-Kennung des Panels, in der Kopfzeile sichtbar: zeigt ohne
// Entwicklerwerkzeuge, welche Panel-Fassung der Browser tatsaechlich geladen
// hat (muss mit manifest.json uebereinstimmen, siehe Test).
const PANEL_BUILD = "2026.10.1-dev.7";
const FINDEN_STANDARD_RADIUS_METER = 2000;
const FINDEN_MIN_RADIUS_METER = 50;
const FINDEN_MAX_RADIUS_METER = 5000;

// Anzahl Symbole der Bewertungsdarstellung (Editor und Detailansicht) -
// Wertebereich 0-5, siehe models.Hofladen.bewertung.
const BEWERTUNG_MAX = 5;

/** Google-Maps-Link für eine WGS84-Koordinate (offizielles URL-Schema,
 * siehe https://developers.google.com/maps/documentation/urls/get-started).
 * Zeigt den Standort nur als Suchergebnis/Pin an (keine Route) – wird
 * ausschliesslich noch im Bearbeitungsformular verwendet, um die gerade
 * eingegebenen Koordinaten zu kontrollieren (siehe mapButton()). */
function googleMapsUrl(lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

/** Zusammengesetzte Adresse eines Hofladens (Strasse, PLZ, Ort, Land),
 * wie sie bereits in Kacheln-/Listenansicht zur Anzeige verwendet wird. */
function zusammengesetzteAdresse(item) {
  return [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
}

/** Routing-Ziel für Google/Apple Maps (Issue #3): Ist eine (nicht-leere)
 * Adresse hinterlegt, hat sie Vorrang vor Koordinaten (Adressen sind für
 * Routenberechnungen i. d. R. präziser als ein einzelner Punkt, siehe
 * Issue-Vorgabe). Erst wenn keine Adresse, aber gültige WGS84-Koordinaten
 * vorhanden sind, werden diese als Ziel verwendet. Ohne beides gibt es
 * kein Routing-Ziel (kein funktionsloser Link). */
function ermittleRoutingZiel(item) {
  const adresse = zusammengesetzteAdresse(item);
  if (adresse) return adresse;
  if (isValidWgs84(item.latitude, item.longitude)) return `${item.latitude},${item.longitude}`;
  return null;
}

/** Google-Maps-Routen-Link (offizielles URL-Schema für Wegbeschreibungen,
 * siehe https://developers.google.com/maps/documentation/urls/get-started#directions-action).
 * ``destination`` akzeptiert sowohl eine Adresse als Freitext als auch
 * ``lat,lon`` – keine eigene Geocoding-Umwandlung nötig. */
function googleMapsRoutenUrl(ziel) {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(ziel)}&travelmode=driving`;
}

/** Apple-Maps-Routen-Link (offizielles URL-Schema, siehe
 * https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html).
 * ``daddr`` akzeptiert ebenfalls Adresse als Freitext oder ``lat,lon``;
 * ``dirflg=d`` wählt eine Autoroute (analog zu Google Maps'
 * ``travelmode=driving``). */
function appleMapsRoutenUrl(ziel) {
  return `https://maps.apple.com/?daddr=${encodeURIComponent(ziel)}&dirflg=d`;
}

// --- Kartenansicht (Issue #2): Leaflet + OpenStreetMap ------------------
//
// Home Assistant bietet keine offizielle, für Custom Panels vorgesehene
// Möglichkeit, eine interaktive Karte mit beliebigen eigenen Markern
// einzubetten (nur die Lovelace-eigene, dashboard-interne Kartenkarte).
// Für eine eingebettete Karte mit mehreren gleichzeitig sichtbaren
// Markern wurde daher bewusst Leaflet + OpenStreetMap gewählt – eine
// dokumentierte, minimal-invasive Ausnahme vom Projektgrundsatz „keine
// neuen Abhängigkeiten“ (siehe docs/architecture.md):
// - keine Build-Pipeline/npm-Abhängigkeit nötig: die fest gepinnte Version
//   liegt als unveränderte Distributionsdatei im Repository
//   (static/vendor/leaflet, THIRD_PARTY_NOTICES.md) und wird von
//   Home Assistant selbst ausgeliefert - bewusst KEIN CDN (Befund F7:
//   keine Lieferketten-Abhängigkeit zur Laufzeit, keine Verbindung zu
//   Dritten ausser den OSM-Kacheln, Betrieb auch ohne Internetzugang
//   zum CDN);
// - kein API-Schlüssel und kein Kartendienst-Konto nötig
//   (OpenStreetMap-Kacheln sind ohne Registrierung nutzbar);
// - BSD-2-Clause-Lizenz, seit vielen Jahren aktiv gewartet, kompakt.
// Wird bewusst erst beim ersten Öffnen der Kartenansicht nachgeladen
// (nicht beim Start des Panels). Für sehr viele Marker (> KARTE_CLUSTER_AB)
// wird zusätzlich leaflet.markercluster (MIT, ebenfalls lokal gebündelt)
// nachgeladen.
const LEAFLET_VERSION = "1.9.4";
const MARKERCLUSTER_VERSION = "1.5.3";
const VENDOR_BASIS = "/api/hofkarte/static/vendor";
const LEAFLET_JS_URL = `${VENDOR_BASIS}/leaflet/leaflet.js?v=${LEAFLET_VERSION}`;
const LEAFLET_CSS_URL = `${VENDOR_BASIS}/leaflet/leaflet.css?v=${LEAFLET_VERSION}`;
const MARKERCLUSTER_JS_URL = `${VENDOR_BASIS}/leaflet.markercluster/leaflet.markercluster.js?v=${MARKERCLUSTER_VERSION}`;
const MARKERCLUSTER_CSS_URLS = [
  `${VENDOR_BASIS}/leaflet.markercluster/MarkerCluster.css?v=${MARKERCLUSTER_VERSION}`,
  `${VENDOR_BASIS}/leaflet.markercluster/MarkerCluster.Default.css?v=${MARKERCLUSTER_VERSION}`,
];
const KARTE_CLUSTER_AB = 200; // ab dieser Markeranzahl wird geclustert (Befund F10)

const skriptPromises = new Map();

/** Ein lokales Skript einmalig per <script>-Tag laden. Mehrfache Aufrufe
 * liefern dasselbe Promise. Schlägt das Laden fehl, wird das fehlerhafte
 * <script>-Element wieder entfernt und das Promise verworfen (kein
 * Wiederverwenden eines kaputten Elements; ein erneuter Versuch ist nur
 * auf ausdrückliche Anforderung möglich - Befund F8). */
function ladeSkript(url, bereit, fehlertext) {
  if (bereit()) return Promise.resolve();
  if (skriptPromises.has(url)) return skriptPromises.get(url);
  const p = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onload = () => (bereit() ? resolve() : (script.remove(), reject(new Error(fehlertext))));
    script.onerror = () => { script.remove(); reject(new Error(fehlertext)); };
    document.head.appendChild(script);
  }).catch((err) => {
    skriptPromises.delete(url);
    throw err;
  });
  skriptPromises.set(url, p);
  return p;
}

/** Leaflet (globale ``L``-Schnittstelle) laden (siehe ladeSkript()). */
function ladeLeaflet() {
  return ladeSkript(LEAFLET_JS_URL, () => !!window.L, "Kartenbibliothek konnte nicht geladen werden.").then(() => window.L);
}

/** leaflet.markercluster laden (setzt Leaflet voraus). */
function ladeMarkercluster() {
  return ladeSkript(MARKERCLUSTER_JS_URL, () => !!(window.L && window.L.markerClusterGroup), "Marker-Clustering konnte nicht geladen werden.");
}

// Eigenes Marker-Icon statt Leaflets Standardbild (Issue #4): Leaflets
// automatische Pfaderkennung (Icon.Default._detectIconPath) erzeugt ein
// Sondierungselement im echten (globalen) document.body und fragt sonst
// document.querySelector('link[href$="leaflet.css"]') ab – beides sieht
// das <link rel="stylesheet"> nicht, das karteAnsicht() innerhalb des
// Shadow DOM dieser Komponente einbindet, da Shadow-DOM-Grenzen für
// Style-Zuordnung wie für querySelector() nicht durchquert werden.
// Ergebnis: Icon.Default.imagePath bleibt leer, das Marker-<img> zeigt
// eine defekte Bildkachel ("?"). Statt Leaflets Bild-basiertes
// Standard-Icon zu reparieren (z. B. über einen absoluten CDN-Bildpfad),
// wird hier bewusst ein eigenes, reines Inline-SVG-Icon (kein zusätzliches
// Bild, kein weiterer Netzwerk-Request) über L.divIcon() erzeugt – analog
// zum bereits im Panel verwendeten Symbolstil (vgl. Sidebar-Icon
// "mdi:store-edit"). Da das erzeugte Markup als Kind des Karten-Containers
// im selben Shadow Root landet, greifen die in styles() definierten
// Regeln (.karte-marker-*) zuverlässig – ganz ohne Shadow-DOM-Falle.
const KARTE_MARKER_GLYPH_PATH = "M20 4H4v2h16V4zm1 10v-2l-1-5H4l-1 5v2h1v6h10v-6h4v6h2v-6h1zm-9 4H6v-4h6v4z";

// Marker-Einfärbung nach Öffnungsstatus (Issue Kartenmarker): analog zur
// bereits bestehenden Status-Einfärbung der Kacheln-/Listenansicht
// (siehe .status-open/.status-closed/.status-unknown in styles()), aber
// bewusst mit eigenen CSS-Klassen statt denselben - die Badge-Farben
// (u. a. Rot für "geschlossen") wären auf einem Kartenmarker deutlich
// schwerer von einem echten Fehler-/Warnhinweis zu unterscheiden; Grau
// ist für "geschlossen" auf der Karte eindeutiger.
function karteMarkerStatusKlasse(geoeffnet) {
  if (geoeffnet === true) return "karte-marker-pin-offen";
  if (geoeffnet === false) return "karte-marker-pin-geschlossen";
  return "karte-marker-pin-unbekannt";
}

function erzeugeKarteMarkerIcon(L, geoeffnet) {
  const html = `<svg class="karte-marker-svg" viewBox="0 0 32 42" width="32" height="42" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path class="karte-marker-pin ${karteMarkerStatusKlasse(geoeffnet)}" d="M16 0C7.163 0 0 7.163 0 16c0 11 16 26 16 26s16-15 16-26C32 7.163 24.837 0 16 0z"/>
    <g transform="translate(8,7) scale(0.8)"><path class="karte-marker-glyph" d="${KARTE_MARKER_GLYPH_PATH}"/></g>
  </svg>`;
  return L.divIcon({
    html,
    className: "karte-marker-icon",
    iconSize: [32, 42],
    iconAnchor: [16, 42],
    popupAnchor: [0, -38],
  });
}

const WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

// Konvention (bereits an anderer Stelle im Projekt verwendet, siehe
// Testsuite): "24 Stunden geöffnet" wird als einzelnes Intervall
// 00:00-23:59 gespeichert. Kein neues Datenmodell-Feld nötig.
const FULL_DAY = { beginn: "00:00", ende: "23:59" };
// Befund F1 (Code Review 2026.9.2): Eine Bild-ID wird nur aus einer URL des
// **eigenen Origins** im exakten Muster des eigenen Uploads
// (/api/image/serve/<32 Hex>/original|BxH) gewonnen. Sonst könnte ein
// manipulierter Datensatz (fremde URL mit gleichem Pfad) das Löschen
// beliebiger Home-Assistant-Bild-IDs über "image/delete" auslösen.
// Rein und ohne DOM, damit sie isoliert testbar ist.
function eigeneUploadImageId(url, eigenerOrigin) {
  if (typeof url !== "string" || !eigenerOrigin) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch (err) {
    return null;
  }
  if (parsed.origin !== eigenerOrigin) return null;
  if (parsed.search || parsed.hash || parsed.username || parsed.password) return null;
  const treffer = /^\/api\/image\/serve\/([0-9a-f]{32})\/(?:original|\d{1,4}x\d{1,4})$/.exec(parsed.pathname);
  return treffer ? treffer[1] : null;
}

// Befund F14 (Code Review 2026.9.2): In Kacheln/Listen/Editor werden eigene
// Uploads als 256x256-Vorschau geladen (Home Assistant erzeugt sie beim
// ersten Abruf), das Original nur in der Detailansicht. Fremde URLs bleiben
// unverändert. Rein und ohne DOM.
const VORSCHAU_GROESSE = 256;
function uploadVorschauUrl(url, eigenerOrigin, groesse = VORSCHAU_GROESSE) {
  const id = eigeneUploadImageId(url, eigenerOrigin);
  return id ? `${eigenerOrigin}/api/image/serve/${id}/${groesse}x${groesse}` : url;
}

// Befund F12 (Code Review 2026.9.2): Defense in Depth im Panel. Alle Funktionen
// sind rein (kein DOM) und isoliert testbar.

// Muss mit const.py übereinstimmen (MAX_IMPORT_EINTRAEGE).
const IMPORT_MAX_BYTES = 2 * 1024 * 1024;
const IMPORT_MAX_EINTRAEGE = 500;

const UNSICHERE_HOST_ENDUNGEN = [".localhost", ".local", ".internal", ".lan", ".home.arpa", ".localdomain"];

function istOeffentlicheIpv4(hostname) {
  const teile = hostname.split(".");
  if (teile.length !== 4 || !teile.every((t) => /^\d{1,3}$/.test(t))) return null; // keine IPv4
  const [a, b, c] = teile.map(Number);
  if (teile.some((t) => Number(t) > 255)) return false;
  if (a === 0 || a === 10 || a === 127 || a >= 224) return false;
  if (a === 100 && b >= 64 && b <= 127) return false; // CGNAT
  if (a === 169 && b === 254) return false;
  if (a === 172 && b >= 16 && b <= 31) return false;
  if (a === 192 && b === 168) return false;
  if (a === 192 && b === 0 && c === 0) return false;
  if (a === 198 && (b === 18 || b === 19)) return false;
  return true;
}

// Spiegelt die Backend-Prüfung (url_sicherheit.py) in kleinem Umfang: nur
// http(s), keine Zugangsdaten, keine internen Hostnamen und keine
// nicht öffentlichen IP-Adressen. Die URL-Klasse normalisiert unübliche
// IPv4-Schreibweisen (127.1, 2130706433, 0x7f000001) bereits zu 127.0.0.1.
// Upload-URLs des eigenen Origins (Muster des eigenen Uploads) sind erlaubt.
function istSichereBildUrl(url, eigenerOrigin) {
  if (typeof url !== "string" || !url.trim()) return false;
  let parsed;
  try {
    parsed = new URL(url.trim());
  } catch (err) {
    return false;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
  if (parsed.username || parsed.password) return false;
  if (eigenerOrigin && parsed.origin === eigenerOrigin && !parsed.search && !parsed.hash
      && /^\/api\/image\/serve\/[0-9a-f]{32}\/(?:original|\d{1,4}x\d{1,4})$/.test(parsed.pathname)) {
    return true;
  }
  let host = parsed.hostname.toLowerCase();
  if (host.endsWith(".")) host = host.slice(0, -1);
  if (!host) return false;
  if (host.startsWith("[")) {
    // IPv6: nur globale Unicast-Adressen (2000::/3), kein 6to4/Dokumentationsnetz.
    const m = /^\[([0-9a-f]{1,4})[:\]]/.exec(host);
    if (!m) return false;
    const erstes = parseInt(m[1], 16);
    return erstes >= 0x2000 && erstes <= 0x3fff && erstes !== 0x2002 && host !== "[2001:db8::]";
  }
  const ipv4 = istOeffentlicheIpv4(host);
  if (ipv4 !== null) return ipv4;
  if (host === "localhost" || UNSICHERE_HOST_ENDUNGEN.some((e) => host.endsWith(e))) return false;
  if (!host.includes(".")) return false; // Einzel-Label-Host
  const letztes = host.slice(host.lastIndexOf(".") + 1);
  if (/^\d+$/.test(letztes) || letztes.startsWith("0x")) return false;
  return true;
}

// Spiegelt parsing.py (_EMAIL_REGEX): genau ein "@", kein Leerraum, keines
// der Zeichen ? & % # < > " ' , ; - verhindert eingeschleuste mailto-Parameter.
const EMAIL_MUSTER = /^[^@\s?&%#<>"',;]+@[^@\s?&%#<>"',;]+$/;
function istGueltigeEmail(email) {
  return typeof email === "string" && email.length <= 254 && EMAIL_MUSTER.test(email);
}

function isFullDay(row) { return row.beginn === FULL_DAY.beginn && row.ende === FULL_DAY.ende; }

class HofkartePanel extends HTMLElement {
  constructor() {
    super();
    this.hass = null;
    this.items = [];
    this.editing = null;
    this.viewing = null;
    this.message = "";
    this.error = "";
    this.showCoordInfo = false;
    this.uebersichtsAnsicht = "kacheln"; // "kacheln" | "liste" | "karte" (Issue #1/#2)
    this.listenSortSpalte = null; // "name" | "adresse" | "geoeffnet"
    this.listenSortRichtung = "asc"; // "asc" | "desc"
    this.listenFilter = ""; // Freitextfilter in der Listenansicht
    this.karteNurGeoeffnet = false; // Checkbox "nur aktuell geöffnete Hofläden" (Issue #2)
    this.karteFehler = ""; // Fehlermeldung beim Laden der Kartenbibliothek (Issue #2)
    this._leafletMap = null; // aktive Leaflet-Karteninstanz, ausserhalb des normalen Render-Zyklus verwaltet; lebt, solange die Kartenansicht offen ist (Befund F10)
    this._leafletResizeHandler = null;
    this._karteHost = null; // dauerhafter Karten-Container (wird bei jedem render() nur in den neuen Platzhalter umgehängt, die Karte selbst bleibt bestehen)
    this._markerLayer = null; // aktuelle Marker-Ebene; bei Filteränderung wird nur sie getauscht
    this._markerSignatur = ""; // erkennt, ob sich die dargestellten Marker überhaupt geändert haben
    this._karteToken = 0; // verwirft Ergebnisse veralteter initKarte()-Läufe
    this._filterTimer = null; // Debounce für den Listenfilter
    this._sortSchluessel = new WeakMap(); // vorberechnete Such-/Sortierschlüssel je Hofladen-Objekt (Befund F10)
    this._loadFailed = false; // Laden schlug fehl: kein erneuter Versuch bei jeder hass-Änderung (Befund F9)
    this._loadVersuche = 0;
    this._loadTimer = null; // Backoff-Timer für den automatischen Wiederholversuch
    this.auswahl = new Set(); // ausgewählte Hofladen-IDs für den Export (Issue #5)
    this.importDialog = null; // { eintraege, entscheidungen: Map<bestehende_id, "aktualisieren"|"ueberspringen"> } - nicht null während der Duplikat-Konfliktlösung eines Imports (Issue #5)
    this.webseiteInfoVorschlag = null; // vom Server ermittelte, ggf. aus beiden Quellen zusammengeführte Vorschlagsdaten, bis sie im Bestätigungs-Popup übernommen/verworfen werden (Issue #9/#10). Seit Issue #11 immer das Ergebnis von ermittleAutomatisch() - unabhängig davon, ob es aus der Website, aus OpenStreetMap oder aus beiden Quellen zusammengeführt stammt (siehe mischeAutoVorschlaege()).
    this.autoErmittlungStatusText = ""; // Statusmeldung neben "🔍 Angaben automatisch ermitteln" (Issue #11, ersetzt die bisher getrennten webseiteInfoStatusText/osmInfoStatusText) - in this.* gehalten statt nur im DOM, da render() (u. a. beim Öffnen/Schliessen des Popups) das Formular sonst aus this.editing neu aufbaut und eine rein im DOM gesetzte Meldung dabei verloren ginge (Issue #9)
    this.autoErmittlungStatusKind = ""; // "" | "success" | "error", passend zu autoErmittlungStatusText
    this.autoErmittlungQuellen = null; // { feldname: "website"|"osm"|"beide" } für die im Bestätigungs-Popup angezeigte Quellenkennzeichnung (Issue #11, 5.1), solange this.webseiteInfoVorschlag aus mehr als einer Quelle stammt - sonst null (keine Kennzeichnung nötig).
    this.osmOrteAuswahl = null; // Liste der von der Overpass API gefundenen Treffer, solange mehr als einer gefunden wurde und noch keiner ausgewählt ist (Issue #10, "Ort in der Nähe suchen"); bei genau einem Treffer wird die Auswahlliste übersprungen und direkt this.webseiteInfoVorschlag gesetzt.
    this.osmRadius = OSM_STANDARD_RADIUS_METER; // Im Formular eingestellter Suchradius für OpenStreetMap (Issue #11) - wird wie alle übrigen Formularfelder über erfasseFormularZustand() vor jedem Re-Render gesichert, damit ein bereits geänderter Wert nicht verloren geht. Initialisiert aus den dauerhaft gespeicherten Einstellungen (Options Flow, siehe ladeEinstellungen()), OSM_STANDARD_RADIUS_METER dient nur als Absicherung, bis diese geladen sind.
    this._osmRadiusVorgabe = OSM_STANDARD_RADIUS_METER; // Dauerhaft gespeicherter Vorgabewert (Options Flow) - im Unterschied zu this.osmRadius, das pro Formularsitzung geändert werden kann, ist dies der Wert, auf den start() jedes neue Formular zurücksetzt.
    this._einstellungenGeladen = false; // Verhindert, dass ein bereits von der Nutzerin/dem Nutzer geänderter Sortier-/Radius-Wert durch einen erneuten load() (z. B. nach dem Speichern) überschrieben wird.
    this.finden = null; // Zustand des Dialogs "Hofladen finden" (Discovery, Phase 5); null = geschlossen
    this._findenUnsub = null; // Abmeldefunktion der laufenden enrich-Subscription
    this._findenTimer = null; // Zeitlimit der Anreicherung
    this._findenStandortToken = 0; // verwirft veraltete Geolocation-Antworten
    this._quellenSchnappschuss = {}; // Feld -> Wert bei der Übernahme (erkennt spätere manuelle Änderungen, siehe bereinigteQuellen())
    this._wartendesWebseiteErgebnis = null; // Zwischengespeichertes Website-Ergebnis, während die OSM-Trefferauswahl (mehrere Treffer) noch offen ist (Issue #11, siehe ermittleAutomatisch()/waehleOsmOrt()).
    this.attachShadow({ mode: "open" });
    // Das Stylesheet wird genau einmal angelegt (Befund F10); render()
    // ersetzt nur noch den Inhalt von <main>.
    this._styleEl = document.createElement("style");
    this._styleEl.textContent = this.styles();
    this._mainEl = document.createElement("main");
    this.shadowRoot.append(this._styleEl, this._mainEl);
    this.bindDelegiert();
  }

  set hass(value) {
    this._hass = value;
    // Nach einem Fehlschlag (this._loadFailed) wird NICHT bei jeder
    // Zustandsänderung von Home Assistant neu geladen (Befund F9): ein
    // neuer Versuch erfolgt über den Backoff-Timer oder den Button.
    if (this.isConnected && !this._loaded && !this._loadFailed) this.load();
  }
  get hass() { return this._hass; }

  connectedCallback() {
    this._loadFailed = false;
    this.render();
    if (this.hass) this.load();
  }
  disconnectedCallback() {
    clearTimeout(this._loadTimer); this._loadTimer = null;
    clearTimeout(this._filterTimer); this._filterTimer = null;
    this._karteToken++;
    this.teardownKarte();
  }

  async call(type, payload = {}) {
    return this.hass.connection.sendMessagePromise({ type, ...payload });
  }

  /** Dauerhaft gespeicherte Einstellungen (Options Flow, siehe
   * config_flow.HofKarteOptionsFlow / management.ws_settings) laden und
   * als Vorgabewerte übernehmen - einmalig pro Panel-Sitzung (siehe
   * this._einstellungenGeladen), damit ein bereits von der Nutzerin/dem
   * Nutzer geänderter Sortier- oder Radius-Wert durch ein erneutes
   * load() (z. B. nach dem Speichern eines Hofladens) nicht
   * stillschweigend zurückgesetzt wird. Ein Fehler beim Laden (z. B.
   * HofKarte noch nicht bereit) verhindert bewusst nicht das Laden der
   * eigentlichen Hofladen-Liste - die eingebauten Konstanten
   * (OSM_STANDARD_RADIUS_METER u. Ä.) bleiben dann als Fallback. */
  async ladeEinstellungen() {
    if (this._einstellungenGeladen) return;
    try {
      const result = await this.call("hofkarte/management/settings");
      const einstellungen = result.einstellungen || {};
      this.listenSortSpalte = einstellungen.listen_sort_spalte || this.listenSortSpalte;
      this.listenSortRichtung = einstellungen.listen_sort_richtung || this.listenSortRichtung;
      if (typeof einstellungen.osm_radius_meter === "number") {
        this._osmRadiusVorgabe = einstellungen.osm_radius_meter;
        this.osmRadius = einstellungen.osm_radius_meter;
      }
    } catch (err) {
      console.warn("Einstellungen konnten nicht geladen werden:", err);
    } finally {
      this._einstellungenGeladen = true;
    }
  }

  async load() {
    if (!this.hass || this._loading) return;
    this._loading = true;
    try {
      await this.ladeEinstellungen();
      const result = await this.call("hofkarte/management/list");
      this.items = result.hoflaeden || [];
      this._loaded = true;
      this._loadFailed = false;
      this._loadVersuche = 0;
      clearTimeout(this._loadTimer); this._loadTimer = null;
      this.message = "";
      this.error = "";
      // Detailansicht mit aktualisierten Daten synchron halten, falls
      // gerade ein Hofladen betrachtet wird (z. B. nach externer Änderung).
      if (this.viewing) {
        const aktuell = this.items.find((x) => x.id === this.viewing.id);
        this.viewing = aktuell || null;
      }
      this.render();
    } catch (err) {
      this.error = err?.message || "Die Hofläden konnten nicht geladen werden.";
      this.planeLadeWiederholung();
      this.render();
    } finally { this._loading = false; }
  }

  /** Nach einem Ladefehler nicht in einer Schleife neu laden (Befund F9):
   * ``_loadFailed`` sperrt die Auslösung über ``set hass``; ein einzelner
   * Wiederholversuch erfolgt mit exponentiellem Backoff (2 s, 4 s, … max.
   * 60 s) oder sofort über den Button "Erneut versuchen". */
  planeLadeWiederholung() {
    this._loadFailed = true;
    this._loadVersuche += 1;
    clearTimeout(this._loadTimer);
    if (!this.isConnected) return;
    const wartezeit = Math.min(60000, 2000 * 2 ** (this._loadVersuche - 1));
    this._loadTimer = setTimeout(() => this.ladeErneut(), wartezeit);
  }

  ladeErneut() {
    clearTimeout(this._loadTimer); this._loadTimer = null;
    this._loadFailed = false;
    if (this.isConnected && this.hass) this.load();
  }

  empty() {
    return { id: "", name: "", beschreibung: "", bemerkung: "", adresse: "", plz: "", ort: "", land: "", website: "", mobilnummer: "", email: "", latitude: "", longitude: "", oeffnungszeiten: [], sonderoeffnungszeiten: [], angebote: [], zahlungsarten: [], bilder: [], quellen: [], bewertung: 0 };
  }

  clone(item) { return JSON.parse(JSON.stringify(item)); }

  async save() {
    const data = this.formData();
    try {
      this.validate(data);
      await this.call("hofkarte/management/save", { hofladen: data });
      this.message = "Änderungen gespeichert.";
      this.editing = null;
      await this.load();
    } catch (err) { this.error = err?.message || "Speichern fehlgeschlagen."; this.render(); }
  }

  validate(d) {
    if (!d.name.trim()) throw new Error("Name darf nicht leer sein.");
    if (d.latitude !== null && d.latitude !== "" && (d.latitude < -90 || d.latitude > 90)) throw new Error("Latitude muss zwischen -90 und 90 liegen.");
    if (d.longitude !== null && d.longitude !== "" && (d.longitude < -180 || d.longitude > 180)) throw new Error("Longitude muss zwischen -180 und 180 liegen.");
    for (const row of d.oeffnungszeiten) if (!row.beginn || !row.ende || row.beginn === row.ende) throw new Error("Öffnungszeiten enthalten ungültige oder unvollständige Zeiten.");
    if (d.website && d.website.trim() && !this.isPlausibleUrl(d.website.trim())) throw new Error("Die Webseite muss eine gültige http(s)-Adresse sein (z. B. https://www.beispiel.ch).");
  }

  isPlausibleUrl(value) {
    try {
      const url = new URL(value.match(/^https?:\/\//i) ? value : `https://${value}`);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch { return false; }
  }

  /** WGS84-Koordinatenfelder auslesen. Da Eingabe und Speicherformat
   * identisch sind (beide WGS84-Dezimalgrad), ist keine Umrechnung
   * nötig – die Werte werden nur validiert. */
  resolveCoordinates(f) {
    const latRaw = f.elements["latitude"]?.value ?? "";
    const lonRaw = f.elements["longitude"]?.value ?? "";
    if (latRaw === "" && lonRaw === "") return { latitude: null, longitude: null };

    const lat = Number(latRaw);
    const lon = Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      throw new Error("Latitude/Longitude müssen Zahlen sein.");
    }
    if (!isValidWgs84(lat, lon)) {
      throw new Error("Latitude muss zwischen -90 und 90 und Longitude zwischen -180 und 180 liegen.");
    }
    return { latitude: lat, longitude: lon };
  }

  /** Kartenlogik für das Bearbeitungsformular (editor()). Öffnet Google
   * Maps anhand der gerade eingegebenen WGS84-Koordinaten in einem neuen
   * Tab, um die Eingabe zu kontrollieren – verändert keine Daten (rein
   * lesender externer Link), keine neue Abhängigkeit. Die Detail-,
   * Kacheln- und Listenansicht verwenden stattdessen die Routing-Auswahl
   * (routingAuswahl(), Issue #3), da es dort um Navigation zum Hofladen
   * geht statt um Eingabekontrolle. */
  mapButton(lat, lon) {
    if (!isValidWgs84(lat, lon)) {
      return `<button type="button" class="map-btn" disabled title="Keine gültigen Koordinaten hinterlegt">🗺️ Auf Google Maps anzeigen</button>`;
    }
    const url = googleMapsUrl(lat, lon);
    return `<a class="map-btn" href="${this.escAttr(url)}" target="_blank" rel="noopener noreferrer" title="Standort auf Google Maps anzeigen (neuer Tab)">🗺️ Auf Google Maps anzeigen</a>`;
  }

  /** Kompakte Routing-Auswahl (Issue #3) für Kacheln-, Listen- und
   * Detailansicht: öffnet eine echte Wegbeschreibung (nicht nur einen
   * Standort-Pin) vom aktuellen Standort zum Hofladen, wahlweise in
   * Google Maps oder Apple Maps. Adresse hat Vorrang vor Koordinaten
   * (siehe ermittleRoutingZiel()). Bewusst als zwei sehr kompakte,
   * icon-only Buttons statt eines einzelnen Buttons mit ausklappbarem
   * Menü umgesetzt: das braucht keinen zusätzlichen Interaktions-/
   * Zustands-Code (kein Öffnen/Schliessen, kein Klick-ausserhalb-
   * Handling) und beansprucht dennoch weniger horizontalen Platz als
   * der bisherige einzelne Textbutton. */
  routingAuswahl(item) {
    const ziel = ermittleRoutingZiel(item);
    if (!ziel) {
      return `<span class="route-actions" title="Keine Adresse oder gültigen Koordinaten hinterlegt">
        <button type="button" class="route-btn" disabled aria-label="Route in Google Maps öffnen">🗺️</button>
        <button type="button" class="route-btn" disabled aria-label="Route in Apple Maps öffnen">🧭</button>
      </span>`;
    }
    const googleUrl = googleMapsRoutenUrl(ziel);
    const appleUrl = appleMapsRoutenUrl(ziel);
    return `<span class="route-actions">
      <a class="route-btn" href="${this.escAttr(googleUrl)}" target="_blank" rel="noopener noreferrer" title="Route in Google Maps öffnen" aria-label="Route in Google Maps öffnen">🗺️</a>
      <a class="route-btn" href="${this.escAttr(appleUrl)}" target="_blank" rel="noopener noreferrer" title="Route in Apple Maps öffnen" aria-label="Route in Apple Maps öffnen">🧭</a>
    </span>`;
  }

  // --- Bilder: geführter Upload -----------------------------------------
  //
  // Nutzt Home Assistants eigene image_upload-Komponente
  // (POST /api/image/upload, Serve unter /api/image/serve/<id>/original,
  // Löschen über den WebSocket-Befehl "image/delete") statt eines
  // eigenen Upload-Endpunkts. Die serverseitige Validierung (erlaubte
  // Formate, maximale Grösse) übernimmt diese Home-Assistant-Komponente
  // vollständig; die Prüfung hier dient nur dem sofortigen, direkten
  // Feedback vor dem eigentlichen Upload.

  static UPLOAD_MAX_BYTES = 10 * 1024 * 1024; // entspricht image_upload.MAX_SIZE
  static UPLOAD_ERLAUBTE_TYPEN = ["image/jpeg", "image/png", "image/gif"];

  extractImageId(url) {
    return eigeneUploadImageId(url, window.location.origin);
  }

  setUploadStatus(text, kind = "") {
    const el = this.shadowRoot.querySelector("[data-upload-status]");
    if (!el) return;
    el.textContent = text;
    el.className = `upload-status muted${kind ? " " + kind : ""}`;
  }

  async uploadBild(file) {
    if (!file) return;

    if (!HofkartePanel.UPLOAD_ERLAUBTE_TYPEN.includes(file.type)) {
      this.setUploadStatus("Nicht unterstütztes Dateiformat. Erlaubt: JPEG, PNG, GIF.", "error");
      return;
    }
    if (file.size > HofkartePanel.UPLOAD_MAX_BYTES) {
      this.setUploadStatus("Datei ist zu gross (maximal 10 MB erlaubt).", "error");
      return;
    }

    this.setUploadStatus(`„${file.name}“ wird hochgeladen …`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      // Home Assistants /api/*-Endpunkte erfordern eine Authentifizierung
      // per Bearer-Token (kein Cookie-basiertes Login) – ohne den
      // Authorization-Header schlägt der Upload mit "invalid
      // authentication" fehl, obwohl man in der Oberfläche angemeldet
      // ist. this.hass.auth.accessToken wird vom Frontend automatisch
      // aktuell gehalten (Token-Refresh), siehe auch this.call(), das für
      // WebSocket-Befehle bereits über dieselbe hass-Verbindung läuft.
      const response = await fetch("/api/image/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${this.hass.auth.accessToken}` },
        body: formData,
      });
      if (response.status === 401) {
        throw new Error("Anmeldung abgelaufen. Bitte Seite neu laden und erneut versuchen.");
      }
      if (!response.ok) {
        throw new Error(response.status === 413 ? "Datei ist zu gross." : `Upload fehlgeschlagen (${response.status}).`);
      }
      const ergebnis = await response.json();
      const url = `${window.location.origin}/api/image/serve/${ergebnis.id}/original`;

      if (!this.editing.bilder) this.editing.bilder = [];
      this.editing.bilder.push({ url, beschreibung: null, hochgeladen: true });
      this.setUploadStatus(`„${file.name}“ erfolgreich hochgeladen.`, "success");
      this.render();
    } catch (err) {
      this.setUploadStatus(err?.message || "Upload fehlgeschlagen.", "error");
    }
  }

  async removeBild(index) {
    if (!this.editing.bilder) this.editing.bilder = [];
    const bild = this.editing.bilder[index];
    if (!bild) return;

    if (bild.hochgeladen) {
      const imageId = this.extractImageId(bild.url);
      if (imageId) {
        try {
          await this.call("image/delete", { image_id: imageId });
        } catch (err) {
          // Die zugrunde liegende Datei liess sich nicht bereinigen
          // (z. B. bereits anderweitig gelöscht) - das Bild wird trotzdem
          // aus dem Hofladen entfernt, um die Nutzerin/den Nutzer nicht
          // zu blockieren; kein Datenverlust an Hofladen-Seite dadurch.
          console.warn("Hochgeladenes Bild konnte nicht bereinigt werden:", err);
        }
      }
    }

    this.editing.bilder.splice(index, 1);
    this.render();
  }

  setHauptbild(index) {
    const bilder = this.editing.bilder || [];
    if (index <= 0 || index >= bilder.length) return;
    const [gewaehltes] = bilder.splice(index, 1);
    bilder.unshift(gewaehltes);
    this.render();
  }

  /** Setzt die Statusmeldung neben "🔍 Angaben automatisch ermitteln"
   * (Issue #11, ersetzt die bisher getrennten setWebseiteInfoStatus()/
   * setOsmInfoStatus()). Wird bewusst sowohl im Zustand
   * (this.autoErmittlungStatusText/-Kind) als auch – für sofortiges
   * Feedback ohne einen vollständigen Re-Render auszulösen – direkt im
   * bereits vorhandenen DOM-Element gehalten (Issue #9): render() baut
   * editor() komplett neu auf und übernimmt die Meldung dabei aus dem
   * Zustand (siehe editor()), eine rein im DOM gesetzte Meldung würde vom
   * nächsten Render sonst überschrieben, bevor die Benutzerin/der Benutzer
   * sie überhaupt lesen konnte. */
  setAutoErmittlungStatus(text, kind = "") {
    this.autoErmittlungStatusText = text;
    this.autoErmittlungStatusKind = kind;
    const el = this.shadowRoot.querySelector("[data-auto-info-status]");
    if (!el) return;
    el.textContent = text;
    el.className = `webseite-info-status muted${kind ? " " + kind : ""}`;
  }

  /** Fehlermeldungen für die drei in Issue #8 geforderten Fehlerfälle der
   * Website-Quelle, passend zu den Fehlercodes aus
   * management.ws_webseite_info. */
  static WEBSEITE_INFO_FEHLERMELDUNGEN = {
    invalid_url: "Bitte eine gültige, erreichbare Website-Adresse eingeben.",
    unreachable: "Die Website konnte nicht erreicht oder nicht gelesen werden.",
    not_found: "Auf der Website wurden keine verwertbaren Informationen gefunden.",
  };

  /** Fehlermeldungen für die drei Fehlerfälle der OSM-Quelle aus
   * management.ws_osm_info (Issue #10, siehe osm_info.py für die
   * jeweilige Bedeutung). */
  static OSM_INFO_FEHLERMELDUNGEN = {
    invalid_coordinates: "Bitte zuerst gültige Latitude-/Longitude-Werte eintragen.",
    unreachable: "Die Overpass API (OpenStreetMap) konnte nicht erreicht werden.",
    not_found: "Im Umkreis wurden keine Orte gefunden.",
  };

  /** Übersetzt einen von der Overpass API gefundenen Ort (osm_info.py,
   * OsmOrt) in dieselbe Vorschlags-Form, die auch webseiteInfoPopup()/
   * uebernehmeWebseiteInfo() für Website-Vorschläge verwenden (Issue #10,
   * Anforderung 5.3: Popup wiederverwenden statt duplizieren) - beide
   * Quellen teilen bereits dieselben Feldnamen (name/adresse/plz/ort/
   * website/oeffnungszeiten), eine Umbenennung ist dafür nicht nötig. */
  osmOrtZuVorschlag(ort) {
    return {
      name: ort.name || null,
      adresse: ort.adresse || null,
      plz: ort.plz || null,
      ort: ort.ort || null,
      website: ort.website || null,
      mobilnummer: ort.mobilnummer || null,
      email: ort.email || null,
      oeffnungszeiten: ort.oeffnungszeiten || [],
    };
  }

  /** Fragt die Website-Quelle ab (Issue #8/#9) und liefert ein
   * einheitliches Ergebnisobjekt statt selbst Status/Popup zu setzen -
   * wird seit Issue #11 ausschliesslich von ermittleAutomatisch()
   * aufgerufen, das beide Quellen zusammenführt. */
  async holeWebseiteVorschlag(website) {
    try {
      const result = await this.call("hofkarte/management/webseite_info", { website });
      return { ok: true, vorschlag: result.info || {} };
    } catch (err) {
      const meldung = HofkartePanel.WEBSEITE_INFO_FEHLERMELDUNGEN[err?.code]
        || err?.message || "Informationen konnten nicht ermittelt werden.";
      return { ok: false, meldung };
    }
  }

  /** Fragt die OSM-Quelle ab (Issue #10) und liefert ein einheitliches
   * Ergebnisobjekt (ggf. mit mehreren Treffern zur Auswahl) - analog zu
   * holeWebseiteVorschlag(), ebenfalls seit Issue #11 nur noch von
   * ermittleAutomatisch() aufgerufen. */
  async holeOsmOrte(latitude, longitude, radius) {
    try {
      const result = await this.call("hofkarte/management/osm_info", { latitude, longitude, radius });
      return { ok: true, orte: result.orte || [] };
    } catch (err) {
      const meldung = HofkartePanel.OSM_INFO_FEHLERMELDUNGEN[err?.code]
        || err?.message || "Es konnten keine Orte ermittelt werden.";
      return { ok: false, meldung };
    }
  }

  /** Führt Website- und OSM-Vorschlag zu einem gemeinsamen Vorschlag
   * zusammen (Issue #11, 5.1 - ersetzt zwei getrennte Aktionen durch
   * eine). Bei einem Konflikt (beide Quellen liefern einen Wert für
   * dasselbe Feld, aber unterschiedlich) hat die Website-Quelle Vorrang
   * (i. d. R. die vom Betreiber selbst gepflegte, genauere Angabe); der
   * abweichende OSM-Wert wird dabei NICHT stillschweigend verworfen,
   * sondern bleibt im zurückgegebenen "quellen"-Objekt nachvollziehbar
   * (aktuell nur zur Kennzeichnung im Popup genutzt, siehe
   * webseiteInfoPopup()) - "lieber nichts als falsch" gilt auch für das
   * Verwerfen abweichender Angaben. */
  mischeAutoVorschlaege(websiteVorschlag, osmVorschlag) {
    const ziel = {};
    const quellen = {};

    for (const feld of ["name", "beschreibung", "adresse", "plz", "ort", "land", "website", "mobilnummer", "email"]) {
      const w = websiteVorschlag?.[feld];
      const o = osmVorschlag?.[feld];
      if (w) {
        ziel[feld] = w;
        quellen[feld] = (o && o !== w) ? "website+osm" : "website";
      } else if (o) {
        ziel[feld] = o;
        quellen[feld] = "osm";
      }
    }

    if (Array.isArray(websiteVorschlag?.oeffnungszeiten) && websiteVorschlag.oeffnungszeiten.length) {
      ziel.oeffnungszeiten = websiteVorschlag.oeffnungszeiten;
      quellen.oeffnungszeiten = "website";
    } else if (Array.isArray(osmVorschlag?.oeffnungszeiten) && osmVorschlag.oeffnungszeiten.length) {
      ziel.oeffnungszeiten = osmVorschlag.oeffnungszeiten;
      quellen.oeffnungszeiten = "osm";
    }

    for (const feld of ["angebote", "zahlungsarten"]) {
      const wListe = Array.isArray(websiteVorschlag?.[feld]) ? websiteVorschlag[feld] : [];
      const oListe = Array.isArray(osmVorschlag?.[feld]) ? osmVorschlag[feld] : [];
      const kombiniert = [...wListe, ...oListe];
      if (kombiniert.length) {
        ziel[feld] = kombiniert;
        quellen[feld] = (wListe.length && oListe.length) ? "website+osm" : (wListe.length ? "website" : "osm");
      }
    }

    return { vorschlag: ziel, quellen };
  }

  /** Führt die Ergebnisse beider Quellen zusammen: öffnet bei mindestens
   * einem Treffer das gemeinsame Bestätigungs-Popup (mit Quellen-
   * Kennzeichnung, falls beide Quellen etwas beigetragen haben), setzt
   * andernfalls eine kombinierte Fehlermeldung, die beide fehlgeschlagenen
   * Quellen benennt statt nur die zuletzt geprüfte (Issue #11, 5.1). */
  zeigeAutoErgebnis(websiteErgebnis, osmErgebnis, osmVorschlag) {
    const websiteVorschlag = websiteErgebnis?.ok ? websiteErgebnis.vorschlag : null;

    if (!websiteVorschlag && !osmVorschlag) {
      const teile = [];
      if (websiteErgebnis && !websiteErgebnis.ok) teile.push(`Website: ${websiteErgebnis.meldung}`);
      if (osmErgebnis && !osmErgebnis.ok) teile.push(`OpenStreetMap: ${osmErgebnis.meldung}`);
      this.setAutoErmittlungStatus(teile.join(" ") || "Es wurden keine Angaben gefunden.", "error");
      this.render();
      return;
    }

    const { vorschlag, quellen } = this.mischeAutoVorschlaege(websiteVorschlag, osmVorschlag);
    this.webseiteInfoVorschlag = vorschlag;
    this.autoErmittlungQuellen = quellen;

    const hinweise = [];
    if (websiteErgebnis && !websiteErgebnis.ok) hinweise.push(`Website: ${websiteErgebnis.meldung}`);
    if (osmErgebnis && !osmErgebnis.ok) hinweise.push(`OpenStreetMap: ${osmErgebnis.meldung}`);
    this.setAutoErmittlungStatus(
      hinweise.length
        ? `Angaben gefunden – bitte im Popup prüfen (${hinweise.join(" ")})`
        : "Angaben gefunden – bitte im Popup prüfen.",
      "success",
    );
    this.render();
  }

  /** Ermittelt Angaben automatisch anhand der Website und/oder der
   * Koordinaten (Issue #11, 5.1 - ersetzt die bisher getrennten
   * ermittleWebseiteInfo()/ermittleOsmInfo()). Fragt beide Quellen
   * parallel ab, soweit deren jeweilige Voraussetzung erfüllt ist
   * (Website-Adresse bzw. gültige Koordinaten), und führt die Ergebnisse
   * anschliessend zu einem einzigen Bestätigungs-Popup zusammen (siehe
   * zeigeAutoErgebnis()). Liefert die OSM-Quelle mehrere Treffer, wird
   * zunächst die bestehende Trefferauswahl gezeigt (siehe waehleOsmOrt())
   * - ein bereits vorliegendes Website-Ergebnis geht dabei nicht
   * verloren (this._wartendesWebseiteErgebnis). Wie die bisherigen
   * Einzelfunktionen (Issue #9, Korrektur 5.1) muss der vollständige
   * Formularzustand VOR dem ersten this.render() gesichert werden - sonst
   * gingen bereits eingetippte, aber noch nicht gespeicherte Werte beim
   * Neuaufbau des Formulars verloren. */
  async ermittleAutomatisch() {
    this.erfasseFormularZustand();

    const website = (this.editing?.website || "").trim();
    const { latitude, longitude } = this.editing || {};
    const hatKoordinaten = isValidWgs84(latitude, longitude);

    if (!website && !hatKoordinaten) {
      this.setAutoErmittlungStatus(
        "Bitte zuerst eine Website-Adresse oder gültige Latitude-/Longitude-Werte eintragen.",
        "error",
      );
      return;
    }

    const btn = this.shadowRoot.querySelector("[data-auto-info-btn]");
    if (btn) btn.disabled = true;
    this.setAutoErmittlungStatus("Angaben werden ermittelt …");

    const [websiteErgebnis, osmErgebnis] = await Promise.all([
      website ? this.holeWebseiteVorschlag(website) : Promise.resolve(null),
      hatKoordinaten ? this.holeOsmOrte(latitude, longitude, this.osmRadius) : Promise.resolve(null),
    ]);

    if (btn) btn.disabled = false;

    if (osmErgebnis?.ok && osmErgebnis.orte.length > 1) {
      // Mehrere OSM-Treffer -> zunächst Auswahlliste anzeigen (Issue #10,
      // 5.2); ein ggf. bereits vorliegendes Website-Ergebnis wird bis zur
      // Auswahl zwischengespeichert, statt es zu verwerfen.
      this._wartendesWebseiteErgebnis = websiteErgebnis;
      this.osmOrteAuswahl = osmErgebnis.orte;
      this.setAutoErmittlungStatus(`${osmErgebnis.orte.length} Orte gefunden – bitte auswählen.`, "success");
      this.render();
      return;
    }

    const osmVorschlag = (osmErgebnis?.ok && osmErgebnis.orte.length === 1)
      ? this.osmOrtZuVorschlag(osmErgebnis.orte[0])
      : null;
    this.zeigeAutoErgebnis(websiteErgebnis, osmErgebnis, osmVorschlag);
  }

  /** Wählt einen Treffer aus der OSM-Trefferauswahl (Issue #10, 5.2) und
   * führt ihn mit einem ggf. zwischengespeicherten Website-Ergebnis
   * zusammen, bevor das gemeinsame Bestätigungs-Popup geöffnet wird
   * (Issue #11, 5.1). */
  waehleOsmOrt(index) {
    const ort = (this.osmOrteAuswahl || [])[index];
    this.osmOrteAuswahl = null;
    const websiteErgebnis = this._wartendesWebseiteErgebnis;
    this._wartendesWebseiteErgebnis = null;
    const osmVorschlag = ort ? this.osmOrtZuVorschlag(ort) : null;
    this.zeigeAutoErgebnis(websiteErgebnis, ort ? { ok: true, orte: [ort] } : null, osmVorschlag);
  }

  /** Bricht die OSM-Trefferauswahl ab, ohne einen Treffer zu übernehmen
   * (Issue #10, 5.2) - this.editing wurde bereits vor dem Öffnen der Liste
   * über erfasseFormularZustand() gesichert (siehe ermittleAutomatisch()).
   * Ein ggf. bereits erfolgreich ermitteltes Website-Ergebnis wird trotz
   * abgebrochener OSM-Auswahl weiterhin im Bestätigungs-Popup angezeigt
   * (Issue #11) statt verworfen zu werden. */
  abbrechenOsmAuswahl() {
    this.osmOrteAuswahl = null;
    const websiteErgebnis = this._wartendesWebseiteErgebnis;
    this._wartendesWebseiteErgebnis = null;
    this.zeigeAutoErgebnis(websiteErgebnis, null, null);
  }

  /** Verwirft die im Popup gezeigten Vorschläge vollständig (Issue #9,
   * "Abbrechen"). this.editing wurde bereits vor dem Öffnen des Popups
   * über erfasseFormularZustand() gesichert (siehe ermittleAutomatisch())
   * – das Formular bleibt dadurch exakt im Zustand vor dem Klick auf
   * "Angaben automatisch ermitteln", inklusive aller zwischenzeitlich
   * eingegebenen, noch ungespeicherten Werte. */
  abbrechenWebseiteInfo() {
    this.webseiteInfoVorschlag = null;
    this.autoErmittlungQuellen = null;
    this.render();
  }

  /** Übernimmt die im Popup bestätigten Vorschläge (Issue #9,
   * "Übernehmen") in this.editing und schliesst das Popup. */
  uebernehmeWebseiteInfoVorschlag() {
    const uebernommen = this.uebernehmeWebseiteInfo(this.webseiteInfoVorschlag || {});
    this.webseiteInfoVorschlag = null;
    this.autoErmittlungQuellen = null;
    this.setAutoErmittlungStatus(
      uebernommen
        ? "Informationen übernommen – bitte vor dem Speichern prüfen und bei Bedarf anpassen."
        : "Es wurden keine Angaben übernommen.",
      uebernommen ? "success" : "",
    );
    this.render();
  }

  /** Überträgt vom Server ermittelte Vorschlagsdaten (webseite_info.py) in
   * das gerade bearbeitete Formular (this.editing). Reine
   * Vorschlagsübernahme in den Bearbeitungszustand – nichts wird dabei
   * gespeichert (siehe management.ws_webseite_info). Wird seit Issue #9
   * ausschliesslich über das Bestätigungs-Popup ausgelöst (siehe
   * uebernehmeWebseiteInfoVorschlag()), nicht mehr direkt nach dem Abruf.
   *
   * Bereits ausgefüllte Textfelder werden durch einen gefundenen
   * Vorschlag ersetzt (die Ausgangsdaten sind ja noch ungespeichert und
   * damit gefahrlos revidierbar); Angebote/Zahlungsarten werden hingegen
   * ergänzt statt ersetzt, um bereits erfasste Einträge nicht zu
   * verwerfen. Gibt zurück, ob überhaupt etwas übernommen wurde. */
  uebernehmeWebseiteInfo(info) {
    if (!this.editing) return false;
    let uebernommen = false;

    // "website" ist seit Issue #10 Teil der gemeinsamen Vorschlagsform
    // (osmOrtZuVorschlag()) - WebseiteInfo (Issue #8/#9) liefert dieses
    // Feld nicht, daher ändert die Ergänzung dessen Verhalten nicht.
    // "mobilnummer"/"email" analog seit der Kontaktdaten-Erweiterung von
    // beiden Quellen geliefert.
    for (const feld of ["name", "beschreibung", "adresse", "plz", "ort", "land", "website", "mobilnummer", "email"]) {
      if (info[feld]) { this.editing[feld] = info[feld]; uebernommen = true; }
    }

    if (Array.isArray(info.oeffnungszeiten) && info.oeffnungszeiten.length) {
      this.editing.oeffnungszeiten = info.oeffnungszeiten.map(z => ({ wochentag: z.wochentag, beginn: z.beginn, ende: z.ende }));
      uebernommen = true;
    }

    for (const feld of ["angebote", "zahlungsarten"]) {
      const vorschlaege = Array.isArray(info[feld]) ? info[feld] : [];
      if (!vorschlaege.length) continue;
      if (!this.editing[feld]) this.editing[feld] = [];
      const bestehendeSlugs = new Set(this.editing[feld].map(x => this.slug(x.name || x)));
      for (const name of vorschlaege) {
        const eintragSlug = this.slug(name);
        if (bestehendeSlugs.has(eintragSlug)) continue;
        bestehendeSlugs.add(eintragSlug);
        this.editing[feld].push({ id: eintragSlug, name });
        uebernommen = true;
      }
    }

    return uebernommen;
  }

  addExternalUrl(value) {
    const trimmed = (value || "").trim();
    if (!trimmed) return;
    if (!this.isPlausibleUrl(trimmed)) {
      this.setUploadStatus("Die Bild-Adresse muss eine gültige http(s)-Adresse sein.", "error");
      return;
    }
    if (!this.editing.bilder) this.editing.bilder = [];
    this.editing.bilder.push({ url: trimmed, beschreibung: null, hochgeladen: false });
    this.setUploadStatus("");
    this.render();
  }

  /** Liest alle "einfachen" Formularfelder (Text-/Adressfelder,
   * Öffnungszeiten, Sonderöffnungszeiten, Angebote/Zahlungsarten) aus dem
   * Formular-DOM in ein einfaches Objekt – bewusst OHNE die
   * Koordinatenfelder, deren Auswertung (resolveCoordinates()) im
   * Gegensatz zu allen übrigen Feldern eine Exception werfen kann
   * (ungültige Zahl bzw. ausserhalb des WGS84-Bereichs). Gemeinsam
   * genutzt von formData() (lässt eine solche Exception bewusst
   * weiterlaufen, siehe save()/validate()) und von
   * erfasseFormularZustand() (Issue #9, siehe dort für den Grund, warum
   * dieser zweite Aufrufer bewusst fehlertolerant gegenüber ungültigen
   * Koordinaten sein muss). */
  leseEinfacheFelder(f) {
    const value = (name) => f.elements[name]?.value ?? "";
    const data = {};
    data.name = value("name"); data.beschreibung = value("beschreibung") || null;
    data.bemerkung = value("bemerkung") || null;
    data.adresse = value("adresse") || null; data.plz = value("plz") || null;
    data.ort = value("ort") || null; data.land = value("land") || null;
    data.mobilnummer = value("mobilnummer") || null;
    data.email = value("email") || null;
    data.website = value("website") || null;
    data.oeffnungszeiten = this.readOpeningHours(f);
    data.sonderoeffnungszeiten = [...f.querySelectorAll("[data-special]")].map(row => ({ datum_von: row.querySelector("[name=datum_von]").value, datum_bis: row.querySelector("[name=datum_bis]").value, geschlossen: row.querySelector("[name=geschlossen]").checked, beginn: row.querySelector("[name=beginn]").value || null, ende: row.querySelector("[name=ende]").value || null }));
    for (const field of ["angebote", "zahlungsarten"]) data[field] = this.lines(f.elements[field]?.value);
    return data;
  }

  /** Bilder-Beschreibungsfelder aus dem Formular-DOM übernehmen. Die
   * Bilderliste selbst lebt in this.editing.bilder (Upload/Entfernen/
   * Hauptbild-Wechsel mutieren sie direkt, siehe uploadBild/removeBild/
   * setHauptbild) – hier werden nur die live editierbaren
   * Beschreibungsfelder aus dem Formular übernommen. Von formData() und
   * erfasseFormularZustand() (Issue #9) gemeinsam genutzt. */
  leseBilderBeschreibungen(f, bilder) {
    return (bilder || []).map((bild, i) => {
      const feld = f.querySelector(`[data-bild-index="${i}"] [data-bild-beschreibung]`);
      return { ...bild, beschreibung: feld ? (feld.value || null) : bild.beschreibung };
    });
  }

  formData() {
    const f = this.shadowRoot.querySelector("form");
    const data = this.clone(this.editing || this.empty());
    Object.assign(data, this.leseEinfacheFelder(f));
    const koordinaten = this.resolveCoordinates(f);
    data.latitude = koordinaten.latitude; data.longitude = koordinaten.longitude;
    data.bilder = this.leseBilderBeschreibungen(f, this.editing?.bilder);
    data.quellen = this.bereinigteQuellen(data);
    return data;
  }

  /** Überträgt sämtliche aktuell im Formular sichtbaren, noch nicht
   * gespeicherten Eingaben nach this.editing – **muss** vor jedem
   * this.render()-Aufruf im Zusammenhang mit "Angaben automatisch
   * ermitteln" (Issue #9) aufgerufen werden, da render() das komplette
   * Formular-HTML ausschliesslich aus this.editing neu aufbaut (siehe
   * editor()). Ohne diesen Schritt ginge jeder bereits eingetippte, aber
   * noch nicht über formData()/"Speichern" in this.editing übernommene
   * Wert beim nächsten Render optisch "verloren" (zurückgesetzt auf den
   * alten this.editing-Stand) – ursprünglich als "der Eintrag wird
   * gelöscht" gemeldet (Issue #9), tatsächlich aber betraf/betrifft das
   * grundsätzlich JEDES Formularfeld, nicht nur "Webseite" (siehe
   * ermittleAutomatisch()).
   *
   * Nutzt bewusst denselben Erfassungsmechanismus wie formData()/save()
   * (leseEinfacheFelder()/leseBilderBeschreibungen()) – bis auf eine
   * Ausnahme: Anders als formData() darf diese Funktion nicht mit einer
   * Exception abbrechen, nur weil Latitude/Longitude gerade unvollständig
   * oder ungültig eingegeben sind (resolveCoordinates() würde dafür
   * werfen) – "Infos ermitteln" darf dadurch nicht blockiert werden. In
   * diesem Fall bleiben nur die beiden Koordinatenfelder unverändert auf
   * ihrem bisherigen this.editing-Stand (kein Datenverlust bei den
   * Koordinaten, aber auch kein Versuch, einen ungültigen Zwischenstand
   * zu übernehmen); alle übrigen Felder werden unabhängig davon erfasst. */
  erfasseFormularZustand() {
    if (!this.editing) return;
    const f = this.shadowRoot.querySelector("form");
    if (!f) return;

    Object.assign(this.editing, this.leseEinfacheFelder(f));
    try {
      const koordinaten = this.resolveCoordinates(f);
      this.editing.latitude = koordinaten.latitude;
      this.editing.longitude = koordinaten.longitude;
    } catch {
      // Bewusst ignoriert, siehe Funktionsdoku oben.
    }
    this.editing.bilder = this.leseBilderBeschreibungen(f, this.editing.bilder);

    // Issue #11: Suchradius für OpenStreetMap ist kein Hofladen-Feld
    // (gehört nicht zu this.editing), muss aber genau wie alle übrigen
    // Formularfelder vor einem Re-Render gesichert werden, sonst ginge ein
    // bereits geänderter Wert beim nächsten Aufbau des Formulars verloren
    // (dieselbe Ursache wie in Issue #9 bereits für andere Felder behoben).
    const radiusEingabe = Number(f.elements["osm_radius"]?.value);
    if (Number.isFinite(radiusEingabe) && radiusEingabe > 0) {
      this.osmRadius = radiusEingabe;
    }
  }

  /** Öffnungszeiten aus den pro Wochentag gruppierten Eingabebereichen
   * auslesen (Modus "geschlossen"/"24h"/"zeiten" je Tag). */
  readOpeningHours(f) {
    const result = [];
    for (let day = 1; day <= 7; day++) {
      const modus = f.querySelector(`input[name="day_mode_${day}"]:checked`)?.value || "geschlossen";
      if (modus === "geschlossen") continue;
      if (modus === "24h") { result.push({ wochentag: day, beginn: FULL_DAY.beginn, ende: FULL_DAY.ende }); continue; }
      f.querySelectorAll(`[data-day-interval="${day}"]`).forEach((row) => {
        const beginn = row.querySelector("[name=beginn]").value;
        const ende = row.querySelector("[name=ende]").value;
        if (beginn && ende) result.push({ wochentag: day, beginn, ende });
      });
    }
    return result;
  }

  lines(text) { return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(name => ({ id: this.slug(name), name })); }
  slug(s) { return String(s).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "eintrag"; }

  async remove(id) {
    if (!confirm("Möchtest du diesen Hofladen wirklich löschen?")) return;
    try { await this.call("hofkarte/management/delete", { hofladen_id: id }); this.message = "Hofladen gelöscht."; this.viewing = null; await this.load(); }
    catch (err) { this.error = err?.message || "Löschen fehlgeschlagen."; this.render(); }
  }

  start(item = null) {
    this.error = ""; this.viewing = null; this.showCoordInfo = false;
    this.webseiteInfoVorschlag = null; this.autoErmittlungQuellen = null;
    this.autoErmittlungStatusText = ""; this.autoErmittlungStatusKind = "";
    this.osmOrteAuswahl = null; this._wartendesWebseiteErgebnis = null;
    this.osmRadius = this._osmRadiusVorgabe;
    this.editing = item ? this.clone(item) : this.empty();
    this.merkeQuellenSchnappschuss();
    this.render();
  }
  cancel() {
    this.editing = null; this.error = "";
    this.webseiteInfoVorschlag = null; this.autoErmittlungQuellen = null;
    this.autoErmittlungStatusText = ""; this.autoErmittlungStatusKind = "";
    this.osmOrteAuswahl = null; this._wartendesWebseiteErgebnis = null;
    this.render();
  }
  view(item) { this.error = ""; this.editing = null; this.viewing = item; this.render(); }
  closeView() { this.viewing = null; this.render(); }

  // --- Rendering -----------------------------------------------------

  /** Ist gerade die Kartenansicht der Übersicht sichtbar? */
  istKartenansicht() {
    return !this.editing && !this.viewing && !this.importDialog && this.uebersichtsAnsicht === "karte" && this.items.length > 0;
  }

  render() {
    if (!this.shadowRoot) return;
    // Die Leaflet-Karte lebt, solange die Kartenansicht offen ist (Befund
    // F10): sie wird nur beim Verlassen der Kartenansicht abgebaut
    // (map.remove()), nicht bei jedem Render. Ihr Container (this._karteHost)
    // wird in initKarte() in den neu erzeugten Platzhalter umgehängt.
    const inKarte = this.istKartenansicht();
    if (!inKarte) this.teardownKarte();
    // <style> existiert dauerhaft (Konstruktor) - hier wird nur <main> ersetzt.
    this._mainEl.innerHTML = this.currentView() + (this.finden ? this.findenDialog() : "");
    this.bind();
    if (inKarte) this.initKarte();
    // Barrierefreiheit (Issue #9, 5.2): Fokus beim Öffnen des
    // Bestätigungs-Popups auf den Dialog selbst setzen, damit
    // Tastatur-/Screenreader-Nutzung (inkl. der Escape-Taste, siehe
    // bind()) sofort funktioniert, ohne dass zuerst manuell dorthin
    // navigiert werden muss.
    if (this.webseiteInfoVorschlag) {
      this.shadowRoot.querySelector("[data-webseite-info-dialog]")?.focus();
    }
    if (this.osmOrteAuswahl) {
      this.shadowRoot.querySelector("[data-osm-orte-dialog]")?.focus();
    }
    if (this.finden && !this._findenFokusGesetzt) {
      this._findenFokusGesetzt = true;
      this.shadowRoot.querySelector("[data-finden-dialog]")?.focus();
    } else if (!this.finden) {
      this._findenFokusGesetzt = false;
    }
  }

  /** Aktive Leaflet-Karteninstanz, Marker-Ebene, Container und den
   * Resize-Handler sauber entfernen (siehe render()/disconnectedCallback()).
   * Wird nur beim Verlassen der Kartenansicht bzw. beim Entfernen des
   * Panels aufgerufen. */
  teardownKarte() {
    this._karteToken++; // laufende initKarte()-/aktualisiereMarker()-Läufe werden verworfen
    if (this._leafletResizeHandler) {
      window.removeEventListener("resize", this._leafletResizeHandler);
      this._leafletResizeHandler = null;
    }
    if (this._leafletMap) {
      this._leafletMap.remove();
      this._leafletMap = null;
    }
    this._karteHost?.remove();
    this._karteHost = null;
    this._markerLayer = null;
    this._markerSignatur = "";
    this._markerIcons = null;
  }

  /** Stylesheets der lokal gebündelten Bibliotheken einmalig dauerhaft in
   * den Shadow-DOM einhängen (ausserhalb von <main>, daher von render()
   * nicht betroffen - kein erneutes Einfügen/Laden pro Render). */
  sorgeFuerKarteCss(mitCluster) {
    this._karteCss = this._karteCss || new Set();
    const urls = [LEAFLET_CSS_URL, ...(mitCluster ? MARKERCLUSTER_CSS_URLS : [])];
    for (const url of urls) {
      if (this._karteCss.has(url)) continue;
      this._karteCss.add(url);
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = url;
      this.shadowRoot.append(link);
    }
  }

  /** Fehlermeldung der Kartenansicht anzeigen, OHNE render() aufzurufen
   * (Befund F8: ein Render würde initKarte() erneut auslösen und so bei
   * dauerhaft nicht ladbarer Bibliothek eine Endlosschleife erzeugen).
   * Der Text wird per textContent gesetzt. Ein neuer Ladeversuch erfolgt
   * nur ausdrücklich über "Erneut versuchen" (siehe bindDelegiert()). */
  zeigeKarteFehler(text) {
    this.karteFehler = text || "Kartenbibliothek konnte nicht geladen werden.";
    const box = this._mainEl.querySelector("[data-karte-fehler]");
    if (box) {
      const t = box.querySelector("[data-karte-fehler-text]");
      if (t) t.textContent = this.karteFehler;
      box.hidden = false;
    }
  }

  /** Leaflet-Karte in den zuvor von karteAnsicht() gerenderten Platzhalter
   * einhängen. Die Karte wird nur EINMAL pro Öffnen der Kartenansicht
   * erzeugt (Befund F10); bei weiteren Renders wird lediglich ihr
   * Container umgehängt und die Marker-Ebene bei Bedarf getauscht.
   * Ein einmal fehlgeschlagenes Laden der Bibliothek löst keinen
   * automatischen Neuversuch aus (Befund F8). */
  async initKarte() {
    const slot = this._mainEl.querySelector("[data-karte-container]");
    if (!slot) { this.teardownKarte(); return; } // z. B. "keine Koordinaten"-Meldung statt Karte

    if (this._leafletMap && this._karteHost) {
      slot.replaceWith(this._karteHost);
      this._leafletMap.invalidateSize();
      this.aktualisiereMarker();
      return;
    }
    if (this.karteFehler) return; // kein automatischer Neuversuch (F8)

    const token = ++this._karteToken;
    let L;
    try {
      L = await ladeLeaflet();
    } catch (err) {
      if (token === this._karteToken) this.zeigeKarteFehler(err?.message);
      return;
    }
    // Zwischenzeitlich könnte die Ansicht gewechselt, das Panel entfernt
    // oder neu gerendert worden sein, während die Bibliothek geladen wurde.
    if (token !== this._karteToken || !this.isConnected || !this.istKartenansicht()) return;
    const aktuellerSlot = this._mainEl.querySelector("[data-karte-container]");
    if (!aktuellerSlot) return;
    this.karteFehler = "";
    this.sorgeFuerKarteCss(false);

    const host = document.createElement("div");
    host.className = "karte-container";
    host.setAttribute("data-karte-container", "");
    aktuellerSlot.replaceWith(host);
    this._karteHost = host;

    const map = L.map(host, { scrollWheelZoom: true });
    this._leafletMap = map;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>-Mitwirkende',
    }).addTo(map);

    // Je Status ein eigenes Icon (statt pro Marker neu erzeugt).
    this._markerIcons = {
      offen: erzeugeKarteMarkerIcon(L, true),
      geschlossen: erzeugeKarteMarkerIcon(L, false),
      unbekannt: erzeugeKarteMarkerIcon(L, null),
    };
    // EIN gemeinsamer Popup-Handler für alle Marker (statt eines
    // Listeners je Marker). Das Popup-Element entsteht bei jedem Öffnen
    // neu, der Klick-Listener daran wird mit ihm verworfen.
    map.on("popupopen", (e) => {
      const knopf = e.popup.getElement()?.querySelector("[data-karte-view]");
      knopf?.addEventListener("click", () => {
        const item = this.items.find((x) => x.id === knopf.dataset.id);
        if (item) this.view(item);
      });
    });

    this._leafletResizeHandler = () => map.invalidateSize();
    window.addEventListener("resize", this._leafletResizeHandler);
    // Absicherung für die erstmalige Grössenberechnung (z. B. bei einer
    // noch laufenden Sidebar-/Layout-Animation im selben Moment).
    setTimeout(() => this._leafletMap === map && map.invalidateSize(), 0);

    await this.aktualisiereMarker();
  }

  /** Marker-Ebene der Karte aktualisieren: Nur die Ebene wird getauscht,
   * die Karte selbst bleibt bestehen. Ab KARTE_CLUSTER_AB Markern wird das
   * lokal gebündelte leaflet.markercluster verwendet (Begründung: die
   * Marker sind DOM-basierte DivIcons - ein Canvas-Renderer wie
   * ``preferCanvas`` greift für sie nicht; Clustering reduziert die Zahl
   * der DOM-Knoten und die Zeichenlast dagegen wirksam). */
  async aktualisiereMarker() {
    const map = this._leafletMap;
    const L = window.L;
    if (!map || !L) return;
    const alleMitKoordinaten = this.items.filter((item) => isValidWgs84(item.latitude, item.longitude));
    const markerItems = this.karteNurGeoeffnet ? alleMitKoordinaten.filter((item) => item.geoeffnet === true) : alleMitKoordinaten;
    const signatur = `${this.karteNurGeoeffnet ? 1 : 0}|` + markerItems.map((i) => `${i.id}:${i.latitude},${i.longitude}:${i.geoeffnet}:${i.name}`).join(";");
    if (signatur === this._markerSignatur) return;

    const token = this._karteToken;
    let cluster = false;
    if (markerItems.length > KARTE_CLUSTER_AB) {
      try {
        await ladeMarkercluster();
        cluster = !!L.markerClusterGroup;
        this.sorgeFuerKarteCss(true);
      } catch (err) {
        console.warn("Marker-Clustering nicht verfügbar, Marker werden einzeln dargestellt:", err);
      }
      if (token !== this._karteToken || this._leafletMap !== map) return;
    }

    const icons = this._markerIcons;
    const iconFuer = (geoeffnet) => geoeffnet === true ? icons.offen : geoeffnet === false ? icons.geschlossen : icons.unbekannt;
    const marker = markerItems.map((item) => {
      const m = L.marker([item.latitude, item.longitude], { icon: iconFuer(item.geoeffnet) });
      // Popup-Inhalt erst beim Öffnen erzeugen (Funktion statt String).
      m.bindPopup(() => `<div class="karte-popup"><strong>${this.esc(item.name)}</strong><br><button type="button" class="link-button" data-karte-view data-id="${this.escAttr(item.id)}">Zur Detailansicht</button></div>`);
      return m;
    });
    const ebene = cluster ? L.markerClusterGroup({ chunkedLoading: true, showCoverageOnHover: false }) : L.layerGroup();
    if (cluster) ebene.addLayers(marker); else marker.forEach((m) => ebene.addLayer(m));
    if (this._markerLayer) map.removeLayer(this._markerLayer);
    ebene.addTo(map);
    this._markerLayer = ebene;
    this._markerSignatur = signatur;

    if (markerItems.length === 1) {
      map.setView([markerItems[0].latitude, markerItems[0].longitude], 14);
    } else if (markerItems.length > 1) {
      map.fitBounds(markerItems.map((item) => [item.latitude, item.longitude]), { padding: [24, 24] });
    } else if (alleMitKoordinaten.length) {
      // Der Geöffnet-Filter ergibt keine Treffer, es gibt aber
      // grundsätzlich Hofläden mit Koordinaten – sinnvollen Ausschnitt
      // über alle vorhandenen Koordinaten zeigen statt einer
      // Default-Weltkarte.
      map.fitBounds(alleMitKoordinaten.map((item) => [item.latitude, item.longitude]), { padding: [24, 24] });
    }
    const leer = this._mainEl.querySelector("[data-karte-leer]");
    if (leer) leer.hidden = markerItems.length > 0;
  }

  currentView() {
    if (this.importDialog) return this.importKonflikte();
    if (this.editing) return this.editor();
    if (this.viewing) return this.detail();
    return this.list();
  }

  styles() {
    return `
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
      main{max-width:1200px;margin:0 auto;padding:24px}
      .top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
      .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:20px}
      .view-toggle{display:flex;gap:8px;margin-top:16px}
      .tile-card{display:flex;flex-direction:column;gap:6px}
      .tile-image{width:100%;height:140px;object-fit:cover;border-radius:8px;margin-bottom:4px}
      .tile-image-placeholder{display:flex;align-items:center;justify-content:center;background:var(--secondary-background-color);font-size:2.5em}
      .link-button{background:none;border:0;padding:0;color:var(--primary-color);font:inherit;font-weight:500;cursor:pointer;text-align:left}
      .link-button:hover{text-decoration:underline}
      .status-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.9em}
      .status-open{background:var(--success-color,#43a047);color:#fff}
      .status-closed{background:var(--error-color,#db4437);color:#fff}
      .status-unknown{background:var(--secondary-background-color);color:var(--secondary-text-color)}
      .export-import-row{display:flex;align-items:center;gap:10px;margin-top:16px;flex-wrap:wrap}
      .auswahl-checkbox{display:flex;align-items:center;gap:6px;font-size:.9em;margin-bottom:4px}
      .auswahl-checkbox input{width:auto;padding:0}
      .import-konflikt{margin-top:16px}
      .import-diff{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px}
      .import-diff-spalte h4{margin:0 0 6px}
      .import-diff-feld{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--divider-color);font-size:.9em}
      .import-diff-feld .diff-label{color:var(--secondary-text-color);flex:0 0 auto}
      .diff-alt{background:color-mix(in srgb, var(--error-color,#db4437) 12%, transparent)}
      .diff-neu{background:color-mix(in srgb, var(--success-color,#43a047) 12%, transparent)}
      @media(max-width:700px){.import-diff{grid-template-columns:1fr}}
      .list-filter{margin-top:16px}
      .list-filter input{max-width:360px}
      .table-scroll{overflow-x:auto;margin-top:12px}
      .hoflaeden-table{width:100%;border-collapse:collapse;background:var(--ha-card-background,var(--card-background-color));border-radius:12px;overflow:hidden}
      .hoflaeden-table th,.hoflaeden-table td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--divider-color)}
      .hoflaeden-table tr:last-child td{border-bottom:0}
      .table-sort{background:none;border:0;padding:0;font:inherit;font-weight:600;color:var(--primary-text-color);cursor:pointer;white-space:nowrap}
      .karte-filter-row{margin-top:16px}
      .karte-filter-row label{display:flex;align-items:center;gap:8px;margin:0;font-size:.95em;font-weight:normal}
      .karte-filter-row input[type=checkbox]{width:auto;padding:0}
      .karte-container{height:480px;border-radius:12px;margin-top:12px;background:var(--secondary-background-color)}
      .karte-empty{margin-top:20px}
      .karte-marker-icon{background:transparent;border:0}
      .karte-marker-svg{display:block}
      .karte-marker-pin{fill:var(--primary-color,#db4437);filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}
      .karte-marker-pin-offen{fill:var(--success-color,#43a047)}
      .karte-marker-pin-geschlossen{fill:var(--disabled-text-color,#9e9e9e)}
      .karte-marker-pin-unbekannt{fill:var(--primary-color,#db4437)}
      .karte-marker-glyph{fill:#fff}
      .karte-popup{font-size:.95em}
      .karte-popup button{margin-top:6px}
      @media(max-width:700px){.karte-container{height:360px}}
      .card{background:var(--ha-card-background,var(--card-background-color));border-radius:12px;padding:16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px #0002)}
      form > section.card{margin-bottom:20px}
      .card h2{margin-top:0}
      .actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap}
      button{border:0;border-radius:8px;padding:9px 14px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer;font-size:.95em}
      button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}
      button.danger{background:var(--error-color,#db4437);color:#fff}
      button.icon{padding:6px 10px;border-radius:50%;line-height:1;font-size:1.1em}
      label{display:block;margin:10px 0 5px;font-size:.9em}
      .fields{display:grid;grid-template-columns:1fr;gap:8px}
      .field-row{display:grid;grid-template-columns:1fr;gap:8px}
      .field-row.two{grid-template-columns:1fr 1fr}
      .field-row label{margin:0}
      input,textarea,select{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);border-radius:7px;background:var(--primary-background-color);color:var(--primary-text-color);font-size:.95em}
      textarea{min-height:100px}
      @media(max-width:700px){main{padding:12px}.field-row.two{grid-template-columns:1fr}.grid{grid-template-columns:1fr}}
      .coord-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}
      .coord-row .field-row{flex:1;min-width:160px}
      .info-btn{flex:0 0 auto;width:34px;height:34px;border-radius:50%;background:var(--info-color,#2196f3);color:#fff;font-weight:bold;box-shadow:0 1px 3px #0003;border:2px solid transparent}
      .info-btn:hover,.info-btn:focus-visible{background:var(--info-color,#1976d2);outline:2px solid var(--info-color,#2196f3);outline-offset:2px}
      .map-btn{flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 14px;border-radius:8px;background:var(--secondary-background-color);color:var(--primary-text-color);text-decoration:none;font-size:.95em;box-sizing:border-box}
      .map-btn[disabled],.map-btn.disabled{opacity:.5;cursor:not-allowed;pointer-events:none}
      .coord-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
      .route-actions{display:inline-flex;gap:4px;flex-wrap:wrap}
      .route-btn{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;padding:0;border-radius:8px;background:var(--secondary-background-color);color:var(--primary-text-color);text-decoration:none;font-size:1.05em;box-sizing:border-box;border:0;cursor:pointer}
      .route-btn[disabled]{opacity:.5;cursor:not-allowed;pointer-events:none}
      .info-box{margin-top:8px;padding:12px 14px;border-radius:8px;background:var(--secondary-background-color);font-size:.9em;line-height:1.5}
      .info-box code{background:var(--primary-background-color);padding:1px 5px;border-radius:4px}
      .day-block{border:1px solid var(--divider-color);border-radius:10px;padding:10px 12px;margin:8px 0}
      .day-block .day-title{font-weight:600;margin-bottom:6px}
      .day-mode{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px;font-size:.9em}
      .day-mode label{display:flex;align-items:center;gap:5px;margin:0;font-weight:normal}
      .interval-row{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:end;margin:6px 0}
      .interval-row input[type=time]{max-width:140px}
      .special input[type=time]{max-width:140px}
      .special{display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:8px;align-items:end;margin:8px 0}
      @media(max-width:700px){.special{grid-template-columns:1fr 1fr}}
      [hidden]{display:none!important}
      .notice{padding:10px;margin:12px 0;border-radius:8px;background:var(--info-color,#2196f3);color:white}
      .notice.error{background:var(--error-color,#db4437)}
      .muted{color:var(--secondary-text-color)}
      h1,h2{font-weight:500}
      .pill{display:inline-block;padding:3px 10px;border-radius:12px;background:var(--secondary-background-color);margin:2px 4px 2px 0;font-size:.9em}
      .day{font-weight:500}
      .detail-section{margin-bottom:20px}
      .detail-section h3{margin:0 0 8px;font-size:1em;text-transform:uppercase;letter-spacing:.03em;color:var(--secondary-text-color)}
      .opening-table{width:100%;border-collapse:collapse}
      .opening-table td{padding:4px 8px 4px 0;vertical-align:top}
      .opening-table td:first-child{font-weight:500;width:120px}
      a.website-link{color:var(--primary-color);text-decoration:none;font-weight:500}
      a.website-link:hover{text-decoration:underline}
      .thumbs{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
      .bild-row{display:flex;gap:10px;align-items:center;padding:8px;border:1px solid var(--divider-color);border-radius:8px;margin-bottom:8px}
      .bild-row img{width:64px;height:64px;object-fit:cover;border-radius:6px;flex:0 0 auto}
      .bild-row-fields{flex:1;min-width:0}
      .bild-row-fields input{width:100%}
      .bild-row-meta{margin-top:4px;font-size:.85em}
      .bild-row-actions{display:flex;gap:6px;flex:0 0 auto}
      .upload-row{display:flex;align-items:center;gap:12px;margin-top:10px;flex-wrap:wrap}
      .upload-start-btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 16px;border-radius:8px;background:var(--success-color,#43a047);color:#fff;cursor:pointer;font-size:.95em;font-weight:500;border:0;box-shadow:0 1px 3px #0003}
      .upload-start-btn:hover,.upload-start-btn:focus-visible{filter:brightness(0.95);outline:2px solid var(--success-color,#43a047);outline-offset:2px}
      .upload-status{font-size:.9em}
      .upload-status.error{color:var(--error-color,#db4437)}
      .upload-status.success{color:var(--success-color,#43a047)}
      .thumbs img{width:96px;height:96px;object-fit:cover;border-radius:8px}
      .webseite-info-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px}
      .webseite-info-status.error{color:var(--error-color,#db4437)}
      .webseite-info-status.success{color:var(--success-color,#43a047)}
      .modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;padding:16px;z-index:1000}
      .modal{background:var(--ha-card-background,var(--card-background-color));border-radius:12px;padding:20px;max-width:480px;width:100%;max-height:85vh;overflow:auto;box-shadow:0 4px 24px rgba(0,0,0,.4)}
      .modal h2{margin-top:0}
      .modal.breit{max-width:640px}
      .top-aktionen{display:flex;gap:8px;flex-wrap:wrap}
      .finden-form{display:flex;flex-direction:column;gap:10px;margin:12px 0}
      .finden-form label{display:flex;flex-direction:column;gap:4px;font-size:.9em}
      .finden-form input[type=text],.finden-form input[type=url]{width:100%;box-sizing:border-box}
      .finden-koordinaten{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}
      .finden-koordinaten label{flex:1 1 120px}
      .finden-form .finden-check{flex-direction:row;align-items:flex-start;gap:8px}
      .finden-kandidat,.finden-zeile{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--divider-color);border-radius:8px;cursor:pointer;margin:0;font-size:1em;text-align:left}
      /* Radio/Checkbox nicht auf 100 % Breite aufziehen (globale input-Regel) */
      .finden-kandidat input[type=radio],.finden-zeile input[type=checkbox],.finden-check input[type=checkbox]{width:auto;flex:0 0 auto;margin:3px 0 0;padding:0}
      .finden-kandidat-text,.finden-zeile-text{overflow-wrap:anywhere;line-height:1.35}
      .finden-zeile-text .quelle-badge{font-size:.85em}
      .finden-zeile-text .webseite-info-label{display:block}
      .finden-kandidat-text>.muted:first-of-type{font-size:.85em}
      .finden-kandidat.gewaehlt{border-color:var(--primary-color);background:var(--secondary-background-color)}
      .finden-kandidat-text,.finden-zeile-text{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1}
      .finden-zeilen{display:flex;flex-direction:column;gap:6px;margin:8px 0}
      .finden-warnung{color:var(--warning-color,#ff9800);font-size:.9em}
      .finden-fortschritt{margin:8px 0}
      .finden-aktionen{flex-wrap:wrap}
      .osm-orte-liste{display:flex;flex-direction:column;gap:8px;margin-top:12px}
      .osm-orte-eintrag{display:flex;flex-direction:column;align-items:flex-start;gap:2px;text-align:left;width:100%;padding:10px 12px;border-radius:8px}
      .osm-orte-name{font-weight:bold}
      .webseite-info-zeile{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--divider-color);font-size:.95em}
      .webseite-info-zeile:last-of-type{border-bottom:0}
      .webseite-info-label{font-weight:500;flex:0 0 auto}
      .sterne-reihe{display:flex;justify-content:center;gap:4px;margin-top:4px}
      .stern-btn{background:none;border:0;padding:2px;font-size:1.8em;line-height:1;cursor:pointer;color:var(--secondary-text-color,#888)}
      .stern-btn.stern-gefuellt{color:var(--warning-color,#f5a623)}
      .stern-btn:not(.stern-anzeige):hover,.stern-btn:not(.stern-anzeige):focus-visible{color:var(--warning-color,#f5a623);outline:none}
      .stern-anzeige{cursor:default;font-size:1.5em}
      .bewertung-klein{font-size:.85em;color:var(--secondary-text-color);margin-top:2px}
      .kontakt-zeile{margin:4px 0}
    `;
  }

  // --- Liste -----------------------------------------------------------

  /** Einheitliche Statusanzeige "geöffnet/geschlossen/unbekannt" – nutzt
   * das serverseitig berechnete Feld `geoeffnet` (siehe management.py),
   * keine eigene Öffnungszeiten-Berechnung in JavaScript (Issue #1). */
  geoeffnetBadge(geoeffnet) {
    if (geoeffnet === true) return `<span class="status-badge status-open">🟢 Geöffnet</span>`;
    if (geoeffnet === false) return `<span class="status-badge status-closed">🔴 Geschlossen</span>`;
    return `<span class="status-badge status-unknown">Unbekannt</span>`;
  }

  list() {
    const umschalter = `<div class="view-toggle">
      <button type="button" class="${this.uebersichtsAnsicht === "kacheln" ? "" : "secondary"}" data-ansicht="kacheln">🔲 Kacheln</button>
      <button type="button" class="${this.uebersichtsAnsicht === "liste" ? "" : "secondary"}" data-ansicht="liste">📋 Liste</button>
      <button type="button" class="${this.uebersichtsAnsicht === "karte" ? "" : "secondary"}" data-ansicht="karte">🗺️ Karte</button>
    </div>`;
    const inhalt = !this.items.length
      ? `<section class="card"><h2>Noch keine Hofläden</h2><p>Erstelle den ersten Hofladen.</p></section>`
      : (this.uebersichtsAnsicht === "liste" ? this.listTable() : this.uebersichtsAnsicht === "karte" ? this.karteAnsicht() : this.listGrid());
    // Mehrfachauswahl (Checkboxen) sowie Export/Import gibt es bewusst
    // nur in Kacheln- und Listenansicht (Issue #5) - in der Kartenansicht
    // fehlt dafür ein sinnvoller Anwendungsfall.
    const exportImportLeiste = this.items.length && this.uebersichtsAnsicht !== "karte"
      ? `<div class="export-import-row">
          <span class="muted" data-auswahl-anzahl>${this.auswahl.size} ausgewählt</span>
          <button type="button" class="secondary" data-auswahl-alle>Alle auswählen</button>
          <button type="button" class="secondary" data-auswahl-keine>Auswahl aufheben</button>
          <button type="button" class="secondary" data-export ${this.auswahl.size ? "" : "disabled"}>⬇️ Export</button>
          <button type="button" class="secondary" data-import-start>⬆️ Import</button>
          <input type="file" accept="application/json" data-import-input hidden>
        </div>`
      : "";

    return `<div class="top"><div><h1>HofKarte</h1><div class="muted">Hofläden verwalten · Panel ${PANEL_BUILD}</div></div><div class="top-aktionen"><button type="button" class="secondary" data-finden-open>🔎 Hofladen finden</button><button data-new>+ Neuer Hofladen</button></div></div>${this.message ? `<div class="notice">${this.esc(this.message)}</div>` : ""}${this.error ? `<div class="notice error">${this.esc(this.error)}${this._loadFailed ? ` <button type="button" class="secondary" data-erneut-laden>Erneut versuchen</button>` : ""}</div>` : ""}${this.items.length ? umschalter : ""}${exportImportLeiste}${inhalt}`;
  }

  listGrid() {
    return `<div class="grid">${this.items.map(item => this.listCard(item)).join("")}</div>`;
  }

  /** Bild nur rendern, wenn die URL die Sicherheitsprüfung besteht (F12);
   * sonst ein Platzhalter mit Hinweis. Externe Bilder ohne Referrer. */
  bildHtml(url, alt, vorschau = false) {
    if (!istSichereBildUrl(url, window.location.origin)) {
      return `<div class="tile-image tile-image-placeholder" role="img" aria-label="Bild nicht anzeigbar" title="Die Adresse dieses Bildes ist nicht zulässig (z. B. internes Ziel) und wird nicht geladen.">⚠️</div>`;
    }
    // Befund F14: Vorschau (256x256) statt Original ausserhalb der
    // Detailansicht; data-original dient dem Rückfall, falls die Vorschau
    // nicht ausgeliefert wird (siehe bindDelegiert()).
    const src = vorschau ? uploadVorschauUrl(url, window.location.origin) : url;
    const original = src !== url ? ` data-original="${this.escAttr(url)}"` : "";
    return `<img src="${this.escAttr(src)}"${original} alt="${this.escAttr(alt)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  }

  listCard(item) {
    const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
    const vorschauSrc = item.hauptbild_url ? uploadVorschauUrl(item.hauptbild_url, window.location.origin) : "";
    const originalAttr = vorschauSrc && vorschauSrc !== item.hauptbild_url ? ` data-original="${this.escAttr(item.hauptbild_url)}"` : "";
    const bildHtml = item.hauptbild_url && istSichereBildUrl(item.hauptbild_url, window.location.origin)
      ? `<img class="tile-image" src="${this.escAttr(vorschauSrc)}"${originalAttr} alt="${this.escAttr(item.name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`
      : `<div class="tile-image tile-image-placeholder" aria-hidden="true">🏬</div>`;

    return `<section class="card tile-card">
      <label class="auswahl-checkbox"><input type="checkbox" data-auswahl="${this.escAttr(item.id)}" ${this.auswahl.has(item.id) ? "checked" : ""}> Auswählen</label>
      ${bildHtml}
      <h2><button type="button" class="link-button" data-view="${this.escAttr(item.id)}">${this.esc(item.name)}</button></h2>
      ${adresse ? `<div>${this.esc(adresse)}</div>` : ""}
      ${this.websiteLinkHtml(item.website)}
      <div>${this.geoeffnetBadge(item.geoeffnet)}${item.bewertung ? ` <span class="bewertung-klein">${"★".repeat(item.bewertung)}</span>` : ""}</div>
      <div class="coord-actions">${this.routingAuswahl(item)}</div>
      <div class="actions">
        <button class="secondary" data-view="${this.escAttr(item.id)}">Details</button>
        <button class="secondary" data-edit="${this.escAttr(item.id)}">Bearbeiten</button>
        <button class="danger" data-delete="${this.escAttr(item.id)}">Löschen</button>
      </div>
    </section>`;
  }

  /** Sortierte, gefilterte Zeilen für die Listenansicht (rein
   * clientseitig – kein neuer Backend-Endpunkt nötig, siehe Issue #1). */
  /** Vorberechnete Such-/Sortierschlüssel je Hofladen-Objekt (Befund F10):
   * Kleinschreibung und Adressstring werden einmal pro Objekt berechnet
   * statt bei jedem Tastendruck/Vergleich. Die Objekte werden bei jedem
   * Laden neu geliefert, der WeakMap-Eintrag verfällt mit ihnen. */
  sortSchluessel(item) {
    let k = this._sortSchluessel.get(item);
    if (!k) {
      const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ").toLowerCase();
      k = {
        name: String(item.name || "").toLowerCase(),
        adresse,
        geoeffnet: item.geoeffnet === true ? 2 : item.geoeffnet === false ? 1 : 0,
        bewertung: Number(item.bewertung) || 0,
      };
      this._sortSchluessel.set(item, k);
    }
    return k;
  }

  /** Sortierte, gefilterte Zeilen für die Listenansicht (rein
   * clientseitig – kein neuer Backend-Endpunkt nötig, siehe Issue #1). */
  sortierteGefilterteItems() {
    const filterText = this.listenFilter.trim().toLowerCase();
    let ergebnis = !filterText ? this.items : this.items.filter(item => {
      const k = this.sortSchluessel(item);
      return k.name.includes(filterText) || k.adresse.includes(filterText);
    });

    if (this.listenSortSpalte) {
      const spalte = this.listenSortSpalte;
      const richtung = this.listenSortRichtung === "asc" ? 1 : -1;
      const wert = (item) => {
        const k = this.sortSchluessel(item);
        return spalte in k ? k[spalte] : String(item[spalte] || "").toLowerCase();
      };
      ergebnis = [...ergebnis].sort((a, b) => {
        const wa = wert(a), wb = wert(b);
        return wa < wb ? -richtung : wa > wb ? richtung : 0;
      });
    }
    return ergebnis;
  }

  /** Tabellenzeilen der Listenansicht (auch für das Teil-Update beim
   * Filtern, siehe aktualisiereListe()). */
  listenZeilenHtml(zeilen) {
    if (!zeilen.length) return `<tr><td colspan="6" class="muted">Keine Treffer für diesen Filter.</td></tr>`;
    return zeilen.map(item => {
      const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
      return `<tr>
                <td><input type="checkbox" data-auswahl="${this.escAttr(item.id)}" ${this.auswahl.has(item.id) ? "checked" : ""} aria-label="${this.escAttr(item.name)} auswählen"></td>
                <td><button type="button" class="link-button" data-view="${this.escAttr(item.id)}">${this.esc(item.name)}</button></td>
                <td>${this.esc(adresse) || '<span class="muted">–</span>'}</td>
                <td>${this.geoeffnetBadge(item.geoeffnet)}</td>
                <td>${item.bewertung ? "★".repeat(item.bewertung) : '<span class="muted">–</span>'}</td>
                <td>${this.routingAuswahl(item)}</td>
              </tr>`;
    }).join("");
  }

  /** Teil-Update der Listenansicht: nur <tbody> wird ersetzt (Befund F10),
   * Filterfeld, Kopfzeile und Fokus bleiben unberührt. */
  aktualisiereListe() {
    const body = this._mainEl.querySelector("[data-list-body]");
    if (body) body.innerHTML = this.listenZeilenHtml(this.sortierteGefilterteItems());
  }

  /** Teil-Update der Auswahl-Anzeige (Zähler, Export-Knopf, Checkboxen)
   * ohne vollständigen Render (Befund F10). */
  aktualisiereAuswahlAnzeige() {
    const zaehler = this._mainEl.querySelector("[data-auswahl-anzahl]");
    if (zaehler) zaehler.textContent = `${this.auswahl.size} ausgewählt`;
    const export_ = this._mainEl.querySelector("[data-export]");
    if (export_) export_.disabled = this.auswahl.size === 0;
    this._mainEl.querySelectorAll("[data-auswahl]").forEach((cb) => { cb.checked = this.auswahl.has(cb.dataset.auswahl); });
  }

  listTable() {
    const zeilen = this.sortierteGefilterteItems();
    const pfeil = (spalte) => this.listenSortSpalte === spalte ? (this.listenSortRichtung === "asc" ? " ▲" : " ▼") : "";

    return `<div class="list-filter">
        <input type="text" data-listen-filter placeholder="Nach Name oder Adresse filtern …" value="${this.escAttr(this.listenFilter)}">
      </div>
      <div class="table-scroll">
        <table class="hoflaeden-table">
          <thead>
            <tr>
              <th>Auswahl</th>
              <th><button type="button" class="table-sort" data-sort="name">Name${pfeil("name")}</button></th>
              <th><button type="button" class="table-sort" data-sort="adresse">Adresse${pfeil("adresse")}</button></th>
              <th><button type="button" class="table-sort" data-sort="geoeffnet">Status${pfeil("geoeffnet")}</button></th>
              <th><button type="button" class="table-sort" data-sort="bewertung">Bewertung${pfeil("bewertung")}</button></th>
              <th>Route</th>
            </tr>
          </thead>
          <tbody data-list-body>
            ${this.listenZeilenHtml(zeilen)}
          </tbody>
        </table>
      </div>`;
  }

  /** Markup der Kartenansicht (Issue #2). Die eigentliche Leaflet-Karte
   * wird erst nach dem Rendern in initKarte() in den hier erzeugten,
   * noch leeren Container eingehängt (siehe render()). Ohne einen
   * einzigen Hofladen mit gültigen Koordinaten wird gar nicht erst
   * versucht, eine Karte aufzubauen – stattdessen eine klare Meldung. */
  karteAnsicht() {
    const alleMitKoordinaten = this.items.filter((item) => isValidWgs84(item.latitude, item.longitude));
    if (!alleMitKoordinaten.length) {
      return `<section class="card karte-empty"><p class="muted">Keine Hofläden mit hinterlegten Koordinaten vorhanden – es kann keine Karte angezeigt werden.</p></section>`;
    }

    const gefiltert = this.karteNurGeoeffnet ? alleMitKoordinaten.filter((item) => item.geoeffnet === true) : alleMitKoordinaten;

    // Das Leaflet-Stylesheet liegt dauerhaft ausserhalb von <main> (siehe
    // sorgeFuerKarteCss()). Der Platzhalter [data-karte-container] wird in
    // initKarte() durch den dauerhaften Karten-Container ersetzt.
    return `<div class="karte-filter-row">
        <label><input type="checkbox" data-karte-nur-geoeffnet ${this.karteNurGeoeffnet ? "checked" : ""}> Nur aktuell geöffnete Hofläden anzeigen</label>
      </div>
      <div class="notice error" data-karte-fehler ${this.karteFehler ? "" : "hidden"}><span data-karte-fehler-text>${this.esc(this.karteFehler)}</span> <button type="button" class="secondary" data-karte-erneut>Erneut versuchen</button></div>
      <div class="karte-container" data-karte-container></div>
      <p class="muted" data-karte-leer style="margin-top:8px" ${gefiltert.length ? "hidden" : ""}>Kein Hofladen entspricht aktuell diesem Filter.</p>`;
  }

  // --- Export/Import (Issue #5) ------------------------------------------
  //
  // Export läuft vollständig clientseitig über einen Blob-Download - kein
  // neuer Server-Endpunkt nötig. Import ist zweistufig: zuerst eine rein
  // lesende Vorschau ("import_preview"), die Struktur validiert und
  // mögliche Duplikate ermittelt (serverseitig, siehe management.py -
  // Name/Adresse-Abgleich sowie die Validierungslogik sollen nicht ein
  // zweites Mal in JavaScript nachgebaut werden), danach - nach
  // Entscheidung über jedes gefundene Duplikat - der eigentliche Import
  // ("import_commit"). Das hält jegliche Fachlogik serverseitig; das
  // Frontend übernimmt hier bewusst nur Dateiauswahl/-lesen und die
  // Diff-/Dialog-Darstellung.

  /** Vom Server ergänzte, rein berechnete Felder (kein Teil von
   * models.Hofladen, siehe management.py:_serialize_hofladen) vor dem
   * Export entfernen - der Export soll exakt das interne Datenmodell
   * widerspiegeln, keine flüchtigen, zur Exportzeit gültigen Werte. */
  bereinigtFuerExport(item) {
    const { geoeffnet, hauptbild_url, ...rest } = item;
    return rest;
  }

  exportZeitstempel() {
    const jetzt = new Date();
    return jetzt.toISOString().slice(0, 19).replace(/[:T]/g, "-");
  }

  exportAuswahl() {
    if (!this.auswahl.size) return;
    const ausgewaehlt = this.items.filter((item) => this.auswahl.has(item.id));
    const bereinigt = ausgewaehlt.map((item) => this.bereinigtFuerExport(item));

    const blob = new Blob([JSON.stringify(bereinigt, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = `hoflaeden-export-${this.exportZeitstempel()}.json`;
      link.click();
    } finally {
      URL.revokeObjectURL(url);
    }

    this.message = `${ausgewaehlt.length} Hofladen/Hofläden exportiert.`;
    this.error = "";
    this.render();
  }

  /** Datei-Auswahl für den Import verarbeiten: lesen, als JSON parsen und
   * strukturell auf oberster Ebene prüfen (muss eine nicht-leere Liste
   * von Objekten sein) - alles Weitere (Feldvalidierung je Hofladen,
   * Duplikaterkennung) übernimmt der Server (ws_import_preview). */
  async importDatei(file) {
    if (!file) return;
    this.error = "";
    this.message = "";

    // F12: Dateigrösse VOR dem Lesen/Parsen begrenzen.
    if (file.size > IMPORT_MAX_BYTES) {
      this.error = `Die Datei ist zu gross (höchstens ${IMPORT_MAX_BYTES / (1024 * 1024)} MB erlaubt).`;
      this.render();
      return;
    }

    let inhalt;
    try {
      inhalt = await file.text();
    } catch {
      this.error = "Die Datei konnte nicht gelesen werden.";
      this.render();
      return;
    }

    let daten;
    try {
      daten = JSON.parse(inhalt);
    } catch {
      this.error = "Die Datei enthält kein gültiges JSON.";
      this.render();
      return;
    }

    if (!Array.isArray(daten) || !daten.length) {
      this.error = "Die Datei muss eine JSON-Liste mit mindestens einem Hofladen enthalten.";
      this.render();
      return;
    }
    if (daten.length > IMPORT_MAX_EINTRAEGE) {
      this.error = `Die Datei enthält zu viele Hofläden (höchstens ${IMPORT_MAX_EINTRAEGE} je Import erlaubt).`;
      this.render();
      return;
    }
    if (!daten.every((eintrag) => eintrag && typeof eintrag === "object" && !Array.isArray(eintrag))) {
      this.error = "Die Datei enthält ungültige Einträge (jeder Hofladen muss ein Objekt sein).";
      this.render();
      return;
    }

    try {
      const antwort = await this.call("hofkarte/management/import_preview", { hoflaeden: daten });
      this.starteKonfliktloesung(antwort.eintraege || []);
    } catch (err) {
      this.error = err?.message || "Die Datei konnte nicht importiert werden.";
      this.render();
    }
  }

  /** Entscheiden, ob überhaupt eine Konfliktlösung nötig ist: ohne
   * erkannte Duplikate wird direkt importiert, ohne unnötigen Dialog. */
  starteKonfliktloesung(eintraege) {
    const duplikate = eintraege.filter((eintrag) => eintrag.duplikat_von);
    if (!duplikate.length) {
      this.commitImport(eintraege.map((eintrag) => ({ hofladen: eintrag.hofladen, aktion: "neu" })));
      return;
    }
    this.importDialog = { eintraege, entscheidungen: new Map() };
    this.render();
  }

  /** Feldweiser Vergleich zwischen bestehendem und importiertem
   * Hofladen für die Diff-Darstellung im Konfliktdialog. Sammlungsfelder
   * (Öffnungszeiten, Angebote, ...) werden bewusst nur über ihre Anzahl
   * verglichen statt vollständig aufgelistet - genug, um auf einen
   * Blick zu erkennen, ob sich etwas geändert hat, ohne den Dialog mit
   * verschachtelten Detailtabellen zu überladen. */
  diffFelder(bestehend, importiert) {
    const skalar = [
      ["name", "Name"], ["adresse", "Adresse"], ["plz", "PLZ"], ["ort", "Ort"], ["land", "Land"],
      ["website", "Website"], ["mobilnummer", "Mobilnummer"], ["email", "E-Mail"],
      ["beschreibung", "Beschreibung"], ["bemerkung", "Bemerkung"],
      ["latitude", "Latitude"], ["longitude", "Longitude"], ["bewertung", "Bewertung"],
    ];
    const sammlungen = [
      ["oeffnungszeiten", "Öffnungszeiten"], ["sonderoeffnungszeiten", "Sonderöffnungszeiten"],
      ["angebote", "Angebote"], ["zahlungsarten", "Zahlungsarten"], ["bilder", "Bilder"],
    ];

    const zeile = (label, altWert, neuWert) => ({
      label,
      alt: altWert === null || altWert === undefined || altWert === "" ? "–" : String(altWert),
      neu: neuWert === null || neuWert === undefined || neuWert === "" ? "–" : String(neuWert),
      unterschiedlich: String(altWert ?? "") !== String(neuWert ?? ""),
    });

    return [
      ...skalar.map(([feld, label]) => zeile(label, bestehend[feld], importiert[feld])),
      ...sammlungen.map(([feld, label]) => zeile(
        label,
        `${(bestehend[feld] || []).length} Einträge`,
        `${(importiert[feld] || []).length} Einträge`,
      )),
    ];
  }

  importKonfliktEintrag(eintrag) {
    const bestehend = eintrag.bestehend;
    const importiert = eintrag.hofladen;
    const entscheidung = this.importDialog.entscheidungen.get(eintrag.duplikat_von) || "";
    const felder = this.diffFelder(bestehend, importiert);
    const feldZeile = (spalte) => felder.map((f) => `<div class="import-diff-feld${f.unterschiedlich ? ` diff-${spalte}` : ""}"><span class="diff-label">${this.esc(f.label)}</span><span>${this.esc(spalte === "alt" ? f.alt : f.neu)}</span></div>`).join("");

    return `<section class="card import-konflikt">
      <h3>Mögliches Duplikat: ${this.esc(importiert.name)}</h3>
      <div class="import-diff">
        <div class="import-diff-spalte"><h4>Bestehend</h4>${feldZeile("alt")}</div>
        <div class="import-diff-spalte"><h4>Importiert</h4>${feldZeile("neu")}</div>
      </div>
      <div class="actions">
        <button type="button" class="${entscheidung === "aktualisieren" ? "" : "secondary"}" data-import-entscheidung="${this.escAttr(eintrag.duplikat_von)}" data-import-aktion="aktualisieren">Aktualisieren</button>
        <button type="button" class="${entscheidung === "ueberspringen" ? "" : "secondary"}" data-import-entscheidung="${this.escAttr(eintrag.duplikat_von)}" data-import-aktion="ueberspringen">Beibehalten</button>
      </div>
    </section>`;
  }

  importKonflikte() {
    const { eintraege, entscheidungen } = this.importDialog;
    const duplikate = eintraege.filter((eintrag) => eintrag.duplikat_von);
    const neue = eintraege.filter((eintrag) => !eintrag.duplikat_von);
    const alleEntschieden = duplikate.every((eintrag) => entscheidungen.has(eintrag.duplikat_von));

    return `<div class="top"><div><h1>Import: Duplikate prüfen</h1><div class="muted">${neue.length} neue${neue.length === 1 ? "r Hofladen wird" : " Hofläden werden"} direkt importiert, ${duplikate.length} ${duplikate.length === 1 ? "bestehender Hofladen wurde" : "bestehende Hofläden wurden"} als mögliches Duplikat erkannt.</div></div></div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}
      <div class="actions" style="margin:16px 0">
        <button type="button" class="secondary" data-import-alle="aktualisieren">Alle aktualisieren</button>
        <button type="button" class="secondary" data-import-alle="ueberspringen">Alle beibehalten</button>
      </div>
      ${duplikate.map((eintrag) => this.importKonfliktEintrag(eintrag)).join("")}
      <div class="actions" style="margin-top:20px">
        <button type="button" class="secondary" data-import-abbrechen>Abbrechen</button>
        <button type="button" data-import-abschliessen>Import abschliessen${alleEntschieden ? "" : " (unentschiedene Duplikate werden beibehalten)"}</button>
      </div>`;
  }

  schliesseImportAb() {
    const { eintraege, entscheidungen } = this.importDialog;
    const eintraegeFuerCommit = eintraege.map((eintrag) => {
      if (!eintrag.duplikat_von) return { hofladen: eintrag.hofladen, aktion: "neu" };
      // Unentschiedene Duplikate werden nicht stillschweigend
      // überschrieben, sondern sicher beibehalten (kein Datenverlust
      // ohne explizite Bestätigung).
      const aktion = entscheidungen.get(eintrag.duplikat_von) || "ueberspringen";
      return { hofladen: eintrag.hofladen, aktion, bestehende_id: eintrag.duplikat_von };
    });
    this.commitImport(eintraegeFuerCommit);
  }

  async commitImport(eintraege) {
    try {
      const antwort = await this.call("hofkarte/management/import_commit", { eintraege });
      this.importDialog = null;
      this.auswahl.clear();
      this.error = "";
      this.message = `Import abgeschlossen: ${antwort.importiert} neu, ${antwort.aktualisiert} aktualisiert, ${antwort.uebersprungen} übersprungen.`;
      await this.load();
    } catch (err) {
      this.error = err?.message || "Der Import konnte nicht abgeschlossen werden.";
      this.render();
    }
  }

  // --- Detailansicht (read-only) ---------------------------------------

  detail() {
    const d = this.viewing;
    const adresse = [d.adresse, [d.plz, d.ort].filter(Boolean).join(" "), d.land].filter(Boolean).join(", ");
    const hatKoordinaten = d.latitude != null && d.longitude != null;

    return `<div class="top">
        <div><h1>${this.esc(d.name)}</h1><div class="muted">Detailansicht – nur Anzeige</div></div>
        <div class="actions"><button class="secondary" data-back>← Zurück zur Liste</button><button data-edit-from-detail="${this.escAttr(d.id)}">Bearbeiten</button></div>
      </div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}

      ${d.beschreibung ? `<section class="card detail-section"><h3>Allgemeine Informationen</h3><div>${this.esc(d.beschreibung)}</div></section>` : ""}
      ${d.bemerkung ? `<section class="card detail-section"><h3>Bemerkung</h3><div>${this.esc(d.bemerkung)}</div></section>` : ""}

      <section class="card detail-section">
        <h3>Adresse</h3>
        <div>${adresse ? this.esc(adresse) : '<span class="muted">Keine Adresse hinterlegt</span>'}</div>
      </section>

      ${this.detailKontaktSection(d)}

      <section class="card detail-section">
        <h3>Standort / Koordinaten</h3>
        <div class="coord-row">
          <div class="muted">${hatKoordinaten ? `Latitude ${d.latitude.toFixed(6)}, Longitude ${d.longitude.toFixed(6)}` : "Keine Koordinaten hinterlegt"}</div>
        </div>
        <div class="coord-actions">${this.routingAuswahl(d)}</div>
      </section>

      <section class="card detail-section">
        <h3>Öffnungszeiten</h3>
        ${this.detailOpeningHours(d.oeffnungszeiten || [])}
        ${(d.sonderoeffnungszeiten || []).length ? `<h3 style="margin-top:14px">Sonderöffnungszeiten</h3>${this.detailSpecialHours(d.sonderoeffnungszeiten)}` : ""}
      </section>

      ${this.detailAngeboteSection(d.angebote)}
      ${this.detailPillSection("Zahlungsarten", d.zahlungsarten)}

      ${(d.bilder || []).length ? `<section class="card detail-section"><h3>Bilder</h3><div class="thumbs">${d.bilder.map(b => this.bildHtml(b.url, b.beschreibung || d.name)).join("")}</div></section>` : ""}

      <section class="card detail-section">
        <h3>Bewertung</h3>
        ${this.bewertungSterne(d.bewertung || 0, false)}
      </section>

      ${this.detailQuellenSection(d.quellen)}
    `;
  }

  /** Herkunft einzelner Angaben (aus "Hofladen finden"), samt Lizenzhinweis
   * für OpenStreetMap-Daten; nur anzeigen, wenn vorhanden. */
  detailQuellenSection(quellen) {
    if (!Array.isArray(quellen) || !quellen.length) return "";
    const labels = { name: "Name", beschreibung: "Beschreibung", adresse: "Adresse", plz: "PLZ", ort: "Ort", land: "Land", website: "Webseite", mobilnummer: "Telefon", email: "E-Mail", latitude: "Latitude", longitude: "Longitude", oeffnungszeiten: "Öffnungszeiten", angebote: "Angebote", zahlungsarten: "Zahlungsarten" };
    const zeilen = quellen.map((q) => {
      const art = HofkartePanel.FINDEN_QUELLEN_LABEL[q.quelle] || q.quelle;
      const text = this.istHttpUrl(q.url)
        ? `<a class="website-link" href="${this.escAttr(q.url)}" target="_blank" rel="noopener noreferrer">${this.esc(art)}</a>`
        : this.esc(art);
      return `<tr><td>${this.esc(labels[q.feld] || q.feld)}</td><td>${text}</td></tr>`;
    }).join("");
    const osm = quellen.some(q => q.quelle === "openstreetmap");
    return `<section class="card detail-section"><h3>Herkunft der Angaben</h3><table class="opening-table">${zeilen}</table>${osm ? `<div class="muted">© OpenStreetMap-Mitwirkende (ODbL)</div>` : ""}</section>`;
  }

  /** Webseite als anklickbarer Link – kein UI-Block, wenn keine/keine
   * gültige URL hinterlegt ist (siehe Anforderung: kein leerer Bereich). */
  /** Kernlogik für die Website-Darstellung (nur der Link/Hinweis selbst,
   * ohne umgebende Sektion) – wird sowohl von der Detailansicht als auch
   * von Kacheln/Tabellenzeilen verwendet, um Validierung/Linkaufbau
   * nicht zu duplizieren. */
  websiteLinkHtml(website) {
    if (!website || !website.trim()) return "";
    const trimmed = website.trim();
    const href = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    if (!this.isPlausibleUrl(trimmed)) {
      return `<span class="muted">Ungültige Webseiten-Adresse: ${this.esc(trimmed)}</span>`;
    }
    return `<a class="website-link" href="${this.escAttr(href)}" target="_blank" rel="noopener noreferrer">🔗 ${this.esc(trimmed)}</a>`;
  }

  websiteLinkBlock(website) {
    const inhalt = this.websiteLinkHtml(website);
    if (!inhalt) return "";
    return `<section class="card detail-section"><h3>Webseite</h3>${inhalt}</section>`;
  }

  /** Abschnitt "Kontakt" der Detailansicht: Mobilnummer (tel:-Link),
   * E-Mail (mailto:-Link) und Webseite (dieselbe Darstellung wie zuvor
   * im eigenständigen "Webseite"-Abschnitt, siehe websiteLinkHtml()) -
   * unmittelbar nach "Adresse" und vor "Standort / Koordinaten". Entfällt
   * vollständig, wenn keines der drei Felder gesetzt ist (wie bei den
   * übrigen bedingten Abschnitten dieser Ansicht). */
  detailKontaktSection(d) {
    const mobilnummer = (d.mobilnummer || "").trim();
    const email = (d.email || "").trim();
    const websiteHtml = this.websiteLinkHtml(d.website);
    if (!mobilnummer && !email && !websiteHtml) return "";

    const zeilen = [];
    if (mobilnummer) {
      zeilen.push(`<div class="kontakt-zeile"><a class="website-link" href="tel:${this.escAttr(mobilnummer.replace(/[^\d+]/g, ""))}">📞 ${this.esc(mobilnummer)}</a></div>`);
    }
    if (email) {
      // F12: mailto: nur bei validierter Adresse (sonst reiner Text), damit
      // keine Zusatzparameter (?cc=…, &body=…) eingeschleust werden können.
      zeilen.push(istGueltigeEmail(email)
        ? `<div class="kontakt-zeile"><a class="website-link" href="mailto:${this.escAttr(email)}">✉️ ${this.esc(email)}</a></div>`
        : `<div class="kontakt-zeile">✉️ ${this.esc(email)}</div>`);
    }
    if (websiteHtml) {
      zeilen.push(`<div class="kontakt-zeile">${websiteHtml}</div>`);
    }

    return `<section class="card detail-section"><h3>Kontakt</h3>${zeilen.join("")}</section>`;
  }

  detailOpeningHours(rows) {
    const byDay = new Map();
    for (const row of rows) {
      const list = byDay.get(row.wochentag) || [];
      list.push(row);
      byDay.set(row.wochentag, list);
    }
    const lines = [];
    for (let day = 1; day <= 7; day++) {
      const dayRows = (byDay.get(day) || []).slice().sort((a, b) => a.beginn.localeCompare(b.beginn));
      let text;
      if (!dayRows.length) text = '<span class="muted">Geschlossen</span>';
      else if (dayRows.length === 1 && isFullDay(dayRows[0])) text = "24 Stunden geöffnet";
      else text = dayRows.map(r => `${r.beginn}–${r.ende} Uhr`).join(", ");
      lines.push(`<tr><td>${WEEKDAYS[day - 1]}</td><td>${text}</td></tr>`);
    }
    return `<table class="opening-table">${lines.join("")}</table>`;
  }

  detailSpecialHours(rows) {
    return `<table class="opening-table">${rows.map(r => {
      const zeitraum = r.datum_von === r.datum_bis ? this.formatDate(r.datum_von) : `${this.formatDate(r.datum_von)} – ${this.formatDate(r.datum_bis)}`;
      const text = r.geschlossen ? '<span class="muted">Geschlossen</span>' : `${r.beginn || "?"}–${r.ende || "?"} Uhr`;
      return `<tr><td>${this.esc(zeitraum)}</td><td>${text}</td></tr>`;
    }).join("")}</table>`;
  }

  formatDate(iso) {
    if (!iso) return "?";
    const [y, m, d] = iso.split("-");
    return `${d}.${m}.${y}`;
  }

  detailPillSection(label, entries) {
    if (!entries || !entries.length) return "";
    return `<section class="card detail-section"><h3>${label}</h3>${entries.map(e => `<span class="pill">${this.esc(e.name)}</span>`).join("")}</section>`;
  }

  /** Angebote in der Detailansicht – ersetzt die früher getrennten
   * Abschnitte "Kategorien"/"Produkte". Seit der Vereinfachung auf eine
   * schlichte Namensliste ohne Gruppierung reduziert (siehe CHANGELOG)
   * - daher eine einfache Weiterleitung an detailPillSection. */
  detailAngeboteSection(angebote) {
    return this.detailPillSection("Angebote", angebote);
  }

  // --- Editor ------------------------------------------------------------

  editor() {
    const d = this.editing;
    const latValue = (d.latitude != null && d.latitude !== "") ? d.latitude : "";
    const lonValue = (d.longitude != null && d.longitude !== "") ? d.longitude : "";

    const specials = (d.sonderoeffnungszeiten || []).map(x => `<div class="special" data-special><label>Von<input type=date name=datum_von value="${this.escAttr(x.datum_von || "")}"></label><label>Bis<input type=date name=datum_bis value="${this.escAttr(x.datum_bis || "")}"></label><label>Beginn<input type=time name=beginn value="${this.escAttr(x.beginn || "")}"></label><label>Ende<input type=time name=ende value="${this.escAttr(x.ende || "")}"></label><label>Geschlossen<input type=checkbox name=geschlossen ${x.geschlossen ? "checked" : ""}></label><button type=button class=secondary data-remove-special>−</button></div>`).join("");
    const text = (field) => (d[field] || []).map(x => x.name).join("\n");
    const angeboteText = (d.angebote || []).map(x => x.name).join("\n");

    return `<div class="top"><div><h1>${d.id ? "Hofladen bearbeiten" : "Neuen Hofladen erstellen"}</h1><div class="muted">${d.id ? this.esc(d.id) : "Neue stabile ID wird beim Speichern erzeugt."}</div></div></div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}
      <form>
        <section class=card>
          <h2>Allgemeine Informationen</h2>
          <div class="fields">
            <div class="field-row">${this.input("Name", "name", d.name, true)}</div>
            <div class="field-row">${this.input("Beschreibung", "beschreibung", d.beschreibung || "")}</div>
            ${this.area("Bemerkung", "bemerkung", d.bemerkung || "")}
          </div>
        </section>

        <section class=card>
          <h2>Adresse</h2>
          <div class="fields">
            <div class="field-row">${this.input("Adresse", "adresse", d.adresse || "")}</div>
            <div class="field-row two">${this.input("PLZ", "plz", d.plz || "")}${this.input("Ort", "ort", d.ort || "")}</div>
            <div class="field-row">${this.input("Land", "land", d.land || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Standort / Koordinaten <span class="muted" style="font-weight:normal;font-size:.7em">(WGS84)</span></h2>
          <div class="coord-row">
            <div class="field-row two">
              <label>Latitude<input name="latitude" type="number" step="any" value="${this.escAttr(String(latValue))}" placeholder="z. B. 46.9480"></label>
              <label>Longitude<input name="longitude" type="number" step="any" value="${this.escAttr(String(lonValue))}" placeholder="z. B. 7.4474"></label>
            </div>
            <button type="button" class="info-btn" data-toggle-coord-info title="Was sind Latitude/Longitude? (Erklärung anzeigen)" aria-label="Was sind Latitude/Longitude? Erklärung anzeigen">ⓘ</button>
          </div>
          <div class="coord-actions">${this.mapButton(latValue === "" ? NaN : Number(latValue), lonValue === "" ? NaN : Number(lonValue))}</div>
          ${this.showCoordInfo ? this.coordInfoBox() : ""}
        </section>

        <section class=card>
          <h2>Kontakt &amp; Webseite</h2>
          <div class="fields">
            <div class="field-row">${this.input("Mobilnummer", "mobilnummer", d.mobilnummer || "")}</div>
            <div class="field-row">${this.input("E-Mail", "email", d.email || "")}</div>
            <div class="field-row">${this.input("Webseite", "website", d.website || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Automatisch ausfüllen</h2>
          <p class="muted">Ermittelt Name, Adresse, Beschreibung, Öffnungszeiten, Angebote und Zahlungsarten automatisch – über die oben eingetragene Website und/oder über die Koordinaten (freie OpenStreetMap-Overpass-API). Gefundene Angaben werden vor jeder Übernahme in einem Popup zur Prüfung angezeigt, es wird dabei nichts automatisch gespeichert (siehe README.md, Abschnitt "Datenschutz- und Standort-Hinweise").</p>
          <div class="webseite-info-row">
            <button type="button" class="secondary" data-auto-info-btn title="Angaben automatisch anhand der Website und/oder Koordinaten ermitteln" aria-label="Angaben automatisch anhand der Website und/oder Koordinaten ermitteln">🔍 Angaben automatisch ermitteln</button>
            <span class="webseite-info-status muted${this.autoErmittlungStatusKind ? " " + this.autoErmittlungStatusKind : ""}" data-auto-info-status>${this.esc(this.autoErmittlungStatusText)}</span>
          </div>
          <div class="field-row" style="margin-top:8px">
            <label>Suchradius für OpenStreetMap (Meter)<input name="osm_radius" type="number" min="${OSM_MIN_RADIUS_METER}" max="${OSM_MAX_RADIUS_METER}" step="10" value="${this.osmRadius}"></label>
          </div>
        </section>

        <section class=card>
          <h2>Öffnungszeiten</h2>
          ${this.openingHoursEditor(d.oeffnungszeiten || [])}
          <h3>Sonderöffnungszeiten</h3>
          <div id=specials>${specials}</div>
          <button type=button class=secondary data-add-special>+ Sonderzeit hinzufügen</button>
        </section>

        <section class=card>
          <h2>Angebote und Zahlungsarten</h2>
          <p class=muted>Ein Eintrag pro Zeile.</p>
          ${this.area("Angebote", "angebote", angeboteText)}
          ${this.area("Zahlungsarten", "zahlungsarten", text("zahlungsarten"))}
        </section>

        <section class=card>
          <h2>Bilder</h2>
          <p class="muted">Das erste Bild in der Liste ist das Hauptbild. Bilder können hochgeladen oder per externer Adresse verlinkt werden.</p>
          <div id="bilder-liste">${this.bilderListe(d.bilder || [])}</div>
          <div class="upload-row">
            <button type="button" class="upload-start-btn" data-start-upload title="Bild-Upload starten" aria-label="Bild-Upload starten">📤 Bild hochladen</button>
            <input type="file" id="bild-upload-input" accept="image/jpeg,image/png,image/gif" style="display:none">
            <span class="upload-status muted" data-upload-status></span>
          </div>
          <details style="margin-top:10px">
            <summary class="muted" style="cursor:pointer">Oder externe Bild-Adresse manuell hinzufügen</summary>
            <div class="field-row two" style="margin-top:8px">
              <input type="text" data-external-url placeholder="https://beispiel.ch/bild.jpg">
              <button type="button" class="secondary" data-add-external-url>Hinzufügen</button>
            </div>
          </details>
        </section>

        <section class=card>
          <h2>Bewertung</h2>
          ${this.bewertungSterne(d.bewertung || 0, true)}
        </section>

        <div class=actions>
          <button type=button class=secondary data-cancel>Abbrechen</button>
          <button type=submit>Speichern</button>
        </div>
      </form>
      ${this.webseiteInfoVorschlag ? this.webseiteInfoPopup(this.webseiteInfoVorschlag) : ""}
      ${this.osmOrteAuswahl ? this.osmOrteAuswahlPopup(this.osmOrteAuswahl) : ""}`;
  }

  /** Bestätigungs-Popup für die von "🔍 Angaben automatisch ermitteln"
   * gefundenen Vorschlagsdaten (Issue #9, Erweiterung 5.2; seit Issue #11
   * gemeinsames Popup für Website- UND OSM-Ergebnisse, siehe
   * ermittleAutomatisch()/mischeAutoVorschlaege()). Fasst die gefundenen
   * Informationen übersichtlich zusammen und blendet dabei nicht
   * gefundene Felder klar als solche ein (statt sie stillschweigend
   * wegzulassen), bevor die Benutzerin/der Benutzer sie explizit über
   * "Übernehmen" bestätigt oder über "Abbrechen" verwirft. Stammt ein
   * Feld erkennbar aus nur einer Quelle (this.autoErmittlungQuellen -
   * nur gesetzt, wenn tatsächlich beide Quellen abgefragt wurden), wird
   * das als kleine Kennzeichnung angezeigt (Issue #11, 5.1) - bei einem
   * Konflikt (beide Quellen liefern unterschiedliche Werte) bleibt der
   * abweichende Wert der nicht gewählten Quelle sichtbar, statt
   * stillschweigend verworfen zu werden. Als echtes modales Overlay
   * umgesetzt (nicht wie coordInfoBox() als eingebetteter Infokasten), da
   * es – anders als die reine Zusatzerklärung dort – eine tatsächliche
   * Entscheidung mit zwei Handlungsoptionen darstellt, die den Blick auf
   * das Formular dahinter bewusst kurzzeitig blockieren soll. */
  webseiteInfoPopup(info) {
    const quellen = this.autoErmittlungQuellen || {};
    const quellenLabel = { website: "Website", osm: "OpenStreetMap", "website+osm": "Website, abweichend auch OpenStreetMap" };
    const badge = (feld) => {
      const quelle = quellen[feld];
      return quelle ? ` <span class="muted quelle-badge">(${quellenLabel[quelle] || quelle})</span>` : "";
    };
    const zeile = (label, wert, feld) => `<div class="webseite-info-zeile"><span class="webseite-info-label">${this.esc(label)}</span><span>${wert ? this.esc(wert) + (feld ? badge(feld) : "") : '<span class="muted">– nicht gefunden –</span>'}</span></div>`;
    const adresse = [info.adresse, info.plz, info.ort, info.land].filter(Boolean).join(", ");
    // Bei Angeboten/Zahlungsarten reicht eine einfache Aufzählung der
    // gefundenen Namen; bei Öffnungszeiten wäre eine Aufzählung aller
    // einzelnen Wochentag-Einträge unübersichtlich, daher dort bewusst
    // nur die Anzahl gefundener Einträge (siehe Anforderung 5.2).
    const namenListe = (liste) => (Array.isArray(liste) && liste.length ? liste.map(x => x.name || x).join(", ") : "");
    const oeffnungszeitenText = Array.isArray(info.oeffnungszeiten) && info.oeffnungszeiten.length
      ? `${info.oeffnungszeiten.length} Eintrag${info.oeffnungszeiten.length === 1 ? "" : "e"} gefunden`
      : "";

    return `<div class="modal-overlay" data-webseite-info-overlay>
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="webseite-info-titel" tabindex="-1" data-webseite-info-dialog>
        <h2 id="webseite-info-titel">Gefundene Informationen</h2>
        <p class="muted">Bitte prüfen. Erst nach "Übernehmen" werden die Vorschläge in die Formularfelder eingetragen – gespeichert wird dabei weiterhin nichts.</p>
        ${zeile("Name", info.name, "name")}
        ${zeile("Beschreibung", info.beschreibung, "beschreibung")}
        ${zeile("Adresse", adresse, "adresse")}
        ${zeile("Webseite", info.website, "website")}
        ${zeile("Telefon", info.mobilnummer, "mobilnummer")}
        ${zeile("E-Mail", info.email, "email")}
        ${zeile("Öffnungszeiten", oeffnungszeitenText, "oeffnungszeiten")}
        ${zeile("Angebote", namenListe(info.angebote), "angebote")}
        ${zeile("Zahlungsarten", namenListe(info.zahlungsarten), "zahlungsarten")}
        <div class="actions">
          <button type="button" class="secondary" data-webseite-info-abbrechen>Abbrechen</button>
          <button type="button" data-webseite-info-uebernehmen>Übernehmen</button>
        </div>
      </div>
    </div>`;
  }

  /** Trefferauswahl-Popup für "Ort in der Nähe suchen" (Issue #10, 5.2),
   * wenn die Overpass-API-Suche mehr als einen Treffer liefert. Zeigt zu
   * jedem Treffer Name, Adresse (falls vorhanden) und Entfernung, damit
   * die Benutzerin/der Benutzer den passenden Ort auswählen kann - ohne
   * hier bereits etwas zu übernehmen (das erfolgt erst im nachfolgenden,
   * gemeinsam genutzten Bestätigungs-Popup, siehe waehleOsmOrt()/
   * webseiteInfoPopup()). Bei genau einem Treffer wird diese Liste
   * übersprungen (siehe ermittleAutomatisch()). Treffer, die nur über die
   * Namens-Heuristik (osm_info.py, OsmOrt.via_namen_heuristik) gefunden
   * wurden, werden hier als solche gekennzeichnet (Issue #11, 5.2) - kein
   * echtes Hofladen-Tag auf OpenStreetMap, nur ein Namenshinweis auf einer
   * Hofstelle. */
  osmOrteAuswahlPopup(orte) {
    const eintraege = orte.map((ort, index) => {
      const adresse = [ort.adresse, ort.plz, ort.ort].filter(Boolean).join(", ");
      const entfernung = typeof ort.entfernung_meter === "number"
        ? `${Math.round(ort.entfernung_meter)} m entfernt`
        : "";
      return `<button type="button" class="secondary osm-orte-eintrag" data-osm-orte-auswahl="${index}">
        <span class="osm-orte-name">${this.esc(ort.name || "")}</span>
        ${adresse ? `<span class="muted">${this.esc(adresse)}</span>` : ""}
        ${entfernung ? `<span class="muted">${this.esc(entfernung)}</span>` : ""}
        ${ort.via_namen_heuristik ? `<span class="muted">anhand des Namens gefunden, kein Hofladen-Tag auf OpenStreetMap</span>` : ""}
      </button>`;
    }).join("");

    return `<div class="modal-overlay" data-osm-orte-overlay>
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="osm-orte-titel" tabindex="-1" data-osm-orte-dialog>
        <h2 id="osm-orte-titel">Gefundene Orte</h2>
        <p class="muted">Bitte einen Ort auswählen. Die Angaben werden anschliessend noch einmal zur Prüfung angezeigt, bevor etwas übernommen wird.</p>
        <div class="osm-orte-liste">${eintraege}</div>
        <div class="actions">
          <button type="button" class="secondary" data-osm-orte-abbrechen>Abbrechen</button>
        </div>
      </div>
    </div>`;
  }

  /** Liste der Bilder eines Hofladens im Editor – Vorschau, optionale
   * Beschreibung, "Als Hauptbild"/"Entfernen"-Aktionen. Das erste Bild
   * gilt als Hauptbild (bestehende Konvention, siehe images.py). */
  bilderListe(bilder) {
    if (!bilder.length) return `<p class="muted">Noch keine Bilder hinterlegt.</p>`;
    return bilder.map((bild, i) => `<div class="bild-row" data-bild-index="${i}">
      ${this.bildHtml(bild.url, "", true)}
      <div class="bild-row-fields">
        <input type="text" data-bild-beschreibung placeholder="Beschreibung (optional)" value="${this.escAttr(bild.beschreibung || "")}">
        <div class="bild-row-meta muted">${i === 0 ? "Hauptbild · " : ""}${bild.hochgeladen ? "hochgeladen" : "externe Adresse"}</div>
      </div>
      <div class="bild-row-actions">
        ${i !== 0 ? `<button type="button" class="secondary" data-bild-hauptbild="${i}" title="Als Hauptbild festlegen">⭐</button>` : ""}
        <button type="button" class="danger" data-bild-entfernen="${i}" title="Bild entfernen">🗑️</button>
      </div>
    </div>`).join("");
  }

  /** Sterne-Darstellung einer Bewertung (0-5), gemeinsam genutzt vom
   * interaktiven Editor-Abschnitt "Bewertung" und der nur anzeigenden
   * Detailansicht (``interaktiv=false``). Horizontal zentriert (siehe
   * .sterne-reihe). Im interaktiven Modus ist jedes Symbol ein eigener
   * Button (data-bewertung-stern="n") statt eines einzigen Schiebereglers
   * - das bildet die geforderte "Klick auf das n-te Symbol setzt
   * Bewertung auf n"-Logik unmittelbar ab, ohne eine zusätzliche
   * Positions-/Breitenberechnung aus einem Klickereignis ableiten zu
   * müssen. */
  bewertungSterne(wert, interaktiv = false) {
    const aktuell = Math.max(0, Math.min(BEWERTUNG_MAX, Number(wert) || 0));
    const symbole = [];
    for (let n = 1; n <= BEWERTUNG_MAX; n++) {
      const gefuellt = n <= aktuell;
      const glyph = gefuellt ? "★" : "☆";
      if (interaktiv) {
        symbole.push(`<button type="button" class="stern-btn${gefuellt ? " stern-gefuellt" : ""}" data-bewertung-stern="${n}" aria-label="${n} von ${BEWERTUNG_MAX} Sternen" aria-pressed="${gefuellt}">${glyph}</button>`);
      } else {
        symbole.push(`<span class="stern-btn stern-anzeige${gefuellt ? " stern-gefuellt" : ""}" aria-hidden="true">${glyph}</span>`);
      }
    }
    return `<div class="sterne-reihe" role="${interaktiv ? "group" : "img"}" aria-label="Bewertung: ${aktuell} von ${BEWERTUNG_MAX} Sternen">${symbole.join("")}</div>`;
  }

  /** Setzt die Bewertung auf ``wert`` (1-5) bzw. auf 0, wenn erneut auf
   * das aktuell zuletzt gefüllte Symbol geklickt wird (einzige
   * Möglichkeit, 0 zu erreichen - siehe Anforderung "Bewertung").
   * Sichert vorher den übrigen Formularzustand (erfasseFormularZustand()),
   * da render() das Formular danach komplett neu aufbaut (analog zu
   * setHauptbild()/removeBild()). */
  setBewertung(wert) {
    if (!this.editing) return;
    this.erfasseFormularZustand();
    this.editing.bewertung = (this.editing.bewertung === wert) ? 0 : wert;
    this.render();
  }

  coordInfoBox() {
    return `<div class="info-box">
      <strong>Was sind Latitude/Longitude?</strong><br>
      Latitude und Longitude (WGS84, Dezimalgrad) sind das weltweit
      gebräuchliche Koordinatensystem, mit dem auch Home Assistant
      selbst Standorte angibt. Es besteht aus zwei Werten:<br>
      • <strong>Latitude (Breitengrad)</strong> – Wert zwischen -90 und
      90 (Schweiz: ca. 45.8 bis 47.8)<br>
      • <strong>Longitude (Längengrad)</strong> – Wert zwischen -180
      und 180 (Schweiz: ca. 5.9 bis 10.5)<br>
      Beide Werte findest du z. B. in Google Maps (Rechtsklick auf den
      gewünschten Ort → die angezeigten Zahlen sind Latitude,
      Longitude) oder über den Button „Auf Google Maps anzeigen“
      unten, sobald bereits Koordinaten hinterlegt sind.
    </div>`;
  }

  /** Öffnungszeiten-Editor: pro Wochentag ein Block mit Modus
   * Geschlossen / 24 Stunden / Zeiten festlegen (statt eines globalen
   * prompt()-Dialogs). */
  openingHoursEditor(rows) {
    const byDay = new Map();
    for (const row of rows) {
      const list = byDay.get(Number(row.wochentag)) || [];
      list.push(row);
      byDay.set(Number(row.wochentag), list);
    }

    const blocks = [];
    for (let day = 1; day <= 7; day++) {
      const dayRows = byDay.get(day) || [];
      let mode = "geschlossen";
      if (dayRows.length === 1 && isFullDay(dayRows[0])) mode = "24h";
      else if (dayRows.length > 0) mode = "zeiten";

      const intervalsHtml = (mode === "zeiten" ? dayRows : []).map(r => this.intervalRow(day, r)).join("");

      blocks.push(`<div class="day-block" data-day-block="${day}">
        <div class="day-title">${WEEKDAYS[day - 1]}</div>
        <div class="day-mode">
          <label><input type="radio" name="day_mode_${day}" value="geschlossen" ${mode === "geschlossen" ? "checked" : ""}> Geschlossen</label>
          <label><input type="radio" name="day_mode_${day}" value="24h" ${mode === "24h" ? "checked" : ""}> 24 Stunden geöffnet</label>
          <label><input type="radio" name="day_mode_${day}" value="zeiten" ${mode === "zeiten" ? "checked" : ""}> Zeiten festlegen</label>
        </div>
        <div class="day-intervals" data-day-intervals="${day}" style="${mode === "zeiten" ? "" : "display:none"}">
          ${intervalsHtml || this.intervalRow(day, { beginn: "", ende: "" })}
          <button type="button" class="secondary" data-add-interval="${day}">+ weiteres Intervall</button>
        </div>
      </div>`);
    }
    return blocks.join("");
  }

  intervalRow(day, x) {
    return `<div class="interval-row" data-day-interval="${day}">
      <label>Von<input type=time name=beginn value="${this.escAttr(x.beginn || "")}"></label>
      <label>Bis<input type=time name=ende value="${this.escAttr(x.ende || "")}"></label>
      <button type=button class=secondary data-remove-interval title="Intervall entfernen">−</button>
    </div>`;
  }

  input(label, name, value, required = false) { return `<label>${label}<input name="${name}" value="${this.escAttr(String(value))}" ${required ? "required" : ""}></label>`; }
  area(label, name, value) { return `<label>${label}<textarea name="${name}">${this.esc(value)}</textarea></label>`; }

  // --- Ereignisbindung -----------------------------------------------

  /** Einmalig im Konstruktor gebundene Event-Delegation auf <main>
   * (Befund F10): <main> bleibt über alle Renders bestehen, es entstehen
   * daher keine Listener pro Kachel/Zeile/Render mehr. */
  bindDelegiert() {
    const main = this._mainEl;
    main.addEventListener("click", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel) return;
      const a = ziel.closest("[data-ansicht]");
      if (a) {
        this.uebersichtsAnsicht = a.dataset.ansicht;
        if (this.uebersichtsAnsicht === "karte") this.karteFehler = ""; // ausdrückliches Öffnen = neuer Ladeversuch
        this.render();
        return;
      }
      const sortierung = ziel.closest("[data-sort]");
      if (sortierung) {
        const spalte = sortierung.dataset.sort;
        if (this.listenSortSpalte === spalte) {
          this.listenSortRichtung = this.listenSortRichtung === "asc" ? "desc" : "asc";
        } else {
          this.listenSortSpalte = spalte;
          this.listenSortRichtung = "asc";
        }
        this.render();
        return;
      }
      const ansehen = ziel.closest("[data-view]");
      if (ansehen) { this.view(this.items.find(x => x.id === ansehen.dataset.view)); return; }
      const bearbeiten = ziel.closest("[data-edit]");
      if (bearbeiten) { this.start(this.items.find(x => x.id === bearbeiten.dataset.edit)); return; }
      const loeschen = ziel.closest("[data-delete]");
      if (loeschen) { this.remove(loeschen.dataset.delete); return; }
      if (ziel.closest("[data-erneut-laden]")) { this.ladeErneut(); return; }
      if (ziel.closest("[data-karte-erneut]")) { this.karteFehler = ""; this.render(); }
    });
    main.addEventListener("change", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel) return;
      if (ziel.matches("[data-auswahl]")) {
        const id = ziel.dataset.auswahl;
        if (ziel.checked) this.auswahl.add(id); else this.auswahl.delete(id);
        this.aktualisiereAuswahlAnzeige();
      } else if (ziel.matches("[data-karte-nur-geoeffnet]")) {
        this.karteNurGeoeffnet = ziel.checked;
        this.aktualisiereMarker(); // nur die Marker-Ebene tauschen, kein Render
      }
    });
    main.addEventListener("input", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel || !ziel.matches("[data-listen-filter]")) return;
      // Debounce (~150 ms) + Teil-Update nur der Tabellenzeilen: das
      // Eingabefeld bleibt bestehen, Fokus/Cursor gehen nicht verloren.
      const wert = ziel.value;
      clearTimeout(this._filterTimer);
      this._filterTimer = setTimeout(() => {
        this._filterTimer = null;
        this.listenFilter = wert;
        this.aktualisiereListe();
      }, 150);
    });
    // Rückfall auf das Original, falls eine 256x256-Vorschau nicht
    // ausgeliefert wird (Befund F14). Fehler-Ereignisse bubbeln nicht,
    // daher in der Capture-Phase.
    main.addEventListener("error", (e) => {
      const img = e.target;
      if (img instanceof HTMLImageElement && img.dataset.original && img.src !== img.dataset.original) {
        img.src = img.dataset.original;
      }
    }, true);
    this.bindFindenDelegiert();
  }

  bind() {
    this.shadowRoot.querySelector("[data-new]")?.addEventListener("click", () => this.start());
    // Listen-/Karten-Aktionen (Ansichtswechsel, Sortierung, Details,
    // Bearbeiten, Löschen, Auswahl, Filter, Karten-Filter, "Erneut
    // versuchen") laufen über die einmalig gebundene Event-Delegation auf
    // <main> (siehe bindDelegiert(), Befund F10) - hier nicht je Element.
    // --- Export/Import (Issue #5) ---
    this.shadowRoot.querySelector("[data-auswahl-alle]")?.addEventListener("click", () => {
      this.items.forEach((item) => this.auswahl.add(item.id));
      this.aktualisiereAuswahlAnzeige();
    });
    this.shadowRoot.querySelector("[data-auswahl-keine]")?.addEventListener("click", () => {
      this.auswahl.clear();
      this.aktualisiereAuswahlAnzeige();
    });
    this.shadowRoot.querySelector("[data-export]")?.addEventListener("click", () => this.exportAuswahl());
    this.shadowRoot.querySelector("[data-import-start]")?.addEventListener("click", () => {
      this.shadowRoot.querySelector("[data-import-input]")?.click();
    });
    this.shadowRoot.querySelector("[data-import-input]")?.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      this.importDatei(file);
      e.target.value = ""; // erlaubt erneuten Import derselben Datei
    });
    this.shadowRoot.querySelectorAll("[data-import-entscheidung]").forEach((b) => b.addEventListener("click", () => {
      this.importDialog.entscheidungen.set(b.dataset.importEntscheidung, b.dataset.importAktion);
      this.render();
    }));
    this.shadowRoot.querySelectorAll("[data-import-alle]").forEach((b) => b.addEventListener("click", () => {
      const aktion = b.dataset.importAlle;
      for (const eintrag of this.importDialog.eintraege) {
        if (eintrag.duplikat_von) this.importDialog.entscheidungen.set(eintrag.duplikat_von, aktion);
      }
      this.render();
    }));
    this.shadowRoot.querySelector("[data-import-abbrechen]")?.addEventListener("click", () => {
      this.importDialog = null;
      this.render();
    });
    this.shadowRoot.querySelector("[data-import-abschliessen]")?.addEventListener("click", () => this.schliesseImportAb());

    this.shadowRoot.querySelector("[data-edit-from-detail]")?.addEventListener("click", (e) => this.start(this.items.find(x => x.id === e.target.dataset.editFromDetail)));
    this.shadowRoot.querySelector("[data-back]")?.addEventListener("click", () => this.closeView());
    this.shadowRoot.querySelector("[data-cancel]")?.addEventListener("click", () => this.cancel());
    this.shadowRoot.querySelector("form")?.addEventListener("submit", e => { e.preventDefault(); this.save(); });

    this.shadowRoot.querySelector('[data-toggle-coord-info]')?.addEventListener("click", () => { this.showCoordInfo = !this.showCoordInfo; this.render(); });

    this.shadowRoot.querySelectorAll('input[name^="day_mode_"]').forEach(radio => radio.addEventListener("change", (e) => {
      const day = e.target.name.split("_")[2];
      const container = this.shadowRoot.querySelector(`[data-day-intervals="${day}"]`);
      if (container) container.style.display = e.target.value === "zeiten" ? "" : "none";
    }));
    this.shadowRoot.querySelectorAll("[data-add-interval]").forEach(b => b.addEventListener("click", () => {
      const day = b.dataset.addInterval;
      const container = this.shadowRoot.querySelector(`[data-day-intervals="${day}"]`);
      const el = document.createElement("div");
      el.innerHTML = this.intervalRow(day, { beginn: "", ende: "" });
      const neueZeile = el.firstElementChild;
      container.insertBefore(neueZeile, b);
      // Bewusst KEIN erneuter bind()-Aufruf: render() wird hier
      // nicht durchlaufen (Formularzustand/Fokus soll erhalten bleiben,
      // siehe Klassenkommentar oben), der restliche DOM existiert also
      // unverändert weiter. Ein erneuter bind()-Aufruf würde auf allen
      // bereits vorhandenen Elementen - u. a. diesem "+ weiteres
      // Intervall"-Button selbst sowie dem Formular-submit-Handler -
      // einen zusätzlichen, doppelten Listener registrieren (bind()
      // entfernt keine bestehenden Listener). Behobener Bug: Jeder
      // weitere Klick verdoppelte dadurch die Anzahl neu eingefügter
      // Zeilen, und beim Abschicken des Formulars löste der mehrfach
      // gebundene submit-Handler this.save() ebenso mehrfach aus - was
      // bei einem neuen, noch ungespeicherten Hofladen (ohne id) zu
      // mehreren, inhaltlich identischen Hofladen-Einträgen führte, da
      // ws_save() für jeden Aufruf ohne id eine eigene, neue id vergibt.
      // Stattdessen wird hier gezielt nur der "entfernen"-Button der
      // neu eingefügten Zeile selbst verkabelt.
      neueZeile.querySelector("[data-remove-interval]")?.addEventListener("click", () => neueZeile.remove());
    }));
    this.shadowRoot.querySelectorAll("[data-remove-interval]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));

    this.shadowRoot.querySelectorAll("[data-remove-special]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));
    this.shadowRoot.querySelector("[data-add-special]")?.addEventListener("click", () => {
      const el = document.createElement("div");
      el.innerHTML = `<div class="special" data-special><label>Von<input type=date name=datum_von></label><label>Bis<input type=date name=datum_bis></label><label>Beginn<input type=time name=beginn></label><label>Ende<input type=time name=ende></label><label>Geschlossen<input type=checkbox name=geschlossen></label><button type=button class=secondary data-remove-special>−</button></div>`;
      const neueZeile = el.firstElementChild;
      this.shadowRoot.querySelector("#specials").append(neueZeile);
      // Derselbe Grund wie beim "+ weiteres Intervall"-Handler oben:
      // gezielt nur den neu eingefügten "entfernen"-Button verkabeln,
      // statt erneut bind() über den gesamten, unverändert
      // bestehenden DOM laufen zu lassen (kein doppeltes Binden des
      // "+ Sonderzeit hinzufügen"-Buttons bzw. des Formular-submit-
      // Handlers).
      neueZeile.querySelector("[data-remove-special]")?.addEventListener("click", () => neueZeile.remove());
    });

    // --- Bilder ---
    // Der Start-Button löst gezielt die Dateiauswahl des bestehenden,
    // versteckten Datei-Felds aus (input.click()); der eigentliche
    // Upload-Ablauf (Validierung, Upload, Rückmeldung) bleibt
    // unverändert an das "change"-Ereignis dieses Felds gebunden.
    // "🔍 Angaben automatisch ermitteln" (Issue #11, ersetzt die bisher
    // getrennten "Infos ermitteln"/"Ort in der Nähe suchen"-Buttons durch
    // eine einzige Aktion, siehe ermittleAutomatisch()).
    this.shadowRoot.querySelector("[data-auto-info-btn]")?.addEventListener("click", () => {
      this.ermittleAutomatisch();
    });
    // Bestätigungs-Popup (Issue #9, 5.2, seit Issue #11 für beide Quellen
    // gemeinsam genutzt): "Übernehmen"/"Abbrechen" sowie Schliessen per
    // Escape-Taste (Barrierefreiheit, siehe Anforderung 5.2) - der
    // keydown-Listener sitzt bewusst auf dem Overlay selbst (nicht global
    // auf window/document), damit er automatisch mit dem Popup selbst
    // verschwindet und keine manuelle Aufräum-Logik beim Schliessen nötig
    // ist.
    this.shadowRoot.querySelector("[data-webseite-info-uebernehmen]")?.addEventListener("click", () => this.uebernehmeWebseiteInfoVorschlag());
    this.shadowRoot.querySelector("[data-webseite-info-abbrechen]")?.addEventListener("click", () => this.abbrechenWebseiteInfo());
    this.shadowRoot.querySelector("[data-webseite-info-overlay]")?.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); this.abbrechenWebseiteInfo(); }
    });
    // OSM-Trefferauswahl (Issue #10, nur bei mehr als einem Treffer, siehe
    // ermittleAutomatisch()); das nachfolgende Bestätigungs-Popup wird
    // bereits über die obigen data-webseite-info-*-Listener abgedeckt
    // (wiederverwendet, siehe waehleOsmOrt()).
    this.shadowRoot.querySelectorAll("[data-osm-orte-auswahl]").forEach(b =>
      b.addEventListener("click", () => this.waehleOsmOrt(Number(b.dataset.osmOrteAuswahl)))
    );
    this.shadowRoot.querySelector("[data-osm-orte-abbrechen]")?.addEventListener("click", () => this.abbrechenOsmAuswahl());
    this.shadowRoot.querySelector("[data-osm-orte-overlay]")?.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); this.abbrechenOsmAuswahl(); }
    });
    this.shadowRoot.querySelector("[data-start-upload]")?.addEventListener("click", () => {
      this.shadowRoot.querySelector("#bild-upload-input")?.click();
    });
    this.shadowRoot.querySelector("#bild-upload-input")?.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      this.uploadBild(file);
      e.target.value = ""; // erlaubt erneutes Hochladen derselben Datei
    });
    this.shadowRoot.querySelectorAll("[data-bild-entfernen]").forEach(b =>
      b.addEventListener("click", () => this.removeBild(Number(b.dataset.bildEntfernen)))
    );
    this.shadowRoot.querySelectorAll("[data-bild-hauptbild]").forEach(b =>
      b.addEventListener("click", () => this.setHauptbild(Number(b.dataset.bildHauptbild)))
    );
    this.shadowRoot.querySelector("[data-add-external-url]")?.addEventListener("click", () => {
      const input = this.shadowRoot.querySelector("[data-external-url]");
      this.addExternalUrl(input?.value);
      if (input) input.value = "";
    });

    // --- Bewertung (interaktiver Sterne-Editor) ---
    this.shadowRoot.querySelectorAll("[data-bewertung-stern]").forEach(b =>
      b.addEventListener("click", () => this.setBewertung(Number(b.dataset.bewertungStern)))
    );
  }

  // --- Hofladen finden (Discovery, Phase 5) ------------------------------
  //
  // Eigener Dialog in drei Schritten: (1) Suchen, (2) Kandidat wählen,
  // (3) Angaben prüfen. Der Dialog speichert nichts; "In Formular
  // übernehmen" öffnet das normale Bearbeitungsformular, gespeichert wird
  // wie gewohnt dort. Zustand: this.finden (null = Dialog geschlossen).
  // Eingaben des Dialogs werden vor jedem Re-Render aus dem DOM gesichert
  // (erfasseFindenEingaben()), analog zum Formular (erfasseFormularZustand()).

  static FINDEN_FEHLERMELDUNGEN = {
    invalid_coordinates: "Bitte gültige Latitude-/Longitude-Werte eintragen.",
    unreachable: "Die Overpass API (OpenStreetMap) konnte nicht erreicht werden. Bitte später erneut versuchen.",
    not_ready: "HofKarte ist noch nicht bereit.",
    invalid_format: "Es fehlen Angaben für die Anreicherung.",
  };

  static FINDEN_WEBSITE_STATUS = {
    ok: "Website ausgewertet",
    robots_gesperrt: "Die Website verbietet automatisches Auslesen (robots.txt) – nicht abgerufen",
    robots_nicht_lesbar: "robots.txt der Website nicht lesbar – Website nicht abgerufen",
    nicht_erreichbar: "Website nicht erreichbar",
    keine_informationen: "Auf der Website wurde nichts Verwertbares gefunden",
    ungueltige_url: "Ungültige Website-Adresse",
    uebersprungen: "Keine Website angegeben",
  };

  /** Zeilen der Prüf-Ansicht (Schritt 3): Beschriftung und die von der Zeile
   * abgedeckten Hofladen-Felder. */
  static FINDEN_ZEILEN = [
    { key: "name", label: "Name", felder: ["name"] },
    { key: "adresse", label: "Adresse", felder: ["adresse", "plz", "ort"] },
    { key: "land", label: "Land", felder: ["land"] },
    { key: "website", label: "Webseite", felder: ["website"] },
    { key: "mobilnummer", label: "Telefon", felder: ["mobilnummer"] },
    { key: "email", label: "E-Mail", felder: ["email"] },
    { key: "oeffnungszeiten", label: "Öffnungszeiten", felder: ["oeffnungszeiten"] },
    { key: "angebote", label: "Angebote", felder: ["angebote"] },
    { key: "zahlungsarten", label: "Zahlungsarten", felder: ["zahlungsarten"] },
    { key: "koordinaten", label: "Koordinaten", felder: ["latitude", "longitude"] },
  ];

  static FINDEN_QUELLEN_LABEL = { openstreetmap: "OpenStreetMap", website: "Website", angabe: "Eigene Angabe" };

  oeffneFinden() {
    const ha = this.hass?.config;
    const haLat = Number.isFinite(Number(ha?.latitude)) ? ha.latitude : "";
    const haLon = Number.isFinite(Number(ha?.longitude)) ? ha.longitude : "";
    this.finden = {
      schritt: 1, name: "", website: "", latitude: haLat, longitude: haLon,
      radius: FINDEN_STANDARD_RADIUS_METER, erweitert: false,
      standortText: "", standortKind: "", busy: false, fehler: "",
      kandidaten: [], gewaehlt: null, ereignisse: {}, vorschlag: null, felder: {},
    };
    this.render();
    this.ermittleGeraeteStandort();
  }

  schliesseFinden() {
    this.beendeFindenAbo();
    this._findenStandortToken++;
    this.finden = null;
    this.render();
  }

  /** Aktuellen Standort des Geräts übernehmen (Browser-Geolocation; fragt
   * beim ersten Mal nach der Freigabe). Schlägt das fehl (verweigert, keine
   * HTTPS-Verbindung, kein GPS), bleibt der Standort der Home-Assistant-
   * Installation eingetragen. Die Koordinaten verlassen den Browser erst
   * mit "Suchen" (dann gehen sie an Home Assistant und von dort an
   * OpenStreetMap/Overpass). Aktualisiert nur die betroffenen DOM-Elemente,
   * damit laufende Eingaben (Fokus) nicht durch einen Re-Render gestört
   * werden. */
  ermittleGeraeteStandort() {
    const f = this.finden;
    if (!f) return;
    const token = ++this._findenStandortToken;
    const hatHa = f.latitude !== "" && f.longitude !== "";
    const fallback = hatHa
      ? "Gerätestandort nicht verfügbar (Freigabe verweigert oder keine HTTPS-Verbindung) – Standort von Home Assistant eingetragen."
      : "Gerätestandort nicht verfügbar – bitte Koordinaten eintragen.";
    // Browser geben Geolocation nur in einem sicheren Kontext (HTTPS oder
    // localhost) frei und lehnen sonst OHNE Freigabe-Dialog ab (siehe
    // CHANGELOG 0.18.0) - das wird hier ausdrücklich benannt.
    if (typeof window !== "undefined" && window.isSecureContext === false) {
      this.setzeFindenStandortText(
        hatHa
          ? "Gerätestandort braucht eine sichere Verbindung (HTTPS oder localhost) – Standort von Home Assistant eingetragen."
          : "Gerätestandort braucht eine sichere Verbindung (HTTPS oder localhost) – bitte Koordinaten eintragen.",
        "",
      );
      return;
    }
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      this.setzeFindenStandortText(fallback, "");
      return;
    }
    this.setzeFindenStandortText("Standort des Geräts wird ermittelt …", "");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (token !== this._findenStandortToken || !this.finden) return;
        const lat = Number(pos.coords.latitude.toFixed(6));
        const lon = Number(pos.coords.longitude.toFixed(6));
        this.finden.latitude = lat;
        this.finden.longitude = lon;
        const genau = Number.isFinite(pos.coords.accuracy) ? ` (±${Math.round(pos.coords.accuracy)} m)` : "";
        for (const [name, wert] of [["latitude", lat], ["longitude", lon]]) {
          const el = this.shadowRoot.querySelector(`[data-finden-feld="${name}"]`);
          if (el) el.value = String(wert);
        }
        this.setzeFindenStandortText(`Standort des Geräts übernommen${genau}.`, "success");
      },
      () => {
        if (token !== this._findenStandortToken || !this.finden) return;
        this.setzeFindenStandortText(fallback, "");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  setzeFindenStandortText(text, kind) {
    if (!this.finden) return;
    this.finden.standortText = text;
    this.finden.standortKind = kind;
    const el = this.shadowRoot.querySelector("[data-finden-standort-text]");
    if (el) { el.textContent = text; el.className = `muted${kind ? " " + kind : ""}`; }
  }

  /** Eingaben des Dialogs (Schritt 1) aus dem DOM in this.finden sichern. */
  erfasseFindenEingaben() {
    const f = this.finden;
    if (!f) return;
    for (const name of ["name", "website", "latitude", "longitude"]) {
      const el = this.shadowRoot.querySelector(`[data-finden-feld="${name}"]`);
      if (el) f[name] = el.value;
    }
    const radius = this.shadowRoot.querySelector("[data-finden-radius]");
    if (radius) f.radius = Number(radius.value) || FINDEN_STANDARD_RADIUS_METER;
    const erweitert = this.shadowRoot.querySelector("[data-finden-erweitert]");
    if (erweitert) f.erweitert = !!erweitert.checked;
  }

  static koordinatenZahl(wert) {
    return String(wert ?? "").trim() === "" ? NaN : Number(String(wert).replace(",", "."));
  }

  async sucheFinden() {
    this.erfasseFindenEingaben();
    const f = this.finden;
    if (!f || f.busy) return;
    const lat = HofkartePanel.koordinatenZahl(f.latitude);
    const lon = HofkartePanel.koordinatenZahl(f.longitude);
    if (!isValidWgs84(lat, lon)) {
      f.fehler = HofkartePanel.FINDEN_FEHLERMELDUNGEN.invalid_coordinates;
      this.render();
      return;
    }
    f.fehler = "";
    f.busy = true;
    this.render();
    const nachricht = { latitude: lat, longitude: lon, radius: f.radius, erweitert: f.erweitert };
    if (f.name.trim()) nachricht.name = f.name.trim();
    if (f.website.trim()) nachricht.website = f.website.trim();
    try {
      const ergebnis = await this.call("hofkarte/management/discover", nachricht);
      if (this.finden !== f) return; // Dialog wurde inzwischen geschlossen
      f.kandidaten = ergebnis.kandidaten || [];
      const erster = f.kandidaten[0];
      f.gewaehlt = erster && erster.konfidenz === "hoch" ? 0 : null;
      f.schritt = 2;
    } catch (err) {
      if (this.finden !== f) return;
      f.fehler = HofkartePanel.FINDEN_FEHLERMELDUNGEN[err?.code] || err?.message || "Die Suche ist fehlgeschlagen.";
    }
    f.busy = false;
    this.render();
  }

  beendeFindenAbo() {
    if (this._findenTimer) { clearTimeout(this._findenTimer); this._findenTimer = null; }
    const unsub = this._findenUnsub;
    this._findenUnsub = null;
    if (unsub) { Promise.resolve().then(() => unsub()).catch(() => {}); }
  }

  /** Reichert den gewählten Kandidaten (und/oder die Website) über die
   * Subscription "enrich" an; die Fortschrittsereignisse füllen
   * this.finden.ereignisse, "fertig" liefert den Vorschlag. */
  async reichereFindenAn({ ohneKandidat = false } = {}) {
    const f = this.finden;
    if (!f || f.busy) return;
    const kandidat = ohneKandidat ? null : f.kandidaten[f.gewaehlt];
    const website = (f.website || "").trim();
    if (!kandidat && !website) return;
    f.fehler = ""; f.busy = true; f.ereignisse = {}; f.vorschlag = null; f.schritt = 3;
    this.render();
    const nachricht = { type: "hofkarte/management/enrich" };
    if (kandidat) nachricht.kandidat = kandidat;
    if (website) nachricht.website = website;
    const aufEreignis = (ereignis) => {
      if (this.finden !== f || !ereignis) return;
      if (ereignis.phase === "fertig") {
        f.vorschlag = ereignis.vorschlag || { daten: {}, quellen: {}, abweichungen: {} };
        f.felder = {};
        for (const zeile of HofkartePanel.FINDEN_ZEILEN) f.felder[zeile.key] = this.findenZeileWert(zeile, f.vorschlag.daten) !== "";
        f.busy = false;
        this.beendeFindenAbo();
      } else if (ereignis.phase) {
        f.ereignisse[ereignis.phase] = ereignis;
      }
      this.render();
    };
    try {
      this._findenUnsub = await this.hass.connection.subscribeMessage(aufEreignis, nachricht);
      this._findenTimer = setTimeout(() => {
        if (this.finden === f && f.busy) {
          f.busy = false;
          f.fehler = "Die Anreicherung hat zu lange gedauert.";
          this.beendeFindenAbo();
          this.render();
        }
      }, 90000);
    } catch (err) {
      if (this.finden !== f) return;
      f.busy = false;
      f.fehler = HofkartePanel.FINDEN_FEHLERMELDUNGEN[err?.code] || err?.message || "Die Anreicherung ist fehlgeschlagen.";
      this.render();
    }
  }

  /** Lesbarer Text der Werte einer Prüfzeile ("" = nichts gefunden). */
  findenZeileWert(zeile, daten) {
    const d = daten || {};
    if (zeile.key === "adresse") {
      return [d.adresse, [d.plz, d.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    }
    if (zeile.key === "koordinaten") {
      return Number.isFinite(Number(d.latitude)) && d.latitude != null && d.longitude != null
        ? `${Number(d.latitude).toFixed(5)}, ${Number(d.longitude).toFixed(5)}` : "";
    }
    if (zeile.key === "oeffnungszeiten") {
      const eintraege = Array.isArray(d.oeffnungszeiten) ? d.oeffnungszeiten : [];
      const proTag = new Map();
      for (const z of eintraege) {
        const text = `${z.beginn}–${z.ende}`;
        proTag.set(z.wochentag, [...(proTag.get(z.wochentag) || []), text]);
      }
      return [...proTag.entries()].sort((a, b) => a[0] - b[0])
        .map(([tag, zeiten]) => `${(WEEKDAYS[tag - 1] || "").slice(0, 2)} ${zeiten.join(", ")}`).join("; ");
    }
    const wert = d[zeile.key];
    if (Array.isArray(wert)) return wert.map(x => x.name || x).join(", ");
    return wert ? String(wert) : "";
  }

  /** Gibt es schon einen Hofladen mit gleichem Namen oder (<= 100 m) an
   * derselben Stelle? Rein informativ, verhindert nichts. */
  findeBestehenden(kandidat) {
    const norm = (s) => String(s || "").trim().toLowerCase();
    const namen = [kandidat.name, ...(kandidat.weitere_namen || [])].map(norm).filter(Boolean);
    return (this.items || []).find((item) => {
      if (namen.includes(norm(item.name))) return true;
      const lat = Number(item.latitude), lon = Number(item.longitude);
      if (item.latitude == null || item.longitude == null || !Number.isFinite(lat) || !Number.isFinite(lon)) return false;
      const dLat = (lat - kandidat.latitude) * 111195;
      const dLon = (lon - kandidat.longitude) * 111195 * Math.cos(kandidat.latitude * Math.PI / 180);
      return Math.hypot(dLat, dLon) <= 100;
    }) || null;
  }

  findenGruende(k) {
    const s = k.signale || {};
    const teile = [];
    const m = Math.round(k.entfernung_meter ?? 0);
    teile.push(m <= 25 ? `sehr nah (${m} m)` : `${m} m entfernt`);
    if (s.name != null) teile.push(s.name >= 0.85 ? "Name stimmt" : s.name >= 0.5 ? "Name ähnlich" : "Name weicht ab");
    if (s.website) teile.push("Website stimmt überein");
    return teile.join(" · ");
  }

  istHttpUrl(url) { return /^https?:\/\//i.test(String(url || "")); }

  /** Übernimmt die angehakten Zeilen in ein neues Bearbeitungsformular. */
  uebernehmeFindenVorschlag() {
    const f = this.finden;
    if (!f?.vorschlag) return;
    const daten = f.vorschlag.daten || {};
    const quellenListe = Array.isArray(f.vorschlag.quellen) ? f.vorschlag.quellen : Object.entries(f.vorschlag.quellen || {}).map(([feld, q]) => ({ feld, ...q }));
    const info = {};
    const uebernommeneFelder = [];
    for (const zeile of HofkartePanel.FINDEN_ZEILEN) {
      if (!f.felder[zeile.key]) continue;
      for (const feld of zeile.felder) {
        if (daten[feld] != null && daten[feld] !== "" && !(Array.isArray(daten[feld]) && !daten[feld].length)) {
          info[feld] = daten[feld];
          uebernommeneFelder.push(feld);
        }
      }
    }
    const name = f.name.trim();
    const website = f.website.trim();
    this.finden = null;
    this.beendeFindenAbo();
    this.start();
    if (!info.name && name) this.editing.name = name;
    if (!info.website && website) this.editing.website = website;
    this.uebernehmeWebseiteInfo(info);
    if (info.latitude != null && info.longitude != null) {
      this.editing.latitude = info.latitude;
      this.editing.longitude = info.longitude;
    }
    this.editing.quellen = quellenListe.filter(q => uebernommeneFelder.includes(q.feld)).map(q => ({
      feld: q.feld, quelle: q.quelle, status: q.status || "confirmed", url: q.url || null, lizenz: q.lizenz || null,
    }));
    this.merkeQuellenSchnappschuss();
    this.render();
  }

  /** Leeres Formular mit den bisher im Dialog eingegebenen Angaben. */
  findenLeerAnlegen() {
    this.erfasseFindenEingaben();
    const f = this.finden;
    const lat = HofkartePanel.koordinatenZahl(f.latitude);
    const lon = HofkartePanel.koordinatenZahl(f.longitude);
    const name = f.name.trim(), website = f.website.trim();
    this.finden = null;
    this.beendeFindenAbo();
    this.start();
    if (name) this.editing.name = name;
    if (website) this.editing.website = website;
    if (isValidWgs84(lat, lon)) { this.editing.latitude = lat; this.editing.longitude = lon; }
    this.render();
  }

  // --- Herkunft ("quellen") im Formular ----------------------------------

  /** Vergleichswert eines Feldes, um zu erkennen, ob es nach der
   * Übernahme von Hand geändert wurde. */
  quellenWert(feld, daten) {
    const v = daten?.[feld];
    if (feld === "angebote" || feld === "zahlungsarten") return JSON.stringify((v || []).map(x => this.slug(x.name || x)).sort());
    if (feld === "oeffnungszeiten") return JSON.stringify((v || []).map(z => [Number(z.wochentag), z.beginn, z.ende]).sort());
    if (feld === "latitude" || feld === "longitude") return v === null || v === undefined || v === "" ? "" : String(Number(v));
    return String(v ?? "").trim();
  }

  merkeQuellenSchnappschuss() {
    this._quellenSchnappschuss = {};
    for (const q of (this.editing?.quellen || [])) this._quellenSchnappschuss[q.feld] = this.quellenWert(q.feld, this.editing);
  }

  /** Behält nur die Herkunftsangaben von Feldern, die seit der Übernahme
   * unverändert sind (sonst wäre die Angabe falsch). */
  bereinigteQuellen(daten) {
    const snap = this._quellenSchnappschuss || {};
    return (daten.quellen || []).filter(q => !(q.feld in snap) || snap[q.feld] === this.quellenWert(q.feld, daten));
  }

  /** Dialog-HTML (wird über die aktuelle Ansicht gelegt). */
  findenDialog() {
    const f = this.finden;
    const kopf = (titel) => `<h2 id="finden-titel">${this.esc(titel)}</h2>`;
    let inhalt = "";
    if (f.schritt === 1) {
      inhalt = `${kopf("Hofladen finden")}
        <p class="muted">Sucht in OpenStreetMap nach Hofläden in der Nähe und liest, falls vorhanden, deren Website aus. Es wird nichts gespeichert.</p>
        <div class="finden-form">
          <label>Name (optional)<input type="text" data-finden-feld="name" value="${this.escAttr(f.name)}" autocomplete="off"></label>
          <label>Website (optional)<input type="url" data-finden-feld="website" value="${this.escAttr(f.website)}" placeholder="https://…" autocomplete="off"></label>
          <div class="finden-koordinaten">
            <label>Latitude<input type="text" inputmode="decimal" data-finden-feld="latitude" value="${this.escAttr(f.latitude)}"></label>
            <label>Longitude<input type="text" inputmode="decimal" data-finden-feld="longitude" value="${this.escAttr(f.longitude)}"></label>
            <button type="button" class="secondary" data-finden-standort title="Aktuellen Standort des Geräts übernehmen">📍 Mein Standort</button>
          </div>
          <div class="muted ${this.esc(f.standortKind)}" data-finden-standort-text>${this.esc(f.standortText)}</div>
          <label>Umkreis: <span data-finden-radius-anzeige>${this.esc(HofkartePanel.findenRadiusText(f.radius))}</span>
            <input type="range" min="${FINDEN_MIN_RADIUS_METER}" max="${FINDEN_MAX_RADIUS_METER}" step="50" value="${this.escAttr(f.radius)}" data-finden-radius></label>
          <label class="finden-check"><input type="checkbox" data-finden-erweitert ${f.erweitert ? "checked" : ""}> Erweiterte Suche (mehr Tags, langsamer, noch wenig getestet)</label>
        </div>
        ${f.fehler ? `<div class="notice error">${this.esc(f.fehler)}</div>` : ""}
        <div class="actions">
          <button type="button" class="secondary" data-finden-abbrechen>Abbrechen</button>
          <button type="button" data-finden-suchen ${f.busy ? "disabled" : ""}>${f.busy ? "Suche läuft …" : "Suchen"}</button>
        </div>`;
    } else if (f.schritt === 2) {
      const eintraege = f.kandidaten.map((k, i) => {
        const konf = { hoch: "✔ hohe Sicherheit", mittel: "• mittlere Sicherheit", niedrig: "○ niedrige Sicherheit" }[k.konfidenz] || "";
        const adresse = [k.adresse, [k.plz, k.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
        const bestehend = this.findeBestehenden(k);
        return `<label class="finden-kandidat ${f.gewaehlt === i ? "gewaehlt" : ""}">
          <input type="radio" name="finden-kandidat" value="${i}" data-finden-kandidat ${f.gewaehlt === i ? "checked" : ""}>
          <span class="finden-kandidat-text">
            <span class="osm-orte-name">${this.esc(k.name || "(ohne Namen)")}</span> <span class="muted">${this.esc(konf)}</span>
            ${adresse ? `<span class="muted">${this.esc(adresse)}</span>` : ""}
            <span class="muted">${this.esc(this.findenGruende(k))}</span>
            ${bestehend ? `<span class="finden-warnung">⚠ Möglicherweise schon erfasst: ${this.esc(bestehend.name)}</span>` : ""}
          </span></label>`;
      }).join("");
      const websiteVorhanden = !!f.website.trim();
      inhalt = `${kopf(f.kandidaten.length ? `${f.kandidaten.length} Treffer` : "Keine Treffer")}
        ${f.kandidaten.length
          ? `<p class="muted">Bitte den passenden Hofladen wählen. Sortiert nach Übereinstimmung.</p><div class="osm-orte-liste">${eintraege}</div>`
          : `<p class="muted">In OpenStreetMap wurde im Umkreis nichts gefunden. Du kannst die Website direkt auswerten lassen oder den Hofladen von Hand erfassen.</p>`}
        ${f.fehler ? `<div class="notice error">${this.esc(f.fehler)}</div>` : ""}
        <div class="actions finden-aktionen">
          <button type="button" class="secondary" data-finden-zurueck>Zurück</button>
          <button type="button" class="secondary" data-finden-leer>Manuell erfassen</button>
          ${websiteVorhanden ? `<button type="button" class="secondary" data-finden-nur-website>Nur Website auswerten</button>` : ""}
          <button type="button" data-finden-weiter ${f.gewaehlt === null ? "disabled" : ""}>Weiter</button>
        </div>`;
    } else {
      const ev = f.ereignisse || {};
      const statusText = (phase, titel) => {
        const e = ev[phase];
        if (!e) return f.busy ? `⏳ ${titel} …` : "";
        const text = phase === "website" ? (HofkartePanel.FINDEN_WEBSITE_STATUS[e.status] || e.status) : "OpenStreetMap-Daten übernommen";
        const ok = phase === "osm" ? e.status === "ok" : e.status === "ok";
        return `${ok ? "✔" : "ℹ"} ${text}`;
      };
      const fortschritt = [statusText("osm", "OpenStreetMap"), statusText("website", "Website")].filter(Boolean)
        .map(t => `<div class="muted">${this.esc(t)}</div>`).join("");
      let zeilen = "";
      let osmDabei = false;
      if (f.vorschlag) {
        const quellenListe = Array.isArray(f.vorschlag.quellen) ? f.vorschlag.quellen : Object.entries(f.vorschlag.quellen || {}).map(([feld, q]) => ({ feld, ...q }));
        const quelleVon = (feld) => quellenListe.find(q => q.feld === feld);
        const abweichungen = f.vorschlag.abweichungen || {};
        for (const zeile of HofkartePanel.FINDEN_ZEILEN) {
          const wert = this.findenZeileWert(zeile, f.vorschlag.daten);
          if (!wert) continue;
          const q = zeile.felder.map(quelleVon).find(Boolean);
          if (q?.quelle === "openstreetmap") osmDabei = true;
          const label = q ? (HofkartePanel.FINDEN_QUELLEN_LABEL[q.quelle] || q.quelle) : "";
          const badge = q ? (this.istHttpUrl(q.url)
            ? `<a class="website-link" href="${this.escAttr(q.url)}" target="_blank" rel="noopener noreferrer">${this.esc(label)}</a>`
            : this.esc(label)) : "";
          const abwFeld = zeile.felder.find(x => abweichungen[x]);
          const abw = abwFeld ? `<div class="finden-warnung">⚠ weicht von ${this.esc(HofkartePanel.FINDEN_QUELLEN_LABEL[abweichungen[abwFeld]] || "der anderen Quelle")} ab</div>` : "";
          zeilen += `<label class="finden-zeile"><input type="checkbox" data-finden-feldwahl="${this.escAttr(zeile.key)}" ${f.felder[zeile.key] ? "checked" : ""}>
            <span class="finden-zeile-text"><span class="webseite-info-label">${this.esc(zeile.label)}</span> ${this.esc(wert)}
            <span class="muted quelle-badge">${badge}</span>${abw}</span></label>`;
        }
        if (!zeilen) zeilen = `<p class="muted">Es wurden keine verwertbaren Angaben gefunden.</p>`;
      }
      inhalt = `${kopf("Angaben prüfen")}
        <div class="finden-fortschritt">${fortschritt}</div>
        ${f.vorschlag ? `<p class="muted">Gewählte Angaben werden in ein neues Formular übernommen. Gespeichert wird erst dort.</p><div class="finden-zeilen">${zeilen}</div>
          ${osmDabei ? `<p class="muted">© OpenStreetMap-Mitwirkende (ODbL)</p>` : ""}` : ""}
        ${f.fehler ? `<div class="notice error">${this.esc(f.fehler)}</div>` : ""}
        <div class="actions">
          <button type="button" class="secondary" data-finden-zurueck>Zurück</button>
          <button type="button" data-finden-uebernehmen ${f.vorschlag ? "" : "disabled"}>In Formular übernehmen</button>
        </div>`;
    }
    return `<div class="modal-overlay" data-finden-overlay>
      <div class="modal breit" role="dialog" aria-modal="true" aria-labelledby="finden-titel" tabindex="-1" data-finden-dialog>${inhalt}</div>
    </div>`;
  }

  static findenRadiusText(meter) {
    return meter >= 1000 ? `${(meter / 1000).toFixed(meter % 1000 ? 1 : 0)} km` : `${meter} m`;
  }

  /** Ereignis-Delegation des Dialogs (einmalig auf <main> gebunden). */
  bindFindenDelegiert() {
    const main = this._mainEl;
    main.addEventListener("click", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel) return;
      if (ziel.closest("[data-finden-open]")) { this.oeffneFinden(); return; }
      if (!this.finden) return;
      if (ziel.closest("[data-finden-abbrechen]")) { this.schliesseFinden(); return; }
      if (ziel.closest("[data-finden-standort]")) { this.ermittleGeraeteStandort(); return; }
      if (ziel.closest("[data-finden-suchen]")) { this.sucheFinden(); return; }
      if (ziel.closest("[data-finden-zurueck]")) {
        this.beendeFindenAbo();
        this.finden.busy = false; this.finden.fehler = "";
        this.finden.schritt = Math.max(1, this.finden.schritt - 1);
        this.render();
        return;
      }
      if (ziel.closest("[data-finden-leer]")) { this.findenLeerAnlegen(); return; }
      if (ziel.closest("[data-finden-weiter]")) { this.reichereFindenAn(); return; }
      if (ziel.closest("[data-finden-nur-website]")) { this.reichereFindenAn({ ohneKandidat: true }); return; }
      if (ziel.closest("[data-finden-uebernehmen]")) { this.uebernehmeFindenVorschlag(); return; }
      if (ziel.matches("[data-finden-overlay]")) { /* Klick daneben schliesst bewusst nicht (Eingaben nicht verlieren) */ }
    });
    main.addEventListener("change", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel || !this.finden) return;
      if (ziel.matches("[data-finden-kandidat]")) {
        this.finden.gewaehlt = Number(ziel.value);
        const weiter = this.shadowRoot.querySelector("[data-finden-weiter]");
        if (weiter) weiter.disabled = false;
        this.shadowRoot.querySelectorAll(".finden-kandidat").forEach((el) => {
          el.classList.toggle("gewaehlt", !!el.querySelector("input")?.checked);
        });
      } else if (ziel.matches("[data-finden-feldwahl]")) {
        this.finden.felder[ziel.dataset.findenFeldwahl] = ziel.checked;
      } else if (ziel.matches("[data-finden-erweitert]")) {
        this.finden.erweitert = ziel.checked;
      }
    });
    main.addEventListener("input", (e) => {
      const ziel = e.target instanceof Element ? e.target : null;
      if (!ziel || !this.finden) return;
      if (ziel.matches("[data-finden-radius]")) {
        this.finden.radius = Number(ziel.value) || FINDEN_STANDARD_RADIUS_METER;
        const anzeige = this.shadowRoot.querySelector("[data-finden-radius-anzeige]");
        if (anzeige) anzeige.textContent = HofkartePanel.findenRadiusText(this.finden.radius);
      } else if (ziel.matches("[data-finden-feld]")) {
        this.finden[ziel.dataset.findenFeld] = ziel.value;
      }
    });
    main.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.finden && e.target instanceof Element && e.target.closest("[data-finden-overlay]")) {
        e.stopPropagation();
        this.schliesseFinden();
      } else if (e.key === "Enter" && this.finden?.schritt === 1 && e.target instanceof Element && e.target.matches("input[type=text], input[type=url]")) {
        e.preventDefault();
        this.sucheFinden();
      }
    });
  }

  esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c])); }
  escAttr(s) { return this.esc(s).replace(/'/g, "&#39;"); }
}
customElements.define("hofkarte-panel", HofkartePanel);
