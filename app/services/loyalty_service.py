from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.loyalty import LoyaltyTier


DEFAULT_TIERS = [
    {
        "tier_code": "BRONZE",
        "name": "Bronze Member",
        "min_spend": Decimal("0.00"),
        "min_stays": 0,
        "discount_percent": Decimal("0.00"),
        "badge_color": "slate",
        "perks": ["Standard Check-in", "Complimentary High-speed WiFi"],
        "display_order": 1,
    },
    {
        "tier_code": "SILVER",
        "name": "Silver Elite",
        "min_spend": Decimal("10000.00"),
        "min_stays": 2,
        "discount_percent": Decimal("5.00"),
        "badge_color": "blue",
        "perks": ["5% F&B Discount", "Priority Housekeeping Response"],
        "display_order": 2,
    },
    {
        "tier_code": "GOLD",
        "name": "Gold VIP",
        "min_spend": Decimal("25000.00"),
        "min_stays": 5,
        "discount_percent": Decimal("10.00"),
        "badge_color": "amber",
        "perks": ["10% F&B Discount", "1-Hour Late Check-out", "Welcome Drink on Arrival"],
        "display_order": 3,
    },
    {
        "tier_code": "PLATINUM",
        "name": "Platinum Diamond",
        "min_spend": Decimal("50000.00"),
        "min_stays": 10,
        "discount_percent": Decimal("15.00"),
        "badge_color": "primary",
        "perks": [
            "15% F&B Discount",
            "Guaranteed Late Check-out",
            "Complimentary Room Upgrade (Subject to Availability)",
        ],
        "display_order": 4,
    },
]


async def get_loyalty_tiers(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int] = None,
) -> List[LoyaltyTier]:
    """
    Retrieves configured loyalty tiers for the given client/outlet.
    If no tiers exist, automatically seeds default 4-tier model.
    """
    stmt = (
        select(LoyaltyTier)
        .where(
            LoyaltyTier.client_id == client_id,
            (LoyaltyTier.outlet_id == outlet_id) | (LoyaltyTier.outlet_id.is_(None)),
            LoyaltyTier.is_active == True,
        )
        .order_by(LoyaltyTier.min_spend.asc(), LoyaltyTier.display_order.asc())
    )
    result = await session.execute(stmt)
    tiers = list(result.scalars().all())

    # If none found, auto-seed default tiers for this client
    if not tiers:
        for item in DEFAULT_TIERS:
            tier = LoyaltyTier(
                client_id=client_id,
                outlet_id=outlet_id,
                tier_code=item["tier_code"],
                name=item["name"],
                min_spend=item["min_spend"],
                min_stays=item["min_stays"],
                discount_percent=item["discount_percent"],
                badge_color=item["badge_color"],
                perks=item["perks"],
                display_order=item["display_order"],
                is_active=True,
            )
            session.add(tier)
        await session.commit()

        # Re-fetch after commit
        refreshed = await session.execute(stmt)
        tiers = list(refreshed.scalars().all())

    return tiers


async def save_loyalty_tiers(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int],
    tiers_data: List[Dict[str, Any]],
) -> List[LoyaltyTier]:
    """
    Updates or replaces loyalty tiers configuration for the client/outlet.
    """
    # Delete existing tiers for this outlet or client
    del_stmt = delete(LoyaltyTier).where(
        LoyaltyTier.client_id == client_id,
        LoyaltyTier.outlet_id == outlet_id if outlet_id is not None else LoyaltyTier.outlet_id.is_(None),
    )
    await session.execute(del_stmt)

    # Insert new tiers
    for idx, item in enumerate(tiers_data):
        min_spend = Decimal(str(item.get("min_spend") or 0.0))
        min_stays = int(item.get("min_stays") or 0)
        discount = Decimal(str(item.get("discount_percent") or 0.0))
        perks = item.get("perks") if isinstance(item.get("perks"), list) else []

        tier = LoyaltyTier(
            client_id=client_id,
            outlet_id=outlet_id,
            tier_code=(item.get("tier_code") or f"TIER_{idx + 1}").upper(),
            name=str(item.get("name") or f"Tier {idx + 1}").strip(),
            min_spend=min_spend,
            min_stays=min_stays,
            discount_percent=discount,
            badge_color=str(item.get("badge_color") or "primary").strip(),
            perks=perks,
            display_order=int(item.get("display_order") or (idx + 1)),
            is_active=bool(item.get("is_active", True)),
        )
        session.add(tier)

    await session.commit()
    return await get_loyalty_tiers(session, client_id, outlet_id)


def resolve_guest_tier(spend: float, stays: int, tiers: List[LoyaltyTier]) -> LoyaltyTier:
    """
    Determines matching loyalty tier based on spend and stay count.
    Iterates in descending order of min_spend.
    """
    if not tiers:
        # Fallback dummy tier
        return LoyaltyTier(
            tier_code="STANDARD",
            name="Standard Guest",
            min_spend=Decimal("0.00"),
            min_stays=0,
            discount_percent=Decimal("0.00"),
            badge_color="slate",
            perks=[],
            display_order=0,
        )

    # Sort descending by min_spend
    sorted_tiers = sorted(tiers, key=lambda t: float(t.min_spend), reverse=True)
    for tier in sorted_tiers:
        if spend >= float(tier.min_spend):
            return tier

    # Fallback to lowest tier
    return sorted_tiers[-1]
