import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsLanding } from "@/components/dashboard/operations/OperationsLanding";

export default function OperationsPage() {
  return (
    <div className="lk-enter">
      <ResponsivePageHeader
        eyebrow="Operations"
        title="Operations"
        description="Your operational command center. Open a section to manage it on its own focused page — customer support, facility work, drivers, or the full customer order center."
      />
      <OperationsLanding />
    </div>
  );
}
