import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronsUpDown, LogIn, LogOut, Moon, Sun } from "lucide-react";

import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAuth } from "@/features/auth/AuthProvider";
import { api } from "@/shared/api";
import type { Theme } from "@/shared/lib/theme";

import { BrandMark } from "./BrandMark";
import { ADMIN_ITEM, HOME, NAV_GROUPS, isActivePath, type NavItem } from "./nav";

type Props = { pathname: string; theme: Theme; onToggleTheme: () => void };

function NavLink({ item, pathname, badge }: { item: NavItem; pathname: string; badge?: number }) {
  const { isMobile, setOpenMobile } = useSidebar();
  const active = isActivePath(pathname, item.to);
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
        <Link to={item.to} aria-current={active ? "page" : undefined} onClick={() => isMobile && setOpenMobile(false)}>
          <item.icon strokeWidth={1.5} />
          <span>{item.label}</span>
        </Link>
      </SidebarMenuButton>
      {badge ? <SidebarMenuBadge>{badge}</SidebarMenuBadge> : null}
    </SidebarMenuItem>
  );
}

export function AppSidebar({ pathname, theme, onToggleTheme }: Props) {
  const auth = useAuth();
  const navigate = useNavigate();
  const client = auth.client;
  const isAdmin = client?.role === "admin";
  // Counts appear only on queues that need work. Gold and Extract have no cheap count endpoint yet.
  const submissions = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions(), enabled: Boolean(client) });
  const inboxCount = submissions.data?.filter((s) => s.status === "pending").length;
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Light theme" : "Dark theme";
  const signOut = () => {
    auth.logout();
    void navigate({ to: "/" });
  };

  return (
    <Sidebar collapsible="icon" aria-label="Main navigation">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="Academic Wordbank">
              <Link to={client ? "/app" : "/"} aria-label="Academic Wordbank home">
                <BrandMark />
                <span className="flex min-w-0 flex-col leading-tight">
                  <span className="truncate text-sm font-medium">Academic Wordbank</span>
                  <span className="truncate text-xs text-muted-foreground">{client ? client.role : "Writer"}</span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {client && (
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavLink item={HOME} pathname={pathname} />
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
        {NAV_GROUPS.map((group) => {
          const items = group.items.filter((item) => client || item.publicAccess);
          if (items.length === 0) return null;
          return (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {items.map((item) => (
                    <NavLink key={item.to} item={item} pathname={pathname} badge={item.to === "/inbox" ? inboxCount : undefined} />
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          );
        })}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          {isAdmin && <NavLink item={ADMIN_ITEM} pathname={pathname} />}
          {client ? (
            <>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton size="lg" tooltip={client.name}>
                    <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-[2px] bg-secondary text-xs font-medium">
                      {client.name.charAt(0).toUpperCase()}
                    </span>
                    <span className="flex min-w-0 flex-col leading-tight">
                      <span className="truncate text-sm font-medium">{client.name}</span>
                      <span className="truncate text-xs text-muted-foreground">{client.role}</span>
                    </span>
                    <ChevronsUpDown className="ml-auto" strokeWidth={1.5} />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="top" align="start" className="min-w-56">
                  <DropdownMenuItem onSelect={onToggleTheme}>
                    <ThemeIcon strokeWidth={1.5} />
                    {themeLabel}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={signOut}>
                    <LogOut strokeWidth={1.5} />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={signOut} tooltip="Sign out">
                <LogOut strokeWidth={1.5} />
                <span>Sign out</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            </>
          ) : (
            <>
              <SidebarMenuItem>
                <SidebarMenuButton onClick={onToggleTheme} tooltip={themeLabel}>
                  <ThemeIcon strokeWidth={1.5} />
                  <span>{themeLabel}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Staff sign in">
                  <Link to="/signin" search={{ next: pathname }}>
                    <LogIn strokeWidth={1.5} />
                    <span>Staff sign in</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </>
          )}
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
