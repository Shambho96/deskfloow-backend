from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any, Union
from app.models import User, UserClientOutletMapping, Outlet
from app.core.security import hash_password, encrypt_phone, decrypt_phone, hash_phone_blind
from app.core.context import UserContext
from app.schemas.user_schemas import UserCreateRequest, UserUpdateRequest, UserMemberResponse

async def create_team_member(
    db: AsyncSession,
    ctx: UserContext,
    req: UserCreateRequest
) -> UserMemberResponse:
    """
    Creates a new team member (Manager or Staff) with RBAC validation.
    - OWNER: Can create MANAGER (can_login=True) or STAFF (can_login=False) across client outlets.
    - MANAGER: Can ONLY create STAFF (can_login=False) scoped to their active outlet.
    """
    # 1. RBAC Hierarchy Checks
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members are not permitted to add or manage team members."
        )

    role_upper = req.role.upper()
    if role_upper not in ("MANAGER", "STAFF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'MANAGER' or 'STAFF'."
        )

    if ctx.role == "MANAGER" and role_upper != "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers are restricted to creating STAFF members only."
        )

    # Determine login capability
    can_login = (role_upper in ("MANAGER", "OWNER"))
    if can_login and not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required for Manager or Owner accounts with web login access."
        )

    # 2. Outlet Permission Scoping: Strictly assign member to creator's active outlet (ctx.outlet_id)
    target_outlet_id = int(ctx.outlet_id)
    req_outlet_ids = [target_outlet_id]

    # 3. Unique Email Check (if email provided)
    if req.email:
        email_clean = req.email.strip().lower()
        existing_user_query = select(User).where(User.email == email_clean)
        existing_res = await db.execute(existing_user_query)
        if existing_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with email '{email_clean}' already exists."
            )
    else:
        email_clean = None

    # 4. Hash password & Encrypt phone
    if can_login and req.password:
        pwd_hash = hash_password(req.password)
    else:
        pwd_hash = "STAFF_NO_WEB_LOGIN"

    if not email_clean:
        import uuid
        email_clean = f"staff_{uuid.uuid4().hex[:8]}@internal.deskflow.com"

    encrypted_phone = encrypt_phone(req.phone) if req.phone else None
    phone_blind = hash_phone_blind(req.phone) if req.phone else None

    # 5. Create User Record
    new_user = User(
        client_id=ctx.client_id,
        name=req.name.strip(),
        email=email_clean,
        phone_encrypted=encrypted_phone,
        phone_hash=phone_blind,
        password_hash=pwd_hash,
        role=role_upper,
        can_login=can_login,
        is_active=True
    )
    db.add(new_user)
    await db.flush()  # Generate auto-increment user.id

    # 6. Create Outlet Mappings
    for idx, oid in enumerate(req_outlet_ids):
        mapping = UserClientOutletMapping(
            user_id=new_user.id,
            client_id=ctx.client_id,
            outlet_id=oid,
            is_primary=(idx == 0)
        )
        db.add(mapping)

    await db.commit()
    await db.refresh(new_user)

    return UserMemberResponse(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        phone=req.phone or "",
        role=new_user.role,
        client_id=new_user.client_id,
        can_login=new_user.can_login,
        is_active=new_user.is_active,
        assigned_outlet_ids=req_outlet_ids,
        created_at=new_user.created_at
    )

async def list_team_members(
    db: AsyncSession,
    ctx: UserContext,
    role: Optional[str] = None,
    search: Optional[str] = None,
    is_active: bool = True,
    all_outlets: bool = False
) -> List[UserMemberResponse]:
    """
    Lists team members scoped by client and active outlet context.
    - Default: Scoped to active property (ctx.outlet_id).
    - If all_outlets=True and role=OWNER: Lists across all client outlets.
    """
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members are not permitted to view member directory."
        )

    # Base query for users in this client, excluding the logged-in user self
    query = (
        select(User, func.array_agg(UserClientOutletMapping.outlet_id).label("assigned_outlets"))
        .join(UserClientOutletMapping, User.id == UserClientOutletMapping.user_id)
        .where(
            User.client_id == ctx.client_id,
            User.id != ctx.user_id,
            User.is_active == is_active
        )
        .group_by(User.id)
    )

    # Filter by outlet context (unless OWNER requested all_outlets=True)
    if not (all_outlets and ctx.role == "OWNER"):
        query = query.where(UserClientOutletMapping.outlet_id == ctx.outlet_id)

    # Filter by role
    if role:
        query = query.where(User.role == role.upper())

    # Filter by search string
    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(or_(User.name.ilike(search_term), User.email.ilike(search_term)))

    result = await db.execute(query)
    rows = result.all()

    members = []
    for user_obj, assigned_outlets in rows:
        decrypted_phone = decrypt_phone(user_obj.phone_encrypted) if user_obj.phone_encrypted else ""
        members.append(
            UserMemberResponse(
                id=user_obj.id,
                name=user_obj.name,
                email=user_obj.email,
                phone=decrypted_phone,
                role=user_obj.role,
                client_id=user_obj.client_id,
                can_login=user_obj.can_login,
                is_active=user_obj.is_active,
                assigned_outlet_ids=assigned_outlets or [],
                created_at=user_obj.created_at
            )
        )

    return members

async def get_team_member_by_id(
    db: AsyncSession,
    ctx: UserContext,
    user_id: Union[int, str]
) -> UserMemberResponse:
    """Fetches single team member by ID within client/outlet boundary."""
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members cannot view member details."
        )

    query = (
        select(User, func.array_agg(UserClientOutletMapping.outlet_id).label("assigned_outlets"))
        .join(UserClientOutletMapping, User.id == UserClientOutletMapping.user_id)
        .where(User.id == user_id, User.client_id == ctx.client_id)
        .group_by(User.id)
    )
    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team member with ID '{user_id}' not found."
        )

    user_obj, assigned_outlets = row
    decrypted_phone = decrypt_phone(user_obj.phone_encrypted) if user_obj.phone_encrypted else ""

    return UserMemberResponse(
        id=user_obj.id,
        name=user_obj.name,
        email=user_obj.email,
        phone=decrypted_phone,
        role=user_obj.role,
        client_id=user_obj.client_id,
        can_login=user_obj.can_login,
        is_active=user_obj.is_active,
        assigned_outlet_ids=assigned_outlets or [],
        created_at=user_obj.created_at
    )

async def toggle_team_member_status(
    db: AsyncSession,
    ctx: UserContext,
    user_id: Union[int, str],
    is_active: bool
) -> Dict[str, Any]:
    """Activates or deactivates a team member."""
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members cannot modify member status."
        )

    query = select(User).where(User.id == user_id, User.client_id == ctx.client_id)
    result = await db.execute(query)
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team member with ID '{user_id}' not found."
        )

    # Manager cannot modify another Manager or Owner
    if ctx.role == "MANAGER" and target_user.role in ("MANAGER", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers cannot modify Manager or Owner accounts."
        )

    target_user.is_active = is_active
    await db.commit()

    action = "activated" if is_active else "deactivated"
    return {"status": "success", "message": f"User '{target_user.name}' has been {action} successfully."}
