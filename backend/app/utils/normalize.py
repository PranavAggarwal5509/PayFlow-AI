import re
import unicodedata

_LEGAL_SUFFIXES = {
    "pvt", "private", "ltd", "limited", "llp", "inc", "incorporated", "co", "corp",
    "corporation", "company", "llc", "plc", "and", "the",
}  # fmt: skip


def normalize_vendor_name(name: str | None) -> str:
    """Lowercase, strip accents/punctuation and legal-entity suffixes: 'Acme Pvt. Ltd.' → 'acme'."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower().replace("&", " and "))
    tokens = [t for t in text.split() if t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def normalize_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", gstin).upper()
    return cleaned or None


def normalize_invoice_number(number: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", number or "").upper()


def normalize_po_number(number: str | None) -> str:
    return re.sub(r"\s+", "", number or "").upper()

