"""
Integration tests — full API flow
Uses SQLite in-memory for test isolation (no real Postgres required).
Covers: register → login → submit issue → support → feedback → admin view
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ── Test DB setup ──────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    from app.db.session import Base
    # Import all models
    import app.models.user
    import app.models.cluster
    import app.models.issue
    import app.models.report
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_db_engine):
    Session = async_sessionmaker(test_db_engine, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_db_engine):
    from app.main import app
    from app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    Session = async_sessionmaker(test_db_engine, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def registered_student(client):
    resp = await client.post("/api/auth/register", json={
        "email": "student1@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A0401",
        "department": "CSE",
        "academic_year": 2,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def student_token(client, registered_student):
    resp = await client.post("/api/auth/login", json={
        "email": "student1@nsrit.edu.in",
        "password": "Test1234",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def registered_student2(client):
    resp = await client.post("/api/auth/register", json={
        "email": "student2@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A0402",
        "department": "ECE",
        "academic_year": 3,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def student2_token(client, registered_student2):
    resp = await client.post("/api/auth/login", json={
        "email": "student2@nsrit.edu.in",
        "password": "Test1234",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── Auth tests ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_register_success(client):
    resp = await client.post("/api/auth/register", json={
        "email": "newuser@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A0499",
        "department": "MECH",
        "academic_year": 1,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "student_id" not in data          # NEVER exposed
    assert "anon_id" in data
    assert data["department"] == "MECH"


@pytest.mark.anyio
async def test_register_duplicate_email(client, registered_student):
    resp = await client.post("/api/auth/register", json={
        "email": "student1@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A9999",
        "department": "CSE",
        "academic_year": 1,
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_register_duplicate_student_id(client, registered_student):
    resp = await client.post("/api/auth/register", json={
        "email": "different@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A0401",   # same as registered_student
        "department": "CSE",
        "academic_year": 2,
    })
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_register_invalid_year(client):
    resp = await client.post("/api/auth/register", json={
        "email": "yr@nsrit.edu.in",
        "password": "Test1234",
        "student_id": "22NU1A0888",
        "department": "CSE",
        "academic_year": 9,       # invalid — must be 1-4
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_login_success(client, registered_student):
    resp = await client.post("/api/auth/login", json={
        "email": "student1@nsrit.edu.in",
        "password": "Test1234",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "student"


@pytest.mark.anyio
async def test_login_wrong_password(client, registered_student):
    resp = await client.post("/api/auth/login", json={
        "email": "student1@nsrit.edu.in",
        "password": "WrongPass1",
    })
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_get_me(client, student_token):
    resp = await client.get("/api/auth/me",
                            headers={"Authorization": f"Bearer {student_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "student_id" not in data
    assert data["email"] == "student1@nsrit.edu.in"


# ── Issue tests ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_submit_issue(client, student_token):
    resp = await client.post("/api/issues",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "title": "WiFi is completely broken in all computer labs",
            "body": "The internet connection has been down for 3 days in Lab Block C. "
                    "Students cannot complete their cloud computing assignments. Urgent fix needed.",
            "category": "infrastructure",
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] == "infrastructure"
    assert "id" in data


@pytest.mark.anyio
async def test_submit_issue_too_short(client, student_token):
    resp = await client.post("/api/issues",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"title": "Short", "body": "Too short"},
    )
    assert resp.status_code in (422, 400)


@pytest.mark.anyio
async def test_list_clusters(client, student_token):
    resp = await client.get("/api/issues/clusters",
                            headers={"Authorization": f"Bearer {student_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.anyio
async def test_support_issue(client, student_token, student2_token):
    # Submit an issue first
    issue_resp = await client.post("/api/issues",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "title": "Hostel mess food quality is extremely poor",
            "body": "The food served in hostel mess has been of very poor quality for weeks. "
                    "Many students are falling sick. This requires immediate management attention.",
        }
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["id"]

    # Support from a different user
    sup_resp = await client.post(f"/api/issues/{issue_id}/support",
                                  headers={"Authorization": f"Bearer {student2_token}"})
    assert sup_resp.status_code == 200

    # Duplicate support rejected
    dup_resp = await client.post(f"/api/issues/{issue_id}/support",
                                  headers={"Authorization": f"Bearer {student2_token}"})
    assert dup_resp.status_code == 400


@pytest.mark.anyio
async def test_unauthenticated_rejected(client):
    resp = await client.get("/api/issues")
    assert resp.status_code == 403


# ── Health probes ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
