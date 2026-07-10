/**
 * state.js — Global in-memory application state.
 * No localStorage — everything lives in the session.
 */

export const state = {
  estimateId:     null,
  customerId:     null,
  vehicleId:      null,
  rateProfileId:  1,

  customer:       {},
  vehicle:        {},
  insurance:      {},
  lines:          [],   // EstimateLine[]
  images:         [],

  // Rate profile cache
  profile: {
    body_rate:          48,
    paint_rate:         48,
    paint_supply_rate:  28,
    tax_rate_pct:       7,
    lkq_markup_pct:     25,
  },

  // Live totals (recalculated on every line change)
  totals: {
    body_labor_hrs:   0,
    paint_labor_hrs:  0,
    body_labor_cost:  0,
    paint_labor_cost: 0,
    paint_supply_cost:0,
    oem_parts:        0,
    other_parts:      0,
    nontaxed:         0,
    taxed:            0,
    taxable_amount:   0,
    tax_amount:       0,
    non_taxable:      0,
    grand_total:      0,
    deductible:       0,
    net_due:          0,
  },

  // Current tab
  activeTab: 'customer',

  // Active part action / source for Add Parts page
  activeAction: 'Replace',
  activeSource: 'OEM',
};
