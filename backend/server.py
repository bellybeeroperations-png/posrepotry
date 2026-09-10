"""HK Bar POS — FastAPI server."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

HK_TZ = ZoneInfo("Asia/Hong_Kong")
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Response, Request
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from auth import (
    hash_password, verify_password, create_access_token,
    make_current_user_dep, _oid,
)
from models import (
    LoginIn, PinLoginIn, CategoryIn, ProductIn, AreaIn, TableIn, TablePosIn,
    MemberIn, HappyHourIn, OrderIn, OrderUpdate, PaymentIn, StaffIn, ReservationIn,
    WaitlistIn, ComboIn, PinVerifyIn,
)
from seed import seed_all
from routers.kegs import router as kegs_router, decrement_kegs_for_order

# ----- DB -----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="HK Bar POS")
api = APIRouter(prefix="/api")

get_current_user = make_current_user_dep(lambda: db)


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def sl(docs: list) -> list:
    return [serialize(d) for d in docs]


# ===================== AUTH =====================
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user["_id"]), email, user["role"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"token": token, "user": {
        "id": str(user["_id"]), "email": user["email"], "name": user["name"],
        "role": user["role"], "pin": user.get("pin"),
    }}


@api.post("/auth/pin-login")
async def pin_login(body: PinLoginIn, response: Response):
    user = await db.users.find_one({"pin": body.pin, "active": True})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = create_access_token(str(user["_id"]), user["email"], user["role"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"token": token, "user": {
        "id": str(user["_id"]), "email": user["email"], "name": user["name"],
        "role": user["role"], "pin": user.get("pin"),
    }}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# ===================== AREAS & TABLES =====================
@api.get("/areas")
async def list_areas(user: dict = Depends(get_current_user)):
    return sl(await db.areas.find().to_list(100))


@api.post("/areas")
async def create_area(body: AreaIn, user: dict = Depends(get_current_user)):
    doc = {"name": body.name, "created_at": datetime.now(timezone.utc).isoformat()}
    r = await db.areas.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.get("/tables")
async def list_tables(area_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"area_id": area_id} if area_id else {}
    tables = sl(await db.tables.find(q).to_list(500))
    # attach current order + reservation summary
    for t in tables:
        if t.get("current_order_id"):
            o = await db.orders.find_one({"_id": _oid(t["current_order_id"])})
            if o:
                t["current_order"] = {
                    "id": str(o["_id"]),
                    "total": o.get("total", 0),
                    "guests": o.get("guests", 1),
                    "opened_at": o.get("opened_at"),
                }
        if t.get("reservation_id"):
            r = await db.reservations.find_one({"_id": _oid(t["reservation_id"])})
            if r:
                t["reservation"] = {
                    "id": str(r["_id"]),
                    "guest_name": r["guest_name"],
                    "phone": r["phone"],
                    "party_size": r["party_size"],
                    "reserved_for": r["reserved_for"],
                }
    return tables


@api.post("/tables")
async def create_table(body: TableIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["status"] = "available"
    doc["current_order_id"] = None
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.tables.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/tables/{table_id}")
async def update_table(table_id: str, body: TablePosIn, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.tables.update_one({"_id": _oid(table_id)}, {"$set": update})
    t = await db.tables.find_one({"_id": _oid(table_id)})
    return serialize(t)


@api.delete("/tables/{table_id}")
async def delete_table(table_id: str, user: dict = Depends(get_current_user)):
    await db.tables.delete_one({"_id": _oid(table_id)})
    return {"ok": True}


# ===================== MENU: CATEGORIES + PRODUCTS =====================
@api.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    return sl(await db.categories.find().to_list(500))


@api.post("/categories")
async def create_category(body: CategoryIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.categories.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/categories/{cid}")
async def update_category(cid: str, body: CategoryIn, user: dict = Depends(get_current_user)):
    await db.categories.update_one({"_id": _oid(cid)}, {"$set": body.model_dump()})
    return serialize(await db.categories.find_one({"_id": _oid(cid)}))


@api.delete("/categories/{cid}")
async def delete_category(cid: str, user: dict = Depends(get_current_user)):
    await db.categories.delete_one({"_id": _oid(cid)})
    return {"ok": True}


@api.get("/products")
async def list_products(category_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"category_id": category_id} if category_id else {}
    return sl(await db.products.find(q).to_list(1000))


@api.post("/products")
async def create_product(body: ProductIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["active"] = True
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.products.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user: dict = Depends(get_current_user)):
    await db.products.update_one({"_id": _oid(pid)}, {"$set": body.model_dump()})
    return serialize(await db.products.find_one({"_id": _oid(pid)}))


@api.post("/products/{pid}/eightysix")
async def toggle_eightysix(pid: str, on: bool = True, user: dict = Depends(get_current_user)):
    """86 (out-of-stock) or un-86 a product. Instantly hides from public QR menu."""
    await db.products.update_one({"_id": _oid(pid)}, {"$set": {"eightysix": bool(on)}})
    return serialize(await db.products.find_one({"_id": _oid(pid)}))


@api.delete("/products/{pid}")
async def delete_product(pid: str, user: dict = Depends(get_current_user)):
    await db.products.delete_one({"_id": _oid(pid)})
    return {"ok": True}


# ===================== HAPPY HOUR =====================
def _is_hh_active(hh: dict, now_hk: datetime) -> bool:
    if not hh.get("active", True):
        return False
    if now_hk.weekday() not in (hh.get("days") or []):
        return False
    cur = now_hk.strftime("%H:%M")
    start, end = hh.get("start_time", ""), hh.get("end_time", "")
    if not start or not end:
        return False
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end


@api.get("/happy-hours")
async def list_hh(user: dict = Depends(get_current_user)):
    return sl(await db.happy_hours.find().to_list(50))


@api.get("/happy-hours/active")
async def active_hh(user: dict = Depends(get_current_user)):
    now_hk = datetime.now(HK_TZ)
    hhs = await db.happy_hours.find({"active": True}).to_list(50)
    result = [serialize(h) for h in hhs if _is_hh_active(h, now_hk)]
    return {"active": result, "hk_time": now_hk.isoformat(), "weekday": now_hk.weekday()}


@api.post("/happy-hours")
async def create_hh(body: HappyHourIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["active"] = True
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.happy_hours.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/happy-hours/{hid}")
async def update_hh(hid: str, body: HappyHourIn, user: dict = Depends(get_current_user)):
    await db.happy_hours.update_one({"_id": _oid(hid)}, {"$set": body.model_dump()})
    return serialize(await db.happy_hours.find_one({"_id": _oid(hid)}))


@api.delete("/happy-hours/{hid}")
async def delete_hh(hid: str, user: dict = Depends(get_current_user)):
    await db.happy_hours.delete_one({"_id": _oid(hid)})
    return {"ok": True}


# ===================== MEMBERS =====================
@api.get("/members")
async def list_members(q: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]}
    return sl(await db.members.find(query).sort("lifetime_spend", -1).to_list(500))


@api.post("/members")
async def create_member(body: MemberIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "lifetime_spend": 0.0, "visits": 0, "points": 0,
        "favorite_items": [], "avg_duration_min": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = await db.members.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.get("/members/{mid}")
async def get_member(mid: str, user: dict = Depends(get_current_user)):
    m = await db.members.find_one({"_id": _oid(mid)})
    if not m:
        raise HTTPException(404, "Not found")
    orders = sl(await db.orders.find({"member_id": mid, "status": "paid"}).sort("closed_at", -1).to_list(50))
    return {"member": serialize(m), "orders": orders}


@api.delete("/members/{mid}")
async def delete_member(mid: str, user: dict = Depends(get_current_user)):
    await db.members.delete_one({"_id": _oid(mid)})
    return {"ok": True}


# ===================== ORDERS =====================
def _compute_totals(lines, discount_type, discount_value, service_charge_pct, combos=None):
    subtotal = sum(l["price"] * l["qty"] for l in lines)
    discount = 0.0
    combo_discount = 0.0
    combos_applied = []
    if combos:
        line_pids = {l.get("product_id") for l in lines if (l.get("qty") or 0) > 0}
        for c in combos:
            if not c.get("active", True):
                continue
            required = set(c.get("product_ids") or [])
            if required and required.issubset(line_pids):
                d = 0.0
                if c.get("discount_type") == "percent":
                    d = subtotal * (c.get("discount_value", 0) / 100)
                else:
                    d = c.get("discount_value", 0)
                combo_discount += d
                combos_applied.append({
                    "name": c.get("name"),
                    "discount_type": c.get("discount_type"),
                    "discount_value": c.get("discount_value"),
                    "applied_discount": round(d, 2),
                })
    if discount_type == "percent":
        discount = subtotal * (discount_value / 100.0)
    elif discount_type == "cash":
        discount = min(discount_value, subtotal)
    net = max(0.0, subtotal - discount - combo_discount)
    service = round(net * (service_charge_pct / 100.0), 2)
    total = round(net + service, 2)
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "combo_discount": round(combo_discount, 2),
        "combos_applied": combos_applied,
        "service_charge": service,
        "total": total,
    }


async def _active_combos():
    return await db.combos.find({"active": True}).to_list(200)


@api.get("/orders")
async def list_orders(status: Optional[str] = None, limit: int = 100, user: dict = Depends(get_current_user)):
    q = {"status": status} if status else {}
    return sl(await db.orders.find(q).sort("opened_at", -1).to_list(limit))


@api.get("/orders/{oid}")
async def get_order(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    return serialize(o)


@api.post("/orders")
async def create_order(body: OrderIn, user: dict = Depends(get_current_user)):
    lines = [l.model_dump() for l in body.lines]
    combos = await _active_combos()
    totals = _compute_totals(lines, body.discount_type, body.discount_value, body.service_charge_pct, combos)
    doc = body.model_dump()
    doc["lines"] = lines
    doc.update(totals)
    doc["status"] = "open"
    doc["server_id"] = body.server_id or user["id"]
    doc["opened_at"] = datetime.now(timezone.utc).isoformat()
    doc["closed_at"] = None
    r = await db.orders.insert_one(doc)
    order_id = str(r.inserted_id)
    if body.table_id:
        await db.tables.update_one(
            {"_id": _oid(body.table_id)},
            {"$set": {"status": "occupied", "current_order_id": order_id}},
        )
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/orders/{oid}")
async def update_order(oid: str, body: OrderUpdate, user: dict = Depends(get_current_user)):
    existing = await db.orders.find_one({"_id": _oid(oid)})
    if not existing:
        raise HTTPException(404, "Not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    combos = await _active_combos()
    if "lines" in update:
        lines = update["lines"]
        totals = _compute_totals(
            lines,
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
            combos,
        )
        update.update(totals)
    elif "discount_type" in update or "discount_value" in update:
        totals = _compute_totals(
            existing["lines"],
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
            combos,
        )
        update.update(totals)
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": update})
    return serialize(await db.orders.find_one({"_id": _oid(oid)}))


@api.post("/orders/{oid}/fire")
async def fire_order(oid: str, course: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Un-hold items — mark them as fired for kitchen/bar."""
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    lines = o.get("lines", [])
    fired = 0
    for l in lines:
        if l.get("held") and (course is None or l.get("course") == course):
            l["held"] = False
            l["fired_at"] = datetime.now(timezone.utc).isoformat()
            fired += 1
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"lines": lines}})
    return {"fired": fired}


@api.post("/orders/{oid}/pay")
async def pay_order(oid: str, body: PaymentIn, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    change = 0.0
    if body.method == "split":
        paid = sum((s.get("amount") or 0) for s in body.splits)
        if paid + 0.01 < o["total"]:
            raise HTTPException(400, f"Split total HK${paid:.2f} is less than order total HK${o['total']:.2f}")
        change = round(paid - o["total"], 2)
    elif body.method == "cash":
        change = round(body.amount - o["total"], 2)
    payment = {
        "method": body.method, "amount": body.amount, "tip": body.tip,
        "splits": body.splits, "change": max(change, 0),
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "cashier_id": user["id"],
    }
    await db.orders.update_one(
        {"_id": _oid(oid)},
        {"$set": {"status": "paid", "payment": payment,
                  "closed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if o.get("table_id"):
        await db.tables.update_one(
            {"_id": _oid(o["table_id"])},
            {"$set": {"status": "dirty", "current_order_id": None}},
        )
    # decrement kegs for any linked draught lines
    try:
        await decrement_kegs_for_order(o)
    except Exception:
        pass  # keg tracking best-effort; never block payment
    if o.get("member_id"):
        opened = o.get("opened_at")
        dur_min = 0
        if opened:
            try:
                d = datetime.now(timezone.utc) - datetime.fromisoformat(opened)
                dur_min = int(d.total_seconds() / 60)
            except Exception:
                dur_min = 0
        item_names = [l["name"] for l in o.get("lines", [])]
        member = await db.members.find_one({"_id": _oid(o["member_id"])})
        if member:
            visits = member.get("visits", 0) + 1
            lifetime = member.get("lifetime_spend", 0.0) + o["total"]
            points = member.get("points", 0) + int(o["total"] // 10)
            fav = list(set((member.get("favorite_items") or []) + item_names))[:20]
            avg_prev = member.get("avg_duration_min", 0) or 0
            avg_new = int(((avg_prev * (visits - 1)) + dur_min) / max(visits, 1))
            await db.members.update_one(
                {"_id": _oid(o["member_id"])},
                {"$set": {
                    "visits": visits, "lifetime_spend": lifetime,
                    "points": points, "favorite_items": fav,
                    "avg_duration_min": avg_new,
                }},
            )
    return serialize(await db.orders.find_one({"_id": _oid(oid)}))


@api.delete("/orders/{oid}")
async def void_order(oid: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager override required to void")
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"status": "voided"}})
    if o.get("table_id"):
        await db.tables.update_one(
            {"_id": _oid(o["table_id"])},
            {"$set": {"status": "available", "current_order_id": None}},
        )
    return {"ok": True}


# ===================== TABLE ACTIONS =====================
@api.post("/tables/{tid}/clear")
async def clear_table(tid: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": "available", "current_order_id": None}})
    return {"ok": True}


@api.post("/tables/{tid}/status")
async def set_status(tid: str, status: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": status}})
    return {"ok": True}


# ===================== STAFF =====================
@api.get("/staff")
async def list_staff(user: dict = Depends(get_current_user)):
    users = await db.users.find({}, {"password_hash": 0}).to_list(200)
    return sl(users)


@api.post("/staff")
async def create_staff(body: StaffIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager only")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "Email exists")
    doc = {
        "email": body.email.lower(), "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "pin": body.pin, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await db.users.insert_one(doc)
    doc["_id"] = r.inserted_id
    doc.pop("password_hash")
    return serialize(doc)


@api.delete("/staff/{uid}")
async def delete_staff(uid: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager only")
    await db.users.delete_one({"_id": _oid(uid)})
    return {"ok": True}


# ===================== REPORTS =====================
@api.get("/reports/summary")
async def reports_summary(user: dict = Depends(get_current_user)):
    paid = await db.orders.find({"status": "paid"}).to_list(2000)
    total_revenue = sum(o.get("total", 0) for o in paid)
    total_orders = len(paid)
    avg_ticket = total_revenue / total_orders if total_orders else 0

    by_hour = {}
    by_cat = {}
    by_pay = {}
    by_staff = {}
    cats = {str(c["_id"]): c["name"] for c in await db.categories.find().to_list(500)}
    prods = {str(p["_id"]): p for p in await db.products.find().to_list(2000)}
    staff = {str(u["_id"]): u.get("name") for u in await db.users.find().to_list(200)}

    for o in paid:
        # hour
        try:
            h = datetime.fromisoformat(o["closed_at"]).astimezone(timezone.utc).hour
        except Exception:
            h = 0
        by_hour[h] = by_hour.get(h, 0) + o.get("total", 0)
        # category
        for l in o.get("lines", []):
            p = prods.get(l["product_id"])
            if p:
                cn = cats.get(p["category_id"], "Other")
                by_cat[cn] = by_cat.get(cn, 0) + l["price"] * l["qty"]
        # payment
        pay = (o.get("payment") or {}).get("method", "cash")
        by_pay[pay] = by_pay.get(pay, 0) + o.get("total", 0)
        # staff
        sid = o.get("server_id")
        sname = staff.get(sid, "—")
        by_staff[sname] = by_staff.get(sname, 0) + o.get("total", 0)

    hour_items = sorted(by_hour.items())
    cat_items = sorted(by_cat.items(), key=lambda x: -x[1])
    staff_items = sorted(by_staff.items(), key=lambda x: -x[1])
    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_ticket": round(avg_ticket, 2),
        "by_hour": [{"hour": hour, "revenue": round(v, 2)} for hour, v in hour_items],
        "by_category": [{"name": k, "revenue": round(v, 2)} for k, v in cat_items],
        "by_payment": [{"name": k, "revenue": round(v, 2)} for k, v in by_pay.items()],
        "by_staff": [{"name": k, "revenue": round(v, 2)} for k, v in staff_items],
    }


# ===================== KDS =====================
@api.get("/kds")
async def kds(station: str = "all", user: dict = Depends(get_current_user)):
    """Return fired-but-not-bumped lines. station: kitchen|bar|all"""
    orders = await db.orders.find({"status": "open"}).to_list(500)
    prods = {str(p["_id"]): p for p in await db.products.find().to_list(2000)}
    tables = {str(t["_id"]): t for t in await db.tables.find().to_list(500)}
    tickets = []
    for o in orders:
        for i, l in enumerate(o.get("lines", [])):
            if l.get("held") or not l.get("fired_at") or l.get("bumped_at"):
                continue
            p = prods.get(l.get("product_id", ""))
            kind = (p or {}).get("kind") or ("drink" if l.get("course") == "drink" else "food")
            if station == "kitchen" and kind != "food":
                continue
            if station == "bar" and kind != "drink":
                continue
            t = tables.get(o.get("table_id") or "")
            tickets.append({
                "order_id": str(o["_id"]),
                "line_index": i,
                "product_id": l.get("product_id"),
                "name": l["name"],
                "qty": l["qty"],
                "notes": l.get("notes", ""),
                "modifiers": l.get("modifiers", []),
                "course": l.get("course"),
                "kind": kind,
                "table": t["name"] if t else o.get("order_type", "").upper(),
                "order_type": o.get("order_type"),
                "fired_at": l.get("fired_at"),
            })
    tickets.sort(key=lambda x: x["fired_at"] or "")
    return tickets


@api.post("/orders/{oid}/bump/{index}")
async def bump_line(oid: str, index: int, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    lines = o.get("lines", [])
    if index < 0 or index >= len(lines):
        raise HTTPException(400, "Bad line index")
    lines[index]["bumped_at"] = datetime.now(timezone.utc).isoformat()
    lines[index]["bumped_by"] = user["id"]
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"lines": lines}})
    return {"ok": True, "bumped_at": lines[index]["bumped_at"]}


# ===================== SHIFTS =====================
async def _shift_stats(shift: dict) -> dict:
    q = {"status": "paid", "server_id": shift["user_id"],
         "closed_at": {"$gte": shift["clock_in"]}}
    if shift.get("clock_out"):
        q["closed_at"]["$lte"] = shift["clock_out"]
    orders = await db.orders.find(q).to_list(5000)
    revenue = sum(o.get("total", 0) for o in orders)
    tips = sum(((o.get("payment") or {}).get("tip") or 0) for o in orders)
    covers = sum(o.get("guests", 0) or 0 for o in orders)
    by_pay: dict = {}
    for o in orders:
        m = (o.get("payment") or {}).get("method", "cash")
        by_pay[m] = by_pay.get(m, 0) + o.get("total", 0)
    return {
        "shift": serialize(shift),
        "orders": len(orders),
        "revenue": round(revenue, 2),
        "tips": round(tips, 2),
        "covers": covers,
        "avg_ticket": round(revenue / len(orders), 2) if orders else 0,
        "by_payment": [{"method": k, "amount": round(v, 2)} for k, v in by_pay.items()],
    }


@api.post("/shifts/clock-in")
async def clock_in(user: dict = Depends(get_current_user)):
    existing = await db.shifts.find_one({"user_id": user["id"], "clock_out": None})
    if existing:
        return serialize(existing)
    doc = {
        "user_id": user["id"], "user_name": user["name"], "role": user["role"],
        "clock_in": datetime.now(timezone.utc).isoformat(),
        "clock_out": None,
    }
    r = await db.shifts.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.post("/shifts/clock-out")
async def clock_out(user: dict = Depends(get_current_user)):
    shift = await db.shifts.find_one({"user_id": user["id"], "clock_out": None})
    if not shift:
        raise HTTPException(400, "No open shift")
    await db.shifts.update_one(
        {"_id": shift["_id"]},
        {"$set": {"clock_out": datetime.now(timezone.utc).isoformat()}},
    )
    shift = await db.shifts.find_one({"_id": shift["_id"]})
    return await _shift_stats(shift)


@api.get("/shifts/current")
async def shift_current(user: dict = Depends(get_current_user)):
    shift = await db.shifts.find_one({"user_id": user["id"], "clock_out": None})
    if not shift:
        return {"open": False}
    stats = await _shift_stats(shift)
    return {"open": True, **stats}


@api.get("/shifts")
async def list_shifts(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in ("admin", "manager") else {"user_id": user["id"]}
    shifts = await db.shifts.find(q).sort("clock_in", -1).to_list(50)
    return [await _shift_stats(s) for s in shifts]


# ===================== RESERVATIONS =====================
@api.get("/reservations")
async def list_reservations(user: dict = Depends(get_current_user)):
    q = {"status": "pending"}
    return sl(await db.reservations.find(q).sort("reserved_for", 1).to_list(200))


@api.post("/reservations")
async def create_reservation(body: ReservationIn, user: dict = Depends(get_current_user)):
    t = await db.tables.find_one({"_id": _oid(body.table_id)})
    if not t:
        raise HTTPException(404, "Table not found")
    if t.get("status") == "occupied":
        raise HTTPException(400, "Table currently occupied")
    doc = body.model_dump()
    doc["status"] = "pending"
    doc["created_by"] = user["id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.reservations.insert_one(doc)
    await db.tables.update_one(
        {"_id": _oid(body.table_id)},
        {"$set": {"status": "reserved", "reservation_id": str(r.inserted_id)}},
    )
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.post("/reservations/{rid}/seat")
async def seat_reservation(rid: str, user: dict = Depends(get_current_user)):
    r = await db.reservations.find_one({"_id": _oid(rid)})
    if not r:
        raise HTTPException(404, "Not found")
    await db.reservations.update_one({"_id": _oid(rid)}, {"$set": {"status": "seated"}})
    await db.tables.update_one(
        {"_id": _oid(r["table_id"])},
        {"$set": {"status": "available", "reservation_id": None}},
    )
    return {"ok": True}


@api.delete("/reservations/{rid}")
async def cancel_reservation(rid: str, user: dict = Depends(get_current_user)):
    r = await db.reservations.find_one({"_id": _oid(rid)})
    if not r:
        raise HTTPException(404, "Not found")
    await db.reservations.update_one({"_id": _oid(rid)}, {"$set": {"status": "cancelled"}})
    await db.tables.update_one(
        {"_id": _oid(r["table_id"])},
        {"$set": {"status": "available", "reservation_id": None}},
    )
    return {"ok": True}


# ===================== PUBLIC (no auth) =====================
@api.get("/public/menu/{table_id}")
async def public_menu(table_id: str):
    t = None
    try:
        t = await db.tables.find_one({"_id": _oid(table_id)})
    except Exception:
        raise HTTPException(404, "Table not found")
    if not t:
        raise HTTPException(404, "Table not found")
    area = await db.areas.find_one({"_id": _oid(t["area_id"])}) if t.get("area_id") else None
    cats = sl(await db.categories.find().to_list(500))
    raw = await db.products.find({}).to_list(2000)
    prods = sl([p for p in raw if not p.get("eightysix", False) and p.get("active", True)])
    now_hk = datetime.now(HK_TZ)
    hhs = await db.happy_hours.find({"active": True}).to_list(50)
    active = [serialize(h) for h in hhs if _is_hh_active(h, now_hk)]
    return {
        "table": serialize(t),
        "area": serialize(area) if area else None,
        "categories": cats,
        "products": prods,
        "active_hh": active,
    }


# ===================== WAITLIST =====================
@api.get("/waitlist")
async def list_waitlist(user: dict = Depends(get_current_user)):
    q = {"status": {"$in": ["waiting", "notified"]}}
    return sl(await db.waitlist.find(q).sort("added_at", 1).to_list(200))


@api.post("/waitlist")
async def add_waitlist(body: WaitlistIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "status": "waiting",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "notified_at": None,
    })
    r = await db.waitlist.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.post("/waitlist/{wid}/notify")
async def notify_waitlist(wid: str, user: dict = Depends(get_current_user)):
    w = await db.waitlist.find_one({"_id": _oid(wid)})
    if not w:
        raise HTTPException(404, "Not found")
    await db.waitlist.update_one(
        {"_id": _oid(wid)},
        {"$set": {"status": "notified", "notified_at": datetime.now(timezone.utc).isoformat()}},
    )
    # MOCKED SMS — record the intent, no real send
    return {"ok": True, "mocked_sms_to": w["phone"], "message": f"Hi {w['name']}, your table is ready at HK Bar!"}


@api.post("/waitlist/{wid}/seat")
async def seat_waitlist(wid: str, user: dict = Depends(get_current_user)):
    await db.waitlist.update_one({"_id": _oid(wid)}, {"$set": {"status": "seated"}})
    return {"ok": True}


@api.delete("/waitlist/{wid}")
async def cancel_waitlist(wid: str, user: dict = Depends(get_current_user)):
    await db.waitlist.update_one({"_id": _oid(wid)}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


# ===================== COMBOS =====================
@api.get("/combos")
async def list_combos(user: dict = Depends(get_current_user)):
    return sl(await db.combos.find().to_list(100))


@api.post("/combos")
async def create_combo(body: ComboIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.combos.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/combos/{cid}")
async def update_combo(cid: str, body: ComboIn, user: dict = Depends(get_current_user)):
    await db.combos.update_one({"_id": _oid(cid)}, {"$set": body.model_dump()})
    return serialize(await db.combos.find_one({"_id": _oid(cid)}))


@api.delete("/combos/{cid}")
async def delete_combo(cid: str, user: dict = Depends(get_current_user)):
    await db.combos.delete_one({"_id": _oid(cid)})
    return {"ok": True}


# ===================== PIN VERIFY (manager override) =====================
@api.post("/auth/pin-verify")
async def pin_verify(body: PinVerifyIn):
    u = await db.users.find_one({"pin": body.pin, "active": True})
    if not u:
        raise HTTPException(401, "Invalid PIN")
    if u["role"] not in body.required_roles:
        raise HTTPException(403, f"Requires one of: {', '.join(body.required_roles)}")
    return {"valid": True, "user_id": str(u["_id"]), "name": u["name"], "role": u["role"]}


# ===================== BOOTSTRAP =====================
app.include_router(api)
app.include_router(kegs_router)  # split module — kegs + prep-view

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hkbar")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("pin")
    await db.tables.create_index("area_id")
    await db.products.create_index("category_id")
    await db.orders.create_index("status")
    await db.orders.create_index("member_id")
    await seed_all(db)
    logger.info("HK Bar POS ready.")


@app.on_event("shutdown")
async def shutdown():
    client.close()
