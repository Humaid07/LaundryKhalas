import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SettingsSubsection } from "@/components/dashboard/settings/Settings";

export default function Page() {
  return (
    <SubsectionShell sectionKey="settings" slug="agent-guardrails">
      <SettingsSubsection slug="agent-guardrails" />
    </SubsectionShell>
  );
}
