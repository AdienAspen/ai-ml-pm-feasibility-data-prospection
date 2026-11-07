"""Release-time lexical exclusion, separate from frozen text normalization."""

from functools import lru_cache
from pathlib import Path

POLICY = "restricted_lexical_substring_exclusion_v1"
TERMS_FILE = Path(__file__).resolve().parents[3] / "config/restricted_terms.local.txt"


@lru_cache(maxsize=1)
def restricted_terms():
    if not TERMS_FILE.is_file():
        raise RuntimeError("Local restricted-term configuration is required; fail closed")
    terms = tuple(
        line.strip().casefold()
        for line in TERMS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not terms:
        raise RuntimeError("Restricted-term configuration is empty; fail closed")
    return terms


def restricted_match(text, terms=None):
    folded = str(text).casefold()
    return any(term in folded for term in (restricted_terms() if terms is None else terms))


def assert_safe_terms(values):
    if any(restricted_match(value) for value in values):
        raise RuntimeError("Restricted lexical content detected; values withheld")
