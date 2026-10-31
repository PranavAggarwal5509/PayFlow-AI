"""Synthetic demo dataset definition (all names, GSTINs and amounts are fictional).

`generate_sample_invoices.py` turns this catalogue into JSON + PDF files under sample_data/;
`seed_database.py` loads those files into PostgreSQL. GSTINs follow the real 15-character format
but are not registered to anyone.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

VENDORS = [
    # code, name, gstin, city/address, status
    ("V-1001", "Acme Industrial Supplies Pvt Ltd", "27AABCA1001A1Z5", "Plot 14, MIDC Andheri East, Mumbai 400093", "ACTIVE"),
    ("V-1002", "Bharat Office Solutions Pvt Ltd", "29AABCB1002B1Z3", "88 Residency Road, Bengaluru 560025", "ACTIVE"),
    ("V-1003", "Cobalt Logistics LLP", "07AABCC1003C1Z1", "B-21 Okhla Phase II, New Delhi 110020", "ACTIVE"),
    ("V-1004", "Deccan Print & Packaging Ltd", "36AABCD1004D1Z9", "Survey 42, Medchal Road, Hyderabad 500067", "ACTIVE"),
    ("V-1005", "Evergreen Facility Services", "33AABCE1005E1Z7", "12 Anna Salai, Chennai 600002", "ACTIVE"),
    ("V-1006", "Falcon IT Hardware Pvt Ltd", "24AABCF1006F1Z4", "7th Floor, Prahlad Nagar, Ahmedabad 380015", "ACTIVE"),
    ("V-1007", "Gamma Stationers", "19AABCG1007G1Z2", "45 Park Street, Kolkata 700016", "INACTIVE"),
    ("V-1008", "Horizon Catering Services", "32AABCH1008H1Z0", "Marine Drive, Kochi 682031", "PENDING"),
    ("V-1009", "Indus Electricals Pvt Ltd", "09AABCI1009I1Z8", "C-9 Sector 62, Noida 201301", "ACTIVE"),
    ("V-1010", "Jupiter Software Services Pvt Ltd", "27AABCJ1010J1Z6", "Hinjewadi Phase 1, Pune 411057", "ACTIVE"),
    ("V-1011", "Kestrel Cloud Technologies Pvt Ltd", "29AABCK1011K1Z4", "Embassy Tech Village, Bengaluru 560103", "ACTIVE"),
    ("V-1012", "Lotus Furnishings Co", "08AABCL1012L1Z2", "Sitapura Industrial Area, Jaipur 302022", "ACTIVE"),
]  # fmt: skip

# po_number, vendor_code, po_date, currency, status, description, items[(desc, qty, unit_price)]
POS = [
    ("PO-2026-0001", "V-1001", "2026-04-02", "INR", "ACTIVE", "Industrial fasteners and safety equipment", [("Hex bolts M12 (box of 100)", 400, 450), ("Safety helmets", 300, 650), ("Industrial gloves (pair)", 1000, 120)]),
    ("PO-2026-0002", "V-1002", "2026-04-10", "INR", "ACTIVE", "Office furniture and consumables", [("Ergonomic office chair", 40, 4800), ("Standing desk", 20, 9500), ("A4 paper reams", 500, 260)]),
    ("PO-2026-0003", "V-1003", "2026-05-05", "INR", "ACTIVE", "Quarterly freight services", [("Freight Mumbai-Delhi (per trip)", 24, 5000)]),
    ("PO-2026-0004", "V-1004", "2026-05-12", "INR", "ACTIVE", "Branded packaging materials", [("Corrugated boxes 18x12x10", 2000, 18), ("Printed brochures", 5000, 6)]),
    ("PO-2026-0005", "V-1005", "2026-05-20", "INR", "ACTIVE", "Facility housekeeping services FY26", [("Monthly housekeeping service", 6, 50000)]),
    ("PO-2026-0006", "V-1006", "2026-06-01", "INR", "ACTIVE", "Laptops and peripherals", [("Business laptop 14in", 8, 62000), ("Docking station", 8, 9500), ("27in monitor", 10, 14000)]),
    ("PO-2026-0007", "V-1007", "2026-06-08", "INR", "ACTIVE", "Stationery supplies", [("Notebook A5 (pack of 12)", 200, 480), ("Ball pens (box)", 300, 90)]),
    ("PO-2026-0008", "V-1008", "2026-06-15", "INR", "ACTIVE", "Event catering - annual meet", [("Catering per head", 300, 200)]),
    ("PO-2026-0009", "V-1009", "2026-06-22", "INR", "ACTIVE", "Electrical installation and fittings", [("LED panel light 40W", 250, 850), ("Copper cable 2.5mm (100m)", 120, 2400), ("MCB 32A", 150, 380)]),
    ("PO-2026-0010", "V-1010", "2026-07-01", "INR", "ACTIVE", "Software development retainer", [("Developer hours", 1200, 300)]),
    ("PO-2026-0011", "V-1011", "2026-07-10", "USD", "ACTIVE", "Cloud infrastructure services", [("Compute credits", 100, 80), ("Managed database (monthly)", 6, 650)]),
    ("PO-2026-0012", "V-1012", "2026-07-18", "INR", "ACTIVE", "Reception and lounge furnishing", [("Lounge sofa 3-seater", 10, 14500), ("Coffee table", 15, 3200), ("Reception desk", 2, 18000)]),
    ("PO-2026-0013", "V-1001", "2026-01-15", "INR", "CLOSED", "FY25 safety stock (closed)", [("Fire extinguisher 6kg", 100, 900)]),
    ("PO-2026-0014", "V-1002", "2026-03-01", "INR", "CANCELLED", "Cancelled training room fit-out", [("Whiteboard 6x4", 10, 3500)]),
    ("PO-2026-0015", "V-1003", "2026-08-01", "INR", "ACTIVE", "Warehouse handling services", [("Warehouse handling (per pallet)", 3000, 50)]),
    ("PO-2026-0016", "V-1004", "2026-08-12", "INR", "ACTIVE", "Marketing collateral", [("Roll-up banner", 60, 1200), ("Flyers A5", 20000, 2)]),
]  # fmt: skip


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
    items: list[tuple[str, int, float, int]]  # description, qty, unit_price, tax %
    layout: str = "classic"
    total_override: str | None = None
    note: str = ""
    kind: str = "digital"  # digital | scanned | corrupted | copy_of
    copy_of: str | None = None
    extra: dict = field(default_factory=dict)

    def amounts(self) -> tuple[Decimal, Decimal, Decimal]:
        q = Decimal("0.01")
        subtotal = sum((Decimal(str(p)) * qty for _, qty, p, _ in self.items), Decimal("0"))
        tax = sum(
            (Decimal(str(p)) * qty * Decimal(t) / 100 for _, qty, p, t in self.items), Decimal("0")
        )
        subtotal, tax = subtotal.quantize(q, ROUND_HALF_UP), tax.quantize(q, ROUND_HALF_UP)
        total = Decimal(self.total_override) if self.total_override else subtotal + tax
        return subtotal, tax, total


def _v(code: str) -> tuple[str, str, str]:
    row = next(v for v in VENDORS if v[0] == code)
    return row[1], row[3], row[2]


def _spec(code: str, **kw) -> Spec:
    name, addr, gstin = _v(code)
    kw.setdefault("vendor_name", name)
    kw.setdefault("vendor_address", addr)
    kw.setdefault("gstin", gstin)
    return Spec(**kw)


# Invoices already processed before the demo starts (loaded through the real pipeline by the seed
# script). `days_ago` controls the upload date. Order matters for duplicate detection.
HISTORY = [
    _spec("V-1001", file="h01_acme.pdf", scenario="History", expected="APPROVED", number="ACM/2026/0987", date="2026-05-14", due="2026-06-13", po="PO-2026-0001", currency="INR", layout="classic", items=[("Hex bolts M12 (box of 100)", 100, 450, 18), ("Safety helmets", 50, 650, 18)], extra={"days_ago": 160}),
    _spec("V-1001", file="h02_acme.pdf", scenario="History", expected="APPROVED", number="ACM/2026/1011", date="2026-07-03", due="2026-08-02", po="PO-2026-0001", currency="INR", layout="modern", items=[("Industrial gloves (pair)", 500, 120, 18), ("Hex bolts M12 (box of 100)", 150, 450, 18)], extra={"days_ago": 100}),
    _spec("V-1002", file="h03_bharat.pdf", scenario="History", expected="APPROVED", number="BOS-8841", date="2026-06-02", due="2026-07-02", po="PO-2026-0002", currency="INR", layout="compact", items=[("Ergonomic office chair", 10, 4800, 18)], extra={"days_ago": 140}),
    _spec("V-1003", file="h04_cobalt.pdf", scenario="History", expected="APPROVED", number="CL-2026-221", date="2026-06-20", due="2026-07-20", po="PO-2026-0003", currency="INR", layout="classic", items=[("Freight Mumbai-Delhi (per trip)", 15, 5000, 18)], extra={"days_ago": 120}),
    _spec("V-1005", file="h05_evergreen.pdf", scenario="History", expected="APPROVED", number="EFS/2026/0118", date="2026-08-05", due="2026-09-04", po="PO-2026-0005", currency="INR", layout="modern", items=[("Monthly housekeeping service", 1, 50000, 18)], extra={"days_ago": 80}),
    _spec("V-1005", file="h06_evergreen.pdf", scenario="History", expected="APPROVED", number="EFS/2026/0131", date="2026-09-05", due="2026-10-05", po="PO-2026-0005", currency="INR", layout="modern", items=[("Monthly housekeeping service", 1, 52000, 18)], extra={"days_ago": 50}),
    _spec("V-1006", file="h07_falcon.pdf", scenario="History", expected="APPROVED", number="FIT-5530", date="2026-07-21", due="2026-08-20", po="PO-2026-0006", currency="INR", layout="compact", items=[("Business laptop 14in", 2, 62000, 18)], extra={"days_ago": 90}),
    _spec("V-1009", file="h08_indus.pdf", scenario="History", expected="APPROVED", number="IE/26-27/0412", date="2026-08-18", due="2026-09-17", po="PO-2026-0009", currency="INR", layout="classic", items=[("LED panel light 40W", 100, 850, 18), ("MCB 32A", 50, 380, 18)], extra={"days_ago": 70}),
    _spec("V-1010", file="h09_jupiter.pdf", scenario="History", expected="APPROVED", number="JSS/0071", date="2026-09-10", due="2026-10-10", po="PO-2026-0010", currency="INR", layout="modern", items=[("Developer hours", 200, 300, 18)], extra={"days_ago": 45}),
    _spec("V-1012", file="h10_lotus.pdf", scenario="History", expected="APPROVED", number="LFC-3320", date="2026-09-22", due="2026-10-22", po="PO-2026-0012", currency="INR", layout="compact", items=[("Lounge sofa 3-seater", 2, 14500, 18)], extra={"days_ago": 35}),
    _spec("V-1004", file="h11_deccan.pdf", scenario="History", expected="NEEDS_REVIEW", number="DPP-0412", date="2026-09-28", due="2026-10-28", po=None, currency="INR", layout="classic", items=[("Corrugated boxes 18x12x10", 1000, 18, 18)], extra={"days_ago": 25}),
    _spec("V-1007", file="h12_gamma.pdf", scenario="History", expected="REJECTED", number="GS-7781", date="2026-10-02", due="2026-11-01", po="PO-2026-0007", currency="INR", layout="compact", items=[("Ball pens (box)", 100, 90, 18)], extra={"days_ago": 20}),
    _spec("V-1011", file="h13_kestrel.pdf", scenario="History", expected="APPROVED", number="KCT-USD-0099", date="2026-09-30", due="2026-10-30", po="PO-2026-0011", currency="USD", layout="modern", items=[("Compute credits", 20, 80, 0)], extra={"days_ago": 22}),
]  # fmt: skip

# Invoices to upload during the demo (generated into sample_data/invoices/).
INVOICES = [
    _spec("V-1001", file="01_valid_invoice.pdf", scenario="Valid invoice, matching vendor and PO", expected="APPROVED", number="ACM/2026/1042", date="2026-10-12", due="2026-11-11", po="PO-2026-0001", currency="INR", layout="classic", items=[("Hex bolts M12 (box of 100)", 100, 450, 18), ("Safety helmets", 80, 650, 18)]),
    _spec("V-1002", file="02_valid_multi_line.pdf", scenario="Valid invoice with multiple line items", expected="APPROVED", number="BOS-9012", date="2026-10-14", due="2026-11-13", po="PO-2026-0002", currency="INR", layout="modern", items=[("Ergonomic office chair", 6, 4800, 18), ("Standing desk", 4, 9500, 18), ("A4 paper reams", 100, 260, 12)]),
    Spec(file="03_exact_duplicate.pdf", scenario="Exact duplicate PDF (upload after 01)", expected="REJECTED", kind="copy_of", copy_of="01_valid_invoice.pdf", vendor_name="", vendor_address="", gstin=None, number=None, date="", due="", po=None, currency="INR", items=[]),
    _spec("V-1001", file="04_duplicate_invoice_number.pdf", scenario="Same vendor + invoice number, different PDF (upload after 01)", expected="REJECTED", number="ACM/2026/1042", date="2026-10-12", due="2026-11-11", po="PO-2026-0001", currency="INR", layout="compact", items=[("Hex bolts M12 (box of 100)", 100, 450, 18), ("Safety helmets", 80, 650, 18)]),
    _spec("V-1003", file="05_exceeds_po_balance.pdf", scenario="Invoice exceeds remaining PO balance", expected="NEEDS_REVIEW", number="CL-2026-248", date="2026-10-15", due="2026-11-14", po="PO-2026-0003", currency="INR", layout="classic", items=[("Freight Mumbai-Delhi (per trip)", 12, 5000, 18)]),
    _spec("V-1004", file="06_missing_invoice_number.pdf", scenario="Missing invoice number", expected="NEEDS_REVIEW", number=None, date="2026-10-16", due="2026-11-15", po="PO-2026-0004", currency="INR", layout="modern", items=[("Corrugated boxes 18x12x10", 1000, 18, 18), ("Printed brochures", 2000, 6, 18)]),
    _spec("V-1007", file="07_inactive_vendor.pdf", scenario="Inactive vendor", expected="REJECTED", number="GS-7802", date="2026-10-17", due="2026-11-16", po="PO-2026-0007", currency="INR", layout="compact", items=[("Notebook A5 (pack of 12)", 50, 480, 18)]),
    _spec("V-1006", file="08_vendor_name_variation.pdf", scenario="Vendor name variation, no GSTIN", expected="NEEDS_REVIEW", vendor_name="Falcon I.T. Hardware Private Limited", gstin=None, number="FIT-5611", date="2026-10-18", due="2026-11-17", po="PO-2026-0006", currency="INR", layout="classic", items=[("27in monitor", 4, 14000, 18)]),
    _spec("V-1010", file="09_missing_po.pdf", scenario="Missing PO reference", expected="NEEDS_REVIEW", number="JSS/0082", date="2026-10-19", due="2026-11-18", po=None, currency="INR", layout="modern", items=[("Developer hours", 120, 300, 18)]),
    _spec("V-1009", file="10_arithmetic_mismatch.pdf", scenario="Arithmetic mismatch (total printed wrong)", expected="NEEDS_REVIEW", number="IE/26-27/0455", date="2026-10-20", due="2026-11-19", po="PO-2026-0009", currency="INR", layout="compact", items=[("Copper cable 2.5mm (100m)", 20, 2400, 18)], total_override="58400.00"),
    _spec("V-1011", file="11_currency_mismatch.pdf", scenario="Currency mismatch (INR invoice on USD PO)", expected="NEEDS_REVIEW", number="KCT-0107", date="2026-10-21", due="2026-11-20", po="PO-2026-0011", currency="INR", layout="classic", items=[("Managed database (monthly)", 1, 54000, 18)]),
    _spec("V-1009", file="12_scanned_ocr.pdf", scenario="Scanned PDF requiring OCR", expected="APPROVED", number="IE/26-27/0470", date="2026-10-22", due="2026-11-21", po="PO-2026-0009", currency="INR", layout="classic", kind="scanned", items=[("LED panel light 40W", 60, 850, 18)]),
    Spec(file="13_corrupted.pdf", scenario="Corrupted PDF (technical failure, not a rejection)", expected="PROCESSING_FAILED", kind="corrupted", vendor_name="", vendor_address="", gstin=None, number=None, date="", due="", po=None, currency="INR", items=[]),
    _spec("V-1005", file="14_potential_duplicate.pdf", scenario="Potential duplicate (similar number, same amount)", expected="NEEDS_REVIEW", number="EFS/2026/0118-A", date="2026-10-23", due="2026-11-22", po="PO-2026-0005", currency="INR", layout="modern", items=[("Monthly housekeeping service", 1, 50000, 18)]),
    _spec("V-1012", file="15_missing_gstin.pdf", scenario="Vendor GSTIN missing on invoice", expected="NEEDS_REVIEW", gstin=None, number="LFC-3391", date="2026-10-24", due="2026-11-23", po="PO-2026-0012", currency="INR", layout="compact", items=[("Coffee table", 5, 3200, 18), ("Reception desk", 1, 18000, 18)]),
    _spec("V-1011", file="16_valid_usd_invoice.pdf", scenario="Valid foreign-currency invoice (USD)", expected="APPROVED", number="KCT-USD-0112", date="2026-10-25", due="2026-11-24", po="PO-2026-0011", currency="USD", layout="modern", items=[("Compute credits", 30, 80, 0), ("Managed database (monthly)", 1, 650, 0)]),
    _spec("V-1008", file="17_pending_vendor.pdf", scenario="Vendor pending onboarding", expected="NEEDS_REVIEW", number="HCS-0045", date="2026-10-26", due="2026-11-25", po="PO-2026-0008", currency="INR", layout="classic", items=[("Catering per head", 120, 200, 5)]),
]  # fmt: skip

