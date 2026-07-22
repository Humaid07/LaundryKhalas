import { Suspense } from "react";
import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { CustomerOrders } from "@/components/dashboard/operations/CustomerOrders";
import { LiveWhatsAppOrders } from "@/components/dashboard/operations/live/LiveWhatsAppOrders";
import { ServiceTaxonomyWarning } from "@/components/dashboard/operations/live/ServiceTaxonomyWarning";

export default function CustomerOrdersPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        title="Customer Orders"
        description="The dedicated order center for every customer order — WhatsApp, website, app, B2B and manual bookings. Separate from Customer Facing support."
      />
      {/* Service-taxonomy drift guardrail (renders only when live + out of sync). */}
      <ServiceTaxonomyWarning />
      {/* Live WhatsApp-created orders (renders only when the live flag is on). */}
      <LiveWhatsAppOrders />
      {/* CustomerOrders reads the active status tab from ?tab= (useSearchParams). */}
      <Suspense fallback={null}>
        <CustomerOrders />
      </Suspense>
    </div>
  );
}
