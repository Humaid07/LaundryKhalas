import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SalesSubsection } from "@/components/dashboard/sales/Sales";

export default function Page() {
  return (
    <SubsectionShell sectionKey="sales" slug="overview" showFilters>
      <SalesSubsection slug="overview" />
    </SubsectionShell>
  );
}
