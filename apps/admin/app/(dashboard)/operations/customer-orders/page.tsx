import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsSubNav } from "@/components/dashboard/operations/OperationsSubNav";
import { CustomerOrders } from "@/components/dashboard/operations/CustomerOrders";

export default function CustomerOrdersPage() {
  return (
    <div className="lk-enter">
      <OperationsSubNav />
      <ResponsivePageHeader
        title="Customer Orders"
        description="The dedicated order center for every customer order — WhatsApp, website, app, B2B and manual bookings. Separate from Customer Facing support."
      />
      <CustomerOrders />
    </div>
  );
}
