import { Suspense } from "react";
import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { CustomerFacing } from "@/components/dashboard/operations/CustomerFacing";
import { LiveWhatsAppConversations } from "@/components/dashboard/operations/live/LiveWhatsAppConversations";
import { OperationsDeepLink } from "@/components/dashboard/operations/live/OperationsDeepLink";

export default function CustomerFacingPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        title="Customer Facing"
        description="The WhatsApp Agent inbox, tickets, cancellations, order changes, follow-ups and support escalations. Operators view conversations and take over only when the agent raises a flag."
      />
      {/* Deep link from an order card: opens the exact linked conversation + order
          context. Renders nothing when no conversationId param is present. */}
      <Suspense fallback={null}>
        <OperationsDeepLink />
      </Suspense>
      {/* Live WhatsApp inbox + open flags (renders only when the live flag is on). */}
      <LiveWhatsAppConversations />
      <CustomerFacing />
    </div>
  );
}
