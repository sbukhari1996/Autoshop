/**
 * api.js — Central fetch() wrapper for all backend calls.
 * Base URL auto-detects: uses /api/ in production (proxied by Nginx)
 * or http://localhost:8000/api/ for local dev.
 */

const BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : 'https://autoshop-production-b0a7up.railway.app';

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Estimates
  listEstimates:      ()        => request('GET',  '/api/estimates/'),
  getEstimate:        (id)      => request('GET',  `/api/estimates/${id}`),
  createEstimate:     (body)    => request('POST', '/api/estimates/', body),
  updateLines:        (id, lines) => request('PUT', `/api/estimates/${id}/lines`, lines),
  updateInsurance:    (id, ins)   => request('PUT', `/api/estimates/${id}/insurance`, ins),
  exportPDF:          (id)      => `${BASE}/api/estimates/${id}/pdf`,

  // Customers
  listCustomers:      (q = '')  => request('GET',  `/api/customers/?search=${encodeURIComponent(q)}`),
  getCustomer:        (id)      => request('GET',  `/api/customers/${id}`),
  createCustomer:     (body)    => request('POST', '/api/customers/', body),
  updateCustomer:     (id, body)=> request('PUT',  `/api/customers/${id}`, body),

  // Vehicles
  decodeVIN:          (vin)     => request('GET',  `/api/vehicles/decode/${vin}`),
  createVehicle:      (body)    => request('POST', '/api/vehicles/', body),
  getVehicle:         (id)      => request('GET',  `/api/vehicles/${id}`),
  updateVehicle:      (id, body)=> request('PUT',  `/api/vehicles/${id}`, body),

  // Parts
  getPart:            (pn)      => request('GET',  `/api/parts/${encodeURIComponent(pn)}`),
  searchParts:        (q)       => request('GET',  `/api/parts/search/?q=${encodeURIComponent(q)}`),
  queueScrape:        (pn, make, model, year) =>
    request('POST', `/api/parts/scrape?part_number=${pn}&make=${make||''}&model=${model||''}&year=${year||''}`),
  queueVINScrape:     (vin)     => request('POST', `/api/parts/scrape/vin/${vin}`),

  // Insurance companies
  insuranceCompanies: ()        => request('GET',  '/api/insurance-companies'),

  // Rate profiles
  getRateProfile:     (id)      => request('GET',  `/api/rate-profiles/${id}`),
  updateRateProfile:  (id, body)=> request('PUT',  `/api/rate-profiles/${id}`, body),
};
