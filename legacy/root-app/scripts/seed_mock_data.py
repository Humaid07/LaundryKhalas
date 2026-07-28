"""Seed mock reference data for local development.

Everything created here is explicitly mock/demo data for the WhatsApp
Agent MVP: two markets, one CountryConfig each, and two mock facilities per
market. Idempotent - safe to run multiple times.

Usage: python -m scripts.seed_mock_data
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.facility import Facility
from app.models.market import CountryConfig, Market

_MOCK_PRICING = {
    "services": {
        "wash_and_fold": {"unit": "kg", "price_per_unit": 6.0, "min_price": 25.0},
        "dry_cleaning": {"unit": "item", "price_per_unit": 12.0, "min_price": 25.0},
        "ironing": {"unit": "item", "price_per_unit": 4.0, "min_price": 15.0},
    }
}

_MOCK_OPERATING_HOURS = {"open": "09:00", "close": "21:00", "pickup_window_hours": 3}

_MOCK_POLICY = {
    "note": "MOCK policy data for development only - not a real operational commitment.",
    "cancellation_window_hours": 2,
}

_MARKETS = [
    {
        "code": "AE",
        "name": "United Arab Emirates",
        "country": "United Arab Emirates",
        "timezone": "Asia/Dubai",
        "currency": "AED",
        "whatsapp_phone_number": "+9715000000AE",
        "default_service_area": "Dubai",
        "facilities": [
            {"name": "[MOCK] Deira Laundry Hub", "area": "Deira", "city": "Dubai"},
            {"name": "[MOCK] Dubai Marina Facility", "area": "Dubai Marina", "city": "Dubai"},
        ],
    },
    {
        "code": "QA",
        "name": "Qatar",
        "country": "Qatar",
        "timezone": "Asia/Qatar",
        "currency": "QAR",
        "whatsapp_phone_number": "+9745000000QA",
        "default_service_area": "Doha",
        "facilities": [
            {"name": "[MOCK] West Bay Facility", "area": "West Bay", "city": "Doha"},
            {"name": "[MOCK] Al Sadd Laundry Hub", "area": "Al Sadd", "city": "Doha"},
        ],
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for market_def in _MARKETS:
            result = await db.execute(select(Market).where(Market.code == market_def["code"]))
            market = result.scalar_one_or_none()
            if market is None:
                market = Market(
                    code=market_def["code"],
                    name=market_def["name"],
                    country=market_def["country"],
                    timezone=market_def["timezone"],
                    currency=market_def["currency"],
                    default_language="en",
                    is_active=True,
                )
                db.add(market)
                await db.flush()
                print(f"Created market {market.code}")
            else:
                print(f"Market {market.code} already exists, skipping")

            cfg_result = await db.execute(
                select(CountryConfig).where(CountryConfig.market_id == market.id)
            )
            if cfg_result.scalar_one_or_none() is None:
                db.add(
                    CountryConfig(
                        market_id=market.id,
                        whatsapp_phone_number=market_def["whatsapp_phone_number"],
                        default_service_area=market_def["default_service_area"],
                        operating_hours_json=_MOCK_OPERATING_HOURS,
                        pricing_config_json=_MOCK_PRICING,
                        policy_config_json=_MOCK_POLICY,
                    )
                )
                print(f"  Created country config for {market.code}")

            fac_result = await db.execute(
                select(Facility).where(Facility.market_id == market.id)
            )
            existing_facilities = {f.name for f in fac_result.scalars().all()}
            for facility_def in market_def["facilities"]:
                if facility_def["name"] in existing_facilities:
                    continue
                db.add(
                    Facility(
                        market_id=market.id,
                        name=facility_def["name"],
                        area=facility_def["area"],
                        city=facility_def["city"],
                        capacity_daily=50,
                        is_active=True,
                        ppi_score=4.5,
                    )
                )
                print(f"  Created facility {facility_def['name']}")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
