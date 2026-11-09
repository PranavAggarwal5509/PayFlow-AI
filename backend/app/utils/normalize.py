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



_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_digit(gstin: str) -> str | None:
    """Official GSTN mod-36 checksum over the first 14 characters (None if not computable)."""
    if len(gstin) < 14 or any(ch not in _GSTIN_CHARS for ch in gstin[:14]):
        return None
    total = 0
    for index, ch in enumerate(gstin[:14]):
        value = _GSTIN_CHARS.index(ch) * (2 if index % 2 else 1)
        total += value // 36 + value % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def gstin_checksum_valid(gstin: str | None) -> bool:
    return bool(gstin) and len(gstin) == 15 and gstin_check_digit(gstin) == gstin[14]


# OCR look-alikes, applied only where the GSTIN structure says a digit / letter must be.
_TO_DIGIT = str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "G": "6", "T": "7", "B": "8"})
_TO_LETTER = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "7": "T", "8": "B"})
# 2 digits state | 5 letters PAN | 4 digits PAN | 1 letter PAN | entity no. | 'Z' | check
_GSTIN_SHAPE = "DDLLLLLDDDDLAZA"


def repair_gstin(gstin: str | None) -> str | None:
    """Undo OCR look-alike errors (O/0, I/1, S/5, B/8 ...) in a 15-character GSTIN.

    Characters are corrected only where the official GSTIN layout requires a digit or a letter,
    and the repair is accepted ONLY if the result passes the GSTN check digit. A genuinely wrong
    GSTIN (a typo or a fabricated one) is returned unchanged, so it still fails validation.
    """
    if not gstin or len(gstin) != 15 or gstin_checksum_valid(gstin):
        return gstin
    fixed = []
    for ch, kind in zip(gstin, _GSTIN_SHAPE, strict=True):
        if kind == "D":
            fixed.append(ch.translate(_TO_DIGIT))
        elif kind == "L":
            fixed.append(ch.translate(_TO_LETTER))
        elif kind == "Z":
            fixed.append("Z" if ch == "2" else ch)
        else:
            fixed.append(ch)
    base = "".join(fixed)
    # Positions 13 and 15 may legitimately be a digit or a letter: try both readings.
    swap = {**{v: k for k, v in {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}.items()},
            **{"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}}  # fmt: skip
    for c13 in dict.fromkeys([base[12], swap.get(base[12], base[12])]):
        for c15 in dict.fromkeys([base[14], swap.get(base[14], base[14])]):
            candidate = base[:12] + c13 + base[13] + c15
            if gstin_checksum_valid(candidate):
                return candidate
    return gstin


_IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
_ACCOUNT = re.compile(r"(?<![A-Z0-9])(\d[\d -]{7,22}\d)(?![A-Z0-9])")


def parse_bank_details(text: str | None) -> tuple[str | None, str | None]:
    """Pull (account_number, IFSC) out of free-text bank details printed on an invoice."""
    if not text:
        return None, None
    upper = text.upper()
    ifsc_match = _IFSC.search(upper)
    ifsc = ifsc_match.group(1) if ifsc_match else None
    scan = upper.replace(ifsc, " ") if ifsc else upper
    account = None
    for candidate in _ACCOUNT.findall(scan):
        digits = re.sub(r"\D", "", candidate)
        if 9 <= len(digits) <= 18:
            account = digits
            break
    return account, ifsc


def normalize_account_number(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    return digits or None
