# Operations Navigation Rule

Status: **Active** · Last updated: 2026-07-22

## The rule

Operations navigation is split into two clearly separated layers so the UI stays
uncluttered and predictable:

- **Left sidebar** controls **which Operations subsection** the user is in.
- **Page top tabs** control the **workflow / status view** inside that subsection.
- **Main content** shows the **cards / records** for the selected tab.
- **Detail drawer** shows the **full data + actions** for a selected record.

> Do **not** use top tabs to navigate between Operations subsections. Top tabs are
> only for statuses / workflows inside the current subsection. Subsection
> navigation lives **only** in the left sidebar.

## Structure

```
LEFT SIDEBAR
Operations
  ├─ Customer Facing   → /operations/customer-facing
  ├─ Facility Facing   → /operations/facility-facing
  ├─ Drivers           → /operations/drivers
  └─ Customer Orders   → /operations/customer-orders

PAGE-LEVEL TOP TABS  (change per subsection — workflow/status only)
  Customer Facing : WhatsApp Inbox · Pending Replies · Human Takeover · Tickets ·
                    Cancellations · Follow-ups · Complaints · Escalations
  Facility Facing : All Facility Orders · Awaiting Assignment · In Cleaning ·
                    Quality Check · Delayed at Facility · Ready for Delivery ·
                    Facility Issues · Handoffs
  Drivers         : Driver Overview · Pickup Queue · Pickup Scheduled ·
                    In Transit to Facility · Delivery Queue · Out for Delivery ·
                    Completed Deliveries · Driver Issues
  Customer Orders : All Orders · New Orders · Active Orders · Pickup Scheduled ·
                    In Cleaning · Ready for Delivery · Out for Delivery ·
                    Completed · Cancelled · Issues / Escalations
```

## UX pattern

1. Each top tab filters/switches the data shown on that specific page.
2. The selected tab shows only the related cards / records.
3. Cards are clickable.
4. Clicking a card opens the record's **full detail** with all information.
5. **Actions live only inside that detail view** — there is no standalone generic
   "Order Actions" / "Driver actions" / "Customer actions" panel on the page.

### Detail surface per subsection

- **Customer Facing · Facility Facing · Drivers** → open a **right-hand detail
  drawer** (`DetailDrawer` + `DrawerActions`) for a quick, in-context peek.
- **Customer Orders** → opens a **dedicated full-page order workspace** at
  `/operations/customer-orders/[orderId]`, **not** a drawer. The order record is
  information-dense (lifecycle, items, customer, payment, assignment, notes,
  conversation, events), so it earns a spacious page. The active status tab is
  carried in `?tab=` so "back" returns to the exact view. See
  [[customer-order-detail-page]].

### Order / record actions (example — Customer Orders)

Shown **only** inside the opened order detail drawer:
Change status · Assign facility · Assign driver · Reschedule pickup ·
Mark ready for delivery · Escalate to human · Add internal note ·
View related WhatsApp conversation · Open customer-facing chat ·
Cancel order (only if allowed) · Refund request (approval required).

## Shared building blocks

All four subsections are built from the same primitives in
`apps/admin/components/dashboard/operations/workspace/Workspace.tsx`:

| Primitive        | Role                                                        |
| ---------------- | ---------------------------------------------------------- |
| `WorkflowTabs`   | The per-page status/workflow tab strip (never subsection nav) |
| `CardGrid`       | Responsive grid of record cards                            |
| `RecordCard`     | A clickable operational record card (carries no actions)   |
| `DetailDrawer`   | Right-hand drawer with full detail + an actions footer     |
| `DrawerActions`  | The **only** place record actions render                   |

## Privacy

- **Facility Facing** and **Drivers**: customer **area / city only** — never
  customer name, phone, email, full address or payment details.
- **Customer Facing** and **Customer Orders**: phones are **masked** in lists;
  full number / address is a role-gated secure detail only.
- Refunds, cancellations outside policy and outbound replies are **approval-gated**
  (labelled with an `Approval` chip in the drawer). Nothing is dispatched live.

See also: [[privacy-firewall]] · [[dashboard-navigation]] · [[dashboard-information-architecture]]
