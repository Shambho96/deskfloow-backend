from fastapi import Request
from strawberry.fastapi import BaseContext
from typing import Optional
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
    """
    token = request.cookies.get("access_token")
    if not token and "Authorization" in request.headers:
        token = request.headers["Authorization"]

    user_context = None

    if token:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        payload = decode_jwt_token(token)
        if payload and payload.get("role") != "STAFF":
            user_context = UserContext(
                user_id=payload["sub"],
                client_id=payload["client_id"],
                outlet_id=payload["outlet_id"],
                role=payload["role"],
                email=payload.get("email"),
                name=payload.get("name"),
                allowed_outlets=payload.get("allowed_outlets", [])
            )

    return GraphQLContext(request=request, user=user_context)
