import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { PartnerSubsection } from "@/components/dashboard/partner-acquisition/PartnerAcquisition";

export default function Page() {
  return (
    <SubsectionShell sectionKey="partner-acquisition" slug="regional-coverage">
      <PartnerSubsection slug="regional-coverage" />
    </SubsectionShell>
  );
}
