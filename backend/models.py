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
    price: float  # unit price after variant delta (and after HH discount if any)
    qty: int = 1
    variant: Optional[str] = None
    modifiers: List[str] = []
    course: str = "main"
    held: bool = False
    notes: Optional[str] = ""
    hh_pct: float = 0.0  # non-zero when the register applied happy-hour pricing
    seat: int = 1  # which seat # this line belongs to (for split-by-seat + move)


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
    method: Literal["cash", "card", "octopus", "wallet", "split",
                    "fps_qr", "alipayhk", "wechatpay_hk", "payme", "unionpay"] = "cash"
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


# -------- Reservations --------
class ReservationIn(BaseModel):
    table_id: str
    guest_name: str
    phone: str
    party_size: int = 2
    reserved_for: str  # ISO datetime
    notes: Optional[str] = ""


# -------- Waitlist --------
class WaitlistIn(BaseModel):
    name: str
    phone: str
    party_size: int = 2
    quoted_wait_min: int = 15
    notes: Optional[str] = ""


# -------- Combo Deals --------
class ComboSlot(BaseModel):
    operator: Literal["or", "and"] = "or"
    min_qty: int = 1
    max_qty: int = 99
    product_ids: List[str] = []


class ComboSchedule(BaseModel):
    """Optional Deal-of-the-Night window. If unset the combo is always active."""
    days: List[int] = []  # 0=Mon .. 6=Sun; empty => any day
    start_time: Optional[str] = None  # "HH:MM" HK time
    end_time: Optional[str] = None    # supports cross-midnight windows


class ComboIn(BaseModel):
    name: str
    product_ids: List[str] = []  # legacy — flat list still supported
    slots: List[ComboSlot] = []  # NEW — advanced slot rules (A+B+C+D)
    discount_type: Literal["percent", "cash"] = "percent"
    discount_value: float = 10.0
    active: bool = True
    schedule: Optional[ComboSchedule] = None  # Deal-Of-The-Night rotator


# -------- Manager-only ops --------
class AutoCloseIn(BaseModel):
    method: Literal["cash", "card", "octopus", "wallet",
                    "fps_qr", "alipayhk", "wechatpay_hk", "payme", "unionpay"] = "card"
    note: Optional[str] = "Auto-closed at last call"


class MoveLineIn(BaseModel):
    line_index: int
    target_order_id: Optional[str] = None  # None => same order, just reseat
    target_seat: Optional[int] = None      # None => keep current seat


class MergeOrdersIn(BaseModel):
    source_id: str
    target_id: str


# -------- Bar preauth + Delivery --------
class PreauthTabIn(BaseModel):
    customer_name: str
    card_last4: str = Field(min_length=4, max_length=4)
    hold_amount: float = 0.0
    table_id: Optional[str] = None
    party_size: int = 1


class DeliveryLineIn(BaseModel):
    product_id: str
    qty: int = 1
    notes: Optional[str] = ""


class DeliveryIngestIn(BaseModel):
    platform: Literal["foodpanda", "deliveroo", "keeta"] = "foodpanda"
    external_id: str
    customer_name: str
    customer_phone: str = ""
    items: List[DeliveryLineIn] = []
    fee: float = 0.0


class SetupIntentIn(BaseModel):
    customer_name: str
    metadata: dict = {}


class PreauthCompleteIn(BaseModel):
    order_id: str
    setup_intent_id: str


# -------- PIN Verify --------
class PinVerifyIn(BaseModel):
    pin: str
    required_roles: List[str] = ["manager", "admin"]
