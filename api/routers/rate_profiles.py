from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/rate-profiles", tags=["rate-profiles"])


class RateProfileUpdate(BaseModel):
    name:                   Optional[str] = None
    body_rate:              Optional[float] = None
    paint_rate:             Optional[float] = None
    mechanical_rate:        Optional[float] = None
    frame_rate:             Optional[float] = None
    structure_rate:         Optional[float] = None
    electrical_rate:        Optional[float] = None
    aluminum_rate:          Optional[float] = None
    cleanup_rate:           Optional[float] = None
    other_rate:             Optional[float] = None
    glass_rate:             Optional[float] = None
    paint_supply_rate:      Optional[float] = None
    body_supply_rate:       Optional[float] = None
    overlap_adj_hrs:        Optional[float] = None
    overlap_non_adj_hrs:    Optional[float] = None
    allow_deductions:       Optional[bool] = None
    paint_2stage_1st_pct:   Optional[float] = None
    paint_2stage_add_pct:   Optional[float] = None
    blend_pct:              Optional[float] = None
    clearcoat_hrs:          Optional[float] = None
    lkq_markup_pct:         Optional[float] = None
    aftermarket_markup_pct: Optional[float] = None
    reman_markup_pct:       Optional[float] = None
    tax_rate_pct:           Optional[float] = None
    cc_fee_pct:             Optional[float] = None
    apply_cc_fee:           Optional[bool] = None


@router.get("/")
def list_profiles(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT * FROM rate_profiles ORDER BY id")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT * FROM rate_profiles WHERE id=:id"), {"id": profile_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Rate profile not found")
    return dict(row)


@router.put("/{profile_id}")
def update_profile(profile_id: int, body: RateProfileUpdate, db: Session = Depends(get_db)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = profile_id
    db.execute(text(f"UPDATE rate_profiles SET {set_clause} WHERE id = :id"), updates)
    db.commit()
    return {"ok": True}
