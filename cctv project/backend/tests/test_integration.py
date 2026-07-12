import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.room import Room
from app.models.camera import Camera
from app.repositories.room_repo import RoomRepository
from app.repositories.camera_repo import CameraRepository

@pytest.mark.asyncio
async def test_db_seeding_in_test_session(db_session: AsyncSession):
    """Verify that database fixtures are correctly seeded in the test session."""
    # Check users
    user_res = await db_session.execute(select(User).where(User.username == "testop"))
    user = user_res.scalar_one_or_none()
    assert user is not None
    assert user.email == "testop@visionguard.net"

    # Check rooms
    room_res = await db_session.execute(select(Room).where(Room.id == "room-001"))
    room = room_res.scalar_one_or_none()
    assert room is not None
    assert room.name == "Test Room Alpha"

@pytest.mark.asyncio
async def test_auth_login_endpoint(client: AsyncClient):
    """Test login endpoint with seeded credentials."""
    login_data = {
        "email": "testop@visionguard.net",
        "password": "TestPass123!"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    
    resp_json = response.json()
    assert resp_json["success"] is True
    assert "data" in resp_json
    assert "access_token" in resp_json["data"]
    assert resp_json["data"]["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_auth_login_invalid_credentials(client: AsyncClient):
    """Test login endpoint failure with wrong password."""
    login_data = {
        "email": "testop@visionguard.net",
        "password": "WrongPassword!"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    # The API returns 401 for bad credentials
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_rooms_endpoint_authenticated(client: AsyncClient):
    """Test fetching rooms list with authentication."""
    # Login to get token
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "testop@visionguard.net",
        "password": "TestPass123!"
    })
    token = login_res.json()["data"]["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/rooms", headers=headers)
    assert response.status_code == 200
    
    resp_json = response.json()
    assert resp_json["success"] is True
    assert len(resp_json["data"]) == 1
    assert resp_json["data"][0]["name"] == "Test Room Alpha"

@pytest.mark.asyncio
async def test_get_rooms_endpoint_unauthenticated(client: AsyncClient):
    """Test fetching rooms list fails without authentication."""
    response = await client.get("/api/v1/rooms")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_get_cameras_endpoint(client: AsyncClient):
    """Test fetching cameras registered in the system."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "testop@visionguard.net",
        "password": "TestPass123!"
    })
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/cameras", headers=headers)
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["success"] is True
    assert len(resp_json["data"]) == 1
    assert resp_json["data"][0]["id"] == "camera-001"

@pytest.mark.asyncio
async def test_room_repository_operations(db_session: AsyncSession):
    """Verify RoomRepository CRUD interactions with the database."""
    repo = RoomRepository(db_session)
    
    # List all rooms
    rooms = await repo.list_all()
    assert len(rooms) == 1
    assert rooms[0].id == "room-001"

    # Get by id
    room = await repo.get_by_id("room-001")
    assert room is not None
    assert room.name == "Test Room Alpha"

    # Update room status
    room.status = "warning"
    await repo.update(room)
    await db_session.commit()

    updated_room = await repo.get_by_id("room-001")
    assert updated_room.status == "warning"

@pytest.mark.asyncio
async def test_camera_repository_operations(db_session: AsyncSession):
    """Verify CameraRepository interactions with the database."""
    repo = CameraRepository(db_session)
    
    cameras = await repo.list_all()
    assert len(cameras) == 1
    assert cameras[0].id == "camera-001"

    room_cameras = await repo.list_by_room("room-001")
    assert len(room_cameras) == 1
    assert room_cameras[0].id == "camera-001"
