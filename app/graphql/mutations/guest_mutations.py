from typing import List, Optional
import strawberry
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.graphql.queries.guest_queries import _map_guest_item
from app.graphql.types.guest_types import (
    CreateGuestInput,
    GuestCRMItemType,
    LoyaltyTierInput,
    LoyaltyTierType,
    UpdateGuestInput,
    VerifyKycInput,
)
from app.services.guest_service import (
    add_guest_crm_note,
    create_crm_guest,
    set_guest_blacklist,
    update_crm_guest,
    verify_guest_kyc,
)
from app.services.loyalty_service import save_loyalty_tiers


@strawberry.type
class GuestMutation:
    @strawberry.mutation
    async def save_loyalty_tiers(self, info: Info, tiers: List[LoyaltyTierInput]) -> List[LoyaltyTierType]:
        """Save or update custom VIP loyalty tiers and spend thresholds."""
        ctx = get_auth_context(info)
        raw_tiers = [
            {
                "tier_code": t.tier_code,
                "name": t.name,
                "min_spend": t.min_spend,
                "min_stays": t.min_stays or 0,
                "discount_percent": t.discount_percent or 0.0,
                "badge_color": t.badge_color or "primary",
                "perks": t.perks or [],
                "display_order": t.display_order or 0,
                "is_active": t.is_active if t.is_active is not None else True,
            }
            for t in tiers
        ]
        async with AsyncSessionLocal() as session:
            saved = await save_loyalty_tiers(session, ctx.client_id, ctx.outlet_id, raw_tiers)
            return [
                LoyaltyTierType(
                    id=t.id,
                    tier_code=t.tier_code,
                    name=t.name,
                    min_spend=float(t.min_spend),
                    min_stays=t.min_stays,
                    discount_percent=float(t.discount_percent),
                    badge_color=t.badge_color,
                    perks=list(t.perks or []),
                    display_order=t.display_order,
                    is_active=t.is_active,
                )
                for t in saved
            ]

    @strawberry.mutation
    async def create_crm_guest(self, info: Info, input: CreateGuestInput) -> GuestCRMItemType:
        """Register a new guest profile directly into the outlet CRM."""
        ctx = get_auth_context(info)
        data = {
            "first_name": input.first_name,
            "last_name": input.last_name,
            "phone": input.phone,
            "email": input.email,
            "date_of_birth": input.date_of_birth,
            "gender": input.gender,
            "address_line1": input.address_line1,
            "city": input.city,
            "state": input.state,
            "postal_code": input.postal_code,
            "country": input.country or "India",
            "company_name": input.company_name,
            "gst_number": input.gst_number,
            "id_type": input.id_type,
            "id_number": input.id_number,
            "id_verified": input.id_verified or False,
            "id_document_url": input.id_document_url,
            "vip_status": input.vip_status or "STANDARD",
            "nationality": input.nationality or "Indian",
            "special_preferences": input.special_preferences,
            "tags": input.tags or [],
        }
        async with AsyncSessionLocal() as session:
            guest_dict = await create_crm_guest(session, ctx.client_id, ctx.outlet_id, data)
            return _map_guest_item(guest_dict)

    @strawberry.mutation
    async def update_crm_guest(self, info: Info, id: int, input: UpdateGuestInput) -> GuestCRMItemType:
        """Update an existing guest profile in the outlet CRM."""
        ctx = get_auth_context(info)
        data = {
            "first_name": input.first_name,
            "last_name": input.last_name,
            "phone": input.phone,
            "email": input.email,
            "date_of_birth": input.date_of_birth,
            "gender": input.gender,
            "address_line1": input.address_line1,
            "city": input.city,
            "state": input.state,
            "postal_code": input.postal_code,
            "country": input.country,
            "company_name": input.company_name,
            "gst_number": input.gst_number,
            "id_type": input.id_type,
            "id_number": input.id_number,
            "id_verified": input.id_verified,
            "id_document_url": input.id_document_url,
            "vip_status": input.vip_status,
            "is_blacklisted": input.is_blacklisted,
            "blacklist_reason": input.blacklist_reason,
            "nationality": input.nationality,
            "special_preferences": input.special_preferences,
            "tags": input.tags,
        }
        async with AsyncSessionLocal() as session:
            guest_dict = await update_crm_guest(session, ctx.client_id, ctx.outlet_id, id, data)
            return _map_guest_item(guest_dict)

    @strawberry.mutation
    async def verify_guest_kyc(self, info: Info, id: int, input: VerifyKycInput) -> GuestCRMItemType:
        """Verify guest identification and update document details."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            guest_dict = await verify_guest_kyc(
                session=session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                guest_id=id,
                id_type=input.id_type,
                id_number=input.id_number,
                id_document_url=input.id_document_url,
                verified=input.verified,
            )
            return _map_guest_item(guest_dict)

    @strawberry.mutation
    async def add_guest_crm_note(self, info: Info, guest_id: int, note: str) -> GuestCRMItemType:
        """Add a staff note to the guest profile timeline."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            author_name = ctx.name or "Front Desk"
            guest_dict = await add_guest_crm_note(session, ctx.client_id, ctx.outlet_id, guest_id, author_name, note)
            return _map_guest_item(guest_dict)

    @strawberry.mutation
    async def set_guest_blacklist(
        self, info: Info, guest_id: int, is_blacklisted: bool, reason: Optional[str] = None
    ) -> GuestCRMItemType:
        """Blacklist or un-blacklist a guest."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            guest_dict = await set_guest_blacklist(
                session, ctx.client_id, ctx.outlet_id, guest_id, is_blacklisted, reason
            )
            return _map_guest_item(guest_dict)
