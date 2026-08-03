import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { FacilitiesOverview } from "@/components/dashboard/facilities/FacilitiesOverview";

export default function Page() {
  return (
    <SubsectionShell sectionKey="facilities" slug="overview" showFilters={false}>
      <FacilitiesOverview />
    </SubsectionShell>
  );
}
