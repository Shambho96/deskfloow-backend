from fastapi import Request, HTTPException, status
from strawberry.fastapi import BaseContext
from typing import Optional
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import User
from app.core.security import decode_jwt_token
from app.core.context import UserContext

class GraphQLContext(BaseContext):
    def __init__(self, request: Request, user: Optional[UserContext]):
        super().__init__()
        self.request = request
        self.user = user

async def get_graphql_context(request: Request) -> GraphQLContext:
    """
    Strawberry GraphQL context dependency. Runs on every GraphQL request to attach user context.
    Strictly verifies active account status against the database on every request.
    """
    candidates = []
    if "Authorization" in request.headers:
        candidates.append(request.headers["Authorization"])
    if "access_token" in request.cookies:
        candidates.append(request.cookies["access_token"])

    user_context = None

    for raw_token in candidates:
        if not raw_token:
            continue
        token = str(raw_token).strip('"').strip("'").strip()
        if token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip('"').strip("'").strip()

        payload = decode_jwt_token(token)
        if payload and payload.get("role") != "STAFF":
            raw_sub = payload.get("sub")
            user_id = int(raw_sub) if str(raw_sub).isdigit() else raw_sub

            # Check live database status to ensure user has not been deactivated
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User.is_active).where(User.id == user_id))
                is_active = result.scalar_one_or_none()

            if is_active is not True:
                # User was deactivated or deleted: immediately block request with 401
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your account has been deactivated. Please contact your administrator."
                )

            user_context = UserContext(
                user_id=user_id,
                client_id=payload["client_id"],
                outlet_id=payload["outlet_id"],
                role=payload["role"],
                email=payload.get("email"),
                name=payload.get("name"),
                allowed_outlets=payload.get("allowed_outlets", [])
            )
            break

    return GraphQLContext(request=request, user=user_context)
