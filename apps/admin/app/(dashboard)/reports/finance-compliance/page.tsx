import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { ReportSubsection } from "@/components/dashboard/reports/Reports";

export default function Page() {
  return (
    <SubsectionShell sectionKey="reports" slug="finance-compliance">
      <ReportSubsection slug="finance-compliance" />
    </SubsectionShell>
  );
}
