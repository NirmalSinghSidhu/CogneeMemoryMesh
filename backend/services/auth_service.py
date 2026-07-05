import re
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import TenantModel, TenantMembershipModel, UserModel
from backend.utils.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, user_id: int, tenant_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or secrets.token_hex(4)


async def unique_tenant_slug(db: AsyncSession, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    n = 1
    while True:
        existing = (
            await db.execute(select(TenantModel.id).where(TenantModel.slug == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        n += 1
        candidate = f"{slug}-{n}"


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    name: str,
    workspace_name: str | None,
) -> tuple[UserModel, TenantModel]:
    existing = (
        await db.execute(select(UserModel).where(UserModel.email == email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise ValueError("Email already registered")

    tenant_name = workspace_name or f"{name}'s Workspace"
    slug = await unique_tenant_slug(db, tenant_name)

    tenant = TenantModel(name=tenant_name, slug=slug)
    db.add(tenant)
    await db.flush()

    user = UserModel(
        email=email.lower(),
        hashed_password=hash_password(password),
        name=name,
    )
    db.add(user)
    await db.flush()

    membership = TenantMembershipModel(
        user_id=user.id,
        tenant_id=tenant.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()

    return user, tenant


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[UserModel, TenantModel] | None:
    user = (
        await db.execute(select(UserModel).where(UserModel.email == email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None

    row = (
        await db.execute(
            select(TenantModel)
            .join(TenantMembershipModel, TenantMembershipModel.tenant_id == TenantModel.id)
            .where(TenantMembershipModel.user_id == user.id)
            .order_by(TenantMembershipModel.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return user, row
