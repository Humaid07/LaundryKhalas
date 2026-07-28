import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { HumanInterventionQueue } from "@/components/dashboard/operations/HumanInterventionQueue";

export default function HumanInterventionPage() {
  return (
    <div className="lk-enter space-y-5">
      <ResponsivePageHeader
        title="Human Intervention"
        description="Conversations paused because of abuse, threats or a customer request. Claim a case to take over and reply directly; the AI stays paused until you release it. Privacy firewall on — masked phone + sanitized preview only."
      />
      <HumanInterventionQueue />
    </div>
  );
}
