import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { PricingManagement } from "@/components/dashboard/operations/pricing/PricingManagement";

export default function PricingManagementPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        title="Pricing Management"
        description="The single source of truth for prices — WhatsApp agent, orders, and the public website all read the published catalogue. Edit a draft, preview it, and publish; historical orders keep their original prices."
      />
      <PricingManagement />
    </div>
  );
}
