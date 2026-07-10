from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import os, uuid, aiofiles

from database import get_db
from models.estimate import Estimate, EstimateLine, Insurance, EstimateImage
from models.vehicle import Vehicle
from models.customer import Customer
from services.estimate_calc import calculate_estimate, compute_line_total
from config import get_settings

router = APIRouter(prefix="/api/estimates", tags=["estimates"])
settings = get_settings()


# ─── Pydantic schemas ────────────────────────────────────────────

class LineIn(BaseModel):
    line_number:        int
    section:            str
    operation:          str
    description:        str
    part_number:        Optional[str] = None
    part_price:         Optional[float] = 0
    qty:                Optional[int] = 1
    source:             Optional[str] = "OEM"
    body_labor_hrs:     Optional[float] = 0
    paint_labor_hrs:    Optional[float] = 0
    refinish_hrs:       Optional[float] = 0
    clearcoat_hrs:      Optional[float] = 0
    underside_hrs:      Optional[float] = 0
    labor_included:     Optional[bool] = False
    is_taxable:         Optional[bool] = True
    oh_flag:            Optional[bool] = False
    notes:              Optional[str] = None
    supplement_id:      Optional[int] = 0


class InsuranceIn(BaseModel):
    policy_number:          Optional[str] = None
    claim_number:           Optional[str] = None
    coverage_type:          Optional[str] = None
    deductible:             Optional[float] = 0
    date_of_loss:           Optional[date] = None
    company_id:             Optional[int] = None
    company_name_override:  Optional[str] = None
    agent_first_name:       Optional[str] = None
    agent_last_name:        Optional[str] = None
    agent_phone:            Optional[str] = None
    agent_fax:              Optional[str] = None
    adjuster_first_name:    Optional[str] = None
    adjuster_last_name:     Optional[str] = None
    adjuster_phone:         Optional[str] = None
    adjuster_phone_ext:     Optional[str] = None
    adjuster_fax:           Optional[str] = None
    adjuster_email:         Optional[str] = None
    claim_rep_first_name:   Optional[str] = None
    claim_rep_last_name:    Optional[str] = None
    claim_rep_phone:        Optional[str] = None
    claim_rep_fax:          Optional[str] = None
    claim_rep_email:        Optional[str] = None
    claimant_same_as_owner: Optional[bool] = True
    insured_same_as_owner:  Optional[bool] = True


class EstimateCreate(BaseModel):
    customer_id:            int
    vehicle_id:             int
    rate_profile_id:        Optional[int] = 1
    estimator_name:         Optional[str] = "Syed Bukhari"
    inspection_date:        Optional[date] = None
    repair_days:            Optional[int] = 0
    repair_hours_per_day:   Optional[int] = 5
    repair_notes:           Optional[str] = None
    first_poi:              Optional[str] = None
    second_poi:             Optional[str] = None
    lines:                  Optional[List[LineIn]] = []
    insurance:              Optional[InsuranceIn] = None


# ─── Helpers ─────────────────────────────────────────────────────

def _get_profile(db: Session, profile_id: int) -> dict:
    row = db.execute(text("SELECT * FROM rate_profiles WHERE id = :id"), {"id": profile_id}).mappings().first()
    return dict(row) if row else {}


def _recalculate(estimate: Estimate, lines: List[EstimateLine], profile: dict, deductible: float):
    line_dicts = [
        {
            "operation":        l.operation,
            "source":           l.source,
            "is_taxable":       l.is_taxable,
            "labor_included":   l.labor_included,
            "body_labor_hrs":   l.body_labor_hrs,
            "paint_labor_hrs":  l.paint_labor_hrs,
            "refinish_hrs":     l.refinish_hrs,
            "clearcoat_hrs":    l.clearcoat_hrs,
            "underside_hrs":    l.underside_hrs,
            "part_price":       l.part_price,
            "qty":              l.qty,
        }
        for l in lines
    ]
    profile["deductible"] = deductible
    totals = calculate_estimate(line_dicts, profile)
    for k, v in totals.items():
        if hasattr(estimate, k):
            setattr(estimate, k, v)
    estimate.deductible = deductible
    estimate.net_total_due = totals["net_total_due"]


# ─── Routes ──────────────────────────────────────────────────────

@router.get("/")
def list_estimates(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT e.id, e.estimate_number, e.status, e.grand_total, e.created_at,
               c.first_name || ' ' || c.last_name AS customer_name,
               v.year::text || ' ' || v.make || ' ' || v.model AS vehicle
        FROM estimates e
        LEFT JOIN customers c ON c.id = e.customer_id
        LEFT JOIN vehicles v ON v.id = e.vehicle_id
        ORDER BY e.created_at DESC
        LIMIT 100
    """)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{estimate_id}")
def get_estimate(estimate_id: int, db: Session = Depends(get_db)):
    e = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not e:
        raise HTTPException(404, "Estimate not found")

    lines = db.query(EstimateLine).filter(EstimateLine.estimate_id == estimate_id)\
               .order_by(EstimateLine.line_number).all()
    ins   = db.query(Insurance).filter(Insurance.estimate_id == estimate_id).first()
    imgs  = db.query(EstimateImage).filter(EstimateImage.estimate_id == estimate_id).all()
    cust  = db.query(Customer).filter(Customer.id == e.customer_id).first()
    veh   = db.query(Vehicle).filter(Vehicle.id == e.vehicle_id).first()

    return {
        "estimate":   _row_to_dict(e),
        "customer":   _row_to_dict(cust),
        "vehicle":    _row_to_dict(veh),
        "lines":      [_row_to_dict(l) for l in lines],
        "insurance":  _row_to_dict(ins),
        "images":     [_row_to_dict(i) for i in imgs],
    }


@router.post("/", status_code=201)
def create_estimate(body: EstimateCreate, db: Session = Depends(get_db)):
    # Next estimate number for this shop
    result = db.execute(text("SELECT COALESCE(MAX(estimate_number),0)+1 FROM estimates WHERE shop_id=1")).scalar()

    e = Estimate(
        customer_id=body.customer_id,
        vehicle_id=body.vehicle_id,
        rate_profile_id=body.rate_profile_id,
        estimate_number=result,
        estimator_name=body.estimator_name,
        inspection_date=body.inspection_date,
        repair_days=body.repair_days,
        repair_hours_per_day=body.repair_hours_per_day,
        repair_notes=body.repair_notes,
        first_poi=body.first_poi,
        second_poi=body.second_poi,
    )
    db.add(e)
    db.flush()

    lines = []
    for ld in body.lines:
        l = EstimateLine(estimate_id=e.id, **ld.model_dump())
        l.line_total = compute_line_total(ld.model_dump(), {})
        db.add(l)
        lines.append(l)

    if body.insurance:
        ins = Insurance(estimate_id=e.id, **body.insurance.model_dump())
        db.add(ins)
        deductible = body.insurance.deductible or 0
    else:
        deductible = 0

    profile = _get_profile(db, body.rate_profile_id or 1)
    _recalculate(e, lines, profile, deductible)

    db.commit()
    db.refresh(e)
    return {"id": e.id, "estimate_number": e.estimate_number, "grand_total": float(e.grand_total)}


@router.put("/{estimate_id}/lines")
def upsert_lines(estimate_id: int, lines_in: List[LineIn], db: Session = Depends(get_db)):
    e = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not e:
        raise HTTPException(404, "Estimate not found")

    # Delete existing base lines, replace with new set
    db.query(EstimateLine).filter(
        EstimateLine.estimate_id == estimate_id,
        EstimateLine.supplement_id == 0
    ).delete()

    lines = []
    for ld in lines_in:
        l = EstimateLine(estimate_id=estimate_id, **ld.model_dump())
        l.line_total = compute_line_total(ld.model_dump(), {})
        db.add(l)
        lines.append(l)

    ins  = db.query(Insurance).filter(Insurance.estimate_id == estimate_id).first()
    ded  = float(ins.deductible) if ins and ins.deductible else 0
    prof = _get_profile(db, e.rate_profile_id or 1)
    _recalculate(e, lines, prof, ded)

    db.commit()
    return {"grand_total": float(e.grand_total), "lines": len(lines)}


@router.put("/{estimate_id}/insurance")
def upsert_insurance(estimate_id: int, body: InsuranceIn, db: Session = Depends(get_db)):
    ins = db.query(Insurance).filter(Insurance.estimate_id == estimate_id).first()
    if ins:
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(ins, k, v)
    else:
        ins = Insurance(estimate_id=estimate_id, **body.model_dump())
        db.add(ins)
    db.commit()
    return {"ok": True}


@router.post("/{estimate_id}/images")
async def upload_image(estimate_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1]
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(settings.upload_dir, str(estimate_id))
    os.makedirs(path, exist_ok=True)
    full_path = os.path.join(path, fname)
    async with aiofiles.open(full_path, "wb") as f:
        content = await file.read()
        await f.write(content)
    img = EstimateImage(estimate_id=estimate_id, file_path=full_path, file_name=file.filename)
    db.add(img)
    db.commit()
    return {"file_name": file.filename, "path": f"/uploads/{estimate_id}/{fname}"}


@router.get("/{estimate_id}/pdf")
def export_pdf(estimate_id: int, db: Session = Depends(get_db)):
    from services.pdf_generator import generate_pdf
    data = get_estimate(estimate_id, db)
    out_path = os.path.join(settings.upload_dir, f"estimate_{estimate_id}.pdf")
    generate_pdf(data, out_path)
    return FileResponse(out_path, media_type="application/pdf",
                        filename=f"Estimate_{estimate_id}.pdf")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        d[col.name] = str(val) if hasattr(val, 'isoformat') else val
    return d
