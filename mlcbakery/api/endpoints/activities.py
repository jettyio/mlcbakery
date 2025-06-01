from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Sequence
from fastapi.security import HTTPAuthorizationCredentials

from ...database import get_async_db
from ...models import Activity
from ...schemas.activity import ActivityCreate, ActivityResponse
from mlcbakery.api.dependencies import verify_admin_token

router = APIRouter()

# TODO: Add endpoints for activities