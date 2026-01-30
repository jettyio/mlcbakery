"""Tests for mlcbakery/api/dependencies.py"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import uuid

from mlcbakery.models import Collection, ApiKey
from mlcbakery.api.dependencies import (
    get_auth,
    verify_auth,
    optional_auth,
    verify_auth_with_write_access,
    verify_auth_with_access_level,
    verify_api_key_for_collection,
    apply_auth_to_stmt,
    get_user_collection_id,
    get_flexible_auth,
    verify_collection_access_for_api_key,
    get_auth_for_stmt,
)
from mlcbakery.api.access_level import AccessLevel, AccessType
from mlcbakery.auth.passthrough_strategy import (
    PassthroughStrategy,
    sample_org_token,
    sample_user_token,
    authorization_headers,
)
from mlcbakery.auth.admin_token_strategy import AdminTokenStrategy
from conftest import TEST_ADMIN_TOKEN


# --- Helper functions ---

def make_credentials(token: str) -> HTTPAuthorizationCredentials:
    """Create HTTPAuthorizationCredentials from a token string."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def get_test_strategies():
    """Get test auth strategies."""
    return [
        AdminTokenStrategy(TEST_ADMIN_TOKEN),
        PassthroughStrategy()
    ]


async def create_collection_with_api_key(db_session: AsyncSession, collection_name: str):
    """Helper to create a collection and API key."""
    collection = Collection(name=collection_name, owner_identifier="test_owner")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)

    return collection, api_key, plaintext_key


# --- Tests for get_auth ---

@pytest.mark.asyncio
async def test_get_auth_with_admin_token():
    """Test get_auth returns admin payload for admin token."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await get_auth(credentials, strategies)

    assert result is not None
    assert result["access_level"] == AccessLevel.ADMIN
    assert result["access_type"] == AccessType.ADMIN


@pytest.mark.asyncio
async def test_get_auth_with_passthrough_token():
    """Test get_auth returns payload for passthrough JWT token."""
    jwt_token = sample_org_token()
    credentials = make_credentials(jwt_token)
    strategies = get_test_strategies()

    result = await get_auth(credentials, strategies)

    assert result is not None
    assert "access_level" in result
    assert "access_type" in result


@pytest.mark.asyncio
async def test_get_auth_with_invalid_token():
    """Test get_auth returns None for invalid token."""
    credentials = make_credentials("invalid_token_that_matches_nothing")
    # Use only admin strategy so passthrough doesn't match
    strategies = [AdminTokenStrategy(TEST_ADMIN_TOKEN)]

    result = await get_auth(credentials, strategies)

    assert result is None


# --- Tests for verify_auth ---

@pytest.mark.asyncio
async def test_verify_auth_with_valid_token():
    """Test verify_auth succeeds with valid token."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await verify_auth(credentials, strategies)

    assert result is not None
    assert result["access_level"] == AccessLevel.ADMIN


@pytest.mark.asyncio
async def test_verify_auth_with_invalid_token():
    """Test verify_auth raises 401 for invalid token."""
    credentials = make_credentials("invalid_token")
    strategies = [AdminTokenStrategy(TEST_ADMIN_TOKEN)]

    with pytest.raises(HTTPException) as exc_info:
        await verify_auth(credentials, strategies)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# --- Tests for optional_auth ---

@pytest.mark.asyncio
async def test_optional_auth_with_no_credentials():
    """Test optional_auth returns None when no credentials provided."""
    strategies = get_test_strategies()

    result = await optional_auth(None, strategies)

    assert result is None


@pytest.mark.asyncio
async def test_optional_auth_with_valid_credentials():
    """Test optional_auth returns payload when valid credentials provided."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await optional_auth(credentials, strategies)

    assert result is not None
    assert result["access_level"] == AccessLevel.ADMIN


# --- Tests for verify_auth_with_write_access ---

@pytest.mark.asyncio
async def test_verify_auth_with_write_access_admin():
    """Test verify_auth_with_write_access succeeds for admin."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await verify_auth_with_write_access(credentials, strategies)

    assert result is not None
    assert result["access_level"] == AccessLevel.ADMIN


@pytest.mark.asyncio
async def test_verify_auth_with_write_access_read_only_user():
    """Test verify_auth_with_write_access raises 403 for read-only user."""
    # Create a token with READ access only (org:member role)
    jwt_token = sample_org_token(org_role="org:member")
    credentials = make_credentials(jwt_token)
    strategies = get_test_strategies()

    with pytest.raises(HTTPException) as exc_info:
        await verify_auth_with_write_access(credentials, strategies)

    assert exc_info.value.status_code == 403
    assert "Access level WRITE required" in exc_info.value.detail


# --- Tests for verify_auth_with_access_level ---

@pytest.mark.asyncio
async def test_verify_auth_with_access_level_read():
    """Test verify_auth_with_access_level succeeds for READ level."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await verify_auth_with_access_level(
        AccessLevel.READ, credentials, strategies
    )

    assert result is not None


@pytest.mark.asyncio
async def test_verify_auth_with_access_level_admin():
    """Test verify_auth_with_access_level succeeds for ADMIN level with admin token."""
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await verify_auth_with_access_level(
        AccessLevel.ADMIN, credentials, strategies
    )

    assert result is not None
    assert result["access_level"] == AccessLevel.ADMIN


@pytest.mark.asyncio
async def test_verify_auth_with_access_level_insufficient():
    """Test verify_auth_with_access_level raises 403 for insufficient level."""
    jwt_token = sample_org_token(org_role="org:member")  # READ access
    credentials = make_credentials(jwt_token)
    strategies = get_test_strategies()

    with pytest.raises(HTTPException) as exc_info:
        await verify_auth_with_access_level(
            AccessLevel.ADMIN, credentials, strategies
        )

    assert exc_info.value.status_code == 403


# --- Tests for verify_api_key_for_collection ---

@pytest.mark.asyncio
async def test_verify_api_key_for_collection_valid_key(db_session: AsyncSession):
    """Test verify_api_key_for_collection returns collection for valid key."""
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection, api_key_obj, plaintext_key = await create_collection_with_api_key(
        db_session, collection_name
    )

    credentials = make_credentials(plaintext_key)
    result = await verify_api_key_for_collection(credentials, db_session)

    assert result is not None
    coll, key = result
    assert coll.id == collection.id
    assert key.id == api_key_obj.id


@pytest.mark.asyncio
async def test_verify_api_key_for_collection_admin_token(db_session: AsyncSession, monkeypatch):
    """Test verify_api_key_for_collection returns None for admin token."""
    # Patch the ADMIN_AUTH_TOKEN in the dependencies module to match TEST_ADMIN_TOKEN
    import mlcbakery.api.dependencies as deps
    monkeypatch.setattr(deps, 'ADMIN_AUTH_TOKEN', TEST_ADMIN_TOKEN)

    credentials = make_credentials(TEST_ADMIN_TOKEN)
    result = await verify_api_key_for_collection(credentials, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_verify_api_key_for_collection_invalid_format(db_session: AsyncSession):
    """Test verify_api_key_for_collection raises 401 for invalid format."""
    credentials = make_credentials("not_an_mlc_key")

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key_for_collection(credentials, db_session)

    assert exc_info.value.status_code == 401
    assert "Invalid API key format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_for_collection_nonexistent_key(db_session: AsyncSession):
    """Test verify_api_key_for_collection raises 401 for nonexistent key."""
    credentials = make_credentials("mlc_nonexistent12345678901234567890")

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key_for_collection(credentials, db_session)

    assert exc_info.value.status_code == 401
    assert "Invalid or inactive API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_for_collection_inactive_key(db_session: AsyncSession):
    """Test verify_api_key_for_collection raises 401 for inactive key."""
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection, api_key_obj, plaintext_key = await create_collection_with_api_key(
        db_session, collection_name
    )

    # Deactivate the key
    api_key_obj.is_active = False
    await db_session.commit()

    credentials = make_credentials(plaintext_key)

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key_for_collection(credentials, db_session)

    assert exc_info.value.status_code == 401
    assert "Invalid or inactive API key" in exc_info.value.detail


# --- Tests for apply_auth_to_stmt ---

def test_apply_auth_to_stmt_admin():
    """Test apply_auth_to_stmt returns stmt unchanged for admin."""
    stmt = select(Collection)
    auth = {"access_type": AccessType.ADMIN, "identifier": "admin"}

    result = apply_auth_to_stmt(stmt, auth)

    # Admin should get the same statement (no filtering)
    assert str(result) == str(stmt)


def test_apply_auth_to_stmt_regular_user():
    """Test apply_auth_to_stmt adds owner filter for regular user."""
    stmt = select(Collection)
    auth = {"access_type": AccessType.PERSONAL, "identifier": "user123"}

    result = apply_auth_to_stmt(stmt, auth)

    # Should have WHERE clause for owner_identifier
    result_str = str(result)
    assert "owner_identifier" in result_str


def test_apply_auth_to_stmt_org_user():
    """Test apply_auth_to_stmt adds owner filter for org user."""
    stmt = select(Collection)
    auth = {"access_type": AccessType.ORG, "identifier": "org123"}

    result = apply_auth_to_stmt(stmt, auth)

    # Should have WHERE clause for owner_identifier
    result_str = str(result)
    assert "owner_identifier" in result_str


# --- Tests for get_user_collection_id ---

@pytest.mark.asyncio
async def test_get_user_collection_id_unauthenticated(db_session: AsyncSession):
    """Test get_user_collection_id returns empty list for unauthenticated user."""
    result = await get_user_collection_id(None, db_session)

    assert result == []


@pytest.mark.asyncio
async def test_get_user_collection_id_admin(db_session: AsyncSession):
    """Test get_user_collection_id returns None for admin."""
    auth = {"access_type": AccessType.ADMIN, "identifier": "admin"}

    result = await get_user_collection_id(auth, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_get_user_collection_id_user_with_one_collection(db_session: AsyncSession):
    """Test get_user_collection_id returns single ID for user with one collection."""
    user_identifier = f"user-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=f"coll-{uuid.uuid4().hex[:8]}", owner_identifier=user_identifier)
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    auth = {"access_type": AccessType.PERSONAL, "identifier": user_identifier}
    result = await get_user_collection_id(auth, db_session)

    assert result == collection.id


@pytest.mark.asyncio
async def test_get_user_collection_id_user_with_multiple_collections(db_session: AsyncSession):
    """Test get_user_collection_id returns list of IDs for user with multiple collections."""
    user_identifier = f"user-{uuid.uuid4().hex[:8]}"
    collection1 = Collection(name=f"coll1-{uuid.uuid4().hex[:8]}", owner_identifier=user_identifier)
    collection2 = Collection(name=f"coll2-{uuid.uuid4().hex[:8]}", owner_identifier=user_identifier)
    db_session.add_all([collection1, collection2])
    await db_session.commit()
    await db_session.refresh(collection1)
    await db_session.refresh(collection2)

    auth = {"access_type": AccessType.PERSONAL, "identifier": user_identifier}
    result = await get_user_collection_id(auth, db_session)

    assert isinstance(result, list)
    assert len(result) == 2
    assert collection1.id in result
    assert collection2.id in result


@pytest.mark.asyncio
async def test_get_user_collection_id_user_with_no_collections(db_session: AsyncSession):
    """Test get_user_collection_id returns None for user with no collections."""
    auth = {"access_type": AccessType.PERSONAL, "identifier": "user_with_no_collections"}
    result = await get_user_collection_id(auth, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_get_user_collection_id_no_identifier(db_session: AsyncSession):
    """Test get_user_collection_id returns None when no identifier in auth."""
    auth = {"access_type": AccessType.PERSONAL}  # No identifier
    result = await get_user_collection_id(auth, db_session)

    assert result is None


# --- Tests for get_flexible_auth ---

@pytest.mark.asyncio
async def test_get_flexible_auth_with_api_key(db_session: AsyncSession):
    """Test get_flexible_auth returns api_key type for mlc_ tokens."""
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection, api_key_obj, plaintext_key = await create_collection_with_api_key(
        db_session, collection_name
    )

    credentials = make_credentials(plaintext_key)
    strategies = get_test_strategies()

    result = await get_flexible_auth(credentials, db_session, strategies)

    assert result[0] == 'api_key'
    coll, key = result[1]
    assert coll.id == collection.id


@pytest.mark.asyncio
async def test_get_flexible_auth_with_admin_api_key(db_session: AsyncSession):
    """Test get_flexible_auth returns api_key with None for admin token."""
    # Admin token that starts with mlc_ (if it does)
    # Actually, admin token doesn't start with mlc_, so this tests JWT path
    # Let's create a test where admin token is passed
    credentials = make_credentials(TEST_ADMIN_TOKEN)
    strategies = get_test_strategies()

    result = await get_flexible_auth(credentials, db_session, strategies)

    # Admin token doesn't start with mlc_, so it goes through JWT path
    assert result[0] == 'jwt'
    assert result[1]["access_level"] == AccessLevel.ADMIN


@pytest.mark.asyncio
async def test_get_flexible_auth_with_jwt_token(db_session: AsyncSession):
    """Test get_flexible_auth returns jwt type for JWT tokens."""
    jwt_token = sample_org_token()
    credentials = make_credentials(jwt_token)
    strategies = get_test_strategies()

    result = await get_flexible_auth(credentials, db_session, strategies)

    assert result[0] == 'jwt'
    assert "access_level" in result[1]


@pytest.mark.asyncio
async def test_get_flexible_auth_with_invalid_api_key(db_session: AsyncSession):
    """Test get_flexible_auth raises 401 for invalid API key."""
    credentials = make_credentials("mlc_invalid12345678901234567890123")
    strategies = get_test_strategies()

    with pytest.raises(HTTPException) as exc_info:
        await get_flexible_auth(credentials, db_session, strategies)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_flexible_auth_with_invalid_jwt(db_session: AsyncSession):
    """Test get_flexible_auth raises 401 for invalid JWT."""
    credentials = make_credentials("invalid_jwt_token_here")
    # Use only admin strategy to ensure passthrough doesn't match
    strategies = [AdminTokenStrategy(TEST_ADMIN_TOKEN)]

    with pytest.raises(HTTPException) as exc_info:
        await get_flexible_auth(credentials, db_session, strategies)

    assert exc_info.value.status_code == 401
    assert "Invalid API key or JWT token" in exc_info.value.detail


# --- Tests for verify_collection_access_for_api_key ---

def test_verify_collection_access_for_api_key_jwt_auth():
    """Test verify_collection_access_for_api_key is no-op for JWT auth."""
    auth_data = ('jwt', {"access_level": AccessLevel.READ})

    # Should not raise
    verify_collection_access_for_api_key(auth_data, "any_collection")


def test_verify_collection_access_for_api_key_admin_api_key():
    """Test verify_collection_access_for_api_key allows admin API key."""
    auth_data = ('api_key', None)

    # Should not raise
    verify_collection_access_for_api_key(auth_data, "any_collection")


def test_verify_collection_access_for_api_key_valid_collection():
    """Test verify_collection_access_for_api_key allows matching collection."""
    mock_collection = MagicMock()
    mock_collection.name = "my_collection"
    mock_api_key = MagicMock()
    auth_data = ('api_key', (mock_collection, mock_api_key))

    # Should not raise
    verify_collection_access_for_api_key(auth_data, "my_collection")


def test_verify_collection_access_for_api_key_wrong_collection():
    """Test verify_collection_access_for_api_key raises 403 for wrong collection."""
    mock_collection = MagicMock()
    mock_collection.name = "collection_a"
    mock_api_key = MagicMock()
    auth_data = ('api_key', (mock_collection, mock_api_key))

    with pytest.raises(HTTPException) as exc_info:
        verify_collection_access_for_api_key(auth_data, "collection_b")

    assert exc_info.value.status_code == 403
    assert "API key not valid for this collection" in exc_info.value.detail


# --- Tests for get_auth_for_stmt ---

def test_get_auth_for_stmt_admin_api_key():
    """Test get_auth_for_stmt returns ADMIN access for admin API key."""
    auth_data = ('api_key', None)

    result = get_auth_for_stmt(auth_data)

    assert result["access_type"] == AccessType.ADMIN


def test_get_auth_for_stmt_collection_api_key():
    """Test get_auth_for_stmt returns ADMIN access for collection API key."""
    mock_collection = MagicMock()
    mock_api_key = MagicMock()
    auth_data = ('api_key', (mock_collection, mock_api_key))

    result = get_auth_for_stmt(auth_data)

    assert result["access_type"] == AccessType.ADMIN


def test_get_auth_for_stmt_jwt():
    """Test get_auth_for_stmt returns jwt payload as-is."""
    jwt_payload = {
        "access_level": AccessLevel.READ,
        "access_type": AccessType.PERSONAL,
        "identifier": "user123"
    }
    auth_data = ('jwt', jwt_payload)

    result = get_auth_for_stmt(auth_data)

    assert result == jwt_payload
    assert result["access_type"] == AccessType.PERSONAL
    assert result["identifier"] == "user123"
