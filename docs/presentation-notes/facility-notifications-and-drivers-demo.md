# Demo Notes — Facility Notifications & Drivers (2026-07-27)

## What we can show
1. **Facility gets pinged automatically.** Confirm a WhatsApp booking → it auto-assigns
   to a facility → the facility app's **notification bell** lights up with "New order
   assigned". Run an order action (Start cleaning), assign a driver, or have Operations
   reply to an issue → each fires its own notification. All **mock** today (logged +
   shown in-app), one env flip away from live.
2. **Drivers is now its own section.** New left-sidebar / mobile bottom-nav item. Open it
   → Free / On Job / Issues tiles, tabs (All, Free, On Job, Pickup, Delivery, Issues), and
   driver cards showing who's free and who's mid-task with which order.
3. **Assign an order to a driver** → the driver flips to **On Job**, the Free count drops,
   the order timeline records it, and the order detail now shows the assigned driver.

## Suggested flow
Notifications bell → Orders (run an action, watch a new notification) → Drivers list
(tiles + tabs) → assign a free driver to an order → back to Drivers (now On Job) → open
the order detail (driver shown) → Settings → Notifications (manage numbers + subscribed
alert types).

## Talking points (plain language)
- The facility team no longer has to keep refreshing the dashboard — the right people get
  a message the moment something needs them.
- Drivers are operational, so they get their own screen, not a Settings sub-tab.
- Everything is **mock-first**: nothing is texted to a real phone until we explicitly turn
  on a live channel. No customer phone numbers, addresses, or payment details ever appear
  in a facility notification or driver card.
- Isolation is enforced on the server: a facility can only ever see and assign its own
  drivers and its own notifications.

## Business value
Faster facility response (SLA), clearer driver operations, and a safe path to live mobile
alerts later — with the privacy firewall baked in.

## Honest caveats
- Live send (WhatsApp/SMS) is **not** wired yet — notifications are logged, not texted.
- Needs the dev/test Supabase DB + seed data; driver login (per-driver) is future work.
- `facility_staff` is view-only for management actions for now.

## What's next
Wire an approved live notification channel behind the readiness flag; add a limited-edit
staff tier; optional per-driver login.
