-- Pre-confirmation review gate (owner decision 2026-07-31).
--
-- The WhatsApp Operations Agent must show the FULL order summary and let the
-- customer add notes / check details / edit BEFORE the order is confirmed. This
-- column marks when that full summary was last shown. The backend refuses
-- confirm_order unless the summary was shown in a PRIOR turn, and clears this
-- marker on any edit (so a changed order is always re-reviewed).
--
-- Nullable; NULL = no valid, un-edited summary has been shown yet.
-- Additive + idempotent; safe to re-run.
alter table orders add column if not exists review_summary_shown_at timestamptz;

comment on column orders.review_summary_shown_at is
  'When the full order summary was last shown to the customer (pre-confirmation '
  'review gate, owner 2026-07-31). NULL = not shown / invalidated by an edit. '
  'confirm_order is refused unless this was set in a prior turn.';
