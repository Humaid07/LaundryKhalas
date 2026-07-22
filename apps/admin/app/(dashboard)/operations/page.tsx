import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsOverview } from "@/components/dashboard/operations/OperationsOverview";

export default function OperationsPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        eyebrow="Operations"
        title="Operations Overview"
        description="A live summary of the operational command center. Use the sidebar (Operations ▸ Customer Facing, Facility Facing, Drivers, Customer Orders) to open a working page."
      />
      <OperationsOverview />
    </div>
  );
}
