"""Official Meta WhatsApp Cloud API webhook endpoints. Only ever sends a
live reply when settings.live_whatsapp_ready is True; otherwise inbound
webhook traffic is still stored (useful for testing signature/parsing) but
no outbound call is made and the mock channel is used for the stored
"reply" record.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agents.whatsapp_agent.agent import handle_message
from channels.meta_whatsapp import MetaWhatsAppChannel, parse_inbound_webhook
from channels.mock_whatsapp import MockWhatsAppChannel
from db import get_db
from services import storage
from services.privacy import mask_pii
from settings import get_settings

router = APIRouter(prefix="/webhooks", tags=["whatsapp-webhook"])
logger = structlog.get_logger()


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    raw_body = await request.body()

    if settings.meta_whatsapp_app_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        channel = MetaWhatsAppChannel(
            settings.meta_whatsapp_access_token,
            settings.meta_whatsapp_phone_number_id,
            settings.meta_whatsapp_app_secret,
        )
        if not channel.verify_webhook_signature(
            payload_body=raw_body, signature_header=signature
        ):
            logger.warning("whatsapp_webhook_signature_invalid")
            raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    inbound_messages = parse_inbound_webhook(payload)

    for item in inbound_messages:
        conversation = await storage.get_or_create_conversation(
            db, conversation_id=None, channel="whatsapp", customer_phone=item["phone"]
        )
        history_rows = await storage.list_messages(db, conversation_id=conversation.id)
        history = [
            ("customer" if m.direction == "inbound" else "agent", m.text) for m in history_rows
        ]

        await storage.add_message(
            db,
            conversation_id=conversation.id,
            direction="inbound",
            sender_type="customer",
            text=item["text"],
            raw_payload_json=item,
        )

        reply = await handle_message(
            text=item["text"], history=history, db=db, conversation=conversation
        )

        if settings.live_whatsapp_ready:
            send_channel = MetaWhatsAppChannel(
                settings.meta_whatsapp_access_token, settings.meta_whatsapp_phone_number_id
            )
            send_status = "sent"
            await send_channel.send_text(to_phone=item["phone"], text=reply.text)
        else:
            await MockWhatsAppChannel().send_text(to_phone=item["phone"], text=reply.text)
            send_status = "mock_sent"

        outbound = await storage.add_message(
            db,
            conversation_id=conversation.id,
            direction="outbound",
            sender_type="agent",
            text=reply.text,
            domain_status=reply.domain,
        )
        await storage.add_agent_log(
            db,
            conversation_id=conversation.id,
            message_id=outbound.id,
            action="handoff" if reply.handoff else "whatsapp_reply",
            # RULE 8 — mask PII (phone/email) before it enters the audit log.
            input_json={"message": mask_pii(item["text"]), "intent": reply.intent},
            output_json={
                "reply": mask_pii(reply.text),
                "send_status": send_status,
                "domain": reply.domain,
                "handoff": reply.handoff,
                "whatsapp_mode": settings.whatsapp_mode,
            },
            provider=reply.provider,
            model=reply.model,
            success=reply.success,
            error_message=reply.error_message,
        )

    await db.commit()
    return {"status": "ok", "processed": len(inbound_messages)}
