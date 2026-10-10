import strawberry
from typing import Optional, List
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.services.user_service import list_team_members, get_team_member_by_id
from app.graphql.types.user_types import UserType, UserListPayload
from app.graphql.helpers import get_auth_context, map_member_to_user_type

@strawberry.type
class UserQuery:
    @strawberry.field(description="Lists team members scoped by active property context (ctx.outlet_id).")
    async def team_members(
        self,
        info: Info,
        role: Optional[str] = None,
        search: Optional[str] = None,
        is_active: bool = True,
        all_outlets: bool = False
    ) -> UserListPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            members = await list_team_members(
                db=db,
                ctx=ctx,
                role=role,
                search=search,
                is_active=is_active,
                all_outlets=all_outlets
            )
            user_types = [map_member_to_user_type(m) for m in members]
            return UserListPayload(status="success", total=len(user_types), users=user_types)

    @strawberry.field(description="Fetches a single team member by ID.")
    async def team_member(
        self,
        info: Info,
        user_id: int
    ) -> UserType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await get_team_member_by_id(db=db, ctx=ctx, user_id=user_id)
            return map_member_to_user_type(res)
