import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { FinanceSubsection } from "@/components/dashboard/finance-compliance/FinanceCompliance";

export default function Page() {
  return (
    <SubsectionShell sectionKey="finance-compliance" slug="refunds-adjustments">
      <FinanceSubsection slug="refunds-adjustments" />
    </SubsectionShell>
  );
}
