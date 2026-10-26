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
        client = Client(id=1, name="Grand Palace Hotel", is_active=True)
        session.add(client)

        outlet = Outlet(id=101, client_id=1, name="Grand Palace - Ichalkaranji", city="Ichalkaranji", phone="+912302400001")
        session.add(outlet)

        owner = User(
            id=1001,
            client_id=1,
            name="Vikramaditya Roy (Owner)",
            email="owner@grandpalace.com",
            password_hash=hash_password("Owner@123"),
            phone_encrypted=encrypt_phone("+919900011122"),
            phone_hash=hash_phone_blind("+919900011122"),
            role="OWNER",
            can_login=True,
            is_active=True
        )
        session.add(owner)

        mapping = UserClientOutletMapping(id=1, user_id=1001, client_id=1, outlet_id=101, is_primary=True)
        session.add(mapping)
        await session.commit()


@pytest.mark.asyncio
async def test_floor_category_room_lifecycle():
    """End-to-end test for creating floors, categories, rooms, bulk rooms, updating statuses and layout queries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login as owner
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "owner@grandpalace.com",
            "password": "Owner@123"
        })
        assert login_res.status_code == 200
        ac.cookies.update(login_res.cookies)

        # 2. Create Floor 1 via GraphQL
        create_floor_mutation = """
        mutation {
            createFloor(input: { floorNumber: 1, name: "Ground Floor" }) {
                id
                floorNumber
                name
                isActive
                roomCount
            }
        }
        """
        res = await ac.post("/graphql", json={"query": create_floor_mutation})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        floor_id = data["data"]["createFloor"]["id"]
        assert data["data"]["createFloor"]["name"] == "Ground Floor"

        # 3. Create Room Category via GraphQL
        create_cat_mutation = """
        mutation {
            createRoomCategory(input: {
                name: "Deluxe Suite",
                code: "DLX",
                basePrice: 4500.0,
                maxAdults: 2,
                maxChildren: 1,
                amenities: ["WiFi", "AC", "Smart TV"]
            }) {
                id
                name
                code
                basePrice
                maxAdults
                amenities
            }
        }
        """
        res = await ac.post("/graphql", json={"query": create_cat_mutation})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        cat_id = data["data"]["createRoomCategory"]["id"]
        assert data["data"]["createRoomCategory"]["name"] == "Deluxe Suite"
        assert data["data"]["createRoomCategory"]["basePrice"] == 4500.0

        # 4. Create Single Room 101
        create_room_mutation = f"""
        mutation {{
            createRoom(input: {{
                floorId: {floor_id},
                categoryId: {cat_id},
                roomNumber: "101"
            }}) {{
                id
                roomNumber
                status
                floorName
                categoryName
                basePrice
            }}
        }}
        """
        res = await ac.post("/graphql", json={"query": create_room_mutation})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        room_101 = data["data"]["createRoom"]
        room_101_id = room_101["id"]
        assert room_101["roomNumber"] == "101"
        assert room_101["status"] == "AVAILABLE"

        # 5. Bulk Create Rooms 102 - 105
        bulk_create_mutation = f"""
        mutation {{
            createBulkRooms(input: {{
                floorId: {floor_id},
                categoryId: {cat_id},
                startNumber: 102,
                endNumber: 105
            }}) {{
                status
                message
                createdCount
                rooms {{
                    id
                    roomNumber
                    status
                }}
            }}
        }}
        """
        res = await ac.post("/graphql", json={"query": bulk_create_mutation})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        bulk_data = data["data"]["createBulkRooms"]
        assert bulk_data["createdCount"] == 4
        assert len(bulk_data["rooms"]) == 4

        # 6. Update Room 101 status to OCCUPIED
        update_status_mutation = f"""
        mutation {{
            updateRoomStatus(roomId: {room_101_id}, status: OCCUPIED) {{
                id
                roomNumber
                status
            }}
        }}
        """
        res = await ac.post("/graphql", json={"query": update_status_mutation})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        assert data["data"]["updateRoomStatus"]["status"] == "OCCUPIED"

        # 7. Query hotelLayout
        layout_query = """
        query {
            hotelLayout {
                status
                totalFloors
                totalRooms
                availableRooms
                occupiedRooms
                cleaningRooms
                maintenanceRooms
                floors {
                    id
                    floorNumber
                    name
                    roomCount
                    rooms {
                        id
                        roomNumber
                        status
                    }
                }
            }
        }
        """
        res = await ac.post("/graphql", json={"query": layout_query})
        assert res.status_code == 200
        data = res.json()
        assert "errors" not in data, data.get("errors")
        layout = data["data"]["hotelLayout"]
        assert layout["totalFloors"] == 1
        assert layout["totalRooms"] == 5
        assert layout["availableRooms"] == 4
        assert layout["occupiedRooms"] == 1

        # 8. Test Delete Safeguards: Deleting occupied room must fail
        delete_room_mutation = f"""
        mutation {{
            deleteRoom(id: {room_101_id}) {{
                status
                message
            }}
        }}
        """
        res = await ac.post("/graphql", json={"query": delete_room_mutation})
        data = res.json()
        assert "errors" in data
        assert "OCCUPIED" in data["errors"][0]["message"]

        # 9. Test Delete Safeguards: Deleting floor with active rooms must fail
        delete_floor_mutation = f"""
        mutation {{
            deleteFloor(id: {floor_id}) {{
                status
                message
            }}
        }}
        """
        res = await ac.post("/graphql", json={"query": delete_floor_mutation})
        data = res.json()
        assert "errors" in data
        assert "active rooms lie on it" in data["errors"][0]["message"]


@pytest.mark.asyncio
async def test_multi_building_freehand_campus_designer():
    """End-to-end test for multi-building support, physical elevation floor reordering, free-hand custom rooms, utilities, and campus layout."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login as owner
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "owner@grandpalace.com",
            "password": "Owner@123"
        })
        assert login_res.status_code == 200
        ac.cookies.update(login_res.cookies)

        # 2. Create Building 1: Main Ocean Tower
        res = await ac.post("/graphql", json={"query": """
        mutation {
            createBuilding(input: { name: "Main Ocean Tower", code: "MOT", buildingType: "HOTEL_TOWER" }) {
                id
                name
                code
                buildingType
                displayOrder
            }
        }
        """})
        assert res.status_code == 200
        b1_data = res.json()["data"]["createBuilding"]
        b1_id = b1_data["id"]
        assert b1_data["name"] == "Main Ocean Tower"

        # 3. Create Building 2: Heritage Beach Villas
        res = await ac.post("/graphql", json={"query": """
        mutation {
            createBuilding(input: { name: "Heritage Beach Villas", code: "HBV", buildingType: "VILLAS" }) {
                id
                name
                code
            }
        }
        """})
        b2_data = res.json()["data"]["createBuilding"]
        b2_id = b2_data["id"]

        # 4. Create Floors in Building 1 (Floor 1: Ground Floor, Floor 2: Upper Deck)
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            f1: createFloor(input: {{ buildingId: {b1_id}, floorNumber: 1, name: "Ground Floor" }}) {{ id floorNumber }}
            f2: createFloor(input: {{ buildingId: {b1_id}, floorNumber: 2, name: "Upper Deck" }}) {{ id floorNumber }}
        }}
        """})
        floors_b1 = res.json()["data"]
        f1_id = floors_b1["f1"]["id"]
        f2_id = floors_b1["f2"]["id"]

        # 5. Test Physical Floor Reordering (Option 1: bottom-to-top swap)
        # Invert order: make f2 the bottom floor (1) and f1 the top floor (2)
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            reorderFloors(input: {{
                buildingId: {b1_id},
                floorIdsBottomToTop: [{f2_id}, {f1_id}]
            }}) {{
                id
                floorNumber
                name
            }}
        }}
        """})
        reordered = res.json()["data"]["reorderFloors"]
        assert len(reordered) == 2
        assert reordered[0]["id"] == f2_id
        assert reordered[0]["floorNumber"] == 1
        assert reordered[1]["id"] == f1_id
        assert reordered[1]["floorNumber"] == 2

        # 6. Create Free-Hand Custom Room (NO category, manual price 8500, custom amenities)
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            createRoom(input: {{
                floorId: {f2_id},
                roomNumber: "PENTHOUSE-101",
                customName: "Presidential Sky Suite",
                customPrice: 8500.0,
                customAmenities: ["Private Jacuzzi", "Sea View", "Butler Service"]
            }}) {{
                id
                roomNumber
                categoryId
                categoryName
                basePrice
                customName
                customPrice
                customAmenities
            }}
        }}
        """})
        room_data = res.json()["data"]["createRoom"]
        room_id = room_data["id"]
        assert room_data["roomNumber"] == "PENTHOUSE-101"
        assert room_data["categoryId"] is None
        assert room_data["basePrice"] == 8500.0
        assert "Private Jacuzzi" in room_data["customAmenities"]

        # 7. Create Floor in Building 2 and Drag/Move Room to Building 2's Floor
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            createFloor(input: {{ buildingId: {b2_id}, floorNumber: 1, name: "Villa Grounds" }}) {{ id }}
        }}
        """})
        villa_floor_id = res.json()["data"]["createFloor"]["id"]

        # Move room across buildings/floors
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            updateRoom(id: {room_id}, input: {{
                floorId: {villa_floor_id}
            }}) {{
                id
                floorId
                floorName
                buildingName
            }}
        }}
        """})
        moved_room = res.json()["data"]["updateRoom"]
        assert moved_room["floorId"] == villa_floor_id
        assert moved_room["buildingName"] == "Heritage Beach Villas"

        # 8. Create Utility in Building 1 (Infinity Pool) and test status toggling
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            createUtility(input: {{
                buildingId: {b1_id},
                name: "Rooftop Infinity Pool",
                utilityType: "POOL",
                status: OPEN,
                capacity: 50,
                operatingHours: "06:00 AM - 10:00 PM",
                amenities: ["Towel Service", "Poolside Bar"]
            }}) {{
                id
                name
                status
                capacity
                amenities
            }}
        }}
        """})
        pool_data = res.json()["data"]["createUtility"]
        pool_id = pool_data["id"]
        assert pool_data["status"] == "OPEN"
        assert "Poolside Bar" in pool_data["amenities"]

        # Toggle status to CLEANING
        res = await ac.post("/graphql", json={"query": f"""
        mutation {{
            updateUtilityStatus(id: {pool_id}, status: CLEANING) {{
                id
                status
            }}
        }}
        """})
        assert res.json()["data"]["updateUtilityStatus"]["status"] == "CLEANING"

        # 9. Query Full Campus Layout
        res = await ac.post("/graphql", json={"query": """
        query {
            campusLayout {
                status
                totalBuildings
                totalFloors
                totalRooms
                totalUtilities
                buildings {
                    building {
                        id
                        name
                        buildingType
                    }
                    totalFloors
                    totalRooms
                    floors {
                        id
                        floorNumber
                        name
                        rooms {
                            id
                            roomNumber
                            basePrice
                        }
                    }
                    utilities {
                        id
                        name
                        status
                    }
                }
            }
        }
        """})
        campus = res.json()["data"]["campusLayout"]
        assert campus["status"] == "success"
        assert campus["totalBuildings"] == 2
        assert campus["totalRooms"] == 1
        assert campus["totalUtilities"] == 1

