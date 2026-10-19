import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
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

    # WhatsApp / Phone number is required for both Manager and Staff
    if not req.phone or not req.phone.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp / Phone number is required."
        )

    # Determine login capability
    can_login = (role_upper in ("MANAGER", "OWNER"))
    if can_login:
        if not req.email or not req.email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required for Manager accounts."
            )
        if not req.password or len(req.password.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password (minimum 6 characters) is required for Manager accounts."
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
    is_active: Optional[bool] = None,
    all_outlets: bool = False,
    page: int = 1,
    page_size: int = 10
) -> Dict[str, Any]:
    """
    Lists team members scoped by client and active outlet context with server-side pagination.
    - Default: Scoped to active property (ctx.outlet_id).
    - If all_outlets=True and role=OWNER: Lists across all client outlets.
    - If is_active is None: Returns all members (both active and deactivated).
    """
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members are not permitted to view member directory."
        )

    # Sanitize pagination inputs
    page_num = max(1, page)
    limit_num = max(1, min(page_size, 100))

    where_conditions = [
        User.client_id == ctx.client_id,
        User.id != ctx.user_id,
    ]

    # Only filter by is_active if explicitly requested (True or False).
    # If is_active is None (default "All Status"), return BOTH active and deactivated users.
    if is_active is not None:
        where_conditions.append(User.is_active == is_active)

    # Filter by outlet context (unless OWNER requested all_outlets=True)
    if not (all_outlets and ctx.role == "OWNER"):
        where_conditions.append(UserClientOutletMapping.outlet_id == ctx.outlet_id)

    # Filter by role & enforce Manager visibility
    if ctx.role == "MANAGER":
        # Managers can only see Staff members, never Owners or other Managers
        where_conditions.append(User.role == "STAFF")
    elif role:
        where_conditions.append(User.role == role.upper())

    # Filter by search string
    if search:
        search_term = f"%{search.strip()}%"
        where_conditions.append(or_(User.name.ilike(search_term), User.email.ilike(search_term)))

    # 1. Count query for total matching records
    count_query = (
        select(func.count(func.distinct(User.id)))
        .join(UserClientOutletMapping, User.id == UserClientOutletMapping.user_id)
        .where(*where_conditions)
    )
    count_res = await db.execute(count_query)
    total = count_res.scalar() or 0

    # 2. Paginated query
    total_pages = math.ceil(total / limit_num) if total > 0 else 1
    offset = (page_num - 1) * limit_num

    query = (
        select(User, func.array_agg(UserClientOutletMapping.outlet_id).label("assigned_outlets"))
        .join(UserClientOutletMapping, User.id == UserClientOutletMapping.user_id)
        .where(*where_conditions)
        .group_by(User.id)
        .order_by(User.id.desc())
        .offset(offset)
        .limit(limit_num)
    )

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

    return {
        "total": total,
        "page": page_num,
        "page_size": limit_num,
        "total_pages": total_pages,
        "has_next": page_num < total_pages,
        "has_prev": page_num > 1,
        "users": members
    }

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

async def update_team_member(
    db: AsyncSession,
    ctx: UserContext,
    user_id: Union[int, str],
    req: UserUpdateRequest
) -> UserMemberResponse:
    """
    Updates an existing team member profile, role, password, and outlet assignment.
    - OWNER: Can update any MANAGER or STAFF member.
    - MANAGER: Can ONLY update STAFF members assigned to their active outlet.
    """
    if ctx.role == "STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members are not permitted to modify team members."
        )

    # 1. Fetch Target User
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

    target_user, current_assigned_outlets = row

    # 2. RBAC Permissions
    if ctx.role == "MANAGER":
        if target_user.role in ("MANAGER", "OWNER"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot modify Manager or Owner accounts."
            )
        if req.role and req.role.strip().upper() != "STAFF":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers are restricted to managing Staff members only."
            )
    elif ctx.role == "OWNER":
        if target_user.role == "OWNER" and target_user.id != ctx.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify other Owner accounts."
            )

    # 3. Update Name
    if req.name is not None and req.name.strip():
        target_user.name = req.name.strip()

    # 4. Update Email
    if req.email is not None:
        email_clean = req.email.strip().lower() if req.email.strip() else None
        if email_clean and email_clean != target_user.email:
            existing_user_query = select(User).where(User.email == email_clean, User.id != target_user.id)
            existing_res = await db.execute(existing_user_query)
            if existing_res.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"An account with email '{email_clean}' already exists."
                )
            target_user.email = email_clean

    # 5. Update Phone (Must not be empty)
    if req.phone is not None:
        phone_clean = req.phone.strip()
        if not phone_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp / Phone number is required."
            )
        target_user.phone_encrypted = encrypt_phone(phone_clean)
        target_user.phone_hash = hash_phone_blind(phone_clean)

    # 6. Update Role
    role_upper = target_user.role
    if req.role is not None and req.role.strip():
        role_upper = req.role.strip().upper()
        if role_upper not in ("MANAGER", "STAFF"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be either 'MANAGER' or 'STAFF'."
            )
        target_user.role = role_upper
        target_user.can_login = (role_upper in ("MANAGER", "OWNER"))

    # 7. Update Password & Validate Manager Requirements
    if role_upper == "MANAGER":
        if not target_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for Manager accounts."
            )

    if req.password is not None and req.password.strip():
        if len(req.password.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters."
            )
        target_user.password_hash = hash_password(req.password.strip())
    elif role_upper == "MANAGER" and not target_user.can_login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when promoting a member to Manager."
        )

    # 8. Update Outlet Mappings (if provided)
    updated_outlet_ids = current_assigned_outlets or []
    if req.assigned_outlet_ids is not None:
        target_outlet_ids = [int(oid) for oid in req.assigned_outlet_ids if str(oid).isdigit()]
        if not target_outlet_ids:
            target_outlet_ids = [int(ctx.outlet_id)]

        if ctx.role == "MANAGER":
            target_outlet_ids = [int(ctx.outlet_id)]

        # Delete existing outlet mappings
        del_stmt = delete(UserClientOutletMapping).where(UserClientOutletMapping.user_id == target_user.id)
        await db.execute(del_stmt)

        # Add new mappings
        for idx, oid in enumerate(target_outlet_ids):
            mapping = UserClientOutletMapping(
                user_id=target_user.id,
                client_id=ctx.client_id,
                outlet_id=oid,
                is_primary=(idx == 0)
            )
            db.add(mapping)
        updated_outlet_ids = target_outlet_ids

    await db.commit()
    await db.refresh(target_user)

    decrypted_phone = decrypt_phone(target_user.phone_encrypted) if target_user.phone_encrypted else ""

    return UserMemberResponse(
        id=target_user.id,
        name=target_user.name,
        email=target_user.email,
        phone=decrypted_phone,
        role=target_user.role,
        client_id=target_user.client_id,
        can_login=target_user.can_login,
        is_active=target_user.is_active,
        assigned_outlet_ids=updated_outlet_ids,
        created_at=target_user.created_at
    )

