import { createRootRoute, createRoute, createRouter, getRouteApi, Link, Outlet, useRouterState } from "@tanstack/react-router";

import { JournalProfilePage } from "@/features/journal-profile";
import { PatternDetailPage } from "@/features/pattern-detail";
import { SearchExplorerPage } from "@/features/search-explorer";
import { SentenceComposerPage } from "@/features/sentence-composer";
import { ValidationConsolePage } from "@/features/validation-console";
import { useTheme } from "@/shared/lib/theme";

// Writer flow (PRD-10.1): WB-01 → WB-02 → WB-03 → WB-08. WB-04 cho Journal Analyst.
const NAV = [
  { to: "/", label: "Pattern Search", num: "I" },
  { to: "/compose", label: "Composer", num: "II" },
  { to: "/validate", label: "Validation", num: "III" },
  { to: "/journals", label: "Journal Profiles", num: "IV" },
] as const;

function Shell() {
  // Key theo pathname để animation từng section chạy lại khi chuyển trang.
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead">
        <div className="masthead-inner">
          <div className="masthead-top">
            <Link to="/" className="brand">
              <span className="brand-name">Academic <em>Wordbank</em></span>
              <span className="brand-sub">A knowledge base of rhetorical patterns for scholarly writing</span>
            </Link>
            <div className="masthead-right">
              <span className="issue">Vol. 1 · No. 1 · 2026</span>
              <button type="button" className="theme-toggle" aria-pressed={theme === "dark"} onClick={toggle}
                title={theme === "dark" ? "Switch to light edition" : "Switch to dark edition"}>
                <span className="knob" aria-hidden />
                {theme === "dark" ? "Dark" : "Light"}
              </button>
            </div>
          </div>
          <nav aria-label="Contents">
            <ul className="toc">
              {NAV.map((n) => (
                <li key={n.to}>
                  <Link to={n.to} className="toc-link" activeOptions={{ exact: n.to === "/" }} activeProps={{ "aria-current": "page" }}>
                    <span className="num">{n.num}.</span>
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="main" key={pathname}>
        <Outlet />
      </main>
      <footer className="colophon">
        <span>Patterns are self-authored or used with permission · No fabricated citations</span>
        <span>Mock data · OpenAlex disabled</span>
      </footer>
    </>
  );
}

const root = createRootRoute({ component: Shell });

const search = createRoute({ getParentRoute: () => root, path: "/", component: SearchExplorerPage });

const pattern = createRoute({
  getParentRoute: () => root,
  path: "/patterns/$patternId",
  component: () => <PatternDetailPage patternId={getRouteApi("/patterns/$patternId").useParams().patternId} />,
});

const compose = createRoute({
  getParentRoute: () => root,
  path: "/compose",
  validateSearch: (s: Record<string, unknown>): { pattern?: string } => ({ pattern: typeof s.pattern === "string" ? s.pattern : undefined }),
  component: () => <SentenceComposerPage patternId={getRouteApi("/compose").useSearch().pattern} />,
});

const validateRoute = createRoute({
  getParentRoute: () => root,
  path: "/validate",
  validateSearch: (s: Record<string, unknown>): { text?: string } => ({ text: typeof s.text === "string" ? s.text : undefined }),
  component: () => <ValidationConsolePage initialText={getRouteApi("/validate").useSearch().text} />,
});

const journals = createRoute({ getParentRoute: () => root, path: "/journals", component: () => <JournalProfilePage /> });
const journal = createRoute({
  getParentRoute: () => root,
  path: "/journals/$journalId",
  component: () => <JournalProfilePage journalId={getRouteApi("/journals/$journalId").useParams().journalId} />,
});

export const router = createRouter({
  routeTree: root.addChildren([search, pattern, compose, validateRoute, journals, journal]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
