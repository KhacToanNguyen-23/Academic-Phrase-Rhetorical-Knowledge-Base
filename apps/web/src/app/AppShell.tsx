import { Outlet, useRouterState } from "@tanstack/react-router";
import { useState, type CSSProperties } from "react";

import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useTheme } from "@/shared/lib/theme";

import { AppSidebar } from "./AppSidebar";
import { CommandMenu } from "./CommandMenu";
import { titleFor } from "./nav";

const SIDEBAR_KEY = "aprkb.sidebar.collapsed";

function readCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(() => !readCollapsed());

  const onOpenChange = (next: boolean) => {
    setOpen(next);
    try {
      localStorage.setItem(SIDEBAR_KEY, next ? "0" : "1");
    } catch {
      // Storage blocked: the sidebar still works, it just is not remembered.
    }
  };

  return (
    <TooltipProvider>
    <SidebarProvider open={open} onOpenChange={onOpenChange} style={{ "--sidebar-width": "15rem" } as CSSProperties}>
      <a className="skip" href="#main">Skip to content</a>
      <AppSidebar pathname={pathname} theme={theme} onToggleTheme={toggle} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b bg-background px-3 md:hidden">
          <SidebarTrigger aria-label="Open navigation" />
          <span className="truncate text-sm font-medium">{titleFor(pathname)}</span>
        </header>
        <main id="main" className="main w-full">
          <Outlet />
        </main>
      </div>
      <CommandMenu />
      <Toaster position="bottom-right" />
    </SidebarProvider>
    </TooltipProvider>
  );
}
