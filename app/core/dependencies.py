from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.core.security import decode_jwt_token
from app.core.context import UserContext

# Enables the "Authorize 🔓" button in Swagger UI docs (/docs)
security_scheme = HTTPBearer(auto_error=False)

async def get_current_user_context(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> UserContext:
    """
    FastAPI dependency extracting UserContext from HttpOnly cookie or Authorization header.
    Runs on every protected REST API request.
    """
    candidates = []
    if auth_credentials and auth_credentials.credentials:
        candidates.append(auth_credentials.credentials)
    if "Authorization" in request.headers:
        candidates.append(request.headers["Authorization"])
    if "access_token" in request.cookies:
        candidates.append(request.cookies["access_token"])

    last_error = "Authentication required. Please log in."

    for raw_token in candidates:
        if not raw_token:
            continue

        token = str(raw_token).strip('"').strip("'").strip()
        if token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip('"').strip("'").strip()

        payload = decode_jwt_token(token)
        if not payload:
            last_error = "Invalid or expired session. Please log in again."
            continue

        # Double-check Staff Login Guard
        if payload.get("role") == "STAFF":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff accounts are restricted from web API access."
            )

        raw_sub = payload.get("sub")
        user_id = int(raw_sub) if str(raw_sub).isdigit() else raw_sub

        return UserContext(
            user_id=user_id,
            client_id=payload["client_id"],
            outlet_id=payload["outlet_id"],
            role=payload["role"],
            email=payload.get("email"),
            name=payload.get("name"),
            allowed_outlets=payload.get("allowed_outlets", [])
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=last_error
    )
