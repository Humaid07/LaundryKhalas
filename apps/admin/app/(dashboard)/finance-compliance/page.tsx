import { Download } from "lucide-react";
import { SectionLanding } from "@/components/dashboard/section/SectionLanding";
import { Button } from "@/components/dashboard/ui/Button";

export default function FinanceCompliancePage() {
  return (
    <SectionLanding
      sectionKey="finance-compliance"
      actions={<Button variant="secondary"><Download className="h-4 w-4" /> Export</Button>}
    />
  );
}
