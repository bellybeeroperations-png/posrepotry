"""Iter 25 — Loyalty & Rewards backend tests."""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://hk-bar-pos-pro.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "polymuze111@gmail.com"
ADMIN_PW = "admin123"


@pytest.fixture(scope="session")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _new_member(sess, name="TEST_LoyaltyMember"):
    r = sess.post(f"{BASE_URL}/api/members", json={
        "name": name, "phone": f"98{int(time.time()*1000) % 100000000:08d}",
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---- Tiers ----
def test_tiers_returns_4_correct_ladder(sess):
    r = sess.get(f"{BASE_URL}/api/loyalty/tiers")
    assert r.status_code == 200
    tiers = r.json()
    assert len(tiers) == 4
    assert [t["name"] for t in tiers] == ["Bronze", "Silver", "Gold", "Platinum"]
    assert [t["min_spend"] for t in tiers] == [0, 5000, 15000, 50000]
    assert [t["point_multiplier"] for t in tiers] == [1.0, 1.25, 1.5, 2.0]


# ---- Summary ----
def test_summary_structure(sess):
    mid = _new_member(sess)
    r = sess.get(f"{BASE_URL}/api/loyalty/summary/{mid}")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ["tier", "next_tier", "spend_to_next", "stamps", "stamp_goal",
              "points", "vouchers", "can_spin", "pending_scratch"]:
        assert k in d, f"missing {k}"
    assert d["stamp_goal"] == 10
    assert d["tier"]["name"] == "Bronze"
    assert d["next_tier"]["name"] == "Silver"
    assert d["can_spin"] is True
    assert d["stamps"] == 0
    assert d["vouchers"] == []


# ---- Spin ----
def test_spin_once_then_cooldown_400(sess):
    mid = _new_member(sess, "TEST_SpinMember")
    r1 = sess.post(f"{BASE_URL}/api/loyalty/spin/{mid}")
    assert r1.status_code == 200, r1.text
    j = r1.json()
    assert "prize_slug" in j
    assert j["prize"]["title"]
    r2 = sess.post(f"{BASE_URL}/api/loyalty/spin/{mid}")
    assert r2.status_code == 400
    assert "Next spin" in r2.json().get("detail", "")


# ---- Auto-hook: tier upgrade + stamp on paid order ----
def test_paying_order_upgrades_tier_and_adds_stamp(sess, mongo):
    mid = _new_member(sess, "TEST_TierUpgrade")
    mongo.members.update_one({"_id": ObjectId(mid)}, {"$set": {"lifetime_spend": 4990.0}})

    # Create an order attached to member
    ord_body = {
        "order_type": "pick_up", "member_id": mid, "guests": 1,
        "lines": [{"product_id": "p_test", "name": "Test Drink", "price": 50.0, "qty": 1}],
        "service_charge_pct": 0.0,
    }
    r = sess.post(f"{BASE_URL}/api/orders", json=ord_body)
    assert r.status_code == 200, r.text
    order = r.json()
    oid = order["id"]
    total = order["total"]
    assert total == 50.0

    # Pay it
    r = sess.post(f"{BASE_URL}/api/orders/{oid}/pay", json={"method": "cash", "amount": total, "tip": 0})
    assert r.status_code == 200, r.text

    # Verify tier upgraded to Silver
    s = sess.get(f"{BASE_URL}/api/loyalty/summary/{mid}").json()
    assert s["tier"]["name"] == "Silver", f"expected Silver got {s['tier']['name']} (spend={s['member']['lifetime_spend']})"
    assert s["stamps"] >= 1


# ---- Stamp card voucher issue at 10 stamps ----
def test_stamp_card_voucher_issued_at_goal(sess, mongo):
    mid = _new_member(sess, "TEST_StampGoal")
    # Force stamps=9 so pay pushes to 10
    mongo.members.update_one({"_id": ObjectId(mid)}, {"$set": {"stamps": 9}})

    ord_body = {
        "order_type": "pick_up", "member_id": mid, "guests": 1,
        "lines": [{"product_id": "p_test", "name": "Test Drink", "price": 50.0, "qty": 1}],
        "service_charge_pct": 0.0,
    }
    r = sess.post(f"{BASE_URL}/api/orders", json=ord_body)
    oid = r.json()["id"]
    r = sess.post(f"{BASE_URL}/api/orders/{oid}/pay", json={"method": "cash", "amount": 50.0, "tip": 0})
    assert r.status_code == 200

    s = sess.get(f"{BASE_URL}/api/loyalty/summary/{mid}").json()
    stamp_card_vs = [v for v in s["vouchers"] if v.get("source") == "stamp_card"]
    assert len(stamp_card_vs) >= 1, f"expected stamp_card voucher, got {s['vouchers']}"


# ---- Voucher redeem ----
def test_voucher_redeem_applies_cash_discount(sess, mongo):
    mid = _new_member(sess, "TEST_VoucherRedeem")

    # Spin until we get a voucher-kind prize (up to 20 members-ish is bad; use forced insert instead)
    # Simpler: insert a voucher directly via /spin — but that's non-deterministic.
    # Direct-DB insert a spin_wheel voucher to redeem.
    from datetime import datetime, timezone, timedelta
    v_doc = {
        "member_id": mid, "code": "V-TESTREDEEM", "kind": "spin_wheel",
        "title": "HK$20 off voucher", "discount_type": "cash", "discount_value": 20.0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "redeemed_at": None, "redeemed_order_id": None,
        "source": "spin_wheel",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    vid = str(mongo.vouchers.insert_one(v_doc).inserted_id)

    # Create open order
    ord_body = {
        "order_type": "pick_up", "member_id": mid, "guests": 1,
        "lines": [{"product_id": "p_test", "name": "Test Drink", "price": 100.0, "qty": 1}],
        "service_charge_pct": 0.0,
    }
    r = sess.post(f"{BASE_URL}/api/orders", json=ord_body)
    oid = r.json()["id"]

    # Redeem
    r = sess.post(f"{BASE_URL}/api/loyalty/vouchers/{vid}/redeem", json={"order_id": oid})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] == 20.0

    # Verify order updated
    o = mongo.orders.find_one({"_id": ObjectId(oid)})
    assert o["discount_type"] == "cash"
    assert o["discount_value"] == 20.0
    v = mongo.vouchers.find_one({"_id": ObjectId(vid)})
    assert v["redeemed_at"] is not None
    assert v["redeemed_order_id"] == oid

    # Cannot double-redeem
    r2 = sess.post(f"{BASE_URL}/api/loyalty/vouchers/{vid}/redeem", json={"order_id": oid})
    assert r2.status_code == 400


# ---- Cleanup ----
def test_zzz_cleanup(mongo):
    r = mongo.members.delete_many({"name": {"$regex": "^TEST_"}})
    mongo.vouchers.delete_many({"code": "V-TESTREDEEM"})
    print(f"Cleaned {r.deleted_count} test members")
