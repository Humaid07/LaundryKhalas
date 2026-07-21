import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { SettingsStatus } from "@/lib/types";

export function ModeBanner({ status }: { status: SettingsStatus | null }) {
  const live = status?.whatsapp_live_ready ?? false;

  if (live) {
    return (
      <div className="flex items-center gap-2 bg-wa-danger/10 px-4 py-2 text-xs font-medium text-wa-danger">
        <AlertTriangle size={14} />
        Live WhatsApp Mode Enabled — replies will send through the real Meta Cloud API.
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 bg-wa-accent/10 px-4 py-2 text-xs font-medium text-wa-accent-dark">
      <ShieldCheck size={14} />
      Mock Mode — No real WhatsApp messages are being sent.
    </div>
  );
}
