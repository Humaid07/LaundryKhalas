import type { ReactNode } from "react";
import { AuthGuard } from "@/components/shell/AuthGuard";
import { FacilityMobileShell } from "@/components/layout/FacilityMobileShell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <FacilityMobileShell>{children}</FacilityMobileShell>
    </AuthGuard>
  );
}
