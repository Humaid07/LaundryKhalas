import { AppShell } from "@/components/dashboard/shell/AppShell";
import { AuthGuard } from "@/components/dashboard/shell/AuthGuard";
import { FiltersProvider } from "@/components/dashboard/shell/FiltersProvider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <FiltersProvider>
        <AppShell>{children}</AppShell>
      </FiltersProvider>
    </AuthGuard>
  );
}
