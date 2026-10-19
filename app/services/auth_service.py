from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status, Response
from typing import Optional, Dict, Any, Union, List
from app.models import User, UserClientOutletMapping, Outlet
from app.core.security import verify_password, create_jwt_token, create_refresh_token, decode_jwt_token
from app.core.context import UserContext
from app.config import settings

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetches user by email from database."""
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalars().first()

async def get_user_outlets(db: AsyncSession, user_id: Union[int, str]) -> List[Union[int, str]]:
    """Fetches list of active outlet IDs mapped to a user."""
    query = (
        select(UserClientOutletMapping.outlet_id)
        .join(Outlet, UserClientOutletMapping.outlet_id == Outlet.id)
        .where(
            UserClientOutletMapping.user_id == user_id,
            Outlet.is_active == True
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_primary_outlet_id(db: AsyncSession, user_id: Union[int, str]) -> Optional[Union[int, str]]:
    """Fetches the primary active outlet ID mapped to a user."""
    query = (
        select(UserClientOutletMapping.outlet_id)
        .join(Outlet, UserClientOutletMapping.outlet_id == Outlet.id)
        .where(
            UserClientOutletMapping.user_id == user_id,
            UserClientOutletMapping.is_primary == True,
            Outlet.is_active == True
        )
    )
    result = await db.execute(query)
    return result.scalars().first()

async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    target_outlet_id: Optional[Union[int, str]] = None
) -> Dict[str, Any]:
    """
    Authenticates user, enforces Staff Login Guard, and builds JWT payload.
    """
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # STRICT ACCOUNT DEACTIVATION GUARD: Block deactivated users from logging in
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your administrator."
        )

    # STRICT LOGIN GUARD: Block STAFF accounts from web login
    if user.role == "STAFF" or not user.can_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts are restricted from web dashboard login. Stored for WhatsApp ops only."
        )

    allowed_outlets = await get_user_outlets(db, user.id)
    if not allowed_outlets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no assigned hotel outlets"
        )

    active_outlet = target_outlet_id or await get_primary_outlet_id(db, user.id) or allowed_outlets[0]
    if active_outlet not in allowed_outlets and user.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to target outlet '{active_outlet}'"
        )

    jwt_payload = {
        "sub": str(user.id),
        "client_id": user.client_id,
        "outlet_id": active_outlet,
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "allowed_outlets": allowed_outlets
    }

    token = create_jwt_token(jwt_payload)
    refresh_token = create_refresh_token(user.id)

    return {
        "token": token,
        "refresh_token": refresh_token,
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

async def refresh_user_session(
    db: AsyncSession,
    refresh_token: str,
    target_outlet_id: Optional[Union[int, str]] = None
) -> Dict[str, Any]:
    """
    Validates a Refresh Token, fetches the user from DB to confirm they are active,
    and returns a fresh Access Token (and renewed Refresh Token).
    """
    payload = decode_jwt_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please log in again."
        )

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload."
        )

    user_id = int(user_id_raw) if str(user_id_raw).isdigit() else user_id_raw
    query = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists or has been deactivated."
        )

    if user.role == "STAFF" or not user.can_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts are restricted from web dashboard access."
        )

    allowed_outlets = await get_user_outlets(db, user.id)
    if not allowed_outlets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no assigned hotel outlets."
        )

    active_outlet = target_outlet_id or await get_primary_outlet_id(db, user.id) or allowed_outlets[0]
    if active_outlet not in allowed_outlets and user.role != "OWNER":
        active_outlet = allowed_outlets[0]

    new_jwt_payload = {
        "sub": str(user.id),
        "client_id": user.client_id,
        "outlet_id": active_outlet,
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "allowed_outlets": allowed_outlets
    }

    new_access_token = create_jwt_token(new_jwt_payload)
    new_refresh_token = create_refresh_token(user.id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
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

def set_auth_cookie(response: Response, token: str, refresh_token: Optional[str] = None) -> None:
    """Sets clean JWT access and optional refresh token in HttpOnly cookies."""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path="/"
        )

def clear_auth_cookie(response: Response) -> None:
    """Clears both access and refresh cookies upon logout."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
