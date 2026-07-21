import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { MarketingSubsection } from "@/components/dashboard/marketing/Marketing";

export default function Page() {
  return (
    <SubsectionShell sectionKey="marketing" slug="creative-studio">
      <MarketingSubsection slug="creative-studio" />
    </SubsectionShell>
  );
}
