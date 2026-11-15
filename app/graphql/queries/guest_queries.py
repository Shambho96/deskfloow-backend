from typing import List, Optional
import strawberry
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.graphql.types.guest_types import (
    GuestCRMItemType,
    GuestCRMStatsType,
    GuestNoteType,
    GuestPaginationPayloadType,
    GuestStayHistoryType,
    LoyaltyTierType,
    TierBreakdownType,
)
from app.graphql.types.hotel_config_types import (
    HotelSpecialRequestType,
    HotelGuestTagType,
)
from app.services.guest_service import (
    get_guest_by_id,
    get_guest_stay_history,
    get_outlet_crm_stats,
    get_outlet_guests,
)
from app.services.loyalty_service import get_loyalty_tiers
from app.services.hotel_config_service import (
    get_hotel_special_requests,
    get_hotel_guest_tags,
)


def _map_guest_item(d: dict) -> GuestCRMItemType:
    notes_list = [
        GuestNoteType(
            id=str(n.get("id") or ""),
            author_name=str(n.get("author_name") or "Staff"),
            text=str(n.get("text") or ""),
            outlet_id=n.get("outlet_id"),
            created_at=str(n.get("created_at") or ""),
        )
        for n in (d.get("notes") or [])
    ]

    return GuestCRMItemType(
        id=int(d["id"]),
        client_id=int(d["client_id"]),
        outlet_id=int(d.get("outlet_id") or 0),
        first_name=d["first_name"],
        last_name=d["last_name"],
        full_name=d.get("full_name") or f"{d['first_name']} {d['last_name']}",
        phone=d["phone"],
        email=d.get("email"),
        date_of_birth=d.get("date_of_birth"),
        gender=d.get("gender"),
        address_line1=d.get("address_line1"),
        city=d.get("city"),
        state=d.get("state"),
        postal_code=d.get("postal_code"),
        country=d.get("country") or "India",
        company_name=d.get("company_name"),
        gst_number=d.get("gst_number"),
        id_type=d.get("id_type"),
        id_number=d.get("id_number"),
        id_verified=bool(d.get("id_verified", False)),
        id_document_url=d.get("id_document_url"),
        vip_status=d.get("vip_status") or "STANDARD",
        is_blacklisted=bool(d.get("is_blacklisted", False)),
        blacklist_reason=d.get("blacklist_reason"),
        nationality=d.get("nationality") or "Indian",
        special_preferences=d.get("special_preferences"),
        tags=list(d.get("tags") or []),
        notes=notes_list,
        total_stays=int(d.get("total_stays") or 0),
        total_nights=int(d.get("total_nights") or 0),
        total_spend=float(d.get("total_spend") or 0.0),
        last_visit_date=d.get("last_visit_date"),
        active_stay_room=d.get("active_stay_room"),
        tier_code=d.get("tier_code") or "BRONZE",
        tier_name=d.get("tier_name") or "Bronze Member",
        tier_badge_color=d.get("tier_badge_color") or "slate",
        tier_discount=float(d.get("tier_discount") or 0.0),
        tier_perks=list(d.get("tier_perks") or []),
        created_at=d.get("created_at"),
    )


@strawberry.type
class GuestQuery:
    @strawberry.field
    async def loyalty_tiers(self, info: Info) -> List[LoyaltyTierType]:
        """Fetch active loyalty tiers and spend thresholds for this outlet/brand."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            tiers = await get_loyalty_tiers(session, ctx.client_id, ctx.outlet_id)
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
                for t in tiers
            ]

    @strawberry.field
    async def hotel_special_requests(
        self, info: Info, outlet_id: Optional[int] = None
    ) -> List[HotelSpecialRequestType]:
        """Fetch configured hotel special requests for the outlet."""
        ctx = get_auth_context(info)
        target_outlet = outlet_id or (int(ctx.outlet_id) if ctx.outlet_id else None)
        async with AsyncSessionLocal() as session:
            items = await get_hotel_special_requests(session, int(ctx.client_id), target_outlet)
            return [
                HotelSpecialRequestType(
                    id=r.id,
                    client_id=r.client_id,
                    outlet_id=r.outlet_id,
                    code=r.code,
                    label=r.label,
                    category=r.category,
                    is_chargeable=r.is_chargeable,
                    price=float(r.price),
                    icon=r.icon,
                    display_order=r.display_order,
                    is_active=r.is_active,
                )
                for r in items
            ]

    @strawberry.field
    async def hotel_guest_tags(self, info: Info, outlet_id: Optional[int] = None) -> List[HotelGuestTagType]:
        """Fetch configured hotel guest tags for the outlet."""
        ctx = get_auth_context(info)
        target_outlet = outlet_id or (int(ctx.outlet_id) if ctx.outlet_id else None)
        async with AsyncSessionLocal() as session:
            tags = await get_hotel_guest_tags(session, int(ctx.client_id), target_outlet)
            return [
                HotelGuestTagType(
                    id=t.id,
                    client_id=t.client_id,
                    outlet_id=t.outlet_id,
                    name=t.name,
                    color=t.color,
                    category=t.category,
                    description=t.description,
                    display_order=t.display_order,
                    is_active=t.is_active,
                )
                for t in tags
            ]

    @strawberry.field
    async def crm_guests(
        self,
        info: Info,
        search: Optional[str] = None,
        tier_code: Optional[str] = None,
        id_verified: Optional[bool] = None,
        is_blacklisted: Optional[bool] = None,
        page: int = 1,
        limit: int = 50,
    ) -> GuestPaginationPayloadType:
        """Fetch outlet-scoped guests with dynamic loyalty tiers, spend metrics, and search."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            items, total_count, total_pages = await get_outlet_guests(
                session=session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                search=search,
                tier_filter=tier_code,
                id_verified=id_verified,
                is_blacklisted=is_blacklisted,
                page=page,
                limit=limit,
            )
            mapped_items = [_map_guest_item(item) for item in items]
            return GuestPaginationPayloadType(
                items=mapped_items,
                total_count=total_count,
                page=page,
                total_pages=total_pages,
            )

    @strawberry.field
    async def crm_guest(self, info: Info, id: int) -> Optional[GuestCRMItemType]:
        """Fetch detailed guest profile with outlet-specific metrics and notes."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            d = await get_guest_by_id(session, ctx.client_id, ctx.outlet_id, id)
            if not d:
                return None
            return _map_guest_item(d)

    @strawberry.field
    async def crm_guest_stays(self, info: Info, guest_id: int) -> List[GuestStayHistoryType]:
        """Fetch chronological stay history for this guest at this outlet."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            stays = await get_guest_stay_history(session, ctx.client_id, ctx.outlet_id, guest_id)
            return [
                GuestStayHistoryType(
                    reservation_id=s["reservation_id"],
                    reservation_code=s["reservation_code"],
                    room_number=s["room_number"],
                    category_name=s["category_name"],
                    check_in_date=s["check_in_date"],
                    check_out_date=s["check_out_date"],
                    status=s["status"],
                    adults_count=s["adults_count"],
                    children_count=s["children_count"],
                    booking_source=s["booking_source"],
                    total_amount=s["total_amount"],
                    paid_amount=s["paid_amount"],
                    balance_due=s["balance_due"],
                )
                for s in stays
            ]

    @strawberry.field
    async def crm_guest_stats(self, info: Info) -> GuestCRMStatsType:
        """Fetch outlet-level CRM KPI counters and loyalty tier distribution."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            stats = await get_outlet_crm_stats(session, ctx.client_id, ctx.outlet_id)
            tier_breakdowns = [
                TierBreakdownType(
                    tier_code=tb["tier_code"],
                    tier_name=tb["tier_name"],
                    badge_color=tb["badge_color"],
                    min_spend=tb["min_spend"],
                    guest_count=tb["guest_count"],
                )
                for tb in stats["tier_breakdowns"]
            ]
            return GuestCRMStatsType(
                total_guests=stats["total_guests"],
                repeat_guests_count=stats["repeat_guests_count"],
                repeat_guests_rate=stats["repeat_guests_rate"],
                kyc_verified_count=stats["kyc_verified_count"],
                blacklisted_count=stats["blacklisted_count"],
                tier_breakdowns=tier_breakdowns,
            )
