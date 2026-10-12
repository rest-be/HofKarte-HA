"""Namens-Normalisierung und -Ähnlichkeit (Standardbibliothek ``difflib``)."""

from __future__ import annotations

import difflib
import re
import unicodedata

_STOPWOERTER = frozenset(
    {"der", "die", "das", "zum", "zur", "beim", "bei", "und", "von", "am", "im", "en", "la", "le", "du"}
)
# Wörter, die einen Hofladen bezeichnen, aber nichts über *welchen* aussagen.
GENERISCH = frozenset(
    {"hofladen", "hof", "bauernhof", "laden", "ferme", "buure", "buurehof", "landwirtschaft", "hofverkauf"}
)


def normalisiere(text: str | None) -> str:
    """Kleinschreibung ohne Diakritika/Interpunktion ("Müller" -> "muller")."""
    text = (text or "").replace("ß", "ss").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens(text: str, ohne_generisch: bool) -> list[str]:
    toks = [t for t in normalisiere(text).split() if t not in _STOPWOERTER]
    if ohne_generisch:
        toks = [t for t in toks if t not in GENERISCH]
    return sorted(toks)


def name_aehnlichkeit(a: str | None, b: str | None) -> float:
    """Ähnlichkeit 0..1, unabhängig von der Wortreihenfolge
    ("Müller Hofladen" ~ "Hofladen Müller"), zusätzlich ein Vergleich ohne
    generische Wörter (leicht abgewertet, damit "Hofladen X" und "X" nicht
    gleich gut sind wie ein exakter Treffer)."""
    if not a or not b:
        return 0.0
    voll = difflib.SequenceMatcher(None, " ".join(_tokens(a, False)), " ".join(_tokens(b, False))).ratio()
    ka, kb = _tokens(a, True), _tokens(b, True)
    kern = difflib.SequenceMatcher(None, " ".join(ka), " ".join(kb)).ratio() if ka and kb else 0.0
    return max(voll, kern * 0.95)
