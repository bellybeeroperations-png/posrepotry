"""Pydantic schemas for HK Bar POS."""
from datetime import datetime, timezone
from typing import Any, List, Optional, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# -------- Auth --------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class PinLoginIn(BaseModel):
    pin: str = Field(min_length=4, max_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    name: str
    role: str
    pin: Optional[str] = None


# -------- Menu --------
class VariantIn(BaseModel):
    name: str
    price_delta: float = 0.0  # HKD


class ModifierIn(BaseModel):
    name: str
    price_delta: float = 0.0


class CategoryIn(BaseModel):
    name: str
    parent_id: Optional[str] = None
    color: Optional[str] = "#00F2FE"
    icon: Optional[str] = None


class ProductIn(BaseModel):
    name: str
    category_id: str
    price: float
    course: Literal["starter", "main", "dessert", "drink", "side", "other"] = "main"
    kind: Literal["food", "drink"] = "food"
    variants: List[VariantIn] = []
    modifiers: List[ModifierIn] = []
    happy_hour_eligible: bool = False
    description: Optional[str] = ""
    image: Optional[str] = None


# -------- Floorplan --------
class AreaIn(BaseModel):
    name: str


class TableIn(BaseModel):
    area_id: str
    name: str
    seats: int = 4
    x: float = 40
    y: float = 40
    width: float = 90
    height: float = 90
    shape: Literal["rect", "circle"] = "rect"


class TablePosIn(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    shape: Optional[str] = None
    name: Optional[str] = None
    seats: Optional[int] = None


# -------- Members --------
class MemberIn(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    tier: Literal["Regular", "Silver", "Gold", "VIP"] = "Regular"
    notes: Optional[str] = ""


# -------- Happy Hour --------
class HappyHourIn(BaseModel):
    name: str
    days: List[int] = []  # 0=Mon
    start_time: str  # "HH:MM"
    end_time: str
    percent_off: float = 20.0
    category_ids: List[str] = []


# -------- Order --------
class OrderLineIn(BaseModel):
    product_id: str
    name: str
    price: float  # unit price after variant delta
    qty: int = 1
    variant: Optional[str] = None
    modifiers: List[str] = []
    course: str = "main"
    held: bool = False
    notes: Optional[str] = ""


class OrderIn(BaseModel):
    order_type: Literal["dine_in", "pick_up", "delivery"] = "dine_in"
    table_id: Optional[str] = None
    area_id: Optional[str] = None
    member_id: Optional[str] = None
    guests: int = 1
    server_id: Optional[str] = None
    lines: List[OrderLineIn] = []
    discount_type: Literal["none", "percent", "cash"] = "none"
    discount_value: float = 0.0
    service_charge_pct: float = 10.0
    notes: Optional[str] = ""


class OrderUpdate(BaseModel):
    lines: Optional[List[OrderLineIn]] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    member_id: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class PaymentIn(BaseModel):
    method: Literal["cash", "card", "octopus", "wallet", "split"] = "cash"
    amount: float
    tip: float = 0.0
    splits: List[dict] = []  # [{method, amount}]


# -------- Staff --------
class StaffIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "manager", "bartender", "server", "cashier"]
    pin: str = Field(min_length=4, max_length=6)
