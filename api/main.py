from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from config import get_settings
from routers import customers, vehicles, estimates, parts, rate_profiles

settings = get_settings()

app = FastAPI(
    title="AutoEst Pro API",
    description="Auto Collision Estimating Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.svg_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/svgs", StaticFiles(directory=settings.svg_dir), name="svgs")

# Routers
app.include_router(customers.router)
app.include_router(vehicles.router)
app.include_router(estimates.router)
app.include_router(parts.router)
app.include_router(rate_profiles.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "autoest-pro-api"}


@app.get("/api/insurance-companies")
def get_insurance_companies():
    from database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, name FROM insurance_companies ORDER BY name")).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


@app.get("/api/labor-rates/defaults")
def get_default_rates():
    import json
    path = os.path.join(os.path.dirname(__file__), "data", "labor_rates.json")
    with open(path) as f:
        return json.load(f)
