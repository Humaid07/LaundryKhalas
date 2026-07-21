import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsSubNav } from "@/components/dashboard/operations/OperationsSubNav";
import { CustomerFacing } from "@/components/dashboard/operations/CustomerFacing";

export default function CustomerFacingPage() {
  return (
    <div className="lk-enter">
      <OperationsSubNav />
      <ResponsivePageHeader
        title="Customer Facing"
        description="The WhatsApp Agent inbox, tickets, cancellations, order changes, follow-ups and support escalations. Operators view conversations and take over only when the agent raises a flag."
      />
      <CustomerFacing />
    </div>
  );
}
