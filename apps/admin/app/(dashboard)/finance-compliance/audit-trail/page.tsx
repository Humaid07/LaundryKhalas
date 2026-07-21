import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { FinanceSubsection } from "@/components/dashboard/finance-compliance/FinanceCompliance";

export default function Page() {
  return (
    <SubsectionShell sectionKey="finance-compliance" slug="audit-trail">
      <FinanceSubsection slug="audit-trail" />
    </SubsectionShell>
  );
}
