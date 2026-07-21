import { Wand2 } from "lucide-react";
import Link from "next/link";
import { SectionLanding } from "@/components/dashboard/section/SectionLanding";
import { Button } from "@/components/dashboard/ui/Button";

export default function MarketingPage() {
  return (
    <SectionLanding
      sectionKey="marketing"
      actions={<Link href="/marketing/creative-studio"><Button variant="primary"><Wand2 className="h-4 w-4" /> Open Creative Studio</Button></Link>}
    />
  );
}
