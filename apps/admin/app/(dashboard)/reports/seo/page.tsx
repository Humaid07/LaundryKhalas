import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { ReportSubsection } from "@/components/dashboard/reports/Reports";

export default function Page() {
  return (
    <SubsectionShell sectionKey="reports" slug="seo">
      <ReportSubsection slug="seo" />
    </SubsectionShell>
  );
}
