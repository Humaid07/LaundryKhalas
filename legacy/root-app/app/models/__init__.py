"""Import every model so SQLAlchemy's mapper registry and Alembic autogenerate
see the full schema, and so string-based relationship() references resolve.
"""
from app.models.ai_action_log import AIActionLog
from app.models.conversation import Conversation
from app.models.cost_tracking import CostTracking
from app.models.customer import Customer, CustomerAddress
from app.models.facility import Facility
from app.models.human_approval import HumanApproval
from app.models.market import CountryConfig, Market
from app.models.message import Message
from app.models.order import Order, OrderEvent

__all__ = [
    "AIActionLog",
    "Conversation",
    "CostTracking",
    "Customer",
    "CustomerAddress",
    "Facility",
    "HumanApproval",
    "CountryConfig",
    "Market",
    "Message",
    "Order",
    "OrderEvent",
]
