"""Idempotent seed script to expand PayFlow AI with realistic AP historical data.

Expands database to:
- 25 Vendors
- 40 Purchase Orders
- 75 Historical Seed Invoices (marked source_origin='SEED_HISTORY')
- ~250 seeded Invoice Line Items

Preserves existing 15 live-upload invoices completely untouched.
Zero Gemini API calls made.
"""

import sys
import os
import json
import uuid
import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pymupdf

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.models.vendor_po import Vendor, PurchaseOrder, PurchaseOrderItem, POAllocation, POLineAllocation
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.processing import ProcessingRun, Decision, ValidationResult
from app.models.enums import VendorStatus, POStatus, ProcessingStatus, DecisionStatus, AllocationStatus, LineMatchStatus, RunStatus
from app.services.document_layout import extract_pdf_layout
from app.services.evidence_service import build_invoice_visual_evidence
from app.utils.normalize import normalize_vendor_name

def generate_pdf_bytes(invoice_num, vendor_name, po_num, currency, total_amount, subtotal, tax_amount, line_items, invoice_date):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    page.insert_text((50, 60), f"TAX INVOICE: {invoice_num}", fontsize=14)
    page.insert_text((50, 90), f"Vendor: {vendor_name}", fontsize=11)
    page.insert_text((50, 110), f"Invoice Date: {invoice_date}", fontsize=10)
    page.insert_text((50, 130), f"PO Number: {po_num}", fontsize=10)
    page.insert_text((50, 150), f"Currency: {currency}", fontsize=10)

    y = 190
    page.insert_text((50, y), "Description", fontsize=10)
    page.insert_text((300, y), "Qty", fontsize=10)
    page.insert_text((380, y), "Unit Price", fontsize=10)
    page.insert_text((480, y), "Amount", fontsize=10)
    y += 15
    page.draw_line((50, y), (540, y))
    y += 15

    for item in line_items:
        page.insert_text((50, y), str(item["description"])[:35], fontsize=9)
        page.insert_text((300, y), str(item["quantity"]), fontsize=9)
        page.insert_text((380, y), str(item["unit_price"]), fontsize=9)
        page.insert_text((480, y), str(item["total_amount"]), fontsize=9)
        y += 20

    y += 15
    page.draw_line((350, y), (540, y))
    y += 18
    page.insert_text((350, y), f"Subtotal: {subtotal}", fontsize=10)
    y += 16
    page.insert_text((350, y), f"Tax: {tax_amount}", fontsize=10)
    y += 18
    page.insert_text((350, y), f"Total: {currency} {total_amount}", fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def seed_expansion(dry_run=False):
    settings = get_settings()
    db = get_session_factory()()
    uploads_dir = "/app/storage/uploads"
    os.makedirs(uploads_dir, exist_ok=True)

    print(f"--- EXPANSION SEEDING RUN (dry_run={dry_run}) ---")

    # 1. Expand Vendors to 25
    curr_v_count = db.query(Vendor).count()
    print(f"Current vendors in DB: {curr_v_count}")
    new_vendors_data = [
        {"vendor_code": "V-1013", "vendor_name": "Apex Cloud Systems Ltd", "gstin": "27AABCA1013A1Z8", "address": "Plot 42, Hiranandani Tech Park, Powai, Mumbai 400076", "email": "billing@apexcloud.io", "phone": "+91-22-68991013", "status": "ACTIVE"},
        {"vendor_code": "V-1014", "vendor_name": "Nexus Logistics & Supply Chain", "gstin": "29AABCN1014N1Z6", "address": "Hub 12, Outer Ring Road, Bellandur, Bengaluru 560103", "email": "accounts@nexuslogistics.in", "phone": "+91-80-49221014", "status": "ACTIVE"},
        {"vendor_code": "V-1015", "vendor_name": "Sterling Facilities & Security", "gstin": "06AABCS1015S1Z4", "address": "Tower B, Cyber City, DLF Phase 2, Gurugram 122002", "email": "invoicing@sterlingfs.com", "phone": "+91-124-4111015", "status": "ACTIVE"},
    ]
    vendors_added = 0
    for vdata in new_vendors_data:
        existing = db.query(Vendor).filter_by(vendor_code=vdata["vendor_code"]).first()
        if not existing:
            v = Vendor(
                vendor_code=vdata["vendor_code"],
                vendor_name=vdata["vendor_name"],
                normalized_name=normalize_vendor_name(vdata["vendor_name"]),
                gstin=vdata["gstin"],
                address=vdata["address"],
                email=vdata["email"],
                phone=vdata["phone"],
                status=vdata["status"],
                is_demo=True,
            )
            db.add(v)
            vendors_added += 1
    db.commit()
    print(f"Vendors added: {vendors_added}. Total vendors now: {db.query(Vendor).count()}")

    # 2. Expand Purchase Orders to 40
    curr_po_count = db.query(PurchaseOrder).count()
    print(f"Current POs in DB: {curr_po_count}")
    # We need 14 new POs (PO-2026-0017 to PO-2026-0030)
    all_vendors = {v.vendor_code: v for v in db.query(Vendor).all()}

    new_pos_specs = [
        # (po_number, vendor_code, currency, po_date, desc, [items: (desc, qty, price)])
        ("PO-2026-0017", "V-1001", "INR", date(2025, 2, 10), "Industrial Safety Gear & Tooling", [
            ("Safety Helmet Pro", 200, 450.00), ("Heavy Duty Gloves (Pairs)", 500, 180.00), ("Steel Toe Safety Boots", 100, 1500.00)
        ]),
        ("PO-2026-0018", "V-1002", "INR", date(2025, 3, 15), "Office Workspace Ergonomic Furniture", [
            ("Ergonomic Mesh Chair V2", 40, 7500.00), ("Height Adjustable Desk", 20, 18500.00), ("Monitor Arm Dual", 30, 2800.00)
        ]),
        ("PO-2026-0019", "V-1003", "INR", date(2025, 4, 5), "Quarterly Cold Chain Freight Services", [
            ("Intercity Refrigerated Transit", 15, 24000.00), ("Warehouse Temp Monitoring Node", 10, 6500.00)
        ]),
        ("PO-2026-0020", "V-1004", "INR", date(2025, 5, 20), "Corporate Branding & Packaging Collateral", [
            ("Corrugated Shipping Cartons (Box of 100)", 80, 2200.00), ("Custom Printed Packaging Tape", 150, 420.00)
        ]),
        ("PO-2026-0021", "V-1005", "INR", date(2025, 6, 12), "HVAC Deep Sanitation & Duct Cleaning", [
            ("Air Duct Disinfection Unit", 12, 14500.00), ("HEPA Filter Replacement Set", 30, 3200.00)
        ]),
        ("PO-2026-0022", "V-1006", "INR", date(2025, 7, 1), "Enterprise Network Core Switch Upgrades", [
            ("48-Port PoE+ Managed Switch", 6, 92000.00), ("10G SFP+ Optical Transceiver", 24, 4500.00)
        ]),
        ("PO-2026-0023", "V-1007", "INR", date(2025, 8, 14), "Bulk Executive Stationery & Supplies", [
            ("Premium A4 Copy Paper (Carton)", 120, 1400.00), ("Executive Planner & Pen Set", 200, 350.00)
        ]),
        ("PO-2026-0024", "V-1009", "INR", date(2025, 9, 22), "Data Center Electrical Backup Circuitry", [
            ("Industrial Circuit Breaker 63A", 25, 5800.00), ("Copper Busbar Distribution Strip", 10, 12000.00)
        ]),
        ("PO-2026-0025", "V-1010", "INR", date(2025, 10, 10), "Annual Microservices Architecture Retainer", [
            ("Senior DevOps Engineering Hours", 180, 3500.00), ("Cloud Security Audit Module", 2, 85000.00)
        ]),
        ("PO-2026-0026", "V-1011", "USD", date(2025, 11, 5), "High Availability Cloud Kubernetes Nodes", [
            ("c6i.4xlarge Dedicated Compute Node", 12, 680.00), ("Provisioned IOPS Storage TB", 15, 210.00)
        ]),
        ("PO-2026-0027", "V-1012", "INR", date(2025, 12, 1), "Acoustic Wall Panels & Floor Rugs", [
            ("Sound Dampening Fabric Panel", 80, 2400.00), ("Heavy Duty Commercial Carpet Tile", 250, 650.00)
        ]),
        ("PO-2026-0028", "V-1013", "EUR", date(2026, 1, 15), "Global Identity & SSO Gateway License", [
            ("Enterprise SSO Per-Seat Subscription", 150, 18.00), ("Dedicated RADIUS Authentication Pod", 2, 1400.00)
        ]),
        ("PO-2026-0029", "V-1014", "AED", date(2026, 2, 20), "Middle East Logistics Freight Forwarding", [
            ("Air Cargo Dubai - Mumbai Pallet", 8, 3850.00), ("Customs Clearance & Handling Fee", 4, 1200.00)
        ]),
        ("PO-2026-0030", "V-1015", "GBP", date(2026, 3, 10), "Comprehensive Security & Facility Audits", [
            ("Facility Penetration Testing Pack", 1, 6500.00), ("Quarterly Compliance Report Fee", 4, 850.00)
        ]),
    ]

    pos_added = 0
    po_items_added = 0
    for pospec in new_pos_specs:
        ponum, vcode, cur, pdate, desc, items = pospec
        existing = db.query(PurchaseOrder).filter_by(po_number=ponum).first()
        if not existing:
            v = all_vendors[vcode]
            total_po_amt = sum(Decimal(str(qty)) * Decimal(str(price)) for _, qty, price in items)
            po = PurchaseOrder(
                po_number=ponum,
                vendor_id=v.id,
                po_date=pdate,
                currency=cur,
                total_amount=total_po_amt,
                status="ACTIVE",
                description=desc,
                is_demo=True,
            )
            for idesc, iqty, iprice in items:
                qty_dec = Decimal(str(iqty))
                price_dec = Decimal(str(iprice))
                pitem = PurchaseOrderItem(
                    description=idesc,
                    quantity=qty_dec,
                    unit_price=price_dec,
                    total_amount=qty_dec * price_dec,
                )
                po.items.append(pitem)
                po_items_added += 1
            db.add(po)
            pos_added += 1
    db.commit()
    print(f"POs added: {pos_added}, PO Line Items added: {po_items_added}. Total POs now: {db.query(PurchaseOrder).count()}")

    # 3. Seed 75 Historical Invoices (55 APPROVED, 12 NEEDS_REVIEW, 8 REJECTED)
    curr_seed_inv_count = db.query(Invoice).filter_by(source_origin="SEED_HISTORY").count()
    print(f"Current historical seed invoices in DB: {curr_seed_inv_count}")

    # Reload POs with items
    po_map = {po.po_number: po for po in db.query(PurchaseOrder).all()}

    # We will generate 75 deterministic historical records across PO-2026-0017 to PO-2026-0030 (and selected older POs with excess room)
    # Target distribution: 55 APPROVED, 12 NEEDS_REVIEW, 8 REJECTED
    # Generate specifications for 75 records
    invoices_to_create = []

    # Let's define the 75 historical records deterministically
    outcomes = ["APPROVED"] * 55 + ["NEEDS_REVIEW"] * 12 + ["REJECTED"] * 8
    # We can distribute them systematically across dates from Jan 2025 to Oct 2026
    start_date = date(2025, 1, 15)

    # Active expansion POs to spread invoices over
    target_pos = [
        "PO-2026-0017", "PO-2026-0018", "PO-2026-0019", "PO-2026-0020", "PO-2026-0021",
        "PO-2026-0022", "PO-2026-0023", "PO-2026-0024", "PO-2026-0025", "PO-2026-0026",
        "PO-2026-0027", "PO-2026-0028", "PO-2026-0029", "PO-2026-0030"
    ]

    seed_inv_index = 1
    for outcome_idx, outcome in enumerate(outcomes):
        po_num = target_pos[outcome_idx % len(target_pos)]
        po = po_map[po_num]
        vendor = po.vendor
        cur = po.currency

        # Vendor prefix for invoice numbering
        prefix = vendor.vendor_name[:3].upper().replace(" ", "")
        inv_date = start_date + timedelta(days=(outcome_idx * 8) % 620)
        due_date = inv_date + timedelta(days=30)
        inv_number = f"HIST-{prefix}-{inv_date.year % 100:02d}{inv_date.month:02d}-{outcome_idx+1:03d}"

        # Determine line items from PO items
        # Pick 2-3 items
        items = []
        if len(po.items) >= 2:
            base_items = po.items[:2]
        else:
            base_items = po.items

        inv_subtotal = Decimal("0.00")
        for pitem in base_items:
            # allocate a portion of quantity
            qty = Decimal("1.0000") if outcome != "REJECTED" else Decimal("2.0000")
            # If approved, keep small so multiple invoices fit into PO
            price = pitem.unit_price
            line_tot = qty * price
            inv_subtotal += line_tot
            items.append({
                "po_item": pitem,
                "description": pitem.description,
                "quantity": qty,
                "unit_price": price,
                "total_amount": line_tot
            })

        tax_rate = Decimal("0.18") if cur == "INR" else Decimal("0.05")
        tax_amount = round(inv_subtotal * tax_rate, 2)
        total_amount = inv_subtotal + tax_amount

        invoices_to_create.append({
            "index": seed_inv_index,
            "invoice_number": inv_number,
            "vendor": vendor,
            "po": po,
            "currency": cur,
            "invoice_date": inv_date,
            "due_date": due_date,
            "subtotal": inv_subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "line_items": items,
            "outcome": outcome,
        })
        seed_inv_index += 1

    invoices_seeded = 0
    invoice_lines_seeded = 0
    allocations_seeded = 0
    line_allocations_seeded = 0

    scenario_manifest = []

    for item in invoices_to_create:
        inv_num = item["invoice_number"]
        existing = db.query(Invoice).filter_by(invoice_number=inv_num).first()
        if existing:
            continue

        vendor = item["vendor"]
        po = item["po"]
        cur = item["currency"]
        outcome = item["outcome"]
        subtotal = item["subtotal"]
        tax_amount = item["tax_amount"]
        total_amount = item["total_amount"]
        inv_date = item["invoice_date"]
        due_date = item["due_date"]
        lines = item["line_items"]

        # Generate local deterministic PDF
        raw_items_for_pdf = [
            {"description": l["description"], "quantity": str(l["quantity"]), "unit_price": f"{l['unit_price']:.2f}", "total_amount": f"{l['total_amount']:.2f}"}
            for l in lines
        ]
        pdf_bytes = generate_pdf_bytes(
            inv_num, vendor.vendor_name, po.po_number, cur,
            f"{total_amount:.2f}", f"{subtotal:.2f}", f"{tax_amount:.2f}",
            raw_items_for_pdf, str(inv_date)
        )
        file_hash = hashlib.sha256(pdf_bytes).hexdigest()
        stored_fname = f"{uuid.uuid4().hex}.pdf"
        stored_fpath = os.path.join(uploads_dir, stored_fname)
        with open(stored_fpath, "wb") as f:
            f.write(pdf_bytes)

        # Build visual evidence
        layout = extract_pdf_layout(pdf_bytes)
        extracted_dict = {
            "invoice_number": inv_num,
            "vendor_name": vendor.vendor_name,
            "vendor_gstin": vendor.gstin,
            "purchase_order_number": po.po_number,
            "currency": cur,
            "invoice_date": str(inv_date),
            "due_date": str(due_date),
            "subtotal": f"{subtotal:.2f}",
            "tax_amount": f"{tax_amount:.2f}",
            "total_amount": f"{total_amount:.2f}",
            "line_items": raw_items_for_pdf
        }
        visual_ev = build_invoice_visual_evidence(extracted_dict, layout)

        inv = Invoice(
            invoice_number=inv_num,
            vendor_id=vendor.id,
            purchase_order_id=po.id,
            invoice_date=inv_date,
            due_date=due_date,
            currency=cur,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            vendor_name_raw=vendor.vendor_name,
            vendor_gstin_raw=vendor.gstin,
            po_number_raw=po.po_number,
            original_file_name=f"{inv_num.lower()}.pdf",
            stored_file_path=stored_fname,
            file_size_bytes=len(pdf_bytes),
            file_hash=file_hash,
            extraction_method="TEXT",
            page_count=1,
            processing_status=ProcessingStatus.COMPLETED.value,
            decision_status=outcome,
            uploaded_by="seed_historical_harness",
            source_origin="SEED_HISTORY",
            uploaded_at=datetime.combine(inv_date, datetime.min.time(), tzinfo=timezone.utc),
            extracted_data=extracted_dict,
            visual_evidence=visual_ev,
        )

        db.add(inv)
        db.flush() # populate inv.id

        # Companion ProcessingRun to satisfy foreign key constraints for Decision and ValidationResult
        run = ProcessingRun(
            invoice_id=inv.id,
            run_number=1,
            status=RunStatus.COMPLETED.value,
            current_stage="DECISION",
            started_at=inv.uploaded_at,
            completed_at=inv.uploaded_at,
            triggered_by="seed_historical_harness",
        )
        db.add(run)
        db.flush() # populate run.id

        # Add invoice line items & reconciliation
        created_lines = []
        for pos_idx, l in enumerate(lines):
            inv_line = InvoiceLineItem(
                invoice_id=inv.id,
                position=pos_idx,
                description=l["description"],
                quantity=l["quantity"],
                unit_price=l["unit_price"],
                tax_percentage=Decimal("18.00") if cur == "INR" else Decimal("5.00"),
                total_amount=l["total_amount"],
            )
            db.add(inv_line)
            db.flush()
            invoice_lines_seeded += 1
            created_lines.append((inv_line, l))

            if outcome == "APPROVED":
                recon = LineItemReconciliation(
                    invoice_id=inv.id,
                    invoice_line_item_id=inv_line.id,
                    purchase_order_item_id=l["po_item"].id,
                    status=LineMatchStatus.MATCHED.value,
                    matching_method="EXACT_PO_LINE",
                    matched_description=l["po_item"].description,
                    invoice_quantity=l["quantity"],
                    ordered_quantity=l["po_item"].quantity,
                    allocated_quantity=l["quantity"],
                    remaining_quantity=max(Decimal("0.00"), l["po_item"].quantity - l["quantity"]),
                    unit_of_measure="EA",
                    invoice_unit_price=l["unit_price"],
                    po_unit_price=l["po_item"].unit_price,
                    price_variance=Decimal("0.00"),
                    expected_line_amount=l["total_amount"],
                    actual_line_amount=l["total_amount"],
                    explanation="Exact line item match against historical purchase order."
                )
                db.add(recon)

        # If APPROVED, allocate PO amount and line quantity
        if outcome == "APPROVED":
            po_alloc = POAllocation(
                purchase_order_id=po.id,
                invoice_id=inv.id,
                amount=total_amount,
                status=AllocationStatus.ACTIVE.value,
                allocated_by="historical_seed",
            )
            db.add(po_alloc)
            allocations_seeded += 1

            for inv_line, l in created_lines:
                pol_alloc = POLineAllocation(
                    purchase_order_id=po.id,
                    purchase_order_item_id=l["po_item"].id,
                    invoice_id=inv.id,
                    invoice_line_item_id=inv_line.id,
                    quantity=l["quantity"],
                    amount=l["total_amount"],
                    status=AllocationStatus.ACTIVE.value,
                    allocated_by="historical_seed",
                )
                db.add(pol_alloc)
                line_allocations_seeded += 1

        # Add Decision record
        decision_reasons = []
        if outcome == "APPROVED":
            decision_reasons.append({"code": "RULE_PO_BALANCE", "severity": "INFO", "message": "All business and PO validation rules satisfied."})
        elif outcome == "NEEDS_REVIEW":
            decision_reasons.append({"code": "RULE_PRICE_VARIANCE", "severity": "WARNING", "message": "Line item unit price variance requires manual reviewer approval."})
        elif outcome == "REJECTED":
            decision_reasons.append({"code": "RULE_VENDOR_UNREGISTERED", "severity": "BLOCKING", "message": "Invoice failed vendor verification register match."})

        dec = Decision(
            invoice_id=inv.id,
            processing_run_id=run.id,
            status=outcome,
            reasons=decision_reasons,
        )
        db.add(dec)

        # Add ValidationResult
        val = ValidationResult(
            invoice_id=inv.id,
            processing_run_id=run.id,
            validation_type="PO_BALANCE",
            status="PASSED" if outcome == "APPROVED" else ("WARNING" if outcome == "NEEDS_REVIEW" else "FAILED"),
            impact="NONE" if outcome == "APPROVED" else ("REVIEW" if outcome == "NEEDS_REVIEW" else "REJECT"),
            expected_value=str(po.total_amount),
            actual_value=str(total_amount),
            message="Historical check record"
        )
        db.add(val)

        invoices_seeded += 1

        # Add scenario to scenario manifest
        scenario_name = f"Scenario {outcome.capitalize()}: {vendor.vendor_name[:15]} on {po.po_number}"
        scenario_manifest.append({
            "scenario": scenario_name,
            "vendor_name": vendor.vendor_name,
            "vendor_code": vendor.vendor_code,
            "invoice_number": inv_num,
            "po_number": po.po_number,
            "currency": cur,
            "total_amount": f"{total_amount:.2f}",
            "decision": outcome,
            "reason": decision_reasons[0]["message"]
        })

    db.commit()

    print(f"Historical Invoices seeded: {invoices_seeded}")
    print(f"Invoice Lines seeded: {invoice_lines_seeded}")
    print(f"PO Allocations seeded: {allocations_seeded}")
    print(f"PO Line Allocations seeded: {line_allocations_seeded}")
    print(f"Total Invoices now in DB: {db.query(Invoice).count()}")
    print(f"Total Seed History Invoices: {db.query(Invoice).filter_by(source_origin='SEED_HISTORY').count()}")
    print(f"Total Live Upload Invoices: {db.query(Invoice).filter_by(source_origin='LIVE_UPLOAD').count()}")

    # Save scenario manifest
    with open("/app/storage/historical_scenarios_manifest.json", "w") as f:
        json.dump(scenario_manifest, f, indent=2)
    print("Saved scenario manifest with", len(scenario_manifest), "test scenarios.")

    db.close()

if __name__ == "__main__":
    seed_expansion()
