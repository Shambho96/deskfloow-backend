from fastapi import Request, HTTPException, status, Depends
from typing import Optional
from app.core.security import decode_jwt_token
from app.core.context import UserContext

async def get_current_user_context(request: Request) -> UserContext:
    """
    FastAPI dependency extracting UserContext from HttpOnly cookie or Authorization header.
    Runs on every protected REST API request.
    """
    # 1. Extract token from cookie first, fallback to Authorization header
    token = request.cookies.get("access_token")
    if not token and "Authorization" in request.headers:
        token = request.headers["Authorization"]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )

    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    # 2. Decode & verify JWT
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again."
        )

    # 3. Double-check Staff Login Guard
    if payload.get("role") == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts are restricted from web API access."
        )

    # 4. Construct typed UserContext
    return UserContext(
        user_id=payload["sub"],
        client_id=payload["client_id"],
        outlet_id=payload["outlet_id"],
        role=payload["role"],
        email=payload.get("email"),
        name=payload.get("name"),
        allowed_outlets=payload.get("allowed_outlets", [])
    )
