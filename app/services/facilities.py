import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import Facility
from app.models.market import CountryConfig, Market


async def get_market_config(db: AsyncSession, market_id: uuid.UUID) -> CountryConfig | None:
    result = await db.execute(
        select(CountryConfig).where(CountryConfig.market_id == market_id)
    )
    return result.scalar_one_or_none()


async def get_market(db: AsyncSession, market_id: uuid.UUID) -> Market | None:
    result = await db.execute(select(Market).where(Market.id == market_id))
    return result.scalar_one_or_none()


async def list_known_areas(db: AsyncSession, *, market_id: uuid.UUID) -> list[str]:
    """Areas the agent may match against, sourced from active facilities -
    never a hardcoded/invented list.
    """
    result = await db.execute(
        select(Facility.area).where(Facility.market_id == market_id, Facility.is_active.is_(True))
    )
    return sorted({area for (area,) in result.all() if area})


async def find_facility_for_area(
    db: AsyncSession, *, market_id: uuid.UUID, area: str | None
) -> Facility | None:
    """Mock facility assignment: prefer an active facility in the same area,
    otherwise fall back to any active facility in the market. No live
    routing/optimization logic - that is future work.
    """
    query = select(Facility).where(Facility.market_id == market_id, Facility.is_active.is_(True))
    result = await db.execute(query)
    facilities = list(result.scalars().all())
    if not facilities:
        return None

    if area:
        for facility in facilities:
            if facility.area and facility.area.lower() == area.lower():
                return facility

    return facilities[0]
