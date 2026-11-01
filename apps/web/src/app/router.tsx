import { createRootRoute, createRoute, createRouter, getRouteApi, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { AdminPage } from "@/features/admin";
import { InboxPage } from "@/features/inbox";
import { GoldPage } from "@/features/gold";
import { JournalProfilePage } from "@/features/journal-profile";
import { LibraryPage } from "@/features/library";
import { OverviewPage } from "@/features/overview";
import { PlaygroundPage } from "@/features/playground";
import { SlrImportPage } from "@/features/slr-import";
import { useTheme } from "@/shared/lib/theme";

// "/" là dashboard giới thiệu (mở qua logo). UI là bảng điều khiển của bank: người viết dùng qua Writing Engine (API), không qua UI này.
// Data out: Library → Playground (mô phỏng API). Data in: Inbox. Giám sát: Admin.
const NAV = [
  { to: "/library", label: "Library" },
  { to: "/playground", label: "Playground" },
  { to: "/inbox", label: "Inbox" },
  { to: "/journals", label: "Journals" },
  { to: "/admin", label: "Admin" },
  { to: "/import", label: "Import" },
  { to: "/gold", label: "Gold review" },
] as const;

function Shell() {
  // Key theo pathname để animation từng section chạy lại khi chuyển trang.
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  // Bóng đổ header khi cuộn (giống SLRS: data-scrolled)
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead" data-scrolled={scrolled || undefined}>
        <div className="masthead-inner">
          <Link to="/" className="brand" aria-label="Academic Wordbank — home">
            <span className="brand-mark" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z" /><path d="M13 4h5.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H13" /><path d="M7 8.5h1.5M7 12h1.5M16 8.5h1M16 12h1" />
              </svg>
            </span>
            <span className="brand-name">academic <em>wordbank</em></span>
          </Link>
          <nav aria-label="Contents">
            <ul className="toc">
              {NAV.map((n) => (
                <li key={n.to}>
                  <Link to={n.to} className="toc-link" activeProps={{ "aria-current": "page" }}>
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="masthead-right">
            <button type="button" className="theme-toggle" aria-pressed={theme === "dark"} onClick={toggle}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              <span className="knob" aria-hidden />
              {theme === "dark" ? "Dark" : "Light"}
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="main" key={pathname}>
        <Outlet />
      </main>
      <footer className="colophon">
        <span>© 2026 Academic Wordbank · Patterns are self-authored or used with permission</span>
        <span>Mock data · OpenAlex disabled</span>
      </footer>
    </>
  );
}

const root = createRootRoute({ component: Shell });

const str = (v: unknown) => (typeof v === "string" ? v : undefined);

// Trang chủ: giới thiệu + tổng quan; chỉ vào được qua logo, không nằm trên nav.
const overview = createRoute({ getParentRoute: () => root, path: "/", component: OverviewPage });

const library = createRoute({
  getParentRoute: () => root,
  path: "/library",
  validateSearch: (s: Record<string, unknown>): { p?: string } => ({ p: str(s.p) }),
  component: () => <LibraryPage selectedId={getRouteApi("/library").useSearch().p} />,
});

const playground = createRoute({
  getParentRoute: () => root,
  path: "/playground",
  validateSearch: (s: Record<string, unknown>): { pattern?: string } => ({ pattern: str(s.pattern) }),
  component: () => <PlaygroundPage patternId={getRouteApi("/playground").useSearch().pattern} />,
});

const inbox = createRoute({ getParentRoute: () => root, path: "/inbox", component: InboxPage });
const admin = createRoute({ getParentRoute: () => root, path: "/admin", component: AdminPage });
const slrImport = createRoute({ getParentRoute: () => root, path: "/import", component: SlrImportPage });
const gold = createRoute({ getParentRoute: () => root, path: "/gold", component: GoldPage });

const journals = createRoute({ getParentRoute: () => root, path: "/journals", component: () => <JournalProfilePage /> });
const journal = createRoute({
  getParentRoute: () => root,
  path: "/journals/$journalId",
  component: () => <JournalProfilePage journalId={getRouteApi("/journals/$journalId").useParams().journalId} />,
});

export const router = createRouter({
  routeTree: root.addChildren([overview, library, playground, inbox, journals, journal, admin, slrImport, gold]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
