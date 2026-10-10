from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status, Response
from typing import Optional, Dict, Any
from app.models import User, UserClientOutletMapping, Outlet
from app.core.security import verify_password, create_jwt_token, decrypt_phone
from app.core.context import UserContext
from app.config import settings

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetches user by email from database."""
    query = select(User).where(User.email == email, User.is_active == True)
    result = await db.execute(query)
    return result.scalars().first()

async def get_user_outlets(db: AsyncSession, user_id: str) -> list[str]:
    """Fetches list of outlet IDs mapped to a user."""
    query = select(UserClientOutletMapping.outlet_id).where(UserClientOutletMapping.user_id == user_id)
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_primary_outlet_id(db: AsyncSession, user_id: str) -> Optional[str]:
    """Fetches the primary outlet ID mapped to a user."""
    query = select(UserClientOutletMapping.outlet_id).where(
        UserClientOutletMapping.user_id == user_id,
        UserClientOutletMapping.is_primary == True
    )
    result = await db.execute(query)
    return result.scalars().first()

async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    target_outlet_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Authenticates user, enforces Staff Login Guard, and builds JWT payload.
    """
    # 1. Fetch user
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # 2. STRICT LOGIN GUARD: Block STAFF accounts from web login
    if user.role == "STAFF" or not user.can_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts are restricted from web dashboard login. Stored for WhatsApp ops only."
        )

    # 3. Resolve user's allowed outlets
    allowed_outlets = await get_user_outlets(db, user.id)
    if not allowed_outlets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no assigned hotel outlets"
        )

    # 4. Resolve active outlet
    active_outlet = target_outlet_id or await get_primary_outlet_id(db, user.id) or allowed_outlets[0]
    if active_outlet not in allowed_outlets and user.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to target outlet '{active_outlet}'"
        )

    # 5. Build JWT Payload
    jwt_payload = {
        "sub": user.id,
        "client_id": user.client_id,
        "outlet_id": active_outlet,
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "allowed_outlets": allowed_outlets
    }

    token = create_jwt_token(jwt_payload)

    return {
        "token": token,
        "user_context": UserContext(
            user_id=user.id,
            client_id=user.client_id,
            outlet_id=active_outlet,
            role=user.role,
            email=user.email,
            name=user.name,
            allowed_outlets=allowed_outlets
        )
    }

def set_auth_cookie(response: Response, token: str) -> None:
    """Sets HttpOnly secure auth cookie on response object."""
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )

def clear_auth_cookie(response: Response) -> None:
    """Clears HttpOnly auth cookie on logout."""
    response.delete_cookie(key="access_token", path="/")
