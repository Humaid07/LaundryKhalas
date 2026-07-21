import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SettingsSubsection } from "@/components/dashboard/settings/Settings";

export default function Page() {
  return (
    <SubsectionShell sectionKey="settings" slug="roles-permissions">
      <SettingsSubsection slug="roles-permissions" />
    </SubsectionShell>
  );
}
