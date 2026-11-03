import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  getRouteApi,
  lazyRouteComponent,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router";

import { AdminPage } from "@/features/admin";
import { useAuth, type AuthContextValue } from "@/features/auth/AuthProvider";
import { SigninPage } from "@/features/auth/SigninPage";
import { InboxPage } from "@/features/inbox";
import { GoldPage } from "@/features/gold";
import { JournalProfilePage } from "@/features/journal-profile";
import { LibraryPage } from "@/features/library";
import { OverviewPage } from "@/features/overview";
import { ExtractPage } from "@/features/phrase-extraction";
import { PlaygroundPage } from "@/features/playground";
import { PhrasebankCategory, PhrasebankHome } from "@/features/phrasebank/PhrasebankPage";
import { OnlineWriterPage } from "@/features/playground/components/OnlineWriterPage";
import { SlrImportPage } from "@/features/slr-import";
import { VocabularyLemmaPage, VocabularyPage } from "@/features/vocabulary";
import { safeNext } from "@/shared/lib/safe-next";
import { DataState } from "@/components/domain";

import { AppShell } from "./AppShell";

export interface RouterContext {
  auth: AuthContextValue;
}

// The auth guard lives in `guarded.beforeLoad`; App re-runs it (router.invalidate) whenever the session changes.
function Guarded() {
  const auth = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  if (auth.loading) return <DataState state="loading" loadingLabel="Loading" />;
  if (!auth.client) return null;
  if (pathname === "/admin" && auth.client.role !== "admin") {
    return <AdminPage />;
  }
  return <Outlet />;
}

const root = createRootRouteWithContext<RouterContext>()({ component: Outlet });

const str = (v: unknown) => (typeof v === "string" ? v : undefined);

// Public pages, no sidebar.
const publicLayout = createRoute({ getParentRoute: () => root, id: "public", component: Outlet });
const home = createRoute({
  getParentRoute: () => publicLayout,
  path: "/",
  component: lazyRouteComponent(() =>
    import("@/features/landing/LandingPage").then((m) => ({ default: m.LandingPage })),
  ),
});
const signin = createRoute({
  getParentRoute: () => publicLayout,
  path: "/signin",
  validateSearch: (s: Record<string, unknown>): { next?: string } => ({ next: safeNext(s.next) }),
  beforeLoad: ({ context, search }) => {
    if (context.auth.client) throw redirect({ href: search.next ?? "/app", replace: true });
  },
  component: SigninPage,
});

// App shell. /writer is open to guests; every other route sits under `guarded`.
const appLayout = createRoute({ getParentRoute: () => root, id: "shell", component: AppShell });
const guarded = createRoute({
  getParentRoute: () => appLayout,
  id: "guarded",
  beforeLoad: ({ context, location }) => {
    if (context.auth.loading || context.auth.client) return;
    throw redirect({
      to: "/signin",
      search: { next: safeNext(`${location.pathname}${location.searchStr}`) },
      replace: true,
    });
  },
  component: Guarded,
});

const overview = createRoute({ getParentRoute: () => guarded, path: "/app", component: OverviewPage });

const library = createRoute({
  getParentRoute: () => guarded,
  path: "/library",
  validateSearch: (s: Record<string, unknown>): { p?: string } => ({ p: str(s.p) }),
  component: () => <LibraryPage selectedId={getRouteApi("/shell/guarded/library").useSearch().p} />,
});

const phrasebank = createRoute({ getParentRoute: () => guarded, path: "/phrasebank", component: PhrasebankHome });
const phrasebankCategory = createRoute({
  getParentRoute: () => guarded,
  path: "/phrasebank/$slug",
  component: () => <PhrasebankCategory slug={getRouteApi("/shell/guarded/phrasebank/$slug").useParams().slug} />,
});

const playground = createRoute({
  getParentRoute: () => guarded,
  path: "/playground",
  validateSearch: (s: Record<string, unknown>): { pattern?: string } => ({ pattern: str(s.pattern) }),
  component: () => <PlaygroundPage patternId={getRouteApi("/shell/guarded/playground").useSearch().pattern} />,
});

const writer = createRoute({ getParentRoute: () => appLayout, path: "/writer", component: OnlineWriterPage });

const inbox = createRoute({ getParentRoute: () => guarded, path: "/inbox", component: InboxPage });
const admin = createRoute({ getParentRoute: () => guarded, path: "/admin", component: AdminPage });
const slrImport = createRoute({ getParentRoute: () => guarded, path: "/import", component: SlrImportPage });
const gold = createRoute({ getParentRoute: () => guarded, path: "/gold", component: GoldPage });
const vocabularySearch = (s: Record<string, unknown>) => ({
  view: s.view === "families" ? ("families" as const) : s.view === "lemmas" ? ("lemmas" as const) : undefined,
  letter: str(s.letter),
  q: str(s.q),
  coreOnly: typeof s.coreOnly === "boolean" ? s.coreOnly : s.coreOnly === "true" ? true : undefined,
  sort: s.sort === "rank" ? ("rank" as const) : s.sort === "alpha" ? ("alpha" as const) : undefined,
  offset: typeof s.offset === "number" ? s.offset : Number.isFinite(Number(s.offset)) ? Number(s.offset) : undefined,
});
const vocabulary = createRoute({
  getParentRoute: () => guarded,
  path: "/vocabulary",
  validateSearch: vocabularySearch,
  component: VocabularyPage,
});
const vocabularyLemma = createRoute({
  getParentRoute: () => guarded,
  path: "/vocabulary/$lemmaId",
  validateSearch: vocabularySearch,
  component: VocabularyLemmaPage,
});
// ?batch=<id>[,<id>] preselects batches; the Import page links here when a run finishes.
const extract = createRoute({
  getParentRoute: () => guarded,
  path: "/extract",
  validateSearch: (s: Record<string, unknown>): { batch?: string } => ({ batch: str(s.batch) }),
  component: () => <ExtractPage initialBatch={getRouteApi("/shell/guarded/extract").useSearch().batch} />,
});

const journals = createRoute({
  getParentRoute: () => guarded,
  path: "/journals",
  component: () => <JournalProfilePage />,
});
const journal = createRoute({
  getParentRoute: () => guarded,
  path: "/journals/$journalId",
  component: () => (
    <JournalProfilePage journalId={getRouteApi("/shell/guarded/journals/$journalId").useParams().journalId} />
  ),
});

const devUiRoute =
  import.meta.env.DEV || import.meta.env.MODE === "inspect"
    ? createRoute({
        getParentRoute: () => root,
        path: "/dev/ui",
        component: lazyRouteComponent(() =>
          import("@/features/dev-ui/DevUIPage").then((module) => ({ default: module.DevUIPage })),
        ),
      })
    : undefined;

export const router = createRouter({
  routeTree: root.addChildren([
    publicLayout.addChildren([home, signin]),
    appLayout.addChildren([
      writer,
      guarded.addChildren([
        overview,
        library,
        phrasebank,
        phrasebankCategory,
        playground,
        inbox,
        journals,
        journal,
        admin,
        slrImport,
        extract,
        gold,
        vocabulary,
        vocabularyLemma,
      ]),
    ]),
    ...(devUiRoute ? [devUiRoute] : []),
  ]),
  context: { auth: undefined! },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
