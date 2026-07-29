import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { FacilitiesDirectory } from "@/components/dashboard/facilities/FacilitiesDirectory";

export default function Page() {
  return (
    <SubsectionShell sectionKey="facilities" slug="directory" showFilters={false}>
      <FacilitiesDirectory />
    </SubsectionShell>
  );
}
