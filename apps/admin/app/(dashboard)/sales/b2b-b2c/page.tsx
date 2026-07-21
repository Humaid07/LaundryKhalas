import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SalesSubsection } from "@/components/dashboard/sales/Sales";

export default function Page() {
  return (
    <SubsectionShell sectionKey="sales" slug="b2b-b2c">
      <SalesSubsection slug="b2b-b2c" />
    </SubsectionShell>
  );
}
