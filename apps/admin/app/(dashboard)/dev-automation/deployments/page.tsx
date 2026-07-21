import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { DevSubsection } from "@/components/dashboard/dev-automation/DevAutomation";

export default function Page() {
  return (
    <SubsectionShell sectionKey="dev-automation" slug="deployments">
      <DevSubsection slug="deployments" />
    </SubsectionShell>
  );
}
