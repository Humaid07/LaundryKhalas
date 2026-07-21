import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SeoSubsection } from "@/components/dashboard/seo/SeoAgents";

export default function Page() {
  return (
    <SubsectionShell sectionKey="seo-agents" slug="hyperlocal-pages">
      <SeoSubsection slug="hyperlocal-pages" />
    </SubsectionShell>
  );
}
