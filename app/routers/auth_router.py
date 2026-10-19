from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models import Outlet, UserClientOutletMapping, User
from app.schemas.auth_schemas import LoginRequest, SwitchOutletRequest, AuthResponse, UserResponse
from app.services.auth_service import authenticate_user, set_auth_cookie, clear_auth_cookie, get_user_outlets, refresh_user_session
from app.core.dependencies import get_current_user_context
from app.core.context import UserContext
from app.core.security import create_jwt_token
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class OutletInfo(BaseModel):
    id: int
    name: str
    city: str


@router.get("/outlets", response_model=List[OutletInfo])
async def get_my_outlets(
    ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Returns outlet details (id, name, city) for all outlets accessible by the current user."""
    query = (
        select(Outlet)
        .join(UserClientOutletMapping, UserClientOutletMapping.outlet_id == Outlet.id)
        .where(
            UserClientOutletMapping.user_id == ctx.user_id,
            Outlet.is_active == True
        )
        .order_by(Outlet.name.asc())
    )
    result = await db.execute(query)
    outlets = result.scalars().all()
    return [OutletInfo(id=int(o.id), name=o.name, city=o.city) for o in outlets]


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    User login endpoint. Validates credentials, checks Staff Login Guard, 
    sets HttpOnly secure access_token cookie, and returns access_token.
    """
    result = await authenticate_user(
        db=db,
        email=request.email,
        password=request.password,
        target_outlet_id=request.selected_outlet_id
    )

    token = result["token"]
    refresh_token = result.get("refresh_token")
    ctx: UserContext = result["user_context"]

    # Set HttpOnly Cookies (both access and refresh)
    set_auth_cookie(response, token, refresh_token)

    return AuthResponse(
        status="success",
        message="Login successful",
        access_token=token,
        user=UserResponse(
            id=ctx.user_id,
            name=ctx.name or "",
            email=ctx.email or "",
            role=ctx.role,
            client_id=ctx.client_id,
            active_outlet_id=ctx.outlet_id,
            allowed_outlets=ctx.allowed_outlets
        )
    )

@router.post("/refresh", response_model=AuthResponse)
async def refresh_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Refreshes an expired access token using the long-lived HttpOnly refresh_token cookie,
    X-Refresh-Token header, or Authorization header.
    Ensures seamless continuous sessions without forcing the user to re-login.
    """
    refresh_token = request.cookies.get("refresh_token")

    # Fallback 1: Custom header X-Refresh-Token
    if not refresh_token:
        refresh_token = request.headers.get("X-Refresh-Token")

    # Fallback 2: Authorization: Bearer <refresh_token>
    if not refresh_token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            refresh_token = auth_hdr.split(" ", 1)[1].strip()

    # Fallback 3: JSON body { "refresh_token": "..." }
    if not refresh_token:
        try:
            body = await request.json()
            if isinstance(body, dict):
                refresh_token = body.get("refresh_token")
        except Exception:
            pass

    if not refresh_token:
        print("[AUTH_REFRESH] ❌ No refresh token found in cookies, headers, or body.", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token found. Please sign in again."
        )

    try:
        result = await refresh_user_session(db, refresh_token)
    except HTTPException as exc:
        print(f"[AUTH_REFRESH] ❌ refresh_user_session failed: {exc.detail}", flush=True)
        raise exc
    except Exception as exc:
        print(f"[AUTH_REFRESH] ❌ Unexpected refresh error: {str(exc)}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh session due to server error."
        )

    new_access_token = result["access_token"]
    new_refresh_token = result.get("refresh_token")
    ctx: UserContext = result["user_context"]

    # Renew HttpOnly cookies
    set_auth_cookie(response, new_access_token, new_refresh_token)
    print(f"[AUTH_REFRESH] ✅ Successfully refreshed session for user {ctx.user_id} ({ctx.email})", flush=True)

    return AuthResponse(
        status="success",
        message="Session refreshed successfully",
        access_token=new_access_token,
        user=UserResponse(
            id=ctx.user_id,
            name=ctx.name or "",
            email=ctx.email or "",
            role=ctx.role,
            client_id=ctx.client_id,
            active_outlet_id=ctx.outlet_id,
            allowed_outlets=ctx.allowed_outlets
        )
    )

@router.post("/logout")
async def logout(response: Response):
    """Clears authentication HttpOnly cookie."""
    clear_auth_cookie(response)
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(
    response: Response,
    ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Returns currently authenticated user profile & tenant context after verifying active status."""
    query = select(User).where(User.id == ctx.user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user or not user.is_active:
        clear_auth_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been deactivated. Please contact your administrator."
        )

    return UserResponse(
        id=user.id,
        name=user.name or ctx.name or "",
        email=user.email or ctx.email or "",
        role=user.role,
        client_id=user.client_id,
        active_outlet_id=ctx.outlet_id,
        allowed_outlets=ctx.allowed_outlets
    )

@router.post("/switch-outlet", response_model=AuthResponse)
async def switch_outlet(
    request: SwitchOutletRequest,
    response: Response,
    ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Switches active hotel outlet for multi-outlet managers/owners."""
    active_outlets = await get_user_outlets(db, ctx.user_id)

    if request.target_outlet_id not in active_outlets and ctx.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to outlet '{request.target_outlet_id}'"
        )

    # Verify target outlet is active in database
    outlet_query = select(Outlet).where(Outlet.id == request.target_outlet_id, Outlet.is_active == True)
    outlet_result = await db.execute(outlet_query)
    target_outlet = outlet_result.scalars().first()
    if not target_outlet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outlet '{request.target_outlet_id}' is inactive or does not exist."
        )

    jwt_payload = {
        "sub": str(ctx.user_id),
        "client_id": ctx.client_id,
        "outlet_id": request.target_outlet_id,
        "role": ctx.role,
        "name": ctx.name,
        "email": ctx.email,
        "allowed_outlets": active_outlets
    }
    new_token = create_jwt_token(jwt_payload)
    set_auth_cookie(response, new_token)

    return AuthResponse(
        status="success",
        message=f"Switched to outlet '{request.target_outlet_id}'",
        access_token=new_token,
        user=UserResponse(
            id=ctx.user_id,
            name=ctx.name or "",
            email=ctx.email or "",
            role=ctx.role,
            client_id=ctx.client_id,
            active_outlet_id=request.target_outlet_id,
            allowed_outlets=active_outlets
        )
    )
