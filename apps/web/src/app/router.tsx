import { createRootRoute, createRoute, createRouter, getRouteApi, lazyRouteComponent, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { AdminPage } from "@/features/admin";
import { LoginPage } from "@/features/auth/LoginPage";
import { useAuth } from "@/features/auth/AuthProvider";
import { InboxPage } from "@/features/inbox";
import { GoldPage } from "@/features/gold";
import { JournalProfilePage } from "@/features/journal-profile";
import { LibraryPage } from "@/features/library";
import { OverviewPage } from "@/features/overview";
import { ExtractPage } from "@/features/phrase-extraction";
import { PlaygroundPage } from "@/features/playground";
import { PhrasebankCategory, PhrasebankHome } from "@/features/phrasebank/PhrasebankPage";
import { OnlineWriterPage } from "@/features/playground/components/OnlineWriterPage";
import { Loading } from "@/shared/ui";
import { SlrImportPage } from "@/features/slr-import";
import { VocabularyLemmaPage, VocabularyPage } from "@/features/vocabulary";
import { useTheme } from "@/shared/lib/theme";

import { Sidebar } from "./Sidebar";

const SIDEBAR_KEY = "aprkb.sidebar.collapsed";

function Shell() {
  // Key theo pathname để animation từng section chạy lại khi chuyển trang.
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  const auth = useAuth();
  const sideToggleRef = useRef<HTMLButtonElement>(null);
  const appBodyRef = useRef<HTMLDivElement>(null);
  // Bóng đổ header khi cuộn (giống SLRS: data-scrolled)
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  // Desktop: thu gọn thành dải icon (nhớ qua localStorage). Mobile (≤ 860px): drawer trượt, đóng khi chọn trang.
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => { localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0"); }, [collapsed]);
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);
  useEffect(() => {
    appBodyRef.current?.toggleAttribute("inert", mobileOpen);
  }, [mobileOpen]);
  const wasMobileOpen = useRef(false);
  useEffect(() => {
    if (!mobileOpen && wasMobileOpen.current) sideToggleRef.current?.focus();
    wasMobileOpen.current = mobileOpen;
  }, [mobileOpen]);
  const toggleSidebar = () => {
    if (window.matchMedia("(max-width: 860px)").matches) setMobileOpen((o) => !o);
    else setCollapsed((c) => !c);
  };
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead" data-scrolled={scrolled || undefined}>
        <div className="masthead-inner">
          <button ref={sideToggleRef} type="button" className="side-toggle" onClick={toggleSidebar} aria-controls="sidebar" aria-expanded={mobileOpen}
            aria-label="Toggle navigation" title="Toggle navigation">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <Link to="/" className="brand" aria-label="Academic Wordbank — home">
            <span className="brand-mark" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z" /><path d="M13 4h5.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H13" /><path d="M7 8.5h1.5M7 12h1.5M16 8.5h1M16 12h1" />
              </svg>
            </span>
            <span className="brand-name">academic <em>wordbank</em></span>
          </Link>
          <div className="masthead-spacer" />
          <div className="masthead-right">
            {!auth.client && pathname === "/writer" && (
              <Link to="/" className="btn btn-ghost btn-sm">Staff sign in</Link>
            )}
            <button type="button" className="theme-toggle" aria-pressed={theme === "dark"} onClick={toggle}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              <span className="knob" aria-hidden />
              {theme === "dark" ? "Dark" : "Light"}
            </button>
          </div>
        </div>
      </header>
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        client={auth.client}
        onLogout={auth.logout}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        onCloseMobile={() => setMobileOpen(false)}
        onNavigate={() => setMobileOpen(false)}
      />
      {mobileOpen && <div className="side-scrim" aria-hidden onClick={() => setMobileOpen(false)} />}
      <div ref={appBodyRef} className="app-body" data-sidebar={collapsed ? "collapsed" : "expanded"}>
      <main id="main" className="main" key={pathname}>
        {pathname === "/writer" ? <Outlet /> : auth.loading ? <Loading /> : auth.client ? (
          pathname === "/admin" && auth.client.role !== "admin"
            ? <p className="notice notice-warn" role="alert">Admin role required for this page.</p>
            : <Outlet />
        ) : <LoginPage />}
      </main>
      <footer className="colophon">
        <span>© 2026 Academic Wordbank · Patterns are self-authored or used with permission</span>
        <span>Writer dùng API thật · Các trang mô phỏng còn dùng mock</span>
      </footer>
      </div>
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

const phrasebank = createRoute({ getParentRoute: () => root, path: "/phrasebank", component: PhrasebankHome });
const phrasebankCategory = createRoute({
  getParentRoute: () => root,
  path: "/phrasebank/$slug",
  component: () => <PhrasebankCategory slug={getRouteApi("/phrasebank/$slug").useParams().slug} />,
});

const playground = createRoute({
  getParentRoute: () => root,
  path: "/playground",
  validateSearch: (s: Record<string, unknown>): { pattern?: string } => ({ pattern: str(s.pattern) }),
  component: () => <PlaygroundPage patternId={getRouteApi("/playground").useSearch().pattern} />,
});

const writer = createRoute({ getParentRoute: () => root, path: "/writer", component: OnlineWriterPage });

const inbox = createRoute({ getParentRoute: () => root, path: "/inbox", component: InboxPage });
const admin = createRoute({ getParentRoute: () => root, path: "/admin", component: AdminPage });
const slrImport = createRoute({ getParentRoute: () => root, path: "/import", component: SlrImportPage });
const gold = createRoute({ getParentRoute: () => root, path: "/gold", component: GoldPage });
const vocabularySearch = (s: Record<string, unknown>) => ({
  view: s.view === "families" ? ("families" as const) : s.view === "lemmas" ? ("lemmas" as const) : undefined,
  letter: str(s.letter),
  q: str(s.q),
  coreOnly: typeof s.coreOnly === "boolean" ? s.coreOnly : s.coreOnly === "true" ? true : undefined,
  sort: s.sort === "rank" ? ("rank" as const) : s.sort === "alpha" ? ("alpha" as const) : undefined,
  offset: typeof s.offset === "number" ? s.offset : Number.isFinite(Number(s.offset)) ? Number(s.offset) : undefined,
});
const vocabulary = createRoute({
  getParentRoute: () => root,
  path: "/vocabulary",
  validateSearch: vocabularySearch,
  component: VocabularyPage,
});
const vocabularyLemma = createRoute({
  getParentRoute: () => root,
  path: "/vocabulary/$lemmaId",
  validateSearch: vocabularySearch,
  component: VocabularyLemmaPage,
});
// ?batch=<id>[,<id>] preselects batches; the Import page links here when a run finishes.
const extract = createRoute({
  getParentRoute: () => root,
  path: "/extract",
  validateSearch: (s: Record<string, unknown>): { batch?: string } => ({ batch: str(s.batch) }),
  component: () => <ExtractPage initialBatch={getRouteApi("/extract").useSearch().batch} />,
});

const journals = createRoute({ getParentRoute: () => root, path: "/journals", component: () => <JournalProfilePage /> });
const journal = createRoute({
  getParentRoute: () => root,
  path: "/journals/$journalId",
  component: () => <JournalProfilePage journalId={getRouteApi("/journals/$journalId").useParams().journalId} />,
});

const devUiRoute = import.meta.env.DEV || import.meta.env.MODE === "inspect"
  ? createRoute({
      getParentRoute: () => root,
      path: "/dev/ui",
      component: lazyRouteComponent(() => import("@/features/dev-ui/DevUIPage").then((module) => ({ default: module.DevUIPage }))),
    })
  : undefined;

export const router = createRouter({
  routeTree: root.addChildren([
    overview,
    library,
    phrasebank,
    phrasebankCategory,
    playground,
    writer,
    inbox,
    journals,
    journal,
    admin,
    slrImport,
    extract,
    gold,
    vocabulary,
    vocabularyLemma,
    ...(devUiRoute ? [devUiRoute] : []),
  ]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
