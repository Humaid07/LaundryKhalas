import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OrdersSection } from "@/components/dashboard/orders/OrdersSection";

export default function OrdersPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        title="Orders"
        description="Every order created through WhatsApp — live from the database. Open an order for full details, timeline and status, or jump straight to its conversation in Operations."
      />
      <OrdersSection />
    </div>
  );
}
