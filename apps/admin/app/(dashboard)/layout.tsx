import { AppShell } from "@/components/dashboard/shell/AppShell";
import { FiltersProvider } from "@/components/dashboard/shell/FiltersProvider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <FiltersProvider>
      <AppShell>{children}</AppShell>
    </FiltersProvider>
  );
}
