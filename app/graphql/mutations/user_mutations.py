import strawberry
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.schemas.user_schemas import UserCreateRequest, UserUpdateRequest
from app.services.user_service import create_team_member, toggle_team_member_status, update_team_member
from app.graphql.types.user_types import UserType, StatusPayload, CreateUserInput, UpdateUserInput
from app.graphql.helpers import get_auth_context, map_member_to_user_type

@strawberry.type
class UserMutation:
    @strawberry.field(description="Creates a new Manager or Staff team member.")
    async def create_team_member(
        self,
        info: Info,
        input: CreateUserInput
    ) -> UserType:
        ctx = get_auth_context(info)
        req = UserCreateRequest(
            name=input.name,
            email=input.email,
            phone=input.phone,
            role=input.role,
            assigned_outlet_ids=input.assigned_outlet_ids,
            password=input.password
        )
        async with AsyncSessionLocal() as db:
            res = await create_team_member(db=db, ctx=ctx, req=req)
            return map_member_to_user_type(res)

    @strawberry.field(description="Updates an existing team member profile, role, password, or property assignment.")
    async def update_team_member(
        self,
        info: Info,
        input: UpdateUserInput
    ) -> UserType:
        ctx = get_auth_context(info)
        req = UserUpdateRequest(
            name=input.name,
            email=input.email,
            phone=input.phone,
            role=input.role,
            assigned_outlet_ids=input.assigned_outlet_ids,
            password=input.password
        )
        async with AsyncSessionLocal() as db:
            res = await update_team_member(db=db, ctx=ctx, user_id=input.user_id, req=req)
            return map_member_to_user_type(res)

    @strawberry.field(description="Activates or deactivates a team member account.")
    async def toggle_team_member_status(
        self,
        info: Info,
        user_id: int,
        is_active: bool
    ) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await toggle_team_member_status(db=db, ctx=ctx, user_id=user_id, is_active=is_active)
            return StatusPayload(status=res["status"], message=res["message"])
