import os
import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.security import hash_password
from app.models.user import User
from app.models.room import Room
from app.models.camera import Camera
from app.models.system_config import SystemConfig
from app.utils.helpers import generate_id

TEST_DB_FILE = "./test_visionguard.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create the test engine and tables, clean up afterwards."""
    # Ensure any old test DB file is removed
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except PermissionError:
            pass

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Import all models to register them on Base.metadata
    import app.models  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    
    await engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except PermissionError:
            pass

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get an isolated session for a test case, seed essential data, rollback transaction at the end."""
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    
    # Seed essential data for the test run
    # 1. Admin user
    admin = User(
        full_name="Test Operator",
        username="testop",
        email="testop@visionguard.net",
        password_hash=hash_password("TestPass123!"),
        role="admin",
        status="active",
    )
    session.add(admin)

    # 2. Test Room
    room = Room(
        id="room-001",
        name="Test Room Alpha",
        location="Building A, Floor 1",
        status="normal",
    )
    session.add(room)

    # 3. Test Camera
    camera = Camera(
        id="camera-001",
        name="Test CCTV-1",
        room_id="room-001",
        rtsp_url="test",
        status="online",
        fps=10.0,
        latency_ms=100,
        ocr_confidence=98.0,
    )
    session.add(camera)

    # 4. System Config
    config = SystemConfig(
        temp_warning=28.0,
        temp_critical=32.0,
        hum_warning=65.0,
        hum_critical=75.0,
        capture_interval=30,
        retention_days=30,
        system_version="2.0.0",
    )
    session.add(config)
    
    await session.commit()
    
    yield session
    
    await session.close()
    await transaction.rollback()
    await connection.close()

@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI Test Client using the overridden test database session."""
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()
