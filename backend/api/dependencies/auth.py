from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import MeetingModel, get_db
from backend.services.auth_service import ALGORITHM
from backend.utils.config import settings

security = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: int
    tenant_id: int
    email: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        tenant_id = int(payload["tenant_id"])
        email = payload["email"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(user_id=user_id, tenant_id=tenant_id, email=email)


async def get_meeting_for_tenant(
    db: AsyncSession, meeting_id: int, tenant_id: int
) -> MeetingModel:
    result = await db.execute(
        select(MeetingModel).where(
            MeetingModel.id == meeting_id,
            MeetingModel.tenant_id == tenant_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


def tenant_dataset_name(tenant_id: int, meeting_id: int) -> str:
    return f"tenant_{tenant_id}_meeting_{meeting_id}"
