import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { FacilityCompliance } from "@/components/dashboard/facilities/FacilityCompliance";

export default function Page() {
  return (
    <SubsectionShell sectionKey="facilities" slug="compliance">
      <FacilityCompliance />
    </SubsectionShell>
  );
}
