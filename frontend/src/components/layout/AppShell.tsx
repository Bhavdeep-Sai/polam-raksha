import type { ReactNode } from "react";

import { PwaStatusBar } from "@/components/common/PwaStatusBar";
import { Header } from "@/components/layout/Header";
import { MobileNavigation } from "@/components/layout/MobileNavigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuth } from "@/features/auth/AuthContext";
import { PUBLIC_NAV, ROLE_NAV } from "@/lib/navigation";

interface AppShellProps {
  children: ReactNode;
  showSidebar?: boolean;
}

export function AppShell({ children, showSidebar = true }: AppShellProps) {
  const { user } = useAuth();
  const navItems = user ? ROLE_NAV[user.role] : PUBLIC_NAV;
  const isFarmer = user?.role === "FARMER";

  return (
    <div className="flex min-h-screen flex-col bg-brand-bg text-brand-ink">
      <Header />
      <PwaStatusBar />
      <div className="mx-auto flex w-full max-w-7xl flex-1">
        {showSidebar ? <Sidebar items={navItems} largeControls={isFarmer} /> : null}
        <main className="min-w-0 flex-1 px-4 py-6 pb-24 sm:px-6 md:pb-8">
          {children}
        </main>
      </div>
      <MobileNavigation items={navItems} />
    </div>
  );
}
