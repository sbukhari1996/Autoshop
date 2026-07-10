from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Boolean, func
from database import Base


class Estimate(Base):
    __tablename__ = "estimates"

    id                      = Column(Integer, primary_key=True)
    shop_id                 = Column(Integer, ForeignKey("shops.id"), default=1)
    customer_id             = Column(Integer, ForeignKey("customers.id"))
    vehicle_id              = Column(Integer, ForeignKey("vehicles.id"))
    rate_profile_id         = Column(Integer, ForeignKey("rate_profiles.id"), default=1)
    estimate_number         = Column(Integer, default=1)
    status                  = Column(String, default="Open")
    estimator_name          = Column(String, default="Syed Bukhari")
    inspection_date         = Column(DateTime)
    assignment_date         = Column(DateTime)
    repair_days             = Column(Integer, default=0)
    repair_hours_per_day    = Column(Integer, default=5)
    purchase_order_number   = Column(String)
    repair_notes            = Column(Text)
    estimate_description    = Column(Text)
    first_poi               = Column(String)
    second_poi              = Column(String)
    # Computed totals
    total_body_labor_hrs    = Column(Numeric(8, 2), default=0)
    total_paint_labor_hrs   = Column(Numeric(8, 2), default=0)
    total_paint_supply_hrs  = Column(Numeric(8, 2), default=0)
    total_parts_oem         = Column(Numeric(10, 2), default=0)
    total_parts_other       = Column(Numeric(10, 2), default=0)
    total_nontaxed          = Column(Numeric(10, 2), default=0)
    total_taxed             = Column(Numeric(10, 2), default=0)
    taxable_amount          = Column(Numeric(10, 2), default=0)
    tax_amount              = Column(Numeric(10, 2), default=0)
    non_taxable_amount      = Column(Numeric(10, 2), default=0)
    grand_total             = Column(Numeric(10, 2), default=0)
    deductible              = Column(Numeric(10, 2), default=0)
    net_total_due           = Column(Numeric(10, 2), default=0)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EstimateLine(Base):
    __tablename__ = "estimate_lines"

    id                  = Column(Integer, primary_key=True)
    estimate_id         = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"))
    supplement_id       = Column(Integer, default=0)
    line_number         = Column(Integer, nullable=False)
    section             = Column(String, nullable=False)
    operation           = Column(String, nullable=False)
    description         = Column(Text, nullable=False)
    part_number         = Column(String)
    part_price          = Column(Numeric(10, 2), default=0)
    qty                 = Column(Integer, default=1)
    source              = Column(String, default="OEM")
    body_labor_hrs      = Column(Numeric(5, 2), default=0)
    paint_labor_hrs     = Column(Numeric(5, 2), default=0)
    refinish_hrs        = Column(Numeric(5, 2), default=0)
    clearcoat_hrs       = Column(Numeric(5, 2), default=0)
    underside_hrs       = Column(Numeric(5, 2), default=0)
    labor_included      = Column(Boolean, default=False)
    is_taxable          = Column(Boolean, default=True)
    oh_flag             = Column(Boolean, default=False)
    notes               = Column(Text)
    line_total          = Column(Numeric(10, 2), default=0)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class Insurance(Base):
    __tablename__ = "insurance"

    id                      = Column(Integer, primary_key=True)
    estimate_id             = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"))
    policy_number           = Column(String)
    claim_number            = Column(String)
    coverage_type           = Column(String)
    deductible              = Column(Numeric(10, 2), default=0)
    date_of_loss            = Column(DateTime)
    company_id              = Column(Integer, ForeignKey("insurance_companies.id"))
    company_name_override   = Column(String)
    agent_first_name        = Column(String)
    agent_last_name         = Column(String)
    agent_phone             = Column(String)
    agent_fax               = Column(String)
    agent_email             = Column(String)
    adjuster_first_name     = Column(String)
    adjuster_last_name      = Column(String)
    adjuster_phone          = Column(String)
    adjuster_phone_ext      = Column(String)
    adjuster_fax            = Column(String)
    adjuster_email          = Column(String)
    claim_rep_first_name    = Column(String)
    claim_rep_last_name     = Column(String)
    claim_rep_phone         = Column(String)
    claim_rep_phone_ext     = Column(String)
    claim_rep_fax           = Column(String)
    claim_rep_email         = Column(String)
    claimant_same_as_owner  = Column(Boolean, default=True)
    insured_same_as_owner   = Column(Boolean, default=True)
    print_insured           = Column(Boolean, default=False)


class Supplement(Base):
    __tablename__ = "supplements"

    id              = Column(Integer, primary_key=True)
    estimate_id     = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"))
    supplement_num  = Column(Integer, default=1)
    caption         = Column(String, default="Supplement 1")
    total           = Column(Numeric(10, 2), default=0)
    lines_count     = Column(Integer, default=0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class EstimateImage(Base):
    __tablename__ = "estimate_images"

    id          = Column(Integer, primary_key=True)
    estimate_id = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"))
    file_path   = Column(Text, nullable=False)
    file_name   = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
