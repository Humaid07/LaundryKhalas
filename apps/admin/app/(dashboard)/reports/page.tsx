import { FileText } from "lucide-react";
import { SectionLanding } from "@/components/dashboard/section/SectionLanding";
import { Button } from "@/components/dashboard/ui/Button";

export default function ReportsPage() {
  return (
    <SectionLanding
      sectionKey="reports"
      actions={<Button variant="primary"><FileText className="h-4 w-4" /> New report</Button>}
    />
  );
}
