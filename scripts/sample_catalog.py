"""PayFlow AI dataset: realistic Indian GST master data, seeded history and the test invoice set.

Everything here is FICTIONAL but follows real formats and rules so every control is exercised
for real:

* GSTINs carry the official GSTN mod-36 check digit; the embedded PAN matches the entity type
  (C = company, F = firm/LLP, P = proprietor) and the first two digits are the real state code.
* Tax follows the GST place-of-supply rule: supplier state == buyer state (27, Maharashtra) →
  CGST + SGST at half rate each, otherwise IGST. Rates use the post-2025 slabs (5% / 18%).
* HSN (goods) and SAC (services) codes are real classification codes for the items described.
* Grand totals are rounded to the nearest rupee with an explicit "Round Off" line.

Three datasets:
* VENDORS / POS  - master data loaded by `seed_database.py`.
* HISTORY        - invoices "already processed" before the demo. Seeded with their extracted data
                   (no LLM calls) through the real deterministic pipeline, marked SEED_HISTORY,
                   and NEVER touched by the "Reset demo" button.
* INVOICES       - the 15 test invoices uploaded during the demo (LIVE_UPLOAD). "Reset demo" deletes
                   only these, so they can be run again from scratch.

`generate_sample_invoices.py` renders all PDFs + JSON from this file.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

BUYER_STATE = "27"

STATES = {
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "19": "West Bengal",
    "24": "Gujarat", "27": "Maharashtra", "29": "Karnataka", "32": "Kerala", "33": "Tamil Nadu",
    "36": "Telangana",
}  # fmt: skip

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _with_check_digit(gstin: str) -> str:
    """Replace the 15th character with the official GSTN mod-36 check digit."""
    total = 0
    for index, ch in enumerate(gstin[:14]):
        value = _GSTIN_CHARS.index(ch) * (2 if index % 2 else 1)
        total += value // 36 + value % 36
    return gstin[:14] + _GSTIN_CHARS[(36 - total % 36) % 36]


# The company receiving the invoices (the PayFlow AI customer).
BUYER = {
    "name": "Zenith Retail Ventures Pvt Ltd",
    "address": ["Tower B, 6th Floor, Orchid Business Park", "Senapati Bapat Marg, Lower Parel", "Mumbai 400013"],
    "gstin": _with_check_digit("27AACCZ4521M1Z0"),
    "state": "27",
    "ship_to": ["Zenith Retail Ventures Pvt Ltd - Central Warehouse", "Gala 7-12, Sai Logistics Park, Vadpe", "Bhiwandi, Thane 421302"],
}  # fmt: skip


@dataclass(frozen=True)
class VendorInfo:
    code: str
    name: str
    gstin: str
    address: list[str]
    city: str
    status: str
    email: str
    phone: str
    layout: str  # tally | corporate | services
    accent: str  # brand colour used on corporate / services templates

    @property
    def state(self) -> str:
        return self.gstin[:2]

    @property
    def pan(self) -> str:
        return self.gstin[2:12]

    @property
    def one_line_address(self) -> str:
        return ", ".join(self.address)


def _vendor(code, name, gstin, address, city, status, email, phone, layout, accent) -> VendorInfo:
    return VendorInfo(code, name, _with_check_digit(gstin), address, city, status, email, phone, layout, accent)


VENDOR_INFO: list[VendorInfo] = [
    _vendor("V-1001", "Acme Industrial Supplies Pvt Ltd", "27AABCA1001A1Z0", ["Plot 14, MIDC Industrial Area", "Andheri East, Mumbai 400093"], "Mumbai", "ACTIVE", "accounts@acmeindustrial.in", "+91 22 2830 4410", "tally", "#1f3a5f"),
    _vendor("V-1002", "Bharat Office Solutions Pvt Ltd", "29AABCB1002B1Z0", ["88, Residency Road", "Shanthala Nagar, Bengaluru 560025"], "Bengaluru", "ACTIVE", "billing@bharatoffice.co.in", "+91 80 4112 7700", "corporate", "#0f766e"),
    _vendor("V-1003", "Cobalt Logistics LLP", "07AAFFC1003C1Z0", ["B-21, Okhla Industrial Area Phase II", "New Delhi 110020"], "New Delhi", "ACTIVE", "finance@cobaltlogistics.in", "+91 11 4055 9021", "tally", "#1e40af"),
    _vendor("V-1004", "Deccan Print & Packaging Ltd", "36AABCD1004D1Z0", ["Survey No. 42, Medchal Road", "Kompally, Hyderabad 500067"], "Hyderabad", "ACTIVE", "ar@deccanprint.com", "+91 40 2715 6630", "corporate", "#b45309"),
    _vendor("V-1005", "Evergreen Facility Services Pvt Ltd", "33AABCE1005E1Z0", ["12, Anna Salai, Teynampet", "Chennai 600018"], "Chennai", "ACTIVE", "invoices@evergreenfs.in", "+91 44 2433 8890", "services", "#15803d"),
    _vendor("V-1006", "Falcon IT Hardware Pvt Ltd", "24AABCF1006F1Z0", ["7th Floor, Shivalik Shilp, Prahlad Nagar", "Ahmedabad 380015"], "Ahmedabad", "ACTIVE", "sales@falconit.in", "+91 79 4890 2255", "corporate", "#4338ca"),
    _vendor("V-1007", "Gamma Stationers", "19AAJPG1007G1Z0", ["45, Park Street", "Kolkata 700016"], "Kolkata", "INACTIVE", "gammastationers@gmail.com", "+91 33 2229 1173", "tally", "#334155"),
    _vendor("V-1008", "Horizon Catering Services", "32AAKFH1008H1Z0", ["Near Marine Drive Walkway, Shanmugham Road", "Ernakulam, Kochi 682031"], "Kochi", "PENDING", "events@horizoncatering.in", "+91 484 236 4410", "services", "#be123c"),
    _vendor("V-1009", "Indus Electricals Pvt Ltd", "09AABCI1009I1Z0", ["C-9, Sector 62", "Noida, Gautam Buddh Nagar 201301"], "Noida", "ACTIVE", "accounts@induselectricals.com", "+91 120 471 3300", "tally", "#9a3412"),
    _vendor("V-1010", "Jupiter Software Services Pvt Ltd", "27AABCJ1010J1Z0", ["Office 501, Pentagon Tower P2", "Hinjewadi Phase 1, Pune 411057"], "Pune", "ACTIVE", "finance@jupitersoft.io", "+91 20 6713 4500", "services", "#7c3aed"),
    _vendor("V-1011", "Kestrel Cloud Technologies Pvt Ltd", "29AABCK1011K1Z0", ["Embassy Tech Village, Block 4", "Devarabisanahalli, Bengaluru 560103"], "Bengaluru", "ACTIVE", "billing@kestrelcloud.in", "+91 80 6950 2000", "corporate", "#0369a1"),
    _vendor("V-1012", "Lotus Furnishings Co", "08AAGFL1012L1Z0", ["G-118, Sitapura Industrial Area", "Tonk Road, Jaipur 302022"], "Jaipur", "ACTIVE", "lotusfurnishings@yahoo.co.in", "+91 141 277 0912", "tally", "#a21caf"),
    _vendor("V-1013", "Meridian Chemicals Pvt Ltd", "24AABCM1013M1Z0", ["Plot 210, GIDC Makarpura", "Vadodara 390010"], "Vadodara", "ACTIVE", "accounts@meridianchem.co.in", "+91 265 263 8840", "tally", "#047857"),
    _vendor("V-1014", "Nova Packaging Industries", "27AAMFN1014N1Z0", ["Gala 3, Harihar Compound, Mankoli Naka", "Bhiwandi, Thane 421302"], "Bhiwandi", "ACTIVE", "novapack.billing@gmail.com", "+91 98200 41147", "corporate", "#c2410c"),
    _vendor("V-1015", "Orion Security Services Pvt Ltd", "27AABCO1015O1Z0", ["204, Satellite Gazebo, Guru Hargovindji Marg", "Andheri East, Mumbai 400093"], "Mumbai", "ACTIVE", "billing@orionsecurity.in", "+91 22 6692 1800", "services", "#1e3a8a"),
    _vendor("V-1016", "Pinnacle Travels & Tours", "06AAQFP1016P1Z0", ["SCO 41, Sector 29 Market", "Gurugram 122001"], "Gurugram", "ACTIVE", "accounts@pinnacletravels.in", "+91 124 438 0566", "services", "#0e7490"),
]  # fmt: skip

VENDOR_BY_CODE = {v.code: v for v in VENDOR_INFO}
# (code, name, gstin, address, status) — the shape the seed script and older tooling expect.
VENDORS = [(v.code, v.name, v.gstin, v.one_line_address, v.status) for v in VENDOR_INFO]

# Verified remittance details held in the vendor master (fictional accounts).
_BANKS = ["HDFC", "ICIC", "UTIB", "SBIN", "KKBK", "YESB"]
_BANK_NAMES = {"HDFC": "HDFC Bank", "ICIC": "ICICI Bank", "UTIB": "Axis Bank", "SBIN": "State Bank of India",
               "KKBK": "Kotak Mahindra Bank", "YESB": "Yes Bank"}  # fmt: skip


def vendor_bank(code: str) -> tuple[str, str, str]:
    """(bank name, account number, IFSC) on file for a vendor."""
    n = int(code.split("-")[1])
    prefix = _BANKS[n % len(_BANKS)]
    return _BANK_NAMES[prefix], f"5020{n:06d}{n * 37 % 10000:04d}", f"{prefix}0{n:06d}"


def vendor_bank_branch(code: str) -> str:
    return f"{VENDOR_BY_CODE[code].city} Main Branch"


# description -> (HSN/SAC, unit, GST %)
ITEMS: dict[str, tuple[str, str, int]] = {
    "Hex bolts M12 (box of 100)": ("73181500", "BOX", 18),
    "Safety helmets": ("65061010", "NOS", 18),
    "Industrial gloves (pair)": ("40159030", "PRS", 18),
    "Fire extinguisher 6kg": ("84241000", "NOS", 18),
    "Ergonomic office chair": ("94013000", "NOS", 18),
    "Standing desk": ("94033010", "NOS", 18),
    "A4 paper reams": ("48025690", "REAM", 18),
    "Whiteboard 6x4": ("96100000", "NOS", 18),
    "Freight Mumbai-Delhi (per trip)": ("996511", "TRIP", 5),
    "Warehouse handling (per pallet)": ("996729", "PLT", 18),
    "Corrugated boxes 18x12x10": ("48191010", "NOS", 18),
    "Printed brochures": ("49011020", "NOS", 18),
    "Roll-up banner": ("49111020", "NOS", 18),
    "Flyers A5": ("49111090", "NOS", 18),
    "Monthly housekeeping service": ("998533", "MON", 18),
    "Deep cleaning (per visit)": ("998533", "VISIT", 18),
    "Business laptop 14in": ("84713010", "NOS", 18),
    "Docking station": ("84733099", "NOS", 18),
    "27in monitor": ("85285200", "NOS", 18),
    "Notebook A5 (pack of 12)": ("48202000", "PKT", 18),
    "Ball pens (box)": ("96081019", "BOX", 18),
    "Catering per head": ("996334", "PAX", 5),
    "LED panel light 40W": ("94051900", "NOS", 18),
    "Copper cable 2.5mm (100m)": ("85444999", "COIL", 18),
    "MCB 32A": ("85362030", "NOS", 18),
    "Developer hours": ("998314", "HRS", 18),
    "Cloud compute (per vCPU-month)": ("998315", "VCPU", 18),
    "Managed PostgreSQL (monthly)": ("998315", "MON", 18),
    "Lounge sofa 3-seater": ("94016100", "NOS", 18),
    "Coffee table": ("94036000", "NOS", 18),
    "Reception desk": ("94033090", "NOS", 18),
    "Isopropyl alcohol 99% (200L drum)": ("29051220", "DRUM", 18),
    "Cleaning concentrate (50L can)": ("34022090", "CAN", 18),
    "Stretch film roll 23 micron": ("39201012", "ROLL", 18),
    "BOPP tape 48mm (pack of 6)": ("39191000", "PKT", 18),
    "Security guard services (per guard-month)": ("998525", "MON", 18),
    "Security supervisor (per month)": ("998525", "MON", 18),
    "Additional guard cover (per shift)": ("998525", "SHIFT", 18),
    "Corporate cab services (per day)": ("996601", "DAY", 5),
}  # fmt: skip


def item_meta(description: str) -> tuple[str, str, int]:
    return ITEMS.get(description, ("", "NOS", 18))


# po_number, vendor_code, po_date, currency, status, description, items[(desc, qty, unit_price)]
POS = [
    ("PO-2026-0001", "V-1001", "2026-04-02", "INR", "ACTIVE", "Industrial fasteners and safety equipment", [("Hex bolts M12 (box of 100)", 400, 450), ("Safety helmets", 300, 650), ("Industrial gloves (pair)", 1000, 120)]),
    ("PO-2026-0002", "V-1002", "2026-04-10", "INR", "ACTIVE", "Office furniture and consumables", [("Ergonomic office chair", 40, 4800), ("Standing desk", 20, 9500), ("A4 paper reams", 500, 260)]),
    ("PO-2026-0003", "V-1003", "2026-05-05", "INR", "ACTIVE", "Line-haul freight Mumbai-Delhi FY26-27", [("Freight Mumbai-Delhi (per trip)", 24, 5000)]),
    ("PO-2026-0004", "V-1004", "2026-05-12", "INR", "ACTIVE", "Branded packaging materials", [("Corrugated boxes 18x12x10", 2000, 18), ("Printed brochures", 5000, 6)]),
    ("PO-2026-0005", "V-1005", "2026-05-02", "INR", "ACTIVE", "Facility housekeeping services FY26-27", [("Monthly housekeeping service", 12, 50000), ("Deep cleaning (per visit)", 24, 3500)]),
    ("PO-2026-0006", "V-1006", "2026-06-01", "INR", "ACTIVE", "Laptop refresh and peripherals", [("Business laptop 14in", 20, 62000), ("Docking station", 20, 9500), ("27in monitor", 10, 14000)]),
    ("PO-2026-0007", "V-1007", "2026-06-08", "INR", "ACTIVE", "Stationery supplies", [("Notebook A5 (pack of 12)", 200, 480), ("Ball pens (box)", 300, 90)]),
    ("PO-2026-0008", "V-1008", "2026-10-15", "INR", "ACTIVE", "Diwali staff celebration catering", [("Catering per head", 600, 200)]),
    ("PO-2026-0009", "V-1009", "2026-06-22", "INR", "ACTIVE", "Electrical installation and fittings", [("LED panel light 40W", 500, 850), ("Copper cable 2.5mm (100m)", 120, 2400), ("MCB 32A", 300, 380)]),
    ("PO-2026-0010", "V-1010", "2026-07-01", "INR", "ACTIVE", "Software development retainer", [("Developer hours", 2400, 1200)]),
    ("PO-2026-0011", "V-1011", "2026-07-01", "INR", "ACTIVE", "Cloud infrastructure services", [("Cloud compute (per vCPU-month)", 600, 1450), ("Managed PostgreSQL (monthly)", 12, 38000)]),
    ("PO-2026-0012", "V-1012", "2026-07-18", "INR", "ACTIVE", "Reception and lounge furnishing", [("Lounge sofa 3-seater", 10, 14500), ("Coffee table", 15, 3200), ("Reception desk", 2, 18000)]),
    ("PO-2026-0013", "V-1001", "2026-01-15", "INR", "CLOSED", "FY25-26 fire safety stock (closed)", [("Fire extinguisher 6kg", 100, 900)]),
    ("PO-2026-0014", "V-1002", "2026-03-01", "INR", "CANCELLED", "Cancelled training room fit-out", [("Whiteboard 6x4", 10, 3500)]),
    ("PO-2026-0015", "V-1003", "2026-08-01", "INR", "ACTIVE", "Warehouse handling services", [("Warehouse handling (per pallet)", 3000, 50)]),
    ("PO-2026-0016", "V-1004", "2026-08-12", "INR", "ACTIVE", "Marketing collateral", [("Roll-up banner", 60, 1200), ("Flyers A5", 20000, 2)]),
    ("PO-2026-0017", "V-1013", "2026-06-05", "INR", "ACTIVE", "Cleaning and process chemicals", [("Isopropyl alcohol 99% (200L drum)", 40, 21500), ("Cleaning concentrate (50L can)", 60, 4200)]),
    ("PO-2026-0018", "V-1014", "2026-06-18", "INR", "ACTIVE", "Warehouse packaging consumables", [("Stretch film roll 23 micron", 800, 540), ("BOPP tape 48mm (pack of 6)", 1200, 210)]),
    ("PO-2026-0019", "V-1015", "2026-05-01", "INR", "ACTIVE", "Manned guarding - warehouse and HQ", [("Security guard services (per guard-month)", 72, 24000), ("Security supervisor (per month)", 12, 32000), ("Additional guard cover (per shift)", 200, 1500)]),
    ("PO-2026-0020", "V-1016", "2026-07-01", "INR", "ACTIVE", "Employee transport - corporate cabs", [("Corporate cab services (per day)", 400, 3200)]),
]  # fmt: skip

PO_BY_NUMBER = {p[0]: p for p in POS}

_Q = Decimal("0.01")


def po_total(items: list[tuple[str, int, float]]) -> Decimal:
    """PO value including GST at each item's rate (invoices carry tax, so this is what they draw down)."""
    total = sum(
        (Decimal(str(q)) * Decimal(str(p)) * (1 + Decimal(item_meta(d)[2]) / 100) for d, q, p in items),
        Decimal("0"),
    )
    return total.quantize(_Q, ROUND_HALF_UP)


@dataclass
class Spec:
    """One invoice to render. Amounts are computed unless overridden."""

    file: str
    scenario: str
    expected: str  # APPROVED | NEEDS_REVIEW | REJECTED | PROCESSING_FAILED
    vendor_name: str
    vendor_address: str
    gstin: str | None
    number: str | None
    date: str
    due: str
    po: str | None
    currency: str
    items: list[tuple[str, int, float, int]]  # description, qty, unit_price, GST %
    layout: str = "tally"  # tally | corporate | services
    total_override: str | None = None
    note: str = ""
    kind: str = "digital"  # digital | scanned | corrupted | copy_of
    copy_of: str | None = None
    bank: tuple[str, str, str] | None = None  # (bank name, account, IFSC) printed on the invoice
    vendor_code: str | None = None
    state: str = BUYER_STATE  # supplier state code (decides CGST+SGST vs IGST)
    label: str | None = None  # e.g. "REVISED" stamp on a re-issued copy
    description: str = ""  # one-line explanation shown in the UI
    category: str = ""  # edge-case grouping shown in the UI
    extra: dict = field(default_factory=dict)

    @property
    def intra_state(self) -> bool:
        return self.state == BUYER_STATE

    def bank_text(self) -> str | None:
        if not self.bank:
            return None
        name, account, ifsc = self.bank
        return f"{name}, A/C {account}, IFSC {ifsc}"

    def tax_lines(self) -> list[tuple[int, Decimal, Decimal]]:
        """[(rate, taxable value, tax amount)] grouped by GST rate, rounded the way billing systems do."""
        groups: dict[int, Decimal] = {}
        for _, qty, price, rate in self.items:
            groups[rate] = groups.get(rate, Decimal("0")) + Decimal(str(price)) * qty
        out = []
        for rate, taxable in sorted(groups.items()):
            if self.intra_state:
                half = (taxable * Decimal(rate) / 200).quantize(_Q, ROUND_HALF_UP)
                out.append((rate, taxable, half * 2))
            else:
                out.append((rate, taxable, (taxable * Decimal(rate) / 100).quantize(_Q, ROUND_HALF_UP)))
        return out

    def round_off(self) -> Decimal:
        subtotal = sum((t for _, t, _ in self.tax_lines()), Decimal("0"))
        tax = sum((x for _, _, x in self.tax_lines()), Decimal("0"))
        gross = subtotal + tax
        return gross.quantize(Decimal("1"), ROUND_HALF_UP) - gross if self.currency == "INR" else Decimal("0")

    def amounts(self) -> tuple[Decimal, Decimal, Decimal]:
        subtotal = sum((t for _, t, _ in self.tax_lines()), Decimal("0")).quantize(_Q)
        tax = sum((x for _, _, x in self.tax_lines()), Decimal("0")).quantize(_Q)
        total = Decimal(self.total_override) if self.total_override else (subtotal + tax + self.round_off()).quantize(_Q)
        return subtotal, tax, total


def _due(d: str, days: int = 30) -> str:
    return (date.fromisoformat(d) + timedelta(days=days)).isoformat()


def _spec(code: str, po: str | None, lines: list[tuple], **kw) -> Spec:
    """Build an invoice for a vendor. `lines` = [(description, qty)] priced from the PO,
    or [(description, qty, unit_price)] for an explicit price."""
    v = VENDOR_BY_CODE[code]
    po_row = PO_BY_NUMBER.get(kw.pop("price_po", None) or po or "")
    prices = {d: p for d, _, p in (po_row[6] if po_row else [])}
    items = []
    for line in lines:
        desc, qty = line[0], line[1]
        price = line[2] if len(line) > 2 else prices[desc]
        items.append((desc, qty, price, item_meta(desc)[2]))
    kw.setdefault("vendor_name", v.name)
    kw.setdefault("vendor_address", v.one_line_address)
    kw.setdefault("gstin", v.gstin)
    kw.setdefault("bank", vendor_bank(code))
    kw.setdefault("layout", v.layout)
    kw.setdefault("due", _due(kw["date"]))
    kw.setdefault("currency", "INR")
    kw.setdefault("scenario", "History")
    kw.setdefault("expected", "APPROVED")
    return Spec(vendor_code=code, state=v.state, po=po, items=items, **kw)


def _h(code: str, po: str | None, number: str, inv_date: str, lines: list[tuple], **kw) -> Spec:
    slug = number.lower().replace("/", "-")
    return _spec(code, po, lines, file=f"h_{slug}.pdf", number=number, date=inv_date, **kw)


# ---------------------------------------------------------------------------------------------
# HISTORY: 50 invoices processed May-Oct 2026. Loaded by the seed script with their extracted data
# through the deterministic pipeline (no LLM calls) and kept forever (source_origin=SEED_HISTORY).
# Order = upload order (duplicate detection only looks backwards). `resolve` closes a review the way
# a reviewer did at the time.
# ---------------------------------------------------------------------------------------------
_FIN = "finance@payflow.demo"
_REV = "reviewer@payflow.demo"

HISTORY: list[Spec] = sorted(
    [
        # Acme Industrial - PO-2026-0001
        _h("V-1001", "PO-2026-0001", "ACM/2026/0987", "2026-05-14", [("Hex bolts M12 (box of 100)", 100), ("Safety helmets", 50)]),
        _h("V-1001", "PO-2026-0001", "ACM/2026/1011", "2026-07-03", [("Industrial gloves (pair)", 500), ("Hex bolts M12 (box of 100)", 80)]),
        _h("V-1001", "PO-2026-0001", "ACM/2026/1029", "2026-09-08", [("Safety helmets", 60), ("Industrial gloves (pair)", 200)]),
        # Bharat Office - PO-2026-0002
        _h("V-1002", "PO-2026-0002", "BOS/26-27/0418", "2026-06-02", [("Ergonomic office chair", 10)]),
        _h("V-1002", "PO-2026-0002", "BOS/26-27/0533", "2026-08-11", [("Standing desk", 6), ("A4 paper reams", 150)]),
        # Cobalt Logistics - freight PO-2026-0003 (18 of 24 trips used) + warehousing PO-2026-0015
        _h("V-1003", "PO-2026-0003", "CL/DEL/26-27/221", "2026-06-20", [("Freight Mumbai-Delhi (per trip)", 6)]),
        _h("V-1003", "PO-2026-0003", "CL/DEL/26-27/247", "2026-08-05", [("Freight Mumbai-Delhi (per trip)", 7)]),
        _h("V-1003", "PO-2026-0015", "CL/DEL/26-27/259", "2026-09-10", [("Warehouse handling (per pallet)", 640)]),
        _h("V-1003", "PO-2026-0003", "CL/DEL/26-27/268", "2026-09-29", [("Freight Mumbai-Delhi (per trip)", 5)]),
        _h("V-1003", "PO-2026-0015", "CL/DEL/26-27/281", "2026-10-08", [("Warehouse handling (per pallet)", 710)]),
        # Deccan Print - PO-2026-0004 / 0016 (one invoice arrived without a PO and was cleared by a reviewer)
        _h("V-1004", "PO-2026-0004", "DPP/26-27/0341", "2026-06-25", [("Corrugated boxes 18x12x10", 600), ("Printed brochures", 1500)]),
        _h("V-1004", "PO-2026-0016", "DPP/26-27/0388", "2026-08-30", [("Roll-up banner", 20), ("Flyers A5", 8000)]),
        _h("V-1004", None, "DPP/26-27/0412", "2026-09-28", [("Corrugated boxes 18x12x10", 1000)], price_po="PO-2026-0004", expected="NEEDS_REVIEW",
           extra={"resolve": ("APPROVE", "Procurement (Ravi Menon) confirmed this delivery is against PO-2026-0004; GRN 2026-1187 received in full.", _REV)}),
        # Evergreen Facility - monthly housekeeping PO-2026-0005 (deep-clean visits vary each month)
        _h("V-1005", "PO-2026-0005", "EFS/26-27/0092", "2026-05-31", [("Monthly housekeeping service", 1), ("Deep cleaning (per visit)", 1)], note="Service period: May 2026"),
        _h("V-1005", "PO-2026-0005", "EFS/26-27/0105", "2026-06-30", [("Monthly housekeeping service", 1)], note="Service period: June 2026"),
        _h("V-1005", "PO-2026-0005", "EFS/26-27/0118", "2026-07-31", [("Monthly housekeeping service", 1), ("Deep cleaning (per visit)", 2)], note="Service period: July 2026"),
        _h("V-1005", "PO-2026-0005", "EFS/26-27/0124", "2026-08-31", [("Monthly housekeeping service", 1), ("Deep cleaning (per visit)", 3)], note="Service period: August 2026"),
        _h("V-1005", "PO-2026-0005", "EFS/26-27/0131", "2026-09-30", [("Monthly housekeeping service", 1), ("Deep cleaning (per visit)", 4)], note="Service period: September 2026"),
        # Falcon IT - PO-2026-0006 (one batch above the auto-approval limit, signed off by Finance)
        _h("V-1006", "PO-2026-0006", "FIT-26-5530", "2026-07-21", [("Business laptop 14in", 2), ("Docking station", 2)]),
        _h("V-1006", "PO-2026-0006", "FIT-26-5588", "2026-09-02", [("27in monitor", 4)]),
        _h("V-1006", "PO-2026-0006", "FIT-26-5641", "2026-10-06", [("Business laptop 14in", 6), ("Docking station", 6)], expected="NEEDS_REVIEW",
           extra={"resolve": ("APPROVE", "Approved by Finance: budgeted Q3 laptop refresh (CapEx ref CPX-2026-14), quantities match GRN 2026-1342.", _FIN)}),
        # Gamma Stationers - vendor deactivated, invoice blocked
        _h("V-1007", "PO-2026-0007", "GS/2318", "2026-10-02", [("Notebook A5 (pack of 12)", 50)], expected="REJECTED"),
        # Indus Electricals - PO-2026-0009 (one mis-totalled invoice rejected, corrected copy approved)
        _h("V-1009", "PO-2026-0009", "IE/26-27/0390", "2026-07-18", [("LED panel light 40W", 100), ("MCB 32A", 50)]),
        _h("V-1009", "PO-2026-0009", "IE/26-27/0412", "2026-08-18", [("Copper cable 2.5mm (100m)", 20)], total_override="65640.00", expected="NEEDS_REVIEW",
           extra={"resolve": ("REJECT", "Grand total does not equal taxable value plus IGST (overstated by Rs 9,000). Vendor asked to re-issue a corrected invoice.", _REV)}),
        _h("V-1009", "PO-2026-0009", "IE/26-27/0419", "2026-08-26", [("Copper cable 2.5mm (100m)", 20)], note="Corrected invoice replacing IE/26-27/0412"),
        _h("V-1009", "PO-2026-0009", "IE/26-27/0448", "2026-10-10", [("LED panel light 40W", 80), ("MCB 32A", 60)]),
        # Jupiter Software - monthly retainer PO-2026-0010
        _h("V-1010", "PO-2026-0010", "JSS/INV/26-27/071", "2026-07-31", [("Developer hours", 168)], note="Service period: July 2026"),
        _h("V-1010", "PO-2026-0010", "JSS/INV/26-27/079", "2026-08-31", [("Developer hours", 184)], note="Service period: August 2026"),
        _h("V-1010", "PO-2026-0010", "JSS/INV/26-27/086", "2026-09-30", [("Developer hours", 176)], note="Service period: September 2026"),
        _h("V-1010", "PO-2026-0010", "JSS/INV/26-27/094", "2026-10-31", [("Developer hours", 152)], note="Service period: October 2026"),
        # Kestrel Cloud - monthly usage PO-2026-0011
        _h("V-1011", "PO-2026-0011", "KCT/26-27/0211", "2026-07-31", [("Cloud compute (per vCPU-month)", 40), ("Managed PostgreSQL (monthly)", 1)], note="Billing period: July 2026"),
        _h("V-1011", "PO-2026-0011", "KCT/26-27/0236", "2026-08-31", [("Cloud compute (per vCPU-month)", 44), ("Managed PostgreSQL (monthly)", 1)], note="Billing period: August 2026"),
        _h("V-1011", "PO-2026-0011", "KCT/26-27/0262", "2026-09-30", [("Cloud compute (per vCPU-month)", 48), ("Managed PostgreSQL (monthly)", 1)], note="Billing period: September 2026"),
        _h("V-1011", "PO-2026-0011", "KCT/26-27/0289", "2026-10-31", [("Cloud compute (per vCPU-month)", 52), ("Managed PostgreSQL (monthly)", 1)], note="Billing period: October 2026"),
        # Lotus Furnishings - PO-2026-0012
        _h("V-1012", "PO-2026-0012", "LFC/26-27/3320", "2026-08-14", [("Lounge sofa 3-seater", 2), ("Coffee table", 4)]),
        _h("V-1012", "PO-2026-0012", "LFC/26-27/3391", "2026-10-01", [("Reception desk", 1)]),
        # Meridian Chemicals - PO-2026-0017
        _h("V-1013", "PO-2026-0017", "MCPL/26-27/0611", "2026-07-09", [("Isopropyl alcohol 99% (200L drum)", 6), ("Cleaning concentrate (50L can)", 10)]),
        _h("V-1013", "PO-2026-0017", "MCPL/26-27/0688", "2026-09-17", [("Isopropyl alcohol 99% (200L drum)", 8)]),
        # Nova Packaging - PO-2026-0018
        _h("V-1014", "PO-2026-0018", "NPI/26-27/1102", "2026-07-02", [("Stretch film roll 23 micron", 150), ("BOPP tape 48mm (pack of 6)", 200)]),
        _h("V-1014", "PO-2026-0018", "NPI/26-27/1187", "2026-08-20", [("Stretch film roll 23 micron", 120)]),
        _h("V-1014", "PO-2026-0018", "NPI/26-27/1240", "2026-10-05", [("BOPP tape 48mm (pack of 6)", 300)]),
        # Orion Security - monthly manned guarding PO-2026-0019 (extra shifts vary)
        _h("V-1015", "PO-2026-0019", "OSS/MUM/26-27/041", "2026-05-31", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1)], note="Service period: May 2026"),
        _h("V-1015", "PO-2026-0019", "OSS/MUM/26-27/057", "2026-06-30", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1), ("Additional guard cover (per shift)", 4)], note="Service period: June 2026"),
        _h("V-1015", "PO-2026-0019", "OSS/MUM/26-27/073", "2026-07-31", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1), ("Additional guard cover (per shift)", 10)], note="Service period: July 2026"),
        _h("V-1015", "PO-2026-0019", "OSS/MUM/26-27/088", "2026-08-31", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1), ("Additional guard cover (per shift)", 6)], note="Service period: August 2026"),
        _h("V-1015", "PO-2026-0019", "OSS/MUM/26-27/102", "2026-09-30", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1), ("Additional guard cover (per shift)", 12)], note="Service period: September 2026"),
        # Pinnacle Travels - monthly cabs PO-2026-0020
        _h("V-1016", "PO-2026-0020", "PTT/26-27/0614", "2026-07-31", [("Corporate cab services (per day)", 22)], note="Service period: July 2026"),
        _h("V-1016", "PO-2026-0020", "PTT/26-27/0702", "2026-08-31", [("Corporate cab services (per day)", 26)], note="Service period: August 2026"),
        _h("V-1016", "PO-2026-0020", "PTT/26-27/0788", "2026-09-30", [("Corporate cab services (per day)", 24)], note="Service period: September 2026"),
        _h("V-1016", "PO-2026-0020", "PTT/26-27/0861", "2026-10-31", [("Corporate cab services (per day)", 30)], note="Service period: October 2026"),
    ],
    key=lambda s: s.date,
)  # fmt: skip

# ---------------------------------------------------------------------------------------------
# TEST INVOICES: uploaded during the demo (LIVE_UPLOAD). "Reset demo" clears only these.
# Upload order matters for 03/04 (after 01). 14 is a re-sent copy of a SEEDED history invoice.
# ---------------------------------------------------------------------------------------------
_PNB = ("Punjab National Bank", "0361002100098765", "PUNB0036100")
_MERIDIAN_TYPO = VENDOR_BY_CODE["V-1013"].gstin[:9] + "8" + VENDOR_BY_CODE["V-1013"].gstin[10:]  # one digit mistyped

INVOICES: list[Spec] = [
    _spec("V-1001", "PO-2026-0001", [("Hex bolts M12 (box of 100)", 100), ("Safety helmets", 80)],
          file="01_valid_invoice.pdf", number="ACM/2026/1042", date="2026-10-30",
          scenario="Clean intra-state invoice (CGST + SGST)", expected="APPROVED", category="Happy path",
          description="Active vendor in Maharashtra, valid GSTIN, verified bank account; lines and balance match PO-2026-0001."),
    _spec("V-1002", "PO-2026-0002", [("Ergonomic office chair", 6), ("Standing desk", 4), ("A4 paper reams", 100)],
          file="02_interstate_multi_line.pdf", number="BOS/26-27/0571", date="2026-10-31",
          scenario="Inter-state, multi-line invoice (IGST)", expected="APPROVED", category="Happy path",
          description="Karnataka supplier billing Maharashtra: IGST applies. Three lines reconciled against the PO."),
    Spec(file="03_exact_duplicate.pdf", scenario="Exact duplicate PDF (upload after 01)", expected="REJECTED", kind="copy_of",
         copy_of="01_valid_invoice.pdf", vendor_name="", vendor_address="", gstin=None,
         number=None, date="", due="", po=None, currency="INR", items=[], category="Duplicates",
         description="Byte-identical copy of invoice 01 - caught by the file fingerprint before anything else."),
    _spec("V-1001", "PO-2026-0001", [("Hex bolts M12 (box of 100)", 100), ("Safety helmets", 80)],
          file="04_duplicate_invoice_number.pdf", number="ACM/2026/1042", date="2026-10-30", label="REVISED COPY",
          scenario="Same invoice number re-sent as a new PDF (upload after 01)", expected="REJECTED", category="Duplicates",
          description="Vendor re-sends ACM/2026/1042 as a 'revised copy' - different file, same vendor + number."),
    _spec("V-1003", "PO-2026-0003", [("Freight Mumbai-Delhi (per trip)", 10)],
          file="05_exceeds_po_balance.pdf", number="CL/DEL/26-27/284", date="2026-11-02",
          scenario="Invoice exceeds remaining PO balance", expected="NEEDS_REVIEW", category="PO controls",
          description="18 of 24 trips were already billed in history; 10 more trips over-draw PO-2026-0003."),
    _spec("V-1007", "PO-2026-0007", [("Notebook A5 (pack of 12)", 40), ("Ball pens (box)", 60)],
          file="06_inactive_vendor.pdf", number="GS/2336", date="2026-11-03",
          scenario="Inactive vendor", expected="REJECTED", category="Vendor controls",
          description="Gamma Stationers was deactivated in the vendor master - payment is blocked."),
    _spec("V-1009", "PO-2026-0009", [("MCB 32A", 40)], bank=_PNB,
          file="07_bank_details_changed.pdf", number="IE/26-27/0461", date="2026-11-04",
          scenario="Bank account differs from vendor master", expected="NEEDS_REVIEW", category="Fraud controls",
          description="Remittance details point to a new Punjab National Bank account - classic payment-diversion fraud."),
    _spec("V-1014", "PO-2026-0018", [("Stretch film roll 23 micron", 100), ("BOPP tape 48mm (pack of 6)", 150)],
          file="08_arithmetic_mismatch.pdf", number="NPI/26-27/1268", date="2026-11-04", total_override="109890.00",
          scenario="Grand total does not add up", expected="NEEDS_REVIEW", category="Data quality",
          description="Taxable value + CGST + SGST = Rs 1,00,890, but the printed grand total is Rs 1,09,890 (overstated by Rs 9,000)."),
    _spec("V-1010", None, [("Developer hours", 40)], price_po="PO-2026-0010", note="Change request CR-14: GST e-way bill integration",
          file="09_missing_po.pdf", number="JSS/INV/26-27/097", date="2026-11-05",
          scenario="No PO reference on the invoice", expected="NEEDS_REVIEW", category="PO controls",
          description="Change-request work billed without a PO number - the system suggests the likely PO but a human must confirm."),
    _spec("V-1013", "PO-2026-0017", [("Isopropyl alcohol 99% (200L drum)", 4), ("Cleaning concentrate (50L can)", 12)], gstin=_MERIDIAN_TYPO,
          file="10_invalid_gstin.pdf", number="MCPL/26-27/0702", date="2026-11-05",
          scenario="GSTIN fails the check-digit test", expected="NEEDS_REVIEW", category="Vendor controls",
          description="One digit of the supplier GSTIN is mistyped - the GSTN mod-36 check digit no longer validates."),
    _spec("V-1006", "PO-2026-0006", [("Business laptop 14in", 5), ("Docking station", 5)],
          file="11_high_value_approval.pdf", number="FIT-26-5702", date="2026-11-06",
          scenario="Clean invoice above the auto-approval limit", expected="NEEDS_REVIEW", category="Approval authority",
          description="Everything checks out, but Rs 4,21,850 is above the Rs 4,00,000 limit - needs a Finance Manager."),
    _spec("V-1015", "PO-2026-0019", [("Security guard services (per guard-month)", 6), ("Security supervisor (per month)", 1), ("Additional guard cover (per shift)", 16)],
          file="12_scanned_invoice.pdf", number="OSS/MUM/26-27/118", date="2026-10-31", kind="scanned", note="Service period: October 2026",
          scenario="Scanned paper invoice (OCR)", expected="APPROVED", category="Happy path",
          description="Photocopied, slightly skewed scan with no text layer - read by OCR, then the same 24 controls."),
    Spec(file="13_corrupted.pdf", scenario="Corrupted PDF (technical failure, not a rejection)", expected="PROCESSING_FAILED",
         kind="corrupted", vendor_name="", vendor_address="", gstin=None, number=None, date="", due="", po=None, currency="INR",
         items=[], category="Technical failure", description="Truncated file that no PDF reader can open - routed as a technical failure."),
    _spec("V-1005", "PO-2026-0005", [("Monthly housekeeping service", 1), ("Deep cleaning (per visit)", 4)], note="Service period: September 2026",
          file="14_resubmitted_paid_invoice.pdf", number="EFS/26-27/0131", date="2026-09-30", label="PAYMENT REMINDER",
          scenario="Re-submitted invoice already processed in history", expected="REJECTED", category="Duplicates",
          description="Evergreen re-sends September's EFS/26-27/0131 (already approved in the seeded history) as a 'reminder'."),
    _spec("V-1008", "PO-2026-0008", [("Catering per head", 250)], note="Event: Diwali staff celebration, 06-Nov-2026, Bhiwandi warehouse",
          file="15_pending_vendor.pdf", number="HCS/26-27/058", date="2026-11-07",
          scenario="Vendor still pending onboarding", expected="NEEDS_REVIEW", category="Vendor controls",
          description="Horizon Catering has not finished KYC / onboarding - invoice is held until the vendor is activated."),
]  # fmt: skip
