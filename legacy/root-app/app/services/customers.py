import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, CustomerAddress
from app.models.market import Market


async def get_market_by_code(db: AsyncSession, market_code: str) -> Market | None:
    result = await db.execute(select(Market).where(Market.code == market_code.upper()))
    return result.scalar_one_or_none()


async def get_or_create_customer(
    db: AsyncSession,
    *,
    market_id: uuid.UUID,
    phone_number: str,
    name: str | None = None,
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            Customer.market_id == market_id, Customer.phone_number == phone_number
        )
    )
    customer = result.scalar_one_or_none()
    if customer:
        if name and not customer.name:
            customer.name = name
        return customer

    customer = Customer(
        market_id=market_id,
        phone_number=phone_number,
        name=name,
    )
    db.add(customer)
    await db.flush()
    return customer


async def add_customer_address(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    address_text: str,
    area: str | None = None,
    city: str | None = None,
    label: str | None = None,
    is_default: bool = False,
) -> CustomerAddress:
    address = CustomerAddress(
        customer_id=customer_id,
        address_text=address_text,
        area=area,
        city=city,
        label=label,
        is_default=is_default,
    )
    db.add(address)
    await db.flush()
    return address
