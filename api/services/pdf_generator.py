"""
pdf_generator.py
─────────────────────────────────────────────────────────────────
Generates PDF estimates that mirror the Web-Est layout exactly:
  - Shop logo + header block
  - 4-column info block: Vehicle | Owner | Insurance | Agent/Shop
  - Numbered line items grouped by section
  - Totals breakdown table (Body Labor / Paint Labor / Supplies / Parts / Tax)
  - Footer with page numbers

Uses WeasyPrint for pixel-perfect HTML→PDF conversion.
"""

from jinja2 import Template
from weasyprint import HTML, CSS
from datetime import datetime
from services.estimate_calc import calculate_estimate
import os

PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11px;
    color: #222;
    padding: 20px;
  }
  /* ─── Header ─────────────────────────────────── */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }
  .shop-info { font-size: 10px; line-height: 1.5; }
  .shop-name  { font-size: 14px; font-weight: bold; }
  .est-title  { font-size: 28px; font-weight: bold; text-align: right; }
  .est-meta   { font-size: 10px; text-align: right; line-height: 1.6; }

  /* ─── Info block (4 columns) ─────────────────── */
  .info-block {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 10px;
    border: 1px solid #ccc;
    padding: 8px;
    margin-bottom: 14px;
    font-size: 10px;
    line-height: 1.5;
  }
  .info-col .info-label { font-weight: bold; font-size: 10px; margin-bottom: 3px; }

  /* ─── Line items table ───────────────────────── */
  .line-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    font-size: 10px;
  }
  .line-table thead th {
    background: #555;
    color: #fff;
    padding: 4px 6px;
    text-align: left;
    font-size: 10px;
  }
  .line-table .section-row td {
    background: #e8e8e8;
    font-weight: bold;
    padding: 3px 6px;
    text-align: left;
    font-size: 10px;
    letter-spacing: 0.5px;
  }
  .line-table td {
    padding: 3px 6px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
  }
  .line-table tr:nth-child(even) td { background: #f9f9f9; }
  .line-table .section-row td { background: #e0e0e0; }
  .line-num   { width: 22px; text-align: right; padding-right: 8px; }
  .line-oper  { width: 70px; }
  .line-desc  { }
  .line-pn    { width: 110px; font-family: monospace; font-size: 9px; }
  .line-price { width: 70px; text-align: right; }
  .line-labor { width: 140px; font-size: 9px; }

  /* ─── Totals ─────────────────────────────────── */
  .totals-section { page-break-inside: avoid; }
  .totals-title { font-size: 20px; font-weight: bold; margin-bottom: 8px; }
  .totals-table {
    width: 60%;
    border-collapse: collapse;
    font-size: 10px;
    margin-bottom: 20px;
  }
  .totals-table thead th {
    background: #555; color: #fff;
    padding: 4px 8px; text-align: left;
  }
  .totals-table td { padding: 3px 8px; border-bottom: 1px solid #ddd; }
  .totals-table .taxable-check { text-align: center; }

  .summary-table {
    width: 40%;
    border-collapse: collapse;
    font-size: 10px;
    margin-left: auto;
    margin-top: -120px;
  }
  .summary-table td { padding: 3px 8px; border-bottom: 1px solid #ddd; }
  .summary-table .label { text-align: right; font-weight: 600; }
  .summary-table .grand-row td { font-weight: bold; font-size: 13px; }

  /* ─── Footer ─────────────────────────────────── */
  @page {
    margin: 15mm;
    @bottom-center {
      content: "Customer: {{ customer_name }}   Estimate #: {{ estimate_num }}";
      font-size: 9px; color: #666;
    }
    @bottom-right {
      content: counter(page) " of " counter(pages) "   " "{{ generated_date }}";
      font-size: 9px; color: #666;
    }
    @bottom-left {
      content: "Powered By AutoEst Pro";
      font-size: 9px; color: #666;
    }
  }
  .page-break { page-break-after: always; }
</style>
</head>
<body>

<!-- ═══ HEADER ══════════════════════════════════════════════ -->
<div class="header">
  <div class="shop-info">
    <div class="shop-name">{{ shop.name }}</div>
    <div>{{ shop.address }}</div>
    <div>{{ shop.city }}, {{ shop.state }} {{ shop.zip }}</div>
    <div>Business Phone: {{ shop.phone }}</div>
    <div>{{ shop.email }}</div>
  </div>
  <div>
    <div class="est-title">Estimate</div>
    <div class="est-meta">
      Est # {{ estimate.estimate_number }}<br>
      ID # {{ estimate.id }}<br>
      Estimator: {{ estimate.estimator_name }}
    </div>
  </div>
</div>

<!-- ═══ INFO BLOCK ══════════════════════════════════════════ -->
<div class="info-block">
  <div class="info-col">
    <div class="info-label">Vehicle Info</div>
    {{ vehicle.year }} {{ vehicle.make }} -{{ vehicle.model }} {{ vehicle.trim }}<br>
    {{ vehicle.vin }}<br>
    Ext. Color: {{ vehicle.primary_color_name }} - {{ vehicle.primary_color_code }}<br>
    License: {{ vehicle.license_plate }} {{ vehicle.license_state }}<br>
    Body Type: {{ vehicle.body_type }}<br>
    Engine: {{ vehicle.engine }}<br>
    Drive Type: {{ vehicle.drive_type }}<br>
    {% if estimate.first_poi %}First POI: {{ estimate.first_poi }}<br>{% endif %}
    {% if estimate.second_poi %}Second POI: {{ estimate.second_poi }}{% endif %}
  </div>

  <div class="info-col">
    <div class="info-label">Owner</div>
    {{ customer.first_name }} {{ customer.last_name }}<br>
    {% if customer.phone1 %}{{ customer.phone1 }}<br>{% endif %}
    {% if customer.email %}{{ customer.email }}<br>{% endif %}
    {% if customer.address1 %}{{ customer.address1 }}<br>{% endif %}
    {% if customer.address2 %}{{ customer.address2 }}<br>{% endif %}
    {% if customer.city %}{{ customer.city }}, {{ customer.state }} {{ customer.zip }}{% endif %}
    <br><br>
    <span class="info-label">Shop Info</span><br>
    Estimators Phone: {{ shop.phone }}<br>
    Estimators Email: {{ shop.email }}
  </div>

  <div class="info-col">
    <div class="info-label">Insurance Company</div>
    {% if insurance %}
    {{ insurance.company_name or insurance.company_name_override or '' }}<br>
    Policy #: {{ insurance.policy_number or '' }}<br>
    Claim #: {{ insurance.claim_number or '' }}<br>
    Date Of Loss: {{ insurance.date_of_loss or '' }}<br>
    Deductible: ${{ "%.2f"|format(insurance.deductible or 0) }}<br>
    Coverage Type: {{ insurance.coverage_type or '' }}<br>
    Inspection Date: {{ estimate.inspection_date or '' }}<br>
    Repair Days: {{ estimate.repair_days or 0 }}
    {% else %}
    —
    {% endif %}
  </div>

  <div class="info-col">
    <div class="info-label">Insurance Agent</div>
    {% if insurance %}
    {{ insurance.agent_first_name or '' }} {{ insurance.agent_last_name or '' }}<br>
    {% if insurance.agent_phone %}Phone: {{ insurance.agent_phone }}{% endif %}
    {% endif %}
  </div>
</div>

<!-- ═══ LINE ITEMS TABLE ════════════════════════════════════ -->
<table class="line-table">
  <thead>
    <tr>
      <th class="line-num"></th>
      <th class="line-oper">Oper</th>
      <th class="line-desc">Description</th>
      <th class="line-pn">Part Number</th>
      <th class="line-price">Price</th>
      <th class="line-labor">Labor</th>
    </tr>
  </thead>
  <tbody>
    {% set ns = namespace(current_section='') %}
    {% for line in lines %}
      {% if line.section != ns.current_section %}
        {% set ns.current_section = line.section %}
        <tr class="section-row">
          <td colspan="6">{{ line.section }}</td>
        </tr>
      {% endif %}
      <tr>
        <td class="line-num">{{ line.line_number }}</td>
        <td class="line-oper">{{ line.operation }}</td>
        <td class="line-desc">
          {{ line.description }}
          {% if line.notes %}<br><span style="color:#666;font-size:9px">{{ line.notes }}</span>{% endif %}
        </td>
        <td class="line-pn">{{ line.part_number or '' }}</td>
        <td class="line-price">
          {% if line.part_price and line.part_price > 0 %}
            ${{ "%.2f"|format(line.part_price) }}
          {% endif %}
        </td>
        <td class="line-labor">{{ build_labor(line) }}</td>
      </tr>
    {% endfor %}
  </tbody>
</table>

<!-- ═══ TOTALS ══════════════════════════════════════════════ -->
<div class="totals-section">
  <div class="totals-title">Totals</div>

  <table class="totals-table">
    <thead>
      <tr>
        <th>Type</th>
        <th>Labor Time</th>
        <th>Cost</th>
        <th>Total</th>
        <th>Taxable</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Body Labor</td>
        <td>{{ "%.1f"|format(totals.total_body_labor_hrs) }}</td>
        <td>${{ "%.2f"|format(totals.body_rate) }}</td>
        <td>${{ "%.2f"|format(totals.body_labor_cost) }}</td>
        <td></td>
      </tr>
      <tr>
        <td>Paint Labor</td>
        <td>{{ "%.1f"|format(totals.total_paint_labor_hrs) }}</td>
        <td>${{ "%.2f"|format(totals.paint_rate) }}</td>
        <td>${{ "%.2f"|format(totals.paint_labor_cost) }}</td>
        <td></td>
      </tr>
      <tr>
        <td>Paint Supplies</td>
        <td>{{ "%.1f"|format(totals.total_paint_supply_hrs) }}</td>
        <td>${{ "%.2f"|format(totals.supply_rate) }}</td>
        <td>${{ "%.2f"|format(totals.paint_supply_cost) }}</td>
        <td class="taxable-check">✓</td>
      </tr>
      {% if totals.nontaxed > 0 %}
      <tr>
        <td>Nontaxed</td><td></td><td></td>
        <td>${{ "%.2f"|format(totals.nontaxed) }}</td>
        <td></td>
      </tr>
      {% endif %}
      {% if totals.taxed > 0 %}
      <tr>
        <td>Taxed</td><td></td><td></td>
        <td>${{ "%.2f"|format(totals.taxed) }}</td>
        <td class="taxable-check">✓</td>
      </tr>
      {% endif %}
      <tr>
        <td>OEM Parts</td><td></td><td></td>
        <td>${{ "%.2f"|format(totals.oem_parts) }}</td>
        <td class="taxable-check">✓</td>
      </tr>
      {% if totals.other_parts > 0 %}
      <tr>
        <td>Other Parts</td><td></td><td></td>
        <td>${{ "%.2f"|format(totals.other_parts) }}</td>
        <td class="taxable-check">✓</td>
      </tr>
      {% endif %}
    </tbody>
  </table>

  <table class="summary-table">
    <tbody>
      <tr>
        <td class="label">Taxable Amount</td>
        <td>${{ "%.2f"|format(totals.taxable_amount) }}</td>
      </tr>
      <tr>
        <td class="label">Tax {{ totals.tax_pct|int }}%</td>
        <td>${{ "%.2f"|format(totals.tax_amount) }}</td>
      </tr>
      <tr>
        <td class="label">Non-taxable Amount</td>
        <td>${{ "%.2f"|format(totals.non_taxable_amount) }}</td>
      </tr>
      <tr class="grand-row">
        <td class="label">Grand Total</td>
        <td>${{ "%.2f"|format(totals.grand_total) }}</td>
      </tr>
      <tr>
        <td class="label">Less Deductible</td>
        <td>(${{ "%.2f"|format(deductible) }})</td>
      </tr>
      <tr class="grand-row">
        <td class="label">Net Total Due</td>
        <td>${{ "%.2f"|format(totals.net_total_due) }}</td>
      </tr>
    </tbody>
  </table>
</div>

</body>
</html>
"""


def build_labor(line: dict) -> str:
    """Format labor hours string for PDF, matching Web-Est format."""
    parts = []
    if line.get("labor_included"):
        return "Included"
    if line.get("clearcoat_hrs", 0) > 0:
        parts.append(f"{line['clearcoat_hrs']} hrs. Clearcoat")
    if line.get("underside_hrs", 0) > 0:
        parts.append(f"{line['underside_hrs']} hrs. Underside")
    body = (line.get("body_labor_hrs") or 0)
    if body > 0:
        parts.append(f"{body} hrs. Body")
    paint = (line.get("paint_labor_hrs") or 0)
    if paint > 0:
        parts.append(f"{paint} hrs. Paint Panel")
    ref = (line.get("refinish_hrs") or 0)
    if ref > 0:
        parts.append(f"{ref} hrs. Refinish")
    return "\n".join(parts)


def generate_pdf(data: dict, output_path: str) -> str:
    """
    Args:
        data: Full estimate dict from GET /api/estimates/{id}
        output_path: Where to write the PDF file

    Returns:
        output_path
    """
    estimate    = data.get("estimate", {})
    customer    = data.get("customer", {})
    vehicle     = data.get("vehicle", {})
    lines       = data.get("lines", [])
    insurance   = data.get("insurance", {})

    # Default shop info
    shop = {
        "name":    "Master Craft Auto Repair & Collision",
        "address": "38-21 23rd St.",
        "city":    "Long Island",
        "state":   "NY",
        "zip":     "11101",
        "phone":   "(718) 578-4563",
        "email":   "shop@mastercraftautony.com",
    }

    # Build line dicts for calc
    line_dicts = [dict(l) if hasattr(l, '__table__') else l for l in lines]

    profile = {
        "body_rate":          48.0,
        "paint_rate":         48.0,
        "paint_supply_rate":  28.0,
        "tax_rate_pct":       7.0,
        "lkq_markup_pct":     25.0,
        "aftermarket_markup_pct": 0.0,
        "reman_markup_pct":   0.0,
    }

    totals = calculate_estimate(line_dicts, profile)
    deductible = float(insurance.get("deductible") or estimate.get("deductible") or 0)
    totals["net_total_due"] = round(totals["grand_total"] - deductible, 2)
    totals["body_rate"]     = profile["body_rate"]
    totals["paint_rate"]    = profile["paint_rate"]
    totals["supply_rate"]   = profile["paint_supply_rate"]
    totals["nontaxed"]      = totals["total_nontaxed"]
    totals["taxed"]         = totals["total_taxed"]
    totals["oem_parts"]     = totals["total_parts_oem"]
    totals["other_parts"]   = totals["total_parts_other"]

    customer_name = f"{customer.get('first_name','')} {customer.get('last_name','')}".strip()
    generated_date = datetime.now().strftime("%-m/%-d/%Y %-I:%M %p")

    # Render Jinja2 template
    template = Template(PDF_TEMPLATE)
    html_content = template.render(
        shop=shop,
        estimate=estimate,
        customer=customer,
        vehicle=vehicle,
        lines=line_dicts,
        insurance=insurance,
        totals=totals,
        deductible=deductible,
        customer_name=customer_name,
        estimate_num=estimate.get("estimate_number", ""),
        generated_date=generated_date,
        build_labor=build_labor,
    )

    # Generate PDF
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    HTML(string=html_content).write_pdf(
        output_path,
        stylesheets=[
            CSS(string="@page { size: letter; margin: 15mm; }")
        ]
    )
    return output_path
