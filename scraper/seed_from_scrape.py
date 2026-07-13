"""
seed_from_scrape.py
──────────────────────────────────────────────────────────────────
Reads the JSON output of proestimator_scraper.py and inserts all
scraped data into the AutoEst Pro PostgreSQL database.

Usage:
  export DATABASE_URL="postgresql://autoest:autoest_secret@localhost:5432/autoest"
  python seed_from_scrape.py scraped_data/proestimator_full_20240101_120000.json

Options:
  --dry-run     Print SQL without executing
  --clear       DELETE existing data before seeding (keeps schema)
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

log = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", str(val)))
    except (ValueError, TypeError):
        return None


def to_int(val: Any) -> Optional[int]:
    f = to_float(val)
    return int(f) if f is not None else None


def clean(val: Any) -> str:
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def run(json_path: str, dry_run: bool = False, clear: bool = False):
    import os
    import psycopg2
    from psycopg2.extras import execute_values

    db_url = os.getenv("DATABASE_URL", "postgresql://autoest:autoest_secret@localhost:5432/autoest")

    data = json.loads(Path(json_path).read_text())
    estimates = data.get("estimates", [])
    log.info(f"Loaded {len(estimates)} estimates from {json_path}")

    if dry_run:
        log.info("DRY RUN — no changes will be made")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    if clear and not dry_run:
        log.warning("Clearing existing data...")
        for tbl in ["estimate_lines", "estimate_photos", "estimates", "vehicles", "customers"]:
            cur.execute(f"DELETE FROM {tbl} WHERE shop_id = 1 OR TRUE")
        conn.commit()
        log.info("Existing data cleared")

    stats = {"customers": 0, "vehicles": 0, "estimates": 0, "line_items": 0, "photos": 0}

    for est in estimates:
        try:
            c = est.get("customer", {})
            v = est.get("vehicle", {})
            ins = est.get("insurance", {})
            totals = est.get("totals", {})
            lines = est.get("line_items", [])
            photos = est.get("photos", [])
            fields = est.get("all_fields", {})

            # ── Customer ──────────────────────────────────────
            first_name = clean(c.get("first_name") or fields.get("CustomerFirstName", "Unknown"))
            last_name  = clean(c.get("last_name")  or fields.get("CustomerLastName",  ""))
            email      = clean(c.get("email")  or fields.get("CustomerEmail", ""))
            phone      = clean(c.get("phone")  or fields.get("CustomerPhone", ""))
            address    = clean(c.get("address") or fields.get("CustomerAddress", ""))
            city       = clean(c.get("city")   or fields.get("CustomerCity", ""))
            state      = clean(c.get("state")  or fields.get("CustomerState", ""))
            zip_code   = clean(c.get("zip")    or fields.get("CustomerZip", ""))

            if not dry_run:
                cur.execute("""
                    INSERT INTO customers
                        (shop_id, first_name, last_name, email, phone1, address1, city, state, zip)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (1, first_name, last_name, email, phone, address, city, state, zip_code))
                customer_id = cur.fetchone()[0]
            else:
                customer_id = 0
                log.info(f"[DRY] Would insert customer: {first_name} {last_name}")
            stats["customers"] += 1

            # ── Vehicle ───────────────────────────────────────
            vin   = clean(v.get("vin")   or fields.get("VIN", ""))
            year  = to_int(v.get("year") or fields.get("Year"))
            make  = clean(v.get("make")  or fields.get("Make", ""))
            model = clean(v.get("model") or fields.get("Model", ""))
            trim  = clean(v.get("trim")  or fields.get("Style", ""))
            color = clean(v.get("color") or fields.get("Color", ""))
            color_code  = clean(v.get("color_code") or fields.get("ColorCode", ""))
            license_plate = clean(v.get("license") or fields.get("LicensePlate", ""))
            license_state = clean(v.get("license_state") or fields.get("LicenseState", ""))
            mileage = to_int(v.get("mileage") or fields.get("Mileage"))

            if not dry_run:
                if vin:
                    cur.execute("SELECT id FROM vehicles WHERE vin = %s", (vin,))
                    row = cur.fetchone()
                    if row:
                        vehicle_id = row[0]
                    else:
                        cur.execute("""
                            INSERT INTO vehicles
                                (vin, year, make, model, trim, primary_color_name,
                                 primary_color_code, license_plate, license_state)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (vin or None, year, make, model, trim, color,
                              color_code, license_plate, license_state))
                        vehicle_id = cur.fetchone()[0]
                else:
                    cur.execute("""
                        INSERT INTO vehicles (year, make, model, trim, primary_color_name,
                            primary_color_code, license_plate, license_state)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (year, make, model, trim, color, color_code, license_plate, license_state))
                    vehicle_id = cur.fetchone()[0]
            else:
                vehicle_id = 0
                log.info(f"[DRY] Would insert vehicle: {year} {make} {model} VIN={vin}")
            stats["vehicles"] += 1

            # ── Estimate ──────────────────────────────────────
            est_id_ext = clean(est.get("estimate_id", ""))
            claim_num  = clean(ins.get("claim_number") or fields.get("ClaimNumber", ""))
            policy_num = clean(ins.get("policy_number") or fields.get("PolicyNumber", ""))
            ins_company = clean(ins.get("company") or fields.get("InsuranceCompany", ""))
            adjuster   = clean(ins.get("adjuster") or fields.get("Adjuster", ""))
            adj_phone  = clean(ins.get("adjuster_phone") or fields.get("AdjusterPhone", ""))
            deductible = to_float(ins.get("deductible") or fields.get("Deductible") or totals.get("deductible"))
            date_of_loss_raw = clean(ins.get("date_of_loss") or fields.get("DateOfLoss", ""))
            date_of_loss = None
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                try:
                    date_of_loss = datetime.strptime(date_of_loss_raw, fmt).date()
                    break
                except Exception:
                    pass

            parts_total  = to_float(totals.get("parts_total"))
            labor_total  = to_float(totals.get("labor_total"))
            paint_total  = to_float(totals.get("paint_total"))
            tax_amount   = to_float(totals.get("tax"))
            grand_total  = to_float(totals.get("grand_total"))
            net_due      = to_float(totals.get("net_due"))
            notes        = clean(est.get("notes", ""))

            if not dry_run:
                cur.execute("""
                    INSERT INTO estimates
                        (shop_id, customer_id, vehicle_id,
                         status, repair_notes,
                         deductible, tax_amount, grand_total, net_total_due)
                    VALUES
                        (%s, %s, %s,
                         %s, %s,
                         %s, %s, %s, %s)
                    RETURNING id
                """, (
                    1, customer_id, vehicle_id,
                    "imported", notes,
                    deductible or 0, tax_amount or 0,
                    grand_total or 0, net_due or 0,
                ))
                estimate_db_id = cur.fetchone()[0]

                # Insert insurance record separately
                if any([ins_company, claim_num, policy_num, adjuster]):
                    cur.execute("""
                        INSERT INTO insurance
                            (estimate_id, policy_number, claim_number,
                             company_name_override, deductible, date_of_loss,
                             adjuster_first_name, adjuster_phone)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (estimate_db_id, policy_num or None, claim_num or None,
                          ins_company or None, deductible or 0, date_of_loss,
                          adjuster or None, adj_phone or None))
            else:
                estimate_db_id = 0
                log.info(f"[DRY] Would insert estimate: ext_id={est_id_ext} claim={claim_num} total={grand_total}")
            stats["estimates"] += 1

            # ── Line items ────────────────────────────────────
            line_rows = []
            for line in lines:
                # Normalize column names (ProEstimator headers vary)
                desc = clean(
                    line.get("Description") or line.get("description") or
                    line.get("Part Description") or line.get("Item") or
                    line.get("raw_text", "")
                )
                qty = to_float(line.get("Qty") or line.get("qty") or line.get("Quantity") or "1") or 1.0
                unit_price = to_float(
                    line.get("Price") or line.get("MSRP") or line.get("Unit Price") or
                    line.get("price") or "0"
                )
                hours = to_float(line.get("Hours") or line.get("Labor") or line.get("hours") or "0")
                line_type = classify_line_type(line)
                part_num = clean(line.get("Part #") or line.get("Part Number") or line.get("PartNumber") or "")

                if not dry_run and estimate_db_id:
                    line_rows.append((
                        estimate_db_id,
                        len(line_rows) + 1,          # line_number
                        "IMPORTED",                  # section
                        line_type,                   # operation (reusing type as op)
                        desc or "Imported item",
                        part_num or None,
                        unit_price or 0,
                        int(qty),
                        hours or 0,
                        float(qty) * (unit_price or 0),
                    ))

            if line_rows and not dry_run:
                execute_values(cur, """
                    INSERT INTO estimate_lines
                        (estimate_id, line_number, section, operation,
                         description, part_number,
                         part_price, qty, body_labor_hrs, line_total)
                    VALUES %s
                """, line_rows)
            stats["line_items"] += len(line_rows)

            # ── Photos ────────────────────────────────────────
            if not dry_run and estimate_db_id:
                for photo in photos:
                    local = photo.get("local")
                    src   = photo.get("src", "")
                    file_path = local or src
                    if file_path:
                        cur.execute("""
                            INSERT INTO estimate_images (estimate_id, file_path, file_name)
                            VALUES (%s, %s, %s)
                        """, (estimate_db_id, file_path, Path(str(file_path)).name))
                        stats["photos"] += 1

            if not dry_run:
                conn.commit()

        except Exception as e:
            log.error(f"Error seeding estimate {est.get('estimate_id')}: {e}")
            if not dry_run:
                conn.rollback()

    cur.close()
    conn.close()

    log.info("=" * 50)
    log.info("Seed complete!")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    log.info("=" * 50)


def classify_line_type(line: dict) -> str:
    """Guess line item type from headers/classes."""
    raw = " ".join(str(v) for v in line.values()).lower()
    cls = (line.get("_row_class") or "").lower()
    combined = raw + " " + cls
    if any(kw in combined for kw in ["paint", "rfsh", "refinish", "color sand"]):
        return "PAINT"
    if any(kw in combined for kw in ["sublet", "sub-let", "tow", "align"]):
        return "SUBLET"
    if any(kw in combined for kw in ["labor", "r&r", "r&i", "repair", "hours"]):
        return "LABOR"
    if any(kw in combined for kw in ["not incl", " n/i", "ni "]):
        return "NI"
    if any(kw in combined for kw in ["part", "oem", "aft", "lkq", "recon", "part #"]):
        return "PART"
    return "OTHER"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AutoEst DB from ProEstimator scrape JSON")
    parser.add_argument("json_file", help="Path to proestimator_full_*.json")
    parser.add_argument("--dry-run", action="store_true", help="Print without inserting")
    parser.add_argument("--clear",   action="store_true", help="Clear existing data first")
    args = parser.parse_args()

    run(args.json_file, dry_run=args.dry_run, clear=args.clear)
