from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models.customer import Customer

router = APIRouter(prefix="/api/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    first_name:         str
    last_name:          str
    email:              Optional[str] = None
    secondary_email:    Optional[str] = None
    phone1:             Optional[str] = None
    phone1_ext:         Optional[str] = None
    phone1_type:        Optional[str] = None
    phone2:             Optional[str] = None
    phone2_type:        Optional[str] = None
    phone3:             Optional[str] = None
    phone3_type:        Optional[str] = None
    address1:           Optional[str] = None
    address2:           Optional[str] = None
    city:               Optional[str] = None
    state:              Optional[str] = None
    zip:                Optional[str] = None
    business_name:      Optional[str] = None
    notes:              Optional[str] = None


class CustomerOut(CustomerCreate):
    id: int
    class Config:
        from_attributes = True


@router.get("/", response_model=List[CustomerOut])
def list_customers(search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Customer)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Customer.first_name.ilike(like)) |
            (Customer.last_name.ilike(like)) |
            (Customer.email.ilike(like)) |
            (Customer.phone1.ilike(like))
        )
    return q.order_by(Customer.last_name).limit(100).all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


@router.post("/", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    c = Customer(**body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, body: CustomerCreate, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c
