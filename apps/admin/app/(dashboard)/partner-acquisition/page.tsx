import { Handshake } from "lucide-react";
import { SectionLanding } from "@/components/dashboard/section/SectionLanding";
import { Button } from "@/components/dashboard/ui/Button";

export default function PartnerAcquisitionPage() {
  return (
    <SectionLanding
      sectionKey="partner-acquisition"
      actions={<Button variant="primary"><Handshake className="h-4 w-4" /> Add partner lead</Button>}
    />
  );
}
