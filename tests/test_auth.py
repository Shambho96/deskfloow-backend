import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Force testing mode so app/db/session.py uses SQLite in-memory
os.environ["TESTING"] = "True"

from app.main import app
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base
from app.models import Client, Outlet, User, UserClientOutletMapping
from app.core.security import hash_password, encrypt_phone, hash_phone_blind

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Drops and re-creates in-memory SQLite tables before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        client = Client(id="cl_grand_palace", name="Grand Palace Hotel", is_active=True)
        session.add(client)

        outlets = [
            Outlet(id="out_ichalkaranji", client_id="cl_grand_palace", name="Grand Palace - Ichalkaranji", city="Ichalkaranji", phone="+912302400001"),
            Outlet(id="out_kolhapur", client_id="cl_grand_palace", name="Grand Palace - Kolhapur", city="Kolhapur", phone="+912312600002"),
        ]
        session.add_all(outlets)

        owner = User(
            id="usr_owner_01",
            client_id="cl_grand_palace",
            name="Vikramaditya Roy (Owner)",
            email="owner@grandpalace.com",
            password_hash=hash_password("Owner@123"),
            phone_encrypted=encrypt_phone("+919900011122"),
            phone_hash=hash_phone_blind("+919900011122"),
            role="OWNER",
            can_login=True,
            is_active=True
        )

        mgr = User(
            id="usr_mgr_01",
            client_id="cl_grand_palace",
            name="Rajesh Sharma (Manager)",
            email="manager.kolhapur@grandpalace.com",
            password_hash=hash_password("Manager@123"),
            phone_encrypted=encrypt_phone("+919870001111"),
            phone_hash=hash_phone_blind("+919870001111"),
            role="MANAGER",
            can_login=True,
            is_active=True
        )

        staff = User(
            id="usr_staff_01",
            client_id="cl_grand_palace",
            name="Ramesh Kumar (Staff)",
            email="ramesh@grandpalace.com",
            password_hash=hash_password("StaffNoLoginKey"),
            phone_encrypted=encrypt_phone("+919876543210"),
            phone_hash=hash_phone_blind("+919876543210"),
            role="STAFF",
            can_login=False,
            is_active=True
        )

        session.add_all([owner, mgr, staff])

        mappings = [
            UserClientOutletMapping(id="map_o1", user_id="usr_owner_01", client_id="cl_grand_palace", outlet_id="out_kolhapur", is_primary=True),
            UserClientOutletMapping(id="map_m1", user_id="usr_mgr_01", client_id="cl_grand_palace", outlet_id="out_kolhapur", is_primary=True),
            UserClientOutletMapping(id="map_s1", user_id="usr_staff_01", client_id="cl_grand_palace", outlet_id="out_kolhapur", is_primary=True),
        ]
        session.add_all(mappings)
        await session.commit()

@pytest.mark.asyncio
async def test_owner_login_success():
    """Verify OWNER can log in successfully."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "email": "owner@grandpalace.com",
            "password": "Owner@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user"]["role"] == "OWNER"
        assert "access_token" in response.cookies

@pytest.mark.asyncio
async def test_manager_login_success():
    """Verify MANAGER can log in successfully."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "email": "manager.kolhapur@grandpalace.com",
            "password": "Manager@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user"]["role"] == "MANAGER"

@pytest.mark.asyncio
async def test_staff_login_blocked():
    """Verify STRICT LOGIN GUARD blocks STAFF accounts with 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "email": "ramesh@grandpalace.com",
            "password": "StaffNoLoginKey"
        })
        assert response.status_code == 403
        data = response.json()
        assert "Staff accounts are restricted from web dashboard login" in data["detail"]

@pytest.mark.asyncio
async def test_invalid_credentials():
    """Verify wrong password returns 401 Unauthorized."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "email": "owner@grandpalace.com",
            "password": "WrongPassword123"
        })
        assert response.status_code == 401
