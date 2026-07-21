import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { ReportSubsection } from "@/components/dashboard/reports/Reports";

export default function Page() {
  return (
    <SubsectionShell sectionKey="reports" slug="partner-acquisition">
      <ReportSubsection slug="partner-acquisition" />
    </SubsectionShell>
  );
}
