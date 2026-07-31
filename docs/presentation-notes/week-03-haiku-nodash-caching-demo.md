# Presentation Notes — WhatsApp: Haiku 4.5, No-Dash Replies, Prompt Caching (2026-07-31)

## 1. What we can show
- A WhatsApp reply that reads like a human CSR: short sentences, no dash bullets, no
  "6 PM - 8 PM" or "1-2 days" — instead "6 PM to 8 PM", "1 to 2 days".
- The same reply keeping the order reference `LK-AE-1024` and a payment link intact.
- Diagnostics showing the effective model is `claude-haiku-4-5`.
- Logs showing `cache_read_tokens > 0` on the second message of a chat.

## 2. Suggested demo flow
1. Send "how long does dry cleaning take?" → natural reply, no dashes.
2. Send an address + time in one message → booking proceeds, order summary is clean prose.
3. Confirm the order → confirmed once, with the reference preserved.
4. Show the backend log line `customer_reply_style_normalized` (metadata only) and the
   `booking_orchestration_turn` line with `cache_hit=true`.

## 3. Talking points (simple language)
- **Cheaper brain, same job.** We moved the WhatsApp assistant to a smaller, faster,
  much cheaper Claude model (Haiku 4.5) for the high-volume chat path. Quality stays
  because the backend still does all the real work (pricing, availability, confirmation).
- **Reads like a person, not a robot.** We removed dash-style formatting so messages look
  hand-written. A safety net rewrites any stray dashes automatically, but never touches
  order numbers, links, or emails.
- **Pay once, reuse many times.** The big fixed instructions are now cached for up to an
  hour and the recent conversation for a few minutes, so we stop paying to re-send the
  same text every message.

## 4. Business value
- Lower per-conversation LLM cost (cheaper model + caching removing repeated input).
- More trustworthy, professional-looking customer messages.
- Full cost visibility per conversation via the new aggregate report.

## 5. Before vs after
- Before: Sonnet 5, dash-formatted lists/ranges, full prompt re-sent every turn.
- After: Haiku 4.5, natural dash-free prose, 1h/5m mixed prompt cache.

## 6. Risks / caveats to mention honestly
- Live cost savings are estimated until we capture real `usage` from a TEST-mode
  conversation (next step).
- Caching only kicks in above Haiku's 4096-token minimum prefix (our stable prompt +
  tools clear it); below that it silently doesn't cache (no error).
- Safety is unchanged: refunds/complaints still route to a human and pause the AI.

## 7. What is coming next
Run one live TEST-mode conversation, record the measured cost delta and cache hit rate,
then decide on flipping live WhatsApp mode; optionally surface the cost report in the admin
dashboard.
