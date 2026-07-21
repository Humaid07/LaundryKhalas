-- =====================================================================
-- LaundryKhalas — WhatsApp Agent DEV/TEST seed data
-- Migration: 20260721_000002_seed_whatsapp_agent_test_data
--
-- DEV/TEST ONLY. Every row here is FAKE/DEMO data and is explicitly marked:
--   is_test_data = true, is_demo = true, environment = 'dev',
--   seed_source = 'whatsapp_agent_test_seed',
--   seed_batch_id = '20260721_whatsapp_agent_seed_v1', created_by_seed = true.
--
-- All primary keys are FIXED literals so this file is fully idempotent
-- (on conflict do nothing). The guarded Python seed script
-- (scripts/seed_supabase_test_data.py) executes THIS SAME FILE, so seeding
-- via `supabase db push` or via the script yields identical rows and never
-- duplicates. The reset script removes rows by (is_test_data & created_by_seed)
-- and/or this seed_batch_id — it never touches non-test rows.
--
-- No real customers. No real phone numbers. No PII. Phones are obviously fake
-- and stored alongside masked_phone.
-- =====================================================================

-- ---------------------------------------------------------------------
-- customers (6)
-- ---------------------------------------------------------------------
insert into customers (id, display_name, phone_e164, phone_hash, masked_phone, preferred_language, city, area, region, market, source_channel, is_test_data, is_demo, environment, seed_batch_id, seed_source, created_by_seed)
values
  ('000000c1-0000-0000-0000-000000000000', 'Amaan Patel',       '+971500000024', 'hash_demo_c1', '+971 50 •••• 24', 'en', 'Dubai',       'Dubai Marina',    'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true),
  ('000000c2-0000-0000-0000-000000000000', 'Sarah',             '+971500000025', 'hash_demo_c2', '+971 50 •••• 25', 'en', 'Abu Dhabi',   'Abu Dhabi',       'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true),
  ('000000c3-0000-0000-0000-000000000000', 'Jumeirah Hotel',    '+971400000026', 'hash_demo_c3', '+971 4 •••• 26',  'en', 'Dubai',       'Jumeirah',        'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true),
  ('000000c4-0000-0000-0000-000000000000', 'Test User',         '+971500000027', 'hash_demo_c4', '+971 50 •••• 27', 'en', 'Sharjah',     'Al Nahda',        'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true),
  ('000000c5-0000-0000-0000-000000000000', 'Demo Customer',     '+971500002031', 'hash_demo_c5', '+971 50 •••• 31', 'en', 'Dubai',       'Dubai Marina',    'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true),
  ('000000c6-0000-0000-0000-000000000000', 'Hassan Ali',        '+971550000099', 'hash_demo_c6', '+971 55 •••• 99', 'en', 'Sharjah',     'Al Nahda',        'Gulf', 'UAE', 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- orders (5)
-- ---------------------------------------------------------------------
insert into orders (id, order_id, conversation_id, customer_id, customer_name, service, items, region, market, country, city, area, pickup_slot, delivery_slot, facility, driver, status, payment_status, payment_method, amount, source_channel, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed, completed_at)
values
  ('000000d1-0000-0000-0000-000000000000', 'LK-AE-1024', null, '000000c1-0000-0000-0000-000000000000', 'Amaan',          'Wash & Fold + Dry Cleaning', '["Mixed laundry","2 shirts for dry cleaning"]'::jsonb, 'Gulf', 'UAE', 'United Arab Emirates', 'Dubai',     'Dubai Marina', 'Today 6 PM – 8 PM', null, 'Dubai Marina Facility', 'Ahmed Khan', 'pickup_scheduled',  'pending', 'pay_on_delivery', 145.00, 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'TRACK_ORDER_001',      true, null),
  ('000000d2-0000-0000-0000-000000000000', 'LK-AE-1025', null, '000000c2-0000-0000-0000-000000000000', 'Sarah',          'Duvet Cleaning',             '["1 duvet"]'::jsonb,                                    'Gulf', 'UAE', 'United Arab Emirates', 'Abu Dhabi', 'Abu Dhabi',    null, null, 'Abu Dhabi Facility', 'Fatima Noor', 'in_cleaning',       'pending', null,             90.00,  'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'ORDER_IN_CLEANING_001', true, null),
  ('000000d3-0000-0000-0000-000000000000', 'LK-AE-1026', null, '000000c3-0000-0000-0000-000000000000', 'Jumeirah Hotel', 'Business Laundry',           '["Bulk business laundry"]'::jsonb,                      'Gulf', 'UAE', 'United Arab Emirates', 'Dubai',     'Dubai',        null, 'Tomorrow AM', 'Business Bay Facility', null, 'ready_for_delivery','invoiced', 'invoice',         2800.00,'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'B2B_ORDER_001',        true, null),
  ('000000d4-0000-0000-0000-000000000000', 'LK-AE-1027', null, '000000c4-0000-0000-0000-000000000000', 'Test User',      'Ironing / Pressing',         '["Assorted ironing"]'::jsonb,                           'Gulf', 'UAE', 'United Arab Emirates', 'Sharjah',   'Al Nahda',     null, null, 'Sharjah Facility', 'Yousef Amir', 'completed',         'paid',    'card',            60.00,  'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'COMPLETED_ORDER_001',  true, '2026-07-19T18:00:00Z'),
  ('000000d5-0000-0000-0000-000000000000', 'LK-AE-2031', null, '000000c5-0000-0000-0000-000000000000', 'Demo Customer',  'Dry Cleaning',               '["3 suits"]'::jsonb,                                    'Gulf', 'UAE', 'United Arab Emirates', 'Dubai',     'Dubai Marina', 'Today 4 PM – 6 PM', null, 'Dubai Marina Facility', null, 'active',           'pending', null,             120.00, 'whatsapp', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'ACTIVE_ORDER_001',     true, null)
on conflict (order_id) do nothing;

-- ---------------------------------------------------------------------
-- conversations (6)
-- ---------------------------------------------------------------------
insert into conversations (id, customer_id, external_conversation_id, channel, status, priority, human_intervention_required, handoff_reason, assigned_team, linked_order_id, last_message, last_message_at, unread_count, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed)
values
  -- 1. Normal booking flow (bot)
  ('000000a1-0000-0000-0000-000000000000', '000000c5-0000-0000-0000-000000000000', 'wa-demo-a1', 'whatsapp', 'bot',            null,     false, null,                        null,                                'LK-AE-2031', 'Sure. Which service do you need today?',                                 '2026-07-20T09:52:00Z', 0, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'BOOKING_FLOW_001', true),
  -- 2. Refund urgent (human takeover active)
  ('000000a2-0000-0000-0000-000000000000', '000000c1-0000-0000-0000-000000000000', 'wa-demo-a2', 'whatsapp', 'human_takeover', 'urgent', true,  'Refund request',            'Customer Facing / Finance',         'LK-AE-1024', 'Please hold on while we find a quick solution. Our team will get back to you shortly.', '2026-07-20T09:58:00Z', 2, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'REFUND_URGENT_001', true),
  -- 3. Damaged item complaint (human needed)
  ('000000a3-0000-0000-0000-000000000000', '000000c6-0000-0000-0000-000000000000', 'wa-demo-a3', 'whatsapp', 'human_needed',   'high',   true,  'Damaged item complaint',    'Customer Facing / Facility Facing', null,          'I''m sorry about that. Please share your order ID and a photo if possible.',            '2026-07-20T09:40:00Z', 1, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'DAMAGED_ITEM_001', true),
  -- 4. Track order (bot)
  ('000000a4-0000-0000-0000-000000000000', '000000c4-0000-0000-0000-000000000000', 'wa-demo-a4', 'whatsapp', 'bot',            null,     false, null,                        null,                                'LK-AE-1027', 'Your order LK-AE-1027 is completed and was delivered. Anything else I can help with?',  '2026-07-20T09:15:00Z', 0, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'TRACK_ORDER_001', true),
  -- 5. B2B enquiry (human needed)
  ('000000a5-0000-0000-0000-000000000000', '000000c3-0000-0000-0000-000000000000', 'wa-demo-a5', 'whatsapp', 'human_needed',   'medium', true,  'Business enquiry',          'Sales / Partner Acquisition',       'LK-AE-1026', 'Sure. Please share your hotel name, location, and estimated weekly laundry volume. Our team will contact you.', '2026-07-20T08:30:00Z', 1, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'B2B_ENQUIRY_001', true),
  -- 6. Payment issue (human needed)
  ('000000a6-0000-0000-0000-000000000000', '000000c2-0000-0000-0000-000000000000', 'wa-demo-a6', 'whatsapp', 'human_needed',   'high',   true,  'Payment issue',             'Customer Facing / Finance',         'LK-AE-1025', 'Sorry about that. Please share your order ID and payment screenshot if available.',     '2026-07-20T08:05:00Z', 1, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'PAYMENT_ISSUE_001', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- messages (18)
-- ---------------------------------------------------------------------
insert into messages (id, conversation_id, sender_type, message_text, is_internal, status, is_test_data, is_demo, environment, seed_batch_id, seed_source, created_by_seed, created_at)
values
  -- conv 1 (booking)
  ('0000b001-0000-0000-0000-000000000000', '000000a1-0000-0000-0000-000000000000', 'customer', 'Hi, I need laundry pickup today',                                                    false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:50:00Z'),
  ('0000b002-0000-0000-0000-000000000000', '000000a1-0000-0000-0000-000000000000', 'agent',    'Sure. Which service do you need today?',                                             false, 'sent',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:52:00Z'),
  ('0000b003-0000-0000-0000-000000000000', '000000a1-0000-0000-0000-000000000000', 'customer', 'Wash and fold please, Dubai Marina',                                                 false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:53:00Z'),
  -- conv 2 (refund urgent)
  ('0000b004-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'customer', 'This is the second time my order had a problem.',                                    false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:55:00Z'),
  ('0000b005-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'customer', 'I want my refund now!',                                                              false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:56:00Z'),
  ('0000b006-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'agent',    'Please hold on while we find a quick solution. Our team will get back to you shortly.', false, 'sent', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:58:00Z'),
  ('0000b007-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'system',   'Refund request flagged · human intervention required',                               true,  'logged',   true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:58:00Z'),
  -- conv 3 (damaged)
  ('0000b008-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', 'customer', 'My shirt came back damaged',                                                         false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:38:00Z'),
  ('0000b009-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', 'agent',    'I''m sorry about that. Please share your order ID and a photo if possible.',          false, 'sent',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:40:00Z'),
  ('0000b010-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', 'system',   'Damaged item complaint flagged · human intervention required',                       true,  'logged',   true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:40:00Z'),
  -- conv 4 (track)
  ('0000b011-0000-0000-0000-000000000000', '000000a4-0000-0000-0000-000000000000', 'customer', 'Track LK-AE-1027',                                                                   false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:14:00Z'),
  ('0000b012-0000-0000-0000-000000000000', '000000a4-0000-0000-0000-000000000000', 'agent',    'Your order LK-AE-1027 is completed and was delivered. Anything else I can help with?',false, 'sent',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:15:00Z'),
  -- conv 5 (b2b)
  ('0000b013-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', 'customer', 'We are a hotel and need laundry service',                                            false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:28:00Z'),
  ('0000b014-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', 'agent',    'Sure. Please share your hotel name, location, and estimated weekly laundry volume. Our team will contact you.', false, 'sent', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:30:00Z'),
  ('0000b015-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', 'system',   'Business enquiry flagged · routed to Sales / Partner Acquisition',                   true,  'logged',   true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:30:00Z'),
  -- conv 6 (payment)
  ('0000b016-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', 'customer', 'I was charged twice',                                                                false, 'received', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:03:00Z'),
  ('0000b017-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', 'agent',    'Sorry about that. Please share your order ID and payment screenshot if available.',   false, 'sent',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:05:00Z'),
  ('0000b018-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', 'system',   'Payment issue flagged · human intervention required',                                true,  'logged',   true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:05:00Z')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- agent_flags (5)  — refund, damaged, b2b, payment (open) + one resolved
-- ---------------------------------------------------------------------
insert into agent_flags (id, conversation_id, order_id, flag_type, priority, assigned_team, human_intervention_required, reason, suggested_reply, suggested_action, status, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed, created_at, resolved_at)
values
  ('000000f1-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', '000000d1-0000-0000-0000-000000000000', 'refund_request', 'urgent', 'Customer Facing / Finance',         true, 'Customer is angry and demanding an immediate refund.', 'Please hold on while we find a quick solution. Our team will get back to you shortly.', 'Escalate to Finance; do not promise an amount.', 'open',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'REFUND_URGENT_001', true, '2026-07-20T09:58:00Z', null),
  ('000000f2-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', null,                                   'damaged_item',   'high',   'Customer Facing / Facility Facing', true, 'Customer reports a damaged item.',                    null,                                                                                    'Ask for order ID and a photo of the damage.',   'open',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'DAMAGED_ITEM_001', true, '2026-07-20T09:40:00Z', null),
  ('000000f3-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', '000000d3-0000-0000-0000-000000000000', 'b2b_lead',       'medium', 'Sales / Partner Acquisition',       true, 'Business (hotel) enquiry — potential B2B contract.',  null,                                                                                    'Collect business name, location, weekly volume.','open',    true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'B2B_ENQUIRY_001', true, '2026-07-20T08:30:00Z', null),
  ('000000f4-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', '000000d2-0000-0000-0000-000000000000', 'payment_issue',  'high',   'Customer Facing / Finance',         true, 'Customer reports being charged twice.',               null,                                                                                    'Ask for order ID and payment screenshot.',      'open',     true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'PAYMENT_ISSUE_001', true, '2026-07-20T08:05:00Z', null),
  ('000000f5-0000-0000-0000-000000000000', '000000a4-0000-0000-0000-000000000000', '000000d4-0000-0000-0000-000000000000', 'complaint',      'low',    'Customer Facing',                   false,'Prior minor complaint — already resolved.',           null,                                                                                    'No action needed; resolved.',                   'resolved', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'COMPLETED_ORDER_001', true, '2026-07-19T17:00:00Z', '2026-07-19T17:40:00Z')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- human_takeovers (2)  — one active, one ended
-- ---------------------------------------------------------------------
insert into human_takeovers (id, conversation_id, operator_name, status, started_at, ended_at, notes, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed)
values
  ('00000e01-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'Ops — Faris', 'active', '2026-07-20T09:59:00Z', null,                   'Operator took over the urgent refund case.', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'REFUND_URGENT_001', true),
  ('00000e02-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', 'Quality — Huda', 'ended', '2026-07-20T09:41:00Z', '2026-07-20T09:50:00Z', 'Reviewed damage report, returned to queue for facility.', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'DAMAGED_ITEM_001', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- tickets (3)
-- ---------------------------------------------------------------------
insert into tickets (id, conversation_id, order_id, ticket_type, priority, assigned_team, status, title, description, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed, created_at)
values
  ('0000ac01-0000-0000-0000-000000000000', '000000a3-0000-0000-0000-000000000000', null,                                   'damage',  'high',   'Customer Facing / Facility Facing', 'open', 'Damaged shirt reported',   'Customer says a shirt came back damaged. Awaiting order ID + photo.', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'DAMAGED_ITEM_001', true, '2026-07-20T09:41:00Z'),
  ('0000ac02-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', '000000d2-0000-0000-0000-000000000000', 'billing', 'high',   'Customer Facing / Finance',         'open', 'Possible double charge',   'Customer reports being charged twice for LK-AE-1025. Finance to verify.', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'PAYMENT_ISSUE_001', true, '2026-07-20T08:06:00Z'),
  ('0000ac03-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', '000000d3-0000-0000-0000-000000000000', 'general', 'medium', 'Sales / Partner Acquisition',       'open', 'B2B hotel enquiry',        'Hotel wants recurring laundry service. Collect name/location/volume.', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'B2B_ENQUIRY_001', true, '2026-07-20T08:31:00Z')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- approval_queue (2)  — pending drafts awaiting operator approval
-- ---------------------------------------------------------------------
insert into approval_queue (id, conversation_id, message_id, approval_type, draft_text, status, requested_by, is_test_data, is_demo, environment, seed_batch_id, seed_source, test_scenario_id, created_by_seed, created_at)
values
  ('0000a901-0000-0000-0000-000000000000', '000000a6-0000-0000-0000-000000000000', null, 'whatsapp_reply', 'Thanks — I can see your order LK-AE-1025. Our Finance team is reviewing the charge and will update you shortly.', 'pending', 'WhatsApp Agent', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'PAYMENT_ISSUE_001', true, '2026-07-20T08:06:00Z'),
  ('0000a902-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', null, 'whatsapp_reply', 'Thank you! I have shared your details with our partnerships team; they will contact you with a tailored quote.', 'pending', 'WhatsApp Agent', true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', 'B2B_ENQUIRY_001', true, '2026-07-20T08:31:00Z')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- order_events (3)  — audit trail
-- ---------------------------------------------------------------------
insert into order_events (id, order_id, event_type, from_status, to_status, actor_type, actor_name, notes, is_test_data, is_demo, environment, seed_batch_id, seed_source, created_by_seed, created_at)
values
  ('0000ce01-0000-0000-0000-000000000000', '000000d1-0000-0000-0000-000000000000', 'status_change', 'active',      'pickup_scheduled', 'agent',  'WhatsApp Agent', 'Pickup slot confirmed with customer.',    true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:10:00Z'),
  ('0000ce02-0000-0000-0000-000000000000', '000000d2-0000-0000-0000-000000000000', 'status_change', 'picked_up',   'in_cleaning',      'system', 'System',         'Order received at Abu Dhabi Facility.',   true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T07:30:00Z'),
  ('0000ce03-0000-0000-0000-000000000000', '000000d4-0000-0000-0000-000000000000', 'status_change', 'out_for_delivery', 'completed',   'system', 'System',         'Delivered and marked completed.',         true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-19T18:00:00Z')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- agent_logs (4)  — safe-for-demo action trail
-- ---------------------------------------------------------------------
insert into agent_logs (id, conversation_id, action, input_json, output_json, domain, handoff, llm_mode, whatsapp_mode, safe_for_demo, is_test_data, is_demo, environment, seed_batch_id, seed_source, created_by_seed, created_at)
values
  ('00001a01-0000-0000-0000-000000000000', '000000a1-0000-0000-0000-000000000000', 'draft_reply',    '{"intent":"book_pickup"}'::jsonb,      '{"reply":"Sure. Which service do you need today?"}'::jsonb, 'in_domain', false, 'mock', 'mock', true, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:52:00Z'),
  ('00001a02-0000-0000-0000-000000000000', '000000a2-0000-0000-0000-000000000000', 'raise_flag',     '{"intent":"refund_request"}'::jsonb,   '{"flag":"refund_request","priority":"urgent"}'::jsonb,      'in_domain', true,  'mock', 'mock', true, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:58:00Z'),
  ('00001a03-0000-0000-0000-000000000000', '000000a4-0000-0000-0000-000000000000', 'track_order',    '{"order_id":"LK-AE-1027"}'::jsonb,     '{"status":"completed"}'::jsonb,                             'in_domain', false, 'mock', 'mock', true, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T09:15:00Z'),
  ('00001a04-0000-0000-0000-000000000000', '000000a5-0000-0000-0000-000000000000', 'raise_flag',     '{"intent":"b2b_enquiry"}'::jsonb,      '{"flag":"b2b_lead","team":"Sales / Partner Acquisition"}'::jsonb, 'in_domain', true, 'mock', 'mock', true, true, true, 'dev', '20260721_whatsapp_agent_seed_v1', 'whatsapp_agent_test_seed', true, '2026-07-20T08:30:00Z')
on conflict (id) do nothing;

-- Link the seeded orders back to their conversations (kept null above to avoid
-- an insert-order dependency; conversations already reference orders by business id).
update orders set conversation_id = '000000a2-0000-0000-0000-000000000000' where order_id = 'LK-AE-1024' and conversation_id is null;
update orders set conversation_id = '000000a6-0000-0000-0000-000000000000' where order_id = 'LK-AE-1025' and conversation_id is null;
update orders set conversation_id = '000000a5-0000-0000-0000-000000000000' where order_id = 'LK-AE-1026' and conversation_id is null;
update orders set conversation_id = '000000a4-0000-0000-0000-000000000000' where order_id = 'LK-AE-1027' and conversation_id is null;
update orders set conversation_id = '000000a1-0000-0000-0000-000000000000' where order_id = 'LK-AE-2031' and conversation_id is null;
