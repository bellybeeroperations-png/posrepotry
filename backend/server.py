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
    LoginIn, PinLoginIn, CategoryIn, ProductIn, AreaIn,
    MemberIn, HappyHourIn, StaffIn, ReservationIn,
    WaitlistIn, ComboIn, PinVerifyIn,
)
from seed import seed_all
from routers.kegs import router as kegs_router
from routers.tables import router as tables_router
from routers.orders import router as orders_router

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


# NOTE: /api/tables* endpoints now live in routers/tables.py (extracted from this file).


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


@api.get("/products/{pid}/substitutes")
async def product_substitutes(pid: str, user: dict = Depends(get_current_user)):
    """Nearest in-stock alternatives (same category, closest price). Excludes
    86'd products AND any drink whose only tap is 'blown'. Powers the on-shelf
    'Substitution Pop' when a keg blows mid-service."""
    p = await db.products.find_one({"_id": _oid(pid)})
    if not p:
        raise HTTPException(404, "Not found")
    kegs = await db.kegs.find().to_list(500)
    by_prod: dict = {}
    for k in kegs:
        by_prod.setdefault(k.get("product_id"), []).append(k)
    blocked = {pid_ for pid_, ks in by_prod.items() if ks and all(k.get("status") == "blown" for k in ks)}
    same_cat = await db.products.find({
        "category_id": p["category_id"],
        "_id": {"$ne": _oid(pid)},
        "eightysix": {"$ne": True},
    }).to_list(500)
    candidates = [c for c in same_cat if str(c["_id"]) not in blocked]
    candidates.sort(key=lambda c: abs((c.get("price") or 0) - (p.get("price") or 0)))
    return {
        "target": serialize(p),
        "blocked_reason": "eighty_sixed" if p.get("eightysix") else ("keg_blown" if pid in blocked else None),
        "substitutes": [serialize(c) for c in candidates[:3]],
    }


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
# All /api/orders* endpoints moved to routers/orders.py.
# The exclusivity-aware totals engine lives there too.


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
app.include_router(kegs_router)      # split: kegs + prep-view + analytics
app.include_router(tables_router)    # split: tables endpoints
app.include_router(orders_router)    # split: orders + exclusivity totals engine

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
