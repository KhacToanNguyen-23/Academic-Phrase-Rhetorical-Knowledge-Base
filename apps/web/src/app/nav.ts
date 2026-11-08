import {
  BookMarked,
  BookOpen,
  BookText,
  Download,
  FlaskConical,
  Inbox,
  ListChecks,
  LayoutDashboard,
  Newspaper,
  PenLine,
  ScanText,
  ShieldCheck,
  Star,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { to: string; label: string; icon: LucideIcon; publicAccess?: boolean };
export type NavGroup = { label: string; items: NavItem[] };

export const HOME: NavItem = { to: "/app", label: "Workspace", icon: LayoutDashboard };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Reference",
    items: [
      { to: "/library", label: "Library", icon: BookOpen },
      { to: "/phrasebank", label: "Phrasebank", icon: BookMarked },
      { to: "/vocabulary", label: "Vocabulary", icon: BookText },
      { to: "/journals", label: "Journals", icon: Newspaper },
    ],
  },
  {
    label: "Review",
    items: [
      { to: "/inbox", label: "Inbox", icon: Inbox },
      { to: "/gold", label: "Gold review", icon: Star },
      { to: "/extract", label: "Extract", icon: ScanText },
    ],
  },
  { label: "Corpus", items: [{ to: "/import", label: "Import", icon: Download }, { to: "/jobs", label: "Jobs", icon: ListChecks }] },
  {
    label: "Tools",
    items: [
      { to: "/playground", label: "Playground", icon: FlaskConical },
      { to: "/writer", label: "Writer", icon: PenLine, publicAccess: true },
    ],
  },
];

export const ADMIN_ITEM: NavItem = { to: "/admin", label: "Admin", icon: ShieldCheck };

const ALL_ITEMS: NavItem[] = [HOME, ...NAV_GROUPS.flatMap((g) => g.items), ADMIN_ITEM];

export function isActivePath(pathname: string, to: string) {
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function titleFor(pathname: string) {
  return ALL_ITEMS.find((item) => isActivePath(pathname, item.to))?.label ?? "Academic Wordbank";
}
