import { Sparkles } from "lucide-react";
import { SectionLanding } from "@/components/dashboard/section/SectionLanding";
import { Button } from "@/components/dashboard/ui/Button";

export default function SeoAgentsPage() {
  return (
    <SectionLanding
      sectionKey="seo-agents"
      actions={<Button variant="primary"><Sparkles className="h-4 w-4" /> Run all agents</Button>}
    />
  );
}
