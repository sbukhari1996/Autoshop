from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.scraped_part import ScrapedPart, ScrapeJob
import json

router = APIRouter(prefix="/api/parts", tags=["parts"])


@router.get("/{part_number}")
def get_part(part_number: str, db: Session = Depends(get_db)):
    """
    Look up a part number in the scraped_parts cache.
    If not found, queue a scrape job and return 202.
    """
    part = db.query(ScrapedPart).filter(
        ScrapedPart.part_number == part_number.upper()
    ).order_by(ScrapedPart.scraped_at.desc()).first()

    if part:
        return {
            "part_number":      part.part_number,
            "description":      part.description,
            "msrp":             float(part.msrp) if part.msrp else None,
            "dealer_name":      part.dealer_name,
            "svg_local_path":   part.svg_local_path,
            "scraped_at":       str(part.scraped_at),
        }

    # Queue a scrape job
    job = ScrapeJob(
        job_type="part",
        payload=json.dumps({"part_number": part_number.upper()}),
        status="pending"
    )
    db.add(job)
    db.commit()
    return {"status": "queued", "part_number": part_number.upper(), "job_id": job.id}


@router.get("/search/")
def search_parts(q: str, db: Session = Depends(get_db)):
    like = f"%{q.upper()}%"
    parts = db.query(ScrapedPart).filter(
        (ScrapedPart.part_number.ilike(like)) |
        (ScrapedPart.description.ilike(like))
    ).limit(20).all()
    return [
        {
            "part_number":  p.part_number,
            "description":  p.description,
            "msrp":         float(p.msrp) if p.msrp else None,
            "dealer_name":  p.dealer_name,
        }
        for p in parts
    ]


@router.post("/scrape")
def queue_scrape(part_number: str, make: Optional[str] = None,
                 model: Optional[str] = None, year: Optional[int] = None,
                 db: Session = Depends(get_db)):
    job = ScrapeJob(
        job_type="part",
        payload=json.dumps({
            "part_number": part_number.upper(),
            "make": make, "model": model, "year": year
        }),
        status="pending"
    )
    db.add(job)
    db.commit()
    return {"job_id": job.id, "status": "queued"}


@router.post("/scrape/vin/{vin}")
def queue_vin_scrape(vin: str, db: Session = Depends(get_db)):
    job = ScrapeJob(
        job_type="vin_diagram",
        payload=json.dumps({"vin": vin.upper()}),
        status="pending"
    )
    db.add(job)
    db.commit()
    return {"job_id": job.id, "status": "queued"}
