"""
estimate_calc.py
─────────────────────────────────────────────────────────────────
Replicates the Web-Est / Mitchell math engine.

Totals breakdown (matches the PDF exactly):
  Body Labor       = sum(body_labor_hrs) × body_rate
  Paint Labor      = sum(paint_labor_hrs + refinish_hrs) × paint_rate
  Paint Supplies   = sum(paint_labor_hrs + refinish_hrs) × paint_supply_rate
  Nontaxed misc    = sum(non-taxable fixed charges)
  Taxed misc       = sum(taxable fixed charges with no part number)
  OEM Parts        = sum(part_price where source=OEM)
  Other Parts      = sum(part_price where source in After/LKQ/Reman)
  Taxable Amount   = Paint Supplies + Taxed misc + OEM Parts + Other Parts
  Tax              = Taxable Amount × tax_rate_pct / 100
  Non-taxable Amt  = Body Labor + Paint Labor + Nontaxed misc
  Grand Total      = Taxable Amount + Tax + Non-taxable Amount
  Net Total Due    = Grand Total − Deductible
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any


CENTS = Decimal("0.01")


def _d(val) -> Decimal:
    """Safely cast to Decimal."""
    if val is None:
        return Decimal("0")
    return Decimal(str(val))


def calculate_estimate(lines: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        lines:   list of estimate line dicts (matches EstimateLine columns)
        profile: rate profile dict (matches rate_profiles columns)

    Returns:
        dict with all totals, ready to write back to estimates table.
    """
    body_rate       = _d(profile.get("body_rate", 48))
    paint_rate      = _d(profile.get("paint_rate", 48))
    supply_rate     = _d(profile.get("paint_supply_rate", 28))
    tax_pct         = _d(profile.get("tax_rate_pct", 7))
    lkq_markup      = _d(profile.get("lkq_markup_pct", 25)) / 100
    after_markup    = _d(profile.get("aftermarket_markup_pct", 0)) / 100
    reman_markup    = _d(profile.get("reman_markup_pct", 0)) / 100

    total_body_hrs      = Decimal("0")
    total_paint_hrs     = Decimal("0")   # paint panel + refinish
    total_parts_oem     = Decimal("0")
    total_parts_other   = Decimal("0")
    total_nontaxed      = Decimal("0")
    total_taxed         = Decimal("0")

    for line in lines:
        op          = (line.get("operation") or "").upper()
        source      = (line.get("source") or "OEM").upper()
        is_taxable  = line.get("is_taxable", True)
        included    = line.get("labor_included", False)

        # ── Labor accumulation ──────────────────────────────────
        if not included:
            body_hrs    = _d(line.get("body_labor_hrs"))
            paint_hrs   = _d(line.get("paint_labor_hrs"))
            refinish_hrs = _d(line.get("refinish_hrs"))
            # clearcoat and underside fold into paint bucket
            cc_hrs      = _d(line.get("clearcoat_hrs"))
            us_hrs      = _d(line.get("underside_hrs"))

            total_body_hrs  += body_hrs
            total_paint_hrs += paint_hrs + refinish_hrs + cc_hrs + us_hrs

        # ── Parts accumulation ──────────────────────────────────
        base_price  = _d(line.get("part_price", 0)) * _d(line.get("qty", 1))

        if base_price > 0:
            if source == "OEM":
                total_parts_oem += base_price
            elif source == "LKQ":
                total_parts_other += base_price * (1 + lkq_markup)
            elif source in ("AFTER", "AFTERMARKET"):
                total_parts_other += base_price * (1 + after_markup)
            elif source == "REMAN":
                total_parts_other += base_price * (1 + reman_markup)
            else:
                total_parts_other += base_price
        elif base_price == 0 and line.get("part_price") is not None:
            # Fixed-price misc charges (e.g. Flex Additive $10, Cover Car $5)
            fixed = _d(line.get("part_price", 0))
            if fixed > 0:
                if is_taxable:
                    total_taxed += fixed
                else:
                    total_nontaxed += fixed

    # ── Compute dollar totals ────────────────────────────────────
    body_labor_cost     = (total_body_hrs * body_rate).quantize(CENTS, ROUND_HALF_UP)
    paint_labor_cost    = (total_paint_hrs * paint_rate).quantize(CENTS, ROUND_HALF_UP)
    paint_supply_cost   = (total_paint_hrs * supply_rate).quantize(CENTS, ROUND_HALF_UP)

    oem_parts   = total_parts_oem.quantize(CENTS, ROUND_HALF_UP)
    other_parts = total_parts_other.quantize(CENTS, ROUND_HALF_UP)
    taxed_misc  = total_taxed.quantize(CENTS, ROUND_HALF_UP)
    nontaxed    = total_nontaxed.quantize(CENTS, ROUND_HALF_UP)

    taxable_amount = (paint_supply_cost + taxed_misc + oem_parts + other_parts).quantize(CENTS, ROUND_HALF_UP)
    tax_amount     = (taxable_amount * tax_pct / 100).quantize(CENTS, ROUND_HALF_UP)
    non_taxable    = (body_labor_cost + paint_labor_cost + nontaxed).quantize(CENTS, ROUND_HALF_UP)
    grand_total    = (taxable_amount + tax_amount + non_taxable).quantize(CENTS, ROUND_HALF_UP)

    deductible  = _d(profile.get("deductible", 0)).quantize(CENTS, ROUND_HALF_UP)
    net_due     = (grand_total - deductible).quantize(CENTS, ROUND_HALF_UP)

    return {
        "total_body_labor_hrs":     float(total_body_hrs),
        "total_paint_labor_hrs":    float(total_paint_hrs),
        "total_paint_supply_hrs":   float(total_paint_hrs),
        "total_parts_oem":          float(oem_parts),
        "total_parts_other":        float(other_parts),
        "total_nontaxed":           float(nontaxed),
        "total_taxed":              float(taxed_misc),
        "taxable_amount":           float(taxable_amount),
        "tax_amount":               float(tax_amount),
        "non_taxable_amount":       float(non_taxable),
        "grand_total":              float(grand_total),
        "net_total_due":            float(net_due),
        # For display in totals table
        "body_labor_cost":          float(body_labor_cost),
        "paint_labor_cost":         float(paint_labor_cost),
        "paint_supply_cost":        float(paint_supply_cost),
        "body_rate":                float(body_rate),
        "paint_rate":               float(paint_rate),
        "supply_rate":              float(supply_rate),
        "tax_pct":                  float(tax_pct),
    }


def compute_line_total(line: Dict[str, Any], profile: Dict[str, Any]) -> float:
    """
    Single-line display total: part_price × qty only.
    Labor is tracked separately in the totals block, not per-line.
    """
    price = _d(line.get("part_price", 0))
    qty   = _d(line.get("qty", 1))
    return float((price * qty).quantize(CENTS, ROUND_HALF_UP))
