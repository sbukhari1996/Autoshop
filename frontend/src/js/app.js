/**
 * app.js — Main application controller.
 * Wires all tabs, loads data, and delegates to sub-modules.
 */

import { api } from './api.js';
import { state } from './state.js';
import { recalcTotals, fmt } from './calc.js';

// ─── Expose globals for onclick handlers ────────────────────────
window.showTab        = showTab;
window.showPage       = showPage;
window.openNewEstimate    = openNewEstimate;
window.openEstimateList   = openEstimateList;
window.saveCustomer       = saveCustomer;
window.clearCustomer      = clearCustomer;
window.showCustomerSearch = showCustomerSearch;
window.searchCustomers    = searchCustomers;
window.saveVehicle        = saveVehicle;
window.decodeVIN          = decodeVIN;
window.saveInsurance      = saveInsurance;
window.updateDeductible   = updateDeductible;
window.setAction      = setAction;
window.setSource      = setSource;
window.addManualLine  = addManualLine;
window.closeManualModal = closeManualModal;
window.commitManualLine = commitManualLine;
window.lookupPartFromModal = lookupPartFromModal;
window.deleteLine     = deleteLine;
window.partsSearch    = partsSearch;
window.exportPDF      = exportPDF;
window.handleImageDrop  = handleImageDrop;
window.handleImageFiles = handleImageFiles;
window.saveDetails    = saveDetails;
window.showRates      = showRates;

// ─── Labor rate defaults (from JSON / profile) ─────────────────
const SECTIONS = [];
const OPERATIONS = ['Replace','R&I','Repair','Refinish','Overhaul','Align','Blend','Other','None'];

// ─── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  populateYears();
  await loadDefaultRates();
  await loadInsuranceCompanies();
  buildCategoryList();
  populateSectionDropdown();
  loadEstimatesList();
  renderLines();
  showPage('estimates-list');
});

// ─── Tab / page routing ─────────────────────────────────────────
function showTab(tab) {
  // Map tab names to page IDs
  const pageMap = {
    'customer':  'customer',
    'vehicle':   'vehicle',
    'add-parts': 'add-parts',
    'insurance': 'insurance',
    'images':    'images',
    'details':   'details',
  };
  showPage(pageMap[tab] || tab);

  // Update tab button active state
  document.querySelectorAll('.top-tabs button').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`tab-${tab}`);
  if (btn) btn.classList.add('active');
}

function showPage(pageId) {
  document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(`page-${pageId}`);
  if (page) page.classList.add('active');
}

// ─── Estimates list ─────────────────────────────────────────────
async function loadEstimatesList() {
  try {
    const estimates = await api.listEstimates();
    const tbody = document.getElementById('est-list-body');
    if (!estimates.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center p-4 text-gray-400">No estimates yet. Click "New Estimate" to start.</td></tr>';
      return;
    }
    tbody.innerHTML = estimates.map(e => `
      <tr class="hover:bg-blue-50 cursor-pointer" onclick="loadEstimate(${e.id})">
        <td class="p-2 border">${e.estimate_number}</td>
        <td class="p-2 border">${e.customer_name || '—'}</td>
        <td class="p-2 border">${e.vehicle || '—'}</td>
        <td class="p-2 border"><span class="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-800">${e.status}</span></td>
        <td class="p-2 border font-bold">${fmt(e.grand_total)}</td>
        <td class="p-2 border">${new Date(e.created_at).toLocaleDateString()}</td>
        <td class="p-2 border">
          <button class="btn btn-blue text-xs" onclick="event.stopPropagation();loadEstimate(${e.id})">Open</button>
          <a href="${api.exportPDF(e.id)}" target="_blank" class="btn btn-gray text-xs ml-1" onclick="event.stopPropagation()">PDF</a>
        </td>
      </tr>
    `).join('');
  } catch(e) {
    console.error('Failed to load estimates list:', e);
  }
}
window.loadEstimate = loadEstimate;

async function loadEstimate(id) {
  try {
    const data = await api.getEstimate(id);
    state.estimateId = id;
    state.customerId = data.estimate.customer_id;
    state.vehicleId  = data.estimate.vehicle_id;
    state.lines      = data.lines || [];
    state.totals.deductible = parseFloat(data.insurance?.deductible || 0);

    // Populate customer fields
    const c = data.customer;
    if (c) {
      setField('c-first', c.first_name);
      setField('c-last',  c.last_name);
      setField('c-email', c.email);
      setField('c-phone1', c.phone1);
      setField('c-addr1', c.address1);
      setField('c-addr2', c.address2);
      setField('c-city', c.city);
      setField('c-state', c.state);
      setField('c-zip', c.zip);
    }

    // Populate vehicle fields
    const v = data.vehicle;
    if (v) {
      setField('v-vin', v.vin);
      setField('v-year', v.year, 'select');
      setField('v-make', v.make);
      setField('v-model', v.model);
      setField('v-trim', v.trim);
      setField('v-body-type', v.body_type, 'select');
      setField('v-paint-type', v.paint_type, 'select');
      setField('v-engine', v.engine);
      setField('v-color-code', v.primary_color_code);
      setField('v-color-name', v.primary_color_name);
    }

    // Update header
    updateEstimateHeader(data);

    renderLines();
    updateTotalsDisplay();
    showTab('add-parts');
    toast(`Estimate #${data.estimate.estimate_number} loaded`);
  } catch(e) {
    toast('Failed to load estimate: ' + e.message, true);
  }
}

function updateEstimateHeader(data) {
  const e = data.estimate, c = data.customer, v = data.vehicle;
  document.getElementById('estimate-header-info').innerHTML =
    `Est #${e.estimate_number} | ${e.status} | ${c?.first_name||''} ${c?.last_name||''} | ${v?.year||''} ${v?.make||''} ${v?.model||''} | ${v?.vin||''} | <strong>${fmt(e.grand_total)}</strong>`;
}

function openNewEstimate() {
  // Reset state
  state.estimateId = null;
  state.customerId = null;
  state.vehicleId  = null;
  state.lines      = [];
  state.totals.deductible = 0;
  clearCustomer();
  renderLines();
  updateTotalsDisplay();
  document.getElementById('estimate-header-info').textContent = '— New Estimate —';
  showTab('customer');
}

function openEstimateList() {
  loadEstimatesList();
  showPage('estimates-list');
}

// ─── Customer ───────────────────────────────────────────────────
async function saveCustomer() {
  const body = {
    first_name:  getField('c-first'),
    last_name:   getField('c-last'),
    email:       getField('c-email'),
    phone1:      getField('c-phone1'),
    address1:    getField('c-addr1'),
    address2:    getField('c-addr2'),
    city:        getField('c-city'),
    state:       getField('c-state'),
    zip:         getField('c-zip'),
    notes:       getField('c-notes'),
  };
  if (!body.first_name || !body.last_name) { toast('First and last name required', true); return; }
  try {
    let c;
    if (state.customerId) {
      c = await api.updateCustomer(state.customerId, body);
    } else {
      c = await api.createCustomer(body);
      state.customerId = c.id;
    }
    toast('Customer saved');
    showTab('vehicle');
  } catch(e) { toast('Save failed: ' + e.message, true); }
}

function clearCustomer() {
  ['c-first','c-last','c-email','c-email2','c-phone1','c-phone2',
   'c-addr1','c-addr2','c-city','c-state','c-zip','c-notes'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  state.customerId = null;
}

function showCustomerSearch() {
  document.getElementById('customer-search-modal').classList.remove('hidden');
  searchCustomers('');
}

async function searchCustomers(q) {
  try {
    const results = await api.listCustomers(q);
    const tbody = document.getElementById('cust-search-results');
    tbody.innerHTML = results.map(c => `
      <tr class="hover:bg-blue-50 cursor-pointer" onclick="selectCustomer(${c.id})">
        <td class="p-1 border">${c.first_name} ${c.last_name}</td>
        <td class="p-1 border">${c.phone1||''}</td>
        <td class="p-1 border">${c.email||''}</td>
        <td class="p-1"><button class="btn btn-blue text-xs">Select</button></td>
      </tr>
    `).join('');
  } catch(e) {}
}
window.selectCustomer = async function(id) {
  try {
    const c = await api.getCustomer(id);
    state.customerId = c.id;
    setField('c-first', c.first_name);
    setField('c-last',  c.last_name);
    setField('c-email', c.email);
    setField('c-phone1', c.phone1);
    setField('c-addr1', c.address1);
    setField('c-addr2', c.address2);
    setField('c-city', c.city);
    setField('c-state', c.state);
    setField('c-zip', c.zip);
    document.getElementById('customer-search-modal').classList.add('hidden');
    toast('Customer selected');
  } catch(e) {}
};

// ─── Vehicle ────────────────────────────────────────────────────
function populateYears() {
  const sel = document.getElementById('v-year');
  const cur = new Date().getFullYear();
  for (let y = cur + 1; y >= 1980; y--) {
    const o = document.createElement('option');
    o.value = y; o.textContent = y;
    sel.appendChild(o);
  }
}

async function decodeVIN() {
  const vin = getField('v-vin');
  if (!vin || vin.length !== 17) { toast('Enter a valid 17-character VIN', true); return; }
  try {
    const data = await api.decodeVIN(vin);
    setField('v-year', data.year, 'select');
    setField('v-make', data.make);
    setField('v-model', data.model);
    setField('v-trim', data.trim);
    setField('v-body-type', data.body_type, 'select');
    setField('v-drive', data.drive_type, 'select');
    setField('v-engine', data.engine);
    toast('VIN decoded: ' + data.year + ' ' + data.make + ' ' + data.model);
  } catch(e) { toast('VIN decode failed: ' + e.message, true); }
}

async function saveVehicle() {
  const body = {
    vin:                getField('v-vin'),
    year:               parseInt(getField('v-year')) || null,
    make:               getField('v-make'),
    model:              getField('v-model'),
    trim:               getField('v-trim'),
    body_type:          getField('v-body-type'),
    paint_type:         getField('v-paint-type'),
    drive_type:         getField('v-drive'),
    engine:             getField('v-engine'),
    primary_color_code: getField('v-color-code'),
    primary_color_name: getField('v-color-name'),
    license_plate:      getField('v-plate'),
    license_state:      getField('v-plate-state'),
  };
  if (!body.vin) { toast('VIN is required', true); return; }
  try {
    let v;
    if (state.vehicleId) {
      v = await api.updateVehicle(state.vehicleId, body);
    } else {
      v = await api.createVehicle(body);
      state.vehicleId = v.id;
    }
    toast('Vehicle saved');
    // If no estimate yet, create one now
    if (!state.estimateId && state.customerId) {
      await createEstimate();
    }
    showTab('add-parts');
  } catch(e) { toast('Save failed: ' + e.message, true); }
}

async function createEstimate() {
  try {
    const e = await api.createEstimate({
      customer_id: state.customerId,
      vehicle_id:  state.vehicleId,
      first_poi:   getField('v-poi1'),
      second_poi:  getField('v-poi2'),
      lines:       [],
    });
    state.estimateId = e.id;
    toast(`Estimate #${e.estimate_number} created`);
  } catch(e) { toast('Failed to create estimate: ' + e.message, true); }
}

// ─── Insurance ──────────────────────────────────────────────────
async function loadInsuranceCompanies() {
  try {
    const companies = await api.insuranceCompanies();
    const sel = document.getElementById('ins-company');
    companies.forEach(c => {
      const o = document.createElement('option');
      o.value = c.id; o.textContent = c.name;
      sel.appendChild(o);
    });
  } catch(e) {}
}

async function saveInsurance() {
  if (!state.estimateId) { toast('Save the vehicle first', true); return; }
  const body = {
    policy_number:      getField('ins-policy'),
    claim_number:       getField('ins-claim'),
    coverage_type:      getField('ins-coverage'),
    deductible:         parseFloat(getField('ins-deductible')) || 0,
    date_of_loss:       getField('ins-dol') || null,
    company_id:         parseInt(document.getElementById('ins-company').value) || null,
    agent_first_name:   getField('ins-agent-first'),
    agent_last_name:    getField('ins-agent-last'),
    agent_phone:        getField('ins-agent-phone'),
    adjuster_first_name: getField('ins-adj-first'),
    adjuster_last_name:  getField('ins-adj-last'),
    adjuster_phone:      getField('ins-adj-phone'),
    adjuster_email:      getField('ins-adj-email'),
    claim_rep_first_name: getField('ins-rep-first'),
    claim_rep_last_name:  getField('ins-rep-last'),
    claimant_same_as_owner: document.getElementById('ins-claimant-same').checked,
    insured_same_as_owner:  document.getElementById('ins-insured-same').checked,
  };
  try {
    await api.updateInsurance(state.estimateId, body);
    state.totals.deductible = body.deductible;
    updateTotalsDisplay();
    toast('Insurance saved');
  } catch(e) { toast('Save failed: ' + e.message, true); }
}

function updateDeductible(val) {
  state.totals.deductible = parseFloat(val) || 0;
  updateTotalsDisplay();
}

// ─── Add Parts / Line Items ─────────────────────────────────────
function setAction(a) {
  state.activeAction = a;
  document.querySelectorAll('.action-bar button').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`act-${a.replace('&','')}`);
  if (btn) btn.classList.add('active');
  document.getElementById('ml-operation').value = a;
}

function setSource(s) {
  state.activeSource = s;
  document.querySelectorAll('.source-bar button').forEach(b => b.classList.remove('active'));
  document.getElementById(`src-${s}`).classList.add('active');
  document.getElementById('ml-source').value = s;
}

function addManualLine() {
  document.getElementById('manual-line-modal').classList.remove('hidden');
  setField('ml-operation', state.activeAction, 'select');
  setField('ml-source',    state.activeSource, 'select');
}

function closeManualModal() {
  document.getElementById('manual-line-modal').classList.add('hidden');
}

function commitManualLine() {
  const line = {
    line_number:    state.lines.length + 1,
    section:        getField('ml-section'),
    operation:      getField('ml-operation'),
    description:    getField('ml-desc'),
    part_number:    getField('ml-partnum') || null,
    part_price:     parseFloat(getField('ml-price')) || 0,
    qty:            parseInt(getField('ml-qty')) || 1,
    source:         getField('ml-source'),
    body_labor_hrs: parseFloat(document.getElementById('ml-body-hrs').value) || 0,
    paint_labor_hrs: parseFloat(document.getElementById('ml-paint-hrs').value) || 0,
    refinish_hrs:   parseFloat(document.getElementById('ml-refinish-hrs').value) || 0,
    clearcoat_hrs:  parseFloat(document.getElementById('ml-cc-hrs').value) || 0,
    underside_hrs:  0,
    labor_included: document.getElementById('ml-included').checked,
    is_taxable:     document.getElementById('ml-taxable').checked,
    oh_flag:        document.getElementById('ml-oh').checked,
    supplement_id:  0,
  };
  if (!line.section || !line.description) { toast('Section and Description required', true); return; }
  state.lines.push(line);
  renderLines();
  saveLinesDebounced();
  closeManualModal();
  // Clear modal fields
  ['ml-desc','ml-partnum'].forEach(id => setField(id, ''));
  ['ml-price','ml-body-hrs','ml-paint-hrs','ml-refinish-hrs','ml-cc-hrs'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '0';
  });
}

async function lookupPartFromModal() {
  const pn = getField('ml-partnum');
  if (!pn) return;
  try {
    const data = await api.getPart(pn);
    if (data.msrp) {
      document.getElementById('ml-price').value = data.msrp;
      if (data.description) setField('ml-desc', data.description);
      toast(`Price found: $${data.msrp} from ${data.dealer_name}`);
    } else {
      toast('Price lookup queued — check back shortly');
    }
  } catch(e) { toast('Lookup failed: ' + e.message, true); }
}

function deleteLine(idx) {
  state.lines.splice(idx, 1);
  state.lines.forEach((l, i) => l.line_number = i + 1);
  renderLines();
  saveLinesDebounced();
}

// ─── Render lines table ─────────────────────────────────────────
function renderLines() {
  const tbody = document.getElementById('line-tbody');
  if (!state.lines.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center p-4 text-gray-400 text-xs">
      No line items yet. Click a part in the diagram or use "Add Manual" to add items.
    </td></tr>`;
    updateTotalsDisplay();
    return;
  }

  // Group by section
  const grouped = {};
  for (const l of state.lines) {
    if (!grouped[l.section]) grouped[l.section] = [];
    grouped[l.section].push(l);
  }

  let html = '';
  for (const [section, lines] of Object.entries(grouped)) {
    html += `<tr class="section-row"><td colspan="11">${section}</td></tr>`;
    for (const l of lines) {
      const idx = state.lines.indexOf(l);
      const laborStr = buildLaborStr(l);
      html += `
        <tr>
          <td>${l.line_number}</td>
          <td class="text-gray-500 text-xs">${l.section}</td>
          <td>${l.operation}</td>
          <td>${l.description}</td>
          <td class="font-mono text-xs">${l.part_number||''}</td>
          <td class="text-right">${l.part_price ? fmt(l.part_price) : ''}</td>
          <td class="text-center">${l.qty||1}</td>
          <td>${l.source||'OEM'}</td>
          <td class="text-center">${l.oh_flag ? '✓' : ''}</td>
          <td class="text-xs text-gray-700">${laborStr}</td>
          <td><button class="btn btn-red text-xs px-2 py-0" onclick="deleteLine(${idx})">Delete</button></td>
        </tr>`;
    }
  }
  tbody.innerHTML = html;
  updateTotalsDisplay();
}

function buildLaborStr(l) {
  const parts = [];
  if (l.labor_included) return 'Included';
  if (l.body_labor_hrs  > 0) parts.push(`${l.body_labor_hrs} hrs. Body`);
  if (l.paint_labor_hrs > 0) parts.push(`${l.paint_labor_hrs} hrs. Paint Panel`);
  if (l.refinish_hrs    > 0) parts.push(`${l.refinish_hrs} hrs. Refinish`);
  if (l.clearcoat_hrs   > 0) parts.push(`${l.clearcoat_hrs} hrs. Clearcoat`);
  if (l.underside_hrs   > 0) parts.push(`${l.underside_hrs} hrs. Underside`);
  return parts.join('<br>');
}

// ─── Totals display ─────────────────────────────────────────────
function updateTotalsDisplay() {
  const t = recalcTotals();
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  set('t-body-hrs',   t.body_labor_hrs.toFixed(1));
  set('t-body-rate',  fmt(t.body_rate));
  set('t-body-cost',  fmt(t.body_labor_cost));
  set('t-paint-hrs',  t.paint_labor_hrs.toFixed(1));
  set('t-paint-rate', fmt(t.paint_rate));
  set('t-paint-cost', fmt(t.paint_labor_cost));
  set('t-supply-hrs', t.paint_labor_hrs.toFixed(1));
  set('t-supply-rate',fmt(t.supply_rate));
  set('t-supply-cost',fmt(t.paint_supply_cost));
  set('t-nontaxed',   fmt(t.nontaxed));
  set('t-taxed',      fmt(t.taxed));
  set('t-oem',        fmt(t.oem_parts));
  set('t-other',      fmt(t.other_parts));
  set('t-taxable',    fmt(t.taxable_amount));
  set('t-tax-pct',    t.tax_pct);
  set('t-tax',        fmt(t.tax_amount));
  set('t-nontaxable', fmt(t.non_taxable));
  set('t-grand',      fmt(t.grand_total));
  set('t-deductible', `(${fmt(t.deductible)})`);
  set('t-netdue',     fmt(t.net_due));

  // Update supplement display
  set('supp-total', fmt(t.grand_total));
  set('supp-lines', state.lines.length);

  // Update header total
  const hi = document.getElementById('estimate-header-info');
  if (hi && state.estimateId) {
    const cur = hi.textContent;
    hi.innerHTML = hi.innerHTML.replace(/\$[\d,]+\.\d{2}$/, `<strong>${fmt(t.grand_total)}</strong>`);
  }
}

// ─── Debounced save to server ────────────────────────────────────
let saveTimer;
function saveLinesDebounced() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    if (!state.estimateId) return;
    try {
      await api.updateLines(state.estimateId, state.lines);
    } catch(e) {
      console.warn('Auto-save failed:', e.message);
    }
  }, 1500);
}

// ─── Category list (sidebar in Add Parts) ───────────────────────
async function loadDefaultRates() {
  try {
    const data = await fetch('/api/labor-rates/defaults').then(r => r.json()).catch(() => null);
    if (data?.default_profile?.labor) {
      const l = data.default_profile.labor;
      state.profile.body_rate         = l.body?.rate || 48;
      state.profile.paint_rate        = l.paint?.rate || 48;
      state.profile.paint_supply_rate = data.default_profile.supplies?.paint?.rate || 28;
    }
    if (data?.common_sections) {
      SECTIONS.push(...data.common_sections);
    }
  } catch(e) {}
}

function buildCategoryList() {
  const container = document.getElementById('category-list');
  const sections = SECTIONS.length ? SECTIONS : [
    'FRONT BUMPER','GRILLE','FRONT LAMPS','HOOD','COOLING',
    'FRONT FENDER','AIR BAG SYSTEM','ABS/BRAKES','FRONT SUSPENSION',
    'ENGINE/TRANS','WINDSHIELD','FRONT DOOR','REAR DOOR',
    'ROOF','QUARTER PANEL','LIFTGATE','REAR BUMPER','REAR LAMPS',
  ];
  container.innerHTML = sections.map(s => `
    <div class="cat-item" onclick="selectCategory('${s}')" data-section="${s}">${s}</div>
  `).join('');
}

window.selectCategory = function(section) {
  document.querySelectorAll('.cat-item').forEach(el => el.classList.remove('active'));
  const el = document.querySelector(`.cat-item[data-section="${section}"]`);
  if (el) el.classList.add('active');

  // Set modal section default
  const sel = document.getElementById('ml-section');
  if (sel) sel.value = section;

  // Show section diagram placeholder
  loadSectionDiagram(section);
};

async function loadSectionDiagram(section) {
  const panel = document.getElementById('svg-panel');
  // Check if we have a scraped SVG for this section + current vehicle
  const vin = getField('v-vin') || state.vehicle?.vin;
  const filename = vin ? `/svgs/${vin}_*${section.replace(/\s/g,'_')}*.svg` : null;

  // Show placeholder with + button for each line
  panel.innerHTML = `
    <div class="p-4 w-full">
      <div class="flex justify-between items-center mb-2">
        <span class="font-bold text-sm text-gray-700">${section}</span>
        <button class="btn btn-blue text-xs" onclick="addManualLine()">+ Add Line</button>
      </div>
      <div class="text-xs text-gray-400 text-center py-8">
        <div class="text-3xl mb-2">🔩</div>
        <div>Diagram for <strong>${section}</strong></div>
        ${vin ? `<div class="mt-2"><button class="btn btn-gray text-xs" onclick="queueDiagramScrape('${vin}')">Download Diagrams for VIN</button></div>` : ''}
        <div class="mt-4 text-left">
          <div class="font-semibold mb-1">Quick-add common ${section} parts:</div>
          ${getQuickAddParts(section)}
        </div>
      </div>
    </div>`;
}

function getQuickAddParts(section) {
  const quickParts = {
    'FRONT BUMPER':  ['FRT BUMPER COVER','FLEX ADDITIVE','BRUSH GUARD'],
    'GRILLE':        ['GRILLE ASSEMBLY','RADAR SENSOR COVER'],
    'FRONT LAMPS':   ['L FRT COMBINATION LAMP ASSEMBLY','HEADLAMPS - AIM LAMPS','L FRT COMBINATION LAMP SUPPORT'],
    'HOOD':          ['HOOD PANEL','HOOD LATCH','HOOD INSULATOR'],
    'FRONT FENDER':  ['L FENDER PANEL','L FENDER REFLECTOR','L FENDER MUDGUARD'],
    'WINDSHIELD':    ['WINDSHIELD GLASS','WINDSHIELD MOLDING'],
    'FRONT DOOR':    ['L FRONT DOOR SHELL','L FRONT DOOR GLASS','L FRONT DOOR HANDLE'],
    'REAR BUMPER':   ['RR BUMPER COVER','RR BUMPER RETAINER'],
  };
  const parts = quickParts[section] || [];
  if (!parts.length) return '<div class="text-gray-400">Use "Add Manual" to add parts for this section</div>';
  return parts.map(p => `
    <div class="flex items-center justify-between bg-gray-50 border rounded px-2 py-1 mb-1">
      <span>${p}</span>
      <button class="btn btn-blue text-xs" onclick="quickAddPart('${section}', '${p}')">+ Add</button>
    </div>`).join('');
}
window.quickAddPart = function(section, desc) {
  const line = {
    line_number:    state.lines.length + 1,
    section,
    operation:      state.activeAction,
    description:    desc,
    part_number:    null,
    part_price:     0,
    qty:            1,
    source:         state.activeSource,
    body_labor_hrs: 0,
    paint_labor_hrs:0,
    refinish_hrs:   0,
    clearcoat_hrs:  0,
    underside_hrs:  0,
    labor_included: false,
    is_taxable:     true,
    oh_flag:        false,
    supplement_id:  0,
  };
  state.lines.push(line);
  renderLines();
  saveLinesDebounced();
  toast(`Added: ${desc}`);
};

window.queueDiagramScrape = async function(vin) {
  try {
    await api.queueVINScrape(vin);
    toast('Diagram download queued. Check back in a few minutes.');
  } catch(e) { toast('Queue failed: ' + e.message, true); }
};

// ─── Parts search ────────────────────────────────────────────────
async function partsSearch(q) {
  if (!q || q.length < 2) {
    document.getElementById('parts-search-results').classList.add('hidden');
    return;
  }
  try {
    const results = await api.searchParts(q);
    const div = document.getElementById('parts-search-results');
    if (!results.length) { div.classList.add('hidden'); return; }
    div.innerHTML = results.map(p => `
      <div class="p-2 hover:bg-blue-50 cursor-pointer border-b flex justify-between"
           onclick="selectSearchPart(${JSON.stringify(p).replace(/"/g,'&quot;')})">
        <span>${p.part_number} — ${p.description||''}</span>
        <span class="font-bold">${p.msrp ? fmt(p.msrp) : '—'}</span>
      </div>`).join('');
    div.classList.remove('hidden');
  } catch(e) {}
}
window.selectSearchPart = function(p) {
  document.getElementById('parts-search-input').value = p.part_number;
  document.getElementById('parts-search-results').classList.add('hidden');
  document.getElementById('ml-partnum').value = p.part_number;
  if (p.msrp) document.getElementById('ml-price').value = p.msrp;
  if (p.description) setField('ml-desc', p.description);
  addManualLine();
};

// ─── Images ─────────────────────────────────────────────────────
async function handleImageFiles(files) {
  if (!state.estimateId) { toast('Save the vehicle to create an estimate first', true); return; }
  for (const file of files) {
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`/api/estimates/${state.estimateId}/images`, { method: 'POST', body: fd });
      const data = await res.json();
      addImageToGallery(data.path, file.name);
      toast(`Uploaded: ${file.name}`);
    } catch(e) { toast('Upload failed: ' + e.message, true); }
  }
}
function handleImageDrop(e) {
  e.preventDefault();
  handleImageFiles(e.dataTransfer.files);
}
function addImageToGallery(src, name) {
  const div = document.createElement('div');
  div.className = 'relative';
  div.innerHTML = `<img src="${src}" alt="${name}" class="w-full h-32 object-cover rounded border border-gray-300" />
    <div class="text-xs text-gray-500 mt-1 truncate">${name}</div>`;
  document.getElementById('img-gallery').appendChild(div);
}

// ─── Details ─────────────────────────────────────────────────────
function saveDetails() { toast('Details saved'); }
function showRates()   { toast('Rate profiles — open the rate profile editor'); }

// ─── PDF export ─────────────────────────────────────────────────
function exportPDF() {
  if (!state.estimateId) { toast('No estimate open', true); return; }
  window.open(api.exportPDF(state.estimateId), '_blank');
}

// ─── Section dropdown in modal ────────────────────────────────────
function populateSectionDropdown() {
  const sel = document.getElementById('ml-section');
  const sections = SECTIONS.length ? SECTIONS : [
    'FRONT BUMPER','GRILLE','FRONT LAMPS','HOOD','COOLING',
    'FRONT FENDER','AIR BAG SYSTEM','WINDSHIELD','FRONT DOOR',
    'REAR DOOR','ROOF','QUARTER PANEL','LIFTGATE','REAR BUMPER','REAR LAMPS',
  ];
  sel.innerHTML = sections.map(s => `<option value="${s}">${s}</option>`).join('');
}

// ─── Utilities ───────────────────────────────────────────────────
function getField(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}
function setField(id, val, type = 'input') {
  const el = document.getElementById(id);
  if (!el || val === null || val === undefined) return;
  el.value = val;
}
function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `fixed bottom-4 right-4 text-sm px-4 py-2 rounded shadow-lg z-50 ${isError ? 'bg-red-600' : 'bg-gray-800'} text-white`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3000);
}
