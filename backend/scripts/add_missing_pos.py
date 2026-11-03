from app.database.session import get_session_factory
from app.models.vendor_po import Vendor, PurchaseOrder, PurchaseOrderItem
from datetime import date
from decimal import Decimal

db = get_session_factory()()

po_defs = [
    ("PO-2026-0031", "V-1016", "INR", date(2026, 1, 10), "Industrial Dynamics Actuators", Decimal("50"), Decimal("3700.00"), Decimal("185000.00")),
    ("PO-2026-0032", "V-1017", "INR", date(2026, 1, 15), "Enterprise Software Development Sprint", Decimal("4"), Decimal("80000.00"), Decimal("320000.00")),
    ("PO-2026-0033", "V-1018", "INR", date(2026, 1, 20), "Water Treatment Filtration Packs", Decimal("20"), Decimal("4750.00"), Decimal("95000.00")),
    ("PO-2026-0034", "V-1019", "INR", date(2026, 2, 1), "Embedded Controller Modules", Decimal("60"), Decimal("9000.00"), Decimal("540000.00")),
    ("PO-2026-0035", "V-1020", "INR", date(2026, 2, 10), "High-Purity Argon Cylinder Rack", Decimal("10"), Decimal("14200.00"), Decimal("142000.00")),
    ("PO-2026-0036", "V-1021", "INR", date(2026, 2, 18), "Inter-State Multi-Axle Transport", Decimal("5"), Decimal("43000.00"), Decimal("215000.00")),
    ("PO-2026-0037", "V-1022", "INR", date(2026, 3, 1), "Annual Manned Security Services", Decimal("1"), Decimal("375000.00"), Decimal("375000.00")),
    ("PO-2026-0038", "V-1023", "INR", date(2026, 3, 12), "Industrial Switchgear Spares", Decimal("40"), Decimal("3200.00"), Decimal("128000.00")),
    ("PO-2026-0039", "V-1024", "INR", date(2026, 3, 20), "Modular Workstation Partitions", Decimal("15"), Decimal("11000.00"), Decimal("165000.00")),
    ("PO-2026-0040", "V-1025", "INR", date(2026, 4, 5), "Express Document & Parcel Courier Retainer", Decimal("1"), Decimal("88000.00"), Decimal("88000.00")),
    ("PO-2026-0041", "V-1026", "USD", date(2026, 4, 15), "Krypton Enterprise Analytics API Access", Decimal("1"), Decimal("25000.00"), Decimal("25000.00")),
]

for po_num, v_code, cur, dt, desc, qty, price, total in po_defs:
    existing = db.query(PurchaseOrder).filter_by(po_number=po_num).first()
    if not existing:
        vendor = db.query(Vendor).filter_by(vendor_code=v_code).first()
        po = PurchaseOrder(
            vendor_id=vendor.id,
            po_number=po_num,
            po_date=dt,
            total_amount=total,
            currency=cur,
            status="ACTIVE",
            is_demo=True
        )
        db.add(po)
        db.flush()
        poi = PurchaseOrderItem(
            purchase_order_id=po.id,
            description=desc,
            quantity=qty,
            unit_price=price,
            total_amount=total
        )
        db.add(poi)

db.commit()
print("Total POs in DB:", db.query(PurchaseOrder).count())
db.close()
