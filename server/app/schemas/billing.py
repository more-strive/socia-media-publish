from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import OrderType


class PlanOut(BaseModel):
    id: int
    code: str
    name: str
    seats: int
    accounts: int
    credits_monthly: int
    price_monthly: Decimal
    price_yearly: Decimal
    features: list[str] | None = None

    model_config = {"from_attributes": True}


class OrderIn(BaseModel):
    type: OrderType
    plan_id: int | None = None
    quantity: int = Field(default=1, ge=1, description="月数/席位数/积分数")


class OrderOut(BaseModel):
    id: int
    order_no: str
    type: str
    plan_id: int | None = None
    quantity: int
    amount: Decimal
    status: str
    paid_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    plan: PlanOut | None = None
    plan_expire_at: datetime | None = None
    seats_total: int
    seats_used: int
    credits: int


class InvoiceIn(BaseModel):
    order_id: int
    title: str = Field(min_length=1, max_length=128)
    tax_no: str | None = None
    type: str = Field(default="normal", pattern=r"^(normal|vat)$")


class InvoiceOut(BaseModel):
    id: int
    order_id: int
    title: str
    tax_no: str | None = None
    type: str
    amount: Decimal
    status: str
    file_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
