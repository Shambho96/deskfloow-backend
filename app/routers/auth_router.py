from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models import Outlet
from app.schemas.auth_schemas import LoginRequest, SwitchOutletRequest, AuthResponse, UserResponse
from app.services.auth_service import authenticate_user, set_auth_cookie, clear_auth_cookie, get_user_outlets
from app.core.dependencies import get_current_user_context
from app.core.context import UserContext
from app.core.security import create_jwt_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

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
    ctx: UserContext = result["user_context"]

    # Set HttpOnly Cookie
    set_auth_cookie(response, token)

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

@router.post("/logout")
async def logout(response: Response):
    """Clears authentication HttpOnly cookie."""
    clear_auth_cookie(response)
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(ctx: UserContext = Depends(get_current_user_context)):
    """Returns currently authenticated user profile & tenant context."""
    return UserResponse(
        id=ctx.user_id,
        name=ctx.name or "",
        email=ctx.email or "",
        role=ctx.role,
        client_id=ctx.client_id,
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
