"""Iteration 27 loyalty tests: signup bonus, referral, happy-hour boost,
visit streak, feedback, social share."""
import os, time, uuid
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "polymuze111@gmail.com", "password": "admin123"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture
def tag():
    return f"TEST_{uuid.uuid4().hex[:6]}"


def _create_member(c, name, extra=None):
    payload = {"name": name, "phone": f"9{uuid.uuid4().int % 10**7:07d}",
               "email": f"{name.lower().replace(' ','')}@test.com"}
    if extra:
        payload.update(extra)
    r = c.post(f"{API}/members", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _get_summary(c, mid):
    r = c.get(f"{API}/loyalty/summary/{mid}")
    assert r.status_code == 200, r.text
    return r.json()


def _cleanup_member(mid):
    try:
        _db.members.delete_one({"_id": ObjectId(mid)})
        _db.vouchers.delete_many({"member_id": mid})
        _db.orders.delete_many({"member_id": mid})
        _db.feedback.delete_many({"member_id": mid})
        _db.social_shares.delete_many({"member_id": mid})
    except Exception:
        pass


# ---------- 1. Signup bonus ----------
def test_signup_bonus_and_voucher(client, tag):
    m = _create_member(client, f"{tag}_signup")
    try:
        assert m["points"] == 100, f"expected 100 starter points, got {m['points']}"
        summ = _get_summary(client, m["id"])
        signup_vs = [v for v in summ["vouchers"] if v["source"] == "signup"]
        assert len(signup_vs) == 1
        v = signup_vs[0]
        assert v["title"] == "Welcome! HK$50 off your first order"
        assert v["discount_type"] == "cash"
        assert v["discount_value"] == 50.0
    finally:
        _cleanup_member(m["id"])


# ---------- 2. Referral first-order bonus ----------
def _pay_dummy_order(client, mid, total=200.0):
    # Create a paid order directly in DB attached to member so pay flow triggers
    # (using minimal fake line with proper structure).
    prod = _db.products.find_one({}) or {}
    pid = str(prod.get("_id", "")) or "000000000000000000000000"
    r = client.post(f"{API}/orders", json={
        "order_type": "pick_up",
        "member_id": mid,
        "lines": [{"product_id": pid, "name": "Test Item",
                   "price": total, "qty": 1, "course": "main"}],
        "service_charge_pct": 0,
    })
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    r2 = client.post(f"{API}/orders/{oid}/pay", json={"method": "cash", "amount": total * 1.1})
    assert r2.status_code == 200, r2.text
    return oid


def test_referral_first_order_bonus(client, tag):
    m1 = _create_member(client, f"{tag}_ref1")
    m2 = _create_member(client, f"{tag}_ref2", extra={"referred_by": m1["id"]})
    try:
        # Verify referred_by persisted
        doc = _db.members.find_one({"_id": ObjectId(m2["id"])})
        if not doc.get("referred_by"):
            pytest.fail("referred_by not persisted on member — MemberIn missing field")

        pts_m1_before = _get_summary(client, m1["id"])["points"]
        pts_m2_before = _get_summary(client, m2["id"])["points"]

        _pay_dummy_order(client, m2["id"], total=100.0)

        s1 = _get_summary(client, m1["id"])
        s2 = _get_summary(client, m2["id"])
        assert s2["member"].get("referral_awarded") is True
        assert s2["points"] >= pts_m2_before + 200, f"M2 points {s2['points']} vs before {pts_m2_before}"
        assert s1["points"] >= pts_m1_before + 200, f"M1 points {s1['points']} vs before {pts_m1_before}"
        ref_vs_m2 = [v for v in s2["vouchers"] if v.get("source") == "referral_new"]
        ref_vs_m1 = [v for v in s1["vouchers"] if v.get("source") == "referral_ref"]
        assert ref_vs_m2, "M2 missing referral_new voucher"
        assert ref_vs_m1, "M1 missing referral_ref voucher"

        # Second pay must NOT re-award
        pts_m1_mid = s1["points"]
        pts_m2_mid = s2["points"]
        _pay_dummy_order(client, m2["id"], total=100.0)
        s1b = _get_summary(client, m1["id"])
        s2b = _get_summary(client, m2["id"])
        # M1 should not gain another 200 referral bonus
        assert s1b["points"] < pts_m1_mid + 200, "Referral awarded twice for M1"
    finally:
        _cleanup_member(m1["id"])
        _cleanup_member(m2["id"])


# ---------- 3. Happy-Hour boost ----------
def test_happy_hour_points_boost(client, tag):
    m = _create_member(client, f"{tag}_hh")
    hh_id = None
    try:
        # Insert wide HH window covering all weekdays
        r = client.post(f"{API}/happy-hours", json={
            "name": f"{tag}_hh_all", "days": [0,1,2,3,4,5,6],
            "start_time": "00:00", "end_time": "23:59",
            "percent_off": 20.0, "category_ids": [],
        })
        assert r.status_code == 200, r.text
        hh_id = r.json()["id"]

        pts_before = _get_summary(client, m["id"])["points"]
        _pay_dummy_order(client, m["id"], total=500.0)  # base_pts = 50
        pts_after = _get_summary(client, m["id"])["points"]
        # base points (from pay) 50 + HH boost 50 = at least +100
        gained = pts_after - pts_before
        assert gained >= 100, f"expected >=100 (base+HH), got {gained}"
    finally:
        if hh_id:
            client.delete(f"{API}/happy-hours/{hh_id}")
        _cleanup_member(m["id"])


# ---------- 4. Visit-streak ----------
def test_visit_streak_bonus(client, tag):
    m = _create_member(client, f"{tag}_streak")
    try:
        # First pay: no streak bonus
        pts0 = _get_summary(client, m["id"])["points"]
        _pay_dummy_order(client, m["id"], total=100.0)
        doc = _db.members.find_one({"_id": ObjectId(m["id"])})
        assert doc.get("streak_weeks") == 1
        assert doc.get("last_visit_week")

        # Second same-week: no change
        prev_last = doc["last_visit_week"]
        _pay_dummy_order(client, m["id"], total=100.0)
        doc2 = _db.members.find_one({"_id": ObjectId(m["id"])})
        assert doc2["last_visit_week"] == prev_last
        assert doc2["streak_weeks"] == 1

        # Simulate next ISO-week: manually rewind last_visit_week to prev week
        y, w = prev_last.split("-W")
        y, w = int(y), int(w)
        # previous week key
        prev_w = w - 1 if w > 1 else 52
        prev_y = y if w > 1 else y - 1
        prev_key = f"{prev_y}-W{prev_w:02d}"
        _db.members.update_one({"_id": ObjectId(m["id"])},
                               {"$set": {"last_visit_week": prev_key, "streak_weeks": 1}})
        pts_pre = _get_summary(client, m["id"])["points"]
        _pay_dummy_order(client, m["id"], total=100.0)
        doc3 = _db.members.find_one({"_id": ObjectId(m["id"])})
        assert doc3["streak_weeks"] == 2, f"streak={doc3.get('streak_weeks')}"
        pts_post = _get_summary(client, m["id"])["points"]
        # base 10 pts + streak bonus 100 (2*50)
        assert pts_post - pts_pre >= 110, f"expected >=110 gain (10 base + 100 streak), got {pts_post - pts_pre}"
    finally:
        _cleanup_member(m["id"])


# ---------- 5. Feedback ----------
def test_feedback_voucher_and_dupe(client, tag):
    m = _create_member(client, f"{tag}_fb")
    try:
        oid_fake = str(ObjectId())
        r = client.post(f"{API}/loyalty/feedback/{m['id']}",
                        json={"rating": 5, "order_id": oid_fake, "comment": "great"})
        assert r.status_code == 200, r.text
        v = r.json()["voucher"]
        assert v["discount_value"] == 20.0
        assert v["source"] == "feedback"

        r2 = client.post(f"{API}/loyalty/feedback/{m['id']}",
                         json={"rating": 4, "order_id": oid_fake})
        assert r2.status_code == 400, f"expected 400 dupe, got {r2.status_code}"
    finally:
        _cleanup_member(m["id"])


# ---------- 6. Social share ----------
def test_social_share_award_and_dupe(client, tag):
    m = _create_member(client, f"{tag}_ss")
    try:
        pts_before = _get_summary(client, m["id"])["points"]
        r = client.post(f"{API}/loyalty/social-share/{m['id']}",
                        json={"platform": "instagram"})
        assert r.status_code == 200, r.text
        assert r.json()["points_awarded"] == 25
        pts_after = _get_summary(client, m["id"])["points"]
        assert pts_after - pts_before == 25

        r2 = client.post(f"{API}/loyalty/social-share/{m['id']}",
                        json={"platform": "instagram"})
        assert r2.status_code == 400
    finally:
        _cleanup_member(m["id"])
