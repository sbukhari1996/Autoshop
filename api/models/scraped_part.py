from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, func
from database import Base


class ScrapedPart(Base):
    __tablename__ = "scraped_parts"

    id              = Column(Integer, primary_key=True)
    part_number     = Column(String, nullable=False)
    description     = Column(Text)
    msrp            = Column(Numeric(10, 2))
    source_url      = Column(Text)
    dealer_name     = Column(String)
    make            = Column(String)
    model           = Column(String)
    year            = Column(Integer)
    svg_diagram_url = Column(Text)
    svg_local_path  = Column(Text)
    scraped_at      = Column(DateTime(timezone=True), server_default=func.now())


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id              = Column(Integer, primary_key=True)
    job_type        = Column(String, nullable=False)   # 'part' or 'vin_diagram'
    payload         = Column(Text, nullable=False)     # JSON string
    status          = Column(String, default="pending")
    error_message   = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    completed_at    = Column(DateTime(timezone=True))
