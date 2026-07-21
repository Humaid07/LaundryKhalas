import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { DevSubsection } from "@/components/dashboard/dev-automation/DevAutomation";

export default function Page() {
  return (
    <SubsectionShell sectionKey="dev-automation" slug="technical-issues">
      <DevSubsection slug="technical-issues" />
    </SubsectionShell>
  );
}
