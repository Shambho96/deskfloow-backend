from strawberry.types import Info
from app.core.context import UserContext
from app.schemas.user_schemas import UserMemberResponse
from app.graphql.types.user_types import UserType

def get_auth_context(info: Info) -> UserContext:
    """Extracts and verifies authenticated UserContext from GraphQL request info."""
    user = getattr(info.context, "user", None) if info.context else None
    if not user:
        raise Exception("Authentication required. Please log in.")
    return user

def map_member_to_user_type(res: UserMemberResponse) -> UserType:
    """Maps UserMemberResponse Pydantic model to Strawberry UserType."""
    return UserType(
        id=int(res.id),
        name=res.name,
        email=res.email,
        phone=res.phone or "",
        role=res.role,
        client_id=int(res.client_id),
        can_login=res.can_login,
        is_active=res.is_active,
        assigned_outlet_ids=[int(x) for x in res.assigned_outlet_ids],
        created_at=res.created_at.isoformat() if hasattr(res.created_at, 'isoformat') else str(res.created_at)
    )
