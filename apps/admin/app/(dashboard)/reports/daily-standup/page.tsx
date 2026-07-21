import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { ReportSubsection } from "@/components/dashboard/reports/Reports";

export default function Page() {
  return (
    <SubsectionShell sectionKey="reports" slug="daily-standup">
      <ReportSubsection slug="daily-standup" />
    </SubsectionShell>
  );
}
