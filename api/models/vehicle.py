from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id                  = Column(Integer, primary_key=True)
    vin                 = Column(String, unique=True)
    year                = Column(Integer)
    make                = Column(String)
    model               = Column(String)
    trim                = Column(String)
    body_type           = Column(String)
    paint_type          = Column(String)
    drive_type          = Column(String)
    engine              = Column(String)
    transmission        = Column(String)
    production_year     = Column(Integer)
    production_month    = Column(Integer)
    primary_color_code  = Column(String)
    primary_color_name  = Column(String)
    color_interior      = Column(String)
    second_paint_code   = Column(String)
    second_color_name   = Column(String)
    license_plate       = Column(String)
    license_state       = Column(String)
    accessories         = Column(JSONB, default=list)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
