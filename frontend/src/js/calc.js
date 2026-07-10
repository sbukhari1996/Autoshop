/**
 * calc.js — Client-side estimate math (mirrors estimate_calc.py).
 * Keeps the UI totals live without a round-trip to the server.
 */

import { state } from './state.js';

export function recalcTotals() {
  const p = state.profile;
  const lines = state.lines;

  let bodyHrs = 0, paintHrs = 0;
  let oemParts = 0, otherParts = 0;
  let taxedMisc = 0, nontaxedMisc = 0;

  for (const l of lines) {
    if (!l.labor_included) {
      bodyHrs  += (l.body_labor_hrs || 0);
      paintHrs += (l.paint_labor_hrs || 0) + (l.refinish_hrs || 0)
                + (l.clearcoat_hrs || 0) + (l.underside_hrs || 0);
    }

    const price = (l.part_price || 0) * (l.qty || 1);
    const src   = (l.source || 'OEM').toUpperCase();

    if (price > 0) {
      if (src === 'OEM') {
        oemParts += price;
      } else if (src === 'LKQ') {
        otherParts += price * (1 + (p.lkq_markup_pct || 25) / 100);
      } else if (['AFTER', 'AFTERMARKET'].includes(src)) {
        otherParts += price * (1 + (p.aftermarket_markup_pct || 0) / 100);
      } else if (src === 'REMAN') {
        otherParts += price * (1 + (p.reman_markup_pct || 0) / 100);
      } else {
        otherParts += price;
      }
    } else if (l.part_price === null || l.part_price === undefined) {
      // no part
    } else {
      // Fixed misc charge (no part number)
      const fixed = l.part_price || 0;
      if (fixed > 0) {
        if (l.is_taxable) taxedMisc += fixed;
        else              nontaxedMisc += fixed;
      }
    }
  }

  const bodyRate    = p.body_rate || 48;
  const paintRate   = p.paint_rate || 48;
  const supplyRate  = p.paint_supply_rate || 28;
  const taxPct      = p.tax_rate_pct || 7;
  const ded         = state.totals.deductible || 0;

  const bodyCost    = round2(bodyHrs  * bodyRate);
  const paintCost   = round2(paintHrs * paintRate);
  const supplyCost  = round2(paintHrs * supplyRate);
  const oem         = round2(oemParts);
  const other       = round2(otherParts);
  const taxed       = round2(taxedMisc);
  const nontaxed    = round2(nontaxedMisc);

  const taxable     = round2(supplyCost + taxed + oem + other);
  const tax         = round2(taxable * taxPct / 100);
  const nonTaxable  = round2(bodyCost + paintCost + nontaxed);
  const grand       = round2(taxable + tax + nonTaxable);
  const netDue      = round2(grand - ded);

  state.totals = {
    body_labor_hrs:   round2(bodyHrs),
    paint_labor_hrs:  round2(paintHrs),
    body_labor_cost:  bodyCost,
    paint_labor_cost: paintCost,
    paint_supply_cost: supplyCost,
    oem_parts:        oem,
    other_parts:      other,
    nontaxed,
    taxed,
    taxable_amount:   taxable,
    tax_amount:       tax,
    tax_pct:          taxPct,
    non_taxable:      nonTaxable,
    grand_total:      grand,
    deductible:       ded,
    net_due:          netDue,
  };

  return state.totals;
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

export function fmt(n) {
  return '$' + (n || 0).toFixed(2);
}
