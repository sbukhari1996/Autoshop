from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id                  = Column(Integer, primary_key=True)
    shop_id             = Column(Integer, ForeignKey("shops.id"), default=1)
    first_name          = Column(String, nullable=False)
    last_name           = Column(String, nullable=False)
    email               = Column(String)
    secondary_email     = Column(String)
    phone1              = Column(String)
    phone1_ext          = Column(String)
    phone1_type         = Column(String)
    phone2              = Column(String)
    phone2_ext          = Column(String)
    phone2_type         = Column(String)
    phone3              = Column(String)
    phone3_ext          = Column(String)
    phone3_type         = Column(String)
    address1            = Column(Text)
    address2            = Column(Text)
    city                = Column(String)
    state               = Column(String)
    zip                 = Column(String)
    business_name       = Column(String)
    notes               = Column(Text)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
