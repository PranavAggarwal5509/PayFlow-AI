from datetime import date, datetime

_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y",
    "%B %d, %Y", "%d-%b-%Y", "%d/%m/%y", "%d-%m-%y",
)  # fmt: skip


def parse_date(value: str | None) -> date | None:
    """Parse common invoice date formats (day-first for numeric dates, as used in India)."""
    if not value:
        return None
    text = value.strip()
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None

