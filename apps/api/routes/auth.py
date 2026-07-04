import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import (
    AuthContext,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
    _decode_token,
)
from packages.db import get_session
from packages.db.models.tenant import Organization, Project, User
from packages.shared.envelope import ApiResponse
from packages.shared.errors import AuthenticationError, ConflictError

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    org_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register")
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        # Check for existing user
        existing = await session.scalar(select(User).where(User.email == body.email))
        if existing:
            raise ConflictError(f"Email '{body.email}' is already registered")

        # Create org, project, and user in one transaction
        org = Organization(
            name=body.org_name,
            slug=body.org_name.lower().replace(" ", "-")[:60],
        )
        session.add(org)
        await session.flush()

        # Every org gets a default project
        project = Project(
            name="Default",
            slug="default",
            organization_id=org.id,
        )
        session.add(project)

        user = User(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
            organization_id=org.id,
        )
        session.add(user)
        await session.flush()
        await session.commit() # commit here

        tokens = AuthTokens(
            access_token=create_access_token(user.id, org.id),
            refresh_token=create_refresh_token(user.id, org.id),
        )
        return ApiResponse.ok(tokens.model_dump())
    except Exception as e:
        import traceback
        print("EXCEPTION IN REGISTER:", repr(e))
        traceback.print_exc()
        raise


@router.post("/login")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    user = await session.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    tokens = AuthTokens(
        access_token=create_access_token(user.id, user.organization_id),
        refresh_token=create_refresh_token(user.id, user.organization_id),
    )
    return ApiResponse.ok(tokens.model_dump())


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    payload = _decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Expected refresh token")

    tokens = AuthTokens(
        access_token=create_access_token(
            uuid.UUID(payload["sub"]),
            uuid.UUID(payload["org"]),
        ),
        refresh_token=body.refresh_token,  # reuse the same refresh token
    )
    return ApiResponse.ok(tokens.model_dump())


@router.get("/me")
async def get_me(
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, auth.user_id)
    if not user:
        raise AuthenticationError("User not found")

    return ApiResponse.ok({
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "organization_id": str(user.organization_id),
    })
