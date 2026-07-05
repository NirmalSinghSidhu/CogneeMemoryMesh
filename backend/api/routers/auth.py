from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.database.connection import get_db
from backend.models.auth import (
    AuthResponse,
    LoginInput,
    MeResponse,
    RegisterInput,
    TenantResponse,
    UserResponse,
)
from backend.services.auth_service import authenticate_user, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user, tenant, token: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        user=UserResponse(id=user.id, email=user.email, name=user.name),
        tenant=TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug),
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterInput, db: AsyncSession = Depends(get_db)):
    try:
        user, tenant = await register_user(
            db,
            email=data.email,
            password=data.password,
            name=data.name,
            workspace_name=data.workspace_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    return _auth_response(user, tenant, token)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginInput, db: AsyncSession = Depends(get_db)):
    result = await authenticate_user(db, data.email, data.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    user, tenant = result
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    return _auth_response(user, tenant, token)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from backend.database.connection import TenantModel, UserModel

    user = (
        await db.execute(select(UserModel).where(UserModel.id == current_user.user_id))
    ).scalar_one()
    tenant = (
        await db.execute(select(TenantModel).where(TenantModel.id == current_user.tenant_id))
    ).scalar_one()

    return MeResponse(
        user=UserResponse(id=user.id, email=user.email, name=user.name),
        tenant=TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug),
    )
