import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { OperationsSubNav } from "@/components/dashboard/operations/OperationsSubNav";
import { FacilityFacing } from "@/components/dashboard/operations/FacilityFacing";

export default function FacilityFacingPage() {
  return (
    <div className="lk-enter">
      <OperationsSubNav />
      <ResponsivePageHeader
        title="Facility Facing"
        description="Facility assignment, cleaning progress, quality checks, facility issues and delivery handoff. Privacy firewall on — area/city only, no customer PII."
      />
      <FacilityFacing />
    </div>
  );
}
