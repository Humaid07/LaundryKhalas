from datetime import datetime

from pydantic import BaseModel


class TestChatRequest(BaseModel):
    conversation_id: str | None = None
    sender_name: str | None = None
    phone_number: str | None = None
    message: str
    action_id: str | None = None


class MessageAction(BaseModel):
    id: str
    label: str
    type: str = "quick_reply"


class TestChatResponse(BaseModel):
    conversation_id: str
    user_message: str
    agent_reply: str
    domain: str
    mode: str
    provider: str
    actions: list[MessageAction] = []
    # Set whenever this turn created/touched an order behind the scenes, so
    # the UI (and future dashboard) can reflect the state change immediately.
    order_id: str | None = None
    order_status: str | None = None


class MessageRead(BaseModel):
    id: str
    conversation_id: str
    direction: str
    sender_type: str
    text: str
    domain_status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SettingsStatus(BaseModel):
    app_env: str
    agent_mode: str
    llm_provider: str
    llm_live_ready: bool
    whatsapp_mode: str
    whatsapp_live_ready: bool
    database_kind: str
    agent_min_typing_delay_ms: int
    agent_max_typing_delay_ms: int


class OrderRead(BaseModel):
    id: str
    order_id: str
    conversation_id: str | None = None
    customer_name: str | None = None
    service_type: str | None = None
    service_id: str | None = None
    service_display_name: str | None = None
    unit_type: str | None = None
    requires_manual_quote: bool = False
    items: list[str] = []
    pickup_area: str | None = None
    pickup_address: str | None = None
    pickup_date: str | None = None
    pickup_time: str | None = None
    pickup_instructions: str | None = None
    booking_state: str | None = None
    city: str | None = None
    delivery_preference: str | None = None
    status: str
    status_label: str
    notes: str | None = None
    change_request: str | None = None
    amount: float | None = None
    currency: str = "AED"
    facility: str | None = None
    driver: str | None = None
    payment: str | None = None
    source_channel: str
    is_demo: bool
    # Dashboard-only fields (populated by the /search list; None elsewhere).
    customer_phone: str | None = None
    needs_attention: bool = False
    conversation_status: str | None = None
    human_takeover: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class OrderPage(BaseModel):
    """Paginated order list for the dashboard Orders section."""
    orders: list[OrderRead]
    total: int
    page: int
    page_size: int


class OrderStatusUpdate(BaseModel):
    status: str
    actor_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    """Admin-created dashboard user. Role must be one of services.auth.ROLES."""
    email: str
    password: str
    full_name: str | None = None
    role: str = "operations"
    market: str | None = None


class UserUpdate(BaseModel):
    """Partial update of a dashboard user (admin only). Email/password unchanged."""
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class HumanTakeoverRequest(BaseModel):
    operator_name: str | None = None


class HumanMessageRequest(BaseModel):
    text: str
    operator_name: str | None = None


class DbHealth(BaseModel):
    status: str
    mode: str
    backend: str | None = None
    connected: bool | None = None
    app_env: str | None = None
    database_env: str | None = None
    supabase_project_type: str | None = None
    error: str | None = None


class OrderMetrics(BaseModel):
    active_orders: int
    completed_orders: int
    cancellation_requests: int
    pickup_change_requests: int
    support_required: int
    total_orders: int
    orders_by_status: dict[str, int]
