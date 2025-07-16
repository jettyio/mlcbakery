import pytest
import httpx # For making async HTTP requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mlcbakery.main import app # Your FastAPI app instance
from mlcbakery.database import get_async_db, Base, engine # Assuming these are your DB setup
from mlcbakery.models import Collection, Entity, Activity, EntityRelationship, Dataset
from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers

# Define headers globally or pass them around
AUTH_HEADERS = authorization_headers(sample_org_token())


# pytest-asyncio decorator for async test functions
pytestmark = pytest.mark.asyncio

TEST_COLLECTION_NAME_1 = "test_link_coll_1"
TEST_COLLECTION_NAME_2 = "test_link_coll_2"
SOURCE_ENTITY_NAME = "source_ds_1"
TARGET_ENTITY_NAME_1 = "target_ds_1"
TARGET_ENTITY_NAME_2 = "target_ds_2"
ENTITY_TYPE_DATASET = "dataset"
ACTIVITY_NAME_GENERATED = "generated_test_link"
ACTIVITY_NAME_INGESTED = "ingested_test_link"


async def clear_db(session: AsyncSession):
    await session.execute(select(EntityRelationship).delete())
    await session.execute(select(Activity).delete())
    await session.execute(select(Entity).delete())
    await session.execute(select(Collection).delete())
    # Add other tables if necessary to clean up, be careful with order due to FKs
    await session.commit()

# @pytest.fixture(scope="function", autouse=True)
# async def db_session_for_tests():
#     """Override get_async_db dependency for tests and handle setup/teardown."""
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#         # Ensure admin user exists for endpoints requiring auth
#         # This might need to be adjusted based on how your admin user is created/checked
#         temp_session_generator = get_async_db()
#         temp_session = await anext(temp_session_generator)
#         await temp_session.commit()
#         await temp_session.close()

    
#     # # This session is what your test functions will use
#     db = get_async_db()
#     session = await anext(db)
#     await clear_db(session) # Clear relevant tables before each test

#     # # Create initial test data
#     # coll1 = Collection(name=TEST_COLLECTION_NAME_1, description="Test collection 1 for linking")
#     # coll2 = Collection(name=TEST_COLLECTION_NAME_2, description="Test collection 2 for linking")
#     # session.add_all([coll1, coll2])
#     # await session.commit()
#     # await session.refresh(coll1)
#     # await session.refresh(coll2)

#     # source_entity = Entity(name=SOURCE_ENTITY_NAME, entity_type=ENTITY_TYPE_DATASET, collection_id=coll1.id)
#     # target_entity1 = Entity(name=TARGET_ENTITY_NAME_1, entity_type=ENTITY_TYPE_DATASET, collection_id=coll1.id)
#     # target_entity2 = Entity(name=TARGET_ENTITY_NAME_2, entity_type=ENTITY_TYPE_DATASET, collection_id=coll2.id)
#     # session.add_all([source_entity, target_entity1, target_entity2])
#     # await session.commit()
#     # await session.refresh(source_entity)
#     # await session.refresh(target_entity1)
#     # await session.refresh(target_entity2)
    
#     yield session # This is where the test runs

#     # # Teardown: Clear data after tests if needed, or drop tables
#     # await clear_db(session)
#     # await session.close()
#     # If you created all tables: await conn.run_sync(Base.metadata.drop_all) inside engine.begin()

async def _setup_test_data_collections(db_session: AsyncSession) -> tuple[Collection, Collection]:
    coll1 = Collection(name=TEST_COLLECTION_NAME_1, description="Test collection 1 for linking", owner_identifier="test-owner-1")
    coll2 = Collection(name=TEST_COLLECTION_NAME_2, description="Test collection 2 for linking", owner_identifier="test-owner-2")
    db_session.add_all([coll1, coll2])
    await db_session.commit()
    await db_session.refresh(coll1)
    await db_session.refresh(coll2)
    return coll1, coll2

async def _setup_test_data_entities(db_session: AsyncSession, coll1: Collection, coll2: Collection) -> tuple[Dataset, Dataset, Dataset]:
    source_entity = Dataset(name=SOURCE_ENTITY_NAME, collection_id=coll1.id, data_path="path/to/source_entity", format="json")
    target_entity1 = Dataset(name=TARGET_ENTITY_NAME_1, collection_id=coll1.id, data_path="path/to/target_entity_1", format="json")
    target_entity2 = Dataset(name=TARGET_ENTITY_NAME_2, collection_id=coll2.id, data_path="path/to/target_entity_2", format="json")
    db_session.add_all([source_entity, target_entity1, target_entity2])
    await db_session.commit()
    await db_session.refresh(source_entity)
    await db_session.refresh(target_entity1)
    await db_session.refresh(target_entity2)
    return source_entity, target_entity1, target_entity2

@pytest.mark.asyncio
async def test_create_entity_link_success(db_session: AsyncSession):
    """Test successful creation of an entity link with source and target."""
    # Create initial test data
    coll1, coll2 = await _setup_test_data_collections(db_session)
    source_entity, target_entity1, target_entity2 = await _setup_test_data_entities(db_session, coll1, coll2)
    
    # Verify in DB
    source_entity_db = (await db_session.execute(select(Dataset).where(Dataset.name == SOURCE_ENTITY_NAME))).scalar_one()
    target_entity_db = (await db_session.execute(select(Dataset).where(Dataset.name == TARGET_ENTITY_NAME_1))).scalar_one()
    
    assert source_entity_db is not None
    assert target_entity_db is not None

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "source_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{SOURCE_ENTITY_NAME}",
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{TARGET_ENTITY_NAME_1}",
            "activity_name": ACTIVITY_NAME_GENERATED
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 201
    data = response.json()
    assert data["source_entity_id"] is not None
    assert data["target_entity_id"] is not None
    assert data["activity_name"] == ACTIVITY_NAME_GENERATED

    link = (await db_session.execute(select(EntityRelationship).where(EntityRelationship.id == data["id"]))).scalar_one()
    assert link.source_entity_id == source_entity_db.id
    assert link.target_entity_id == target_entity_db.id
    assert link.activity_name == ACTIVITY_NAME_GENERATED


async def test_create_entity_link_no_source_success(db_session: AsyncSession):
    """Test successful creation of an entity link with only a target (e.g., initial creation)."""
    coll1, coll2 = await _setup_test_data_collections(db_session) # Ensure collections are created
    await _setup_test_data_entities(db_session, coll1, coll2)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "source_entity_str": None,
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_2}/{TARGET_ENTITY_NAME_2}",
            "activity_name": ACTIVITY_NAME_INGESTED
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 201
    data = response.json()
    assert data["source_entity_id"] is None
    assert data["target_entity_id"] is not None
    assert data["activity_name"] == ACTIVITY_NAME_INGESTED # Added assertion for activity_name in response

    target_entity_db = (await db_session.execute(select(Dataset).where(Dataset.name == TARGET_ENTITY_NAME_2))).scalar_one()

    link = (await db_session.execute(select(EntityRelationship).where(EntityRelationship.id == data["id"]))).scalar_one()
    assert link.target_entity_id == target_entity_db.id
    assert link.activity_name == ACTIVITY_NAME_INGESTED


async def test_create_entity_link_reuse_activity(db_session: AsyncSession):
    """Test that multiple entity links can be created with the same activity name."""
    # Setup initial data
    coll1, coll2 = await _setup_test_data_collections(db_session)
    await _setup_test_data_entities(db_session, coll1, coll2)
    
    activity_to_reuse = "reused_activity_name_test"

    # First, create a link
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload1 = {
            "source_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{SOURCE_ENTITY_NAME}",
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{TARGET_ENTITY_NAME_1}",
            "activity_name": activity_to_reuse
        }
        response1 = await ac.post("/api/v1/entity-relationships/", json=payload1, headers=AUTH_HEADERS)
        assert response1.status_code == 201
        response1_data = response1.json()
        assert response1_data["activity_name"] == activity_to_reuse
        link1_id = response1_data["id"]

    # Second, create another link with the same activity name
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload2 = {
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_2}/{TARGET_ENTITY_NAME_2}",
            "activity_name": activity_to_reuse # Same activity name
        }
        response2 = await ac.post("/api/v1/entity-relationships/", json=payload2, headers=AUTH_HEADERS)
        assert response2.status_code == 201
        response2_data = response2.json()
        assert response2_data["activity_name"] == activity_to_reuse
        link2_id = response2_data["id"]

    # Verify in the database that both links have the same activity name
    link1_db = (await db_session.execute(select(EntityRelationship).where(EntityRelationship.id == link1_id))).scalar_one_or_none()
    link2_db = (await db_session.execute(select(EntityRelationship).where(EntityRelationship.id == link2_id))).scalar_one_or_none()

    assert link1_db is not None
    assert link2_db is not None
    assert link1_db.activity_name == activity_to_reuse
    assert link2_db.activity_name == activity_to_reuse


async def test_create_entity_link_target_not_found(db_session: AsyncSession):
    """Test error when target entity is not found."""
    await _setup_test_data_entities(db_session, *(await _setup_test_data_collections(db_session)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/non_existent_target",
            "activity_name": "test_fail_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 404
    assert "Target entity 'non_existent_target'" in response.json()["detail"]
    assert "not found in collection" in response.json()["detail"]

async def test_create_entity_link_source_not_found(db_session: AsyncSession):
    """Test error when source entity is not found."""
    await _setup_test_data_entities(db_session, *(await _setup_test_data_collections(db_session)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "source_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/non_existent_source",
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{TARGET_ENTITY_NAME_1}",
            "activity_name": "test_fail_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 404
    assert "Source entity 'non_existent_source'" in response.json()["detail"]
    assert "not found in collection" in response.json()["detail"]

async def test_create_entity_link_collection_not_found_for_target(db_session: AsyncSession):
    """Test error when collection for target entity is not found."""
    await _setup_test_data_entities(db_session, *(await _setup_test_data_collections(db_session)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/non_existent_collection/{TARGET_ENTITY_NAME_1}",
            "activity_name": "test_fail_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 404
    assert "Collection 'non_existent_collection' for target entity" in response.json()["detail"]

async def test_create_entity_link_invalid_format_target(db_session: AsyncSession):
    """Test error when target entity string format is invalid."""
    await _setup_test_data_entities(db_session, *(await _setup_test_data_collections(db_session)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "target_entity_str": "invalid_format",
            "activity_name": "test_fail_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 400 # Bad Request
    assert "Invalid target entity string format: 'invalid_format'" in response.json()["detail"]

async def test_create_entity_link_invalid_format_source(db_session: AsyncSession):
    """Test error when source entity string format is invalid."""
    await _setup_test_data_entities(db_session, *(await _setup_test_data_collections(db_session)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "source_entity_str": "invalid_format",
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{TARGET_ENTITY_NAME_1}",
            "activity_name": "test_fail_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload, headers=AUTH_HEADERS)
        
    assert response.status_code == 400 # Bad Request
    assert "Invalid source entity string format: 'invalid_format'" in response.json()["detail"]

# TODO: Add more tests as needed, e.g., for different entity types if your _resolve_entity_from_string supports more.
# TODO: Consider testing concurrent requests if that's a concern.
# TODO: Test auth failure if AUTH_HEADERS were not provided (though router has dependency)
async def test_create_entity_link_unauthorized(db_session: AsyncSession):
    """Test request without authorization header."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "target_entity_str": f"{ENTITY_TYPE_DATASET}/{TEST_COLLECTION_NAME_1}/{TARGET_ENTITY_NAME_1}",
            "activity_name": "unauth_activity"
        }
        response = await ac.post("/api/v1/entity-relationships/", json=payload) # No AUTH_HEADERS
        
    assert response.status_code == 403 # Unauthorized
    assert "Not authenticated" in response.json()["detail"] or "Forbidden" in response.json()["detail"] 
