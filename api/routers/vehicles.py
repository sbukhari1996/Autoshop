from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import httpx
from database import get_db
from models.vehicle import Vehicle

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvaluesextended/{vin}?format=json"


class VehicleCreate(BaseModel):
    vin:                Optional[str] = None
    year:               Optional[int] = None
    make:               Optional[str] = None
    model:              Optional[str] = None
    trim:               Optional[str] = None
    body_type:          Optional[str] = None
    paint_type:         Optional[str] = None
    drive_type:         Optional[str] = None
    engine:             Optional[str] = None
    transmission:       Optional[str] = None
    primary_color_code: Optional[str] = None
    primary_color_name: Optional[str] = None
    color_interior:     Optional[str] = None
    license_plate:      Optional[str] = None
    license_state:      Optional[str] = None
    accessories:        Optional[List[str]] = []


class VehicleOut(VehicleCreate):
    id: int
    class Config:
        from_attributes = True


@router.get("/decode/{vin}")
async def decode_vin(vin: str):
    """Decode VIN using free NHTSA API."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(NHTSA_URL.format(vin=vin.upper()))
    if resp.status_code != 200:
        raise HTTPException(502, "NHTSA VIN decode failed")
    data = resp.json().get("Results", [{}])[0]
    return {
        "vin":          vin.upper(),
        "year":         int(data.get("ModelYear") or 0) or None,
        "make":         data.get("Make") or None,
        "model":        data.get("Model") or None,
        "trim":         data.get("Trim") or None,
        "body_type":    data.get("BodyClass") or None,
        "drive_type":   data.get("DriveType") or None,
        "engine":       _build_engine(data),
        "transmission": data.get("TransmissionStyle") or None,
    }


def _build_engine(data: dict) -> Optional[str]:
    disp = data.get("DisplacementL") or ""
    cyl  = data.get("EngineCylinders") or ""
    fuel = data.get("FuelTypePrimary") or ""
    if disp and cyl:
        return f"{disp}L {cyl} Cyl {fuel}".strip()
    return None


@router.post("/", response_model=VehicleOut, status_code=201)
def create_vehicle(body: VehicleCreate, db: Session = Depends(get_db)):
    # Check for existing VIN
    if body.vin:
        existing = db.query(Vehicle).filter(Vehicle.vin == body.vin.upper()).first()
        if existing:
            return existing
    v = Vehicle(**body.model_dump())
    if v.vin:
        v.vin = v.vin.upper()
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(404, "Vehicle not found")
    return v


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, body: VehicleCreate, db: Session = Depends(get_db)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(404, "Vehicle not found")
    for k, val in body.model_dump(exclude_unset=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return v
