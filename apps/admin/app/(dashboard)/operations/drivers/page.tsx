import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsSubNav } from "@/components/dashboard/operations/OperationsSubNav";
import { Drivers } from "@/components/dashboard/operations/Drivers";

export default function DriversPage() {
  return (
    <div className="lk-enter">
      <OperationsSubNav />
      <ResponsivePageHeader
        title="Drivers"
        description="Pickup and delivery fleet — driver overview, pickup & delivery queues, performance and driver issues. Area/city only in broad tables."
      />
      <Drivers />
    </div>
  );
}
