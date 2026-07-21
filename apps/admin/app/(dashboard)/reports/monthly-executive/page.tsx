import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { ReportSubsection } from "@/components/dashboard/reports/Reports";

export default function Page() {
  return (
    <SubsectionShell sectionKey="reports" slug="monthly-executive">
      <ReportSubsection slug="monthly-executive" />
    </SubsectionShell>
  );
}
