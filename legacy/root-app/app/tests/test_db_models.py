import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.facility import Facility
from app.models.market import CountryConfig, Market


@pytest.mark.asyncio
async def test_seeded_market_and_facility_exist():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Market).where(Market.code == "AE"))
        market = result.scalar_one()
        assert market.currency == "AED"

        cfg_result = await db.execute(
            select(CountryConfig).where(CountryConfig.market_id == market.id)
        )
        config = cfg_result.scalar_one()
        assert "services" in config.pricing_config_json

        fac_result = await db.execute(select(Facility).where(Facility.market_id == market.id))
        facilities = fac_result.scalars().all()
        assert len(facilities) >= 1
        assert any(f.area == "Marina" for f in facilities)


@pytest.mark.asyncio
async def test_list_markets_endpoint(client, admin_headers):
    response = await client.get("/api/admin/markets", headers=admin_headers)
    assert response.status_code == 200
    codes = {m["code"] for m in response.json()}
    assert "AE" in codes
