import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { ApiError } from "@/features/slr-import/api/client";
import {
  PHRASEBANK_SOURCES,
  phrasebankSources,
  type ManchesterCategory,
  type ManchesterSearchResult,
  type PatternDetail,
  type SourceId,
  type TaxonomyTree,
} from "./source-registry";

const SOURCE_CREDIT = "Source: University of Manchester Academic Phrasebank.";

function isReferenceDisabled(error: unknown) {
  return (
    error instanceof ApiError && error.status === 404 && error.body?.error?.message === "Reference library is disabled"
  );
}
function groupBy<T, K extends string>(items: T[], key: (item: T) => K): [K, T[]][] {
  const groups = new Map<K, T[]>();
  for (const item of items) groups.set(key(item), [...(groups.get(key(item)) ?? []), item]);
  return [...groups.entries()];
}
function SourceCredit() {
  return <p className="text-sm text-muted-foreground">{SOURCE_CREDIT}</p>;
}
function useDebounced(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function CategoryCards({ categories, kind }: { categories: ManchesterCategory[]; kind: "section" | "function" }) {
  const rows = categories.filter((item) => item.kind === kind);
  if (!rows.length)
    return (
      <DataState
        state="empty"
        emptyTitle={`No ${kind === "section" ? "sections" : "general functions"} available`}
        emptyDescription="No categories match the current filters."
      />
    );
  return (
    <div className="grid grid-cols-3 gap-3">
      {rows.map((item) => (
        <Link
          key={item.slug}
          to="/phrasebank/$slug"
          params={{ slug: item.slug }}
          className={
            "flex items-center justify-between rounded-[var(--radius)] border border-border p-4 " +
            "hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
          }
        >
          <span className="font-medium">{item.title}</span>
          <Badge variant="outline">{item.entry_count}</Badge>
        </Link>
      ))}
    </div>
  );
}

type SearchEntry = NonNullable<Awaited<ReturnType<typeof phrasebankSources.search>>>["results"][number]["entry"];
function HighlightedText({ text, query }: { text: string; query: string }) {
  const terms = [...new Set(query.trim().split(/\s+/).filter(Boolean))];
  if (!terms.length) return text;
  const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const set = new Set(terms.map((term) => term.toLocaleLowerCase()));
  const matcher = new RegExp(`(${terms.map(escape).join("|")})`, "gi");
  return (
    <>
      {text.split(matcher).map((part, index) =>
        set.has(part.toLocaleLowerCase()) ? (
          <mark key={index} className="rounded-sm bg-muted px-0.5">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}
function SearchResultEntry({
  entry,
  query,
  slug,
  headingPosition,
}: {
  entry: SearchEntry;
  query: string;
  slug: string;
  headingPosition: string;
}) {
  const navigate = useNavigate();
  const targetId = `heading-${slug}-${headingPosition}`;
  const openHeading = (
    <Link
      to="/phrasebank/$slug"
      params={{ slug }}
      hash={targetId}
      onClick={(event) => {
        event.preventDefault();
        void navigate({ to: "/phrasebank/$slug", params: { slug }, hash: targetId }).then(() =>
          scrollAfterNavigation(targetId),
        );
      }}
      className="text-sm text-primary hover:underline"
    >
      Open heading
    </Link>
  );
  if (entry.kind !== "phrase" || !entry.cells?.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <Table>
        <TableBody>
          <TableRow>
            {entry.cells.map((alternatives, index) => (
              <TableCell key={index} className="whitespace-normal">
                {alternatives.map((text, textIndex) => (
                  <div key={textIndex}>
                    <HighlightedText text={text} query={query} />
                  </div>
                ))}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
      {openHeading}
    </div>
  );
}

function phraseRow(cells: string[][]) {
  return cells.map((alternatives) => alternatives.join(" / ")).join(" ");
}
function PhraseRow({ cells }: { cells: string[][] }) {
  const copy = async () => {
    await navigator.clipboard?.writeText(phraseRow(cells));
  };
  return (
    <TableRow>
      {cells.map((alternatives, index) => (
        <TableCell key={index} className="whitespace-normal">
          {alternatives.map((text, textIndex) => (
            <div key={textIndex}>{text}</div>
          ))}
        </TableCell>
      ))}
      <TableCell>
        <Button variant="outline" size="sm" onClick={() => void copy()} aria-label="Copy phrase row">
          Copy
        </Button>
      </TableCell>
    </TableRow>
  );
}
function taxonomyIntents(taxonomy?: TaxonomyTree) {
  return (taxonomy?.sections ?? []).flatMap((section) =>
    section.moves.flatMap((move) => move.steps.flatMap((step) => step.intents)),
  );
}
function SourceFilters({
  taxonomy,
  sectionCode,
  intentCode,
  onSectionChange,
  onIntentChange,
}: {
  taxonomy?: TaxonomyTree;
  sectionCode: string;
  intentCode: string;
  onSectionChange: (value: string) => void;
  onIntentChange: (value: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Section</span>
        <Select value={sectionCode || "all"} onValueChange={(value) => onSectionChange(value === "all" ? "" : value)}>
          <SelectTrigger aria-label="Section filter">
            <SelectValue placeholder="All sections" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sections</SelectItem>
            {taxonomy?.sections.map((section) => (
              <SelectItem key={section.code} value={section.code}>
                {section.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Intent</span>
        <Select value={intentCode || "all"} onValueChange={(value) => onIntentChange(value === "all" ? "" : value)}>
          <SelectTrigger aria-label="Intent filter">
            <SelectValue placeholder="All intents" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All intents</SelectItem>
            {taxonomyIntents(taxonomy).map((intent) => (
              <SelectItem key={intent.code} value={intent.code}>
                {intent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
function taxonomyUnmappedCount(
  categories: ManchesterCategory[],
  intentCode: string,
  results?: ManchesterSearchResult[],
) {
  if (results) return results.filter((result) => (intentCode ? !result.intent_code : !result.section_code)).length;
  const field = intentCode ? "unmapped_intent_entry_count" : "unmapped_section_entry_count";
  return categories.reduce((total, category) => total + category[field], 0);
}
function EntryList({
  entries,
}: {
  entries: NonNullable<
    NonNullable<Awaited<ReturnType<typeof phrasebankSources.category>>>["headings"][number]["entries"]
  >;
}) {
  const blocks: { id: string; entries: typeof entries }[] = [];
  for (const entry of entries) {
    if (entry.kind !== "phrase") continue;
    const previous = blocks.at(-1);
    if (previous?.id === String(entry.block_index)) previous.entries.push(entry);
    else blocks.push({ id: String(entry.block_index), entries: [entry] });
  }
  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block) => (
        <Table key={block.id}>
          <TableBody>
            {block.entries.map((entry) => (
              <PhraseRow key={entry.id} cells={entry.cells ?? []} />
            ))}
          </TableBody>
        </Table>
      ))}
    </div>
  );
}
function PatternGroups({ patterns }: { patterns: PatternDetail[] }) {
  if (!patterns.length)
    return (
      <DataState
        state="empty"
        emptyTitle="No approved AP-RKB patterns match"
        emptyDescription="Try a different phrase or taxonomy filter."
      />
    );
  const groups = new Map<string, PatternDetail[]>();
  for (const pattern of patterns)
    for (const section of pattern.allowed_sections) {
      const key = `${section} · ${pattern.intent_code}`;
      groups.set(key, [...(groups.get(key) ?? []), pattern]);
    }
  return (
    <div className="flex flex-col gap-4">
      {[...groups.entries()].map(([group, items]) => (
        <section key={group} className="flex flex-col gap-2">
          <h3 className="font-medium">{group}</h3>
          <ul className="flex flex-col gap-2">
            {items.map((pattern) => (
              <li
                id={`pattern-${pattern.id}`}
                key={pattern.id}
                className="flex items-center justify-between gap-4 rounded-[var(--radius)] border border-border p-3"
              >
                <Link
                  to="/phrasebank/pattern/$id"
                  params={{ id: pattern.id }}
                  className="font-serif text-lg text-primary hover:underline"
                >
                  {pattern.canonical_frame}
                </Link>
                <Button asChild variant="outline" size="sm">
                  <Link to="/writer">Use in writer</Link>
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function PhrasebankHome() {
  const [source, setSource] = useState<"all" | SourceId>("all");
  const [search, setSearch] = useState("");
  const [sectionCode, setSectionCode] = useState("");
  const [intentCode, setIntentCode] = useState("");
  const query = useDebounced(search.trim());
  const taxonomy = useQuery({ queryKey: ["phrasebank-taxonomy"], queryFn: phrasebankSources.taxonomy, retry: false });
  const manchester = useQuery({
    queryKey: ["phrasebank-categories"],
    queryFn: PHRASEBANK_SOURCES["manchester-reference"].listGroups,
    retry: false,
  });
  const disabled = isReferenceDisabled(manchester.error);
  const filters = { sectionCode: sectionCode || undefined, intentCode: intentCode || undefined };
  const results = useQuery({
    queryKey: ["phrasebank-search", query, sectionCode, intentCode],
    queryFn: () => PHRASEBANK_SOURCES["manchester-reference"].search(query, filters),
    enabled: Boolean(query) && source !== "aprkb-patterns",
    retry: false,
  });
  const patternSearch = useQuery({
    queryKey: ["phrasebank-pattern-search", query, sectionCode, intentCode],
    queryFn: () => PHRASEBANK_SOURCES["aprkb-patterns"].search(query, filters),
    enabled: source !== "manchester-reference",
    retry: false,
  });
  const patternMatches = patternSearch.data ?? [];
  const referenceSource = PHRASEBANK_SOURCES["manchester-reference"];
  const visibleCategories = (manchester.data ?? []).filter(
    (category) =>
      (!sectionCode ||
        Boolean(taxonomy.data && referenceSource.filterBySection(category, sectionCode, taxonomy.data))) &&
      (!intentCode || referenceSource.filterByIntent(category, intentCode)),
  );
  const visibleResults = results.data ?? [];
  const hasFilters = Boolean(sectionCode || intentCode);
  const unmapped = taxonomyUnmappedCount(manchester.data ?? [], intentCode);
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Phrasebank"
        description="Browse reference categories and approved AP-RKB patterns by section, intent, and phrase."
      />
      <Card>
        <CardHeader>
          <CardTitle>Search the phrasebank</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end gap-3">
          <Input
            className="max-w-xl"
            type="search"
            aria-label="Search phrasebanks"
            placeholder="Search phrases and categories"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Select value={source} onValueChange={(value) => setSource(value as "all" | SourceId)}>
            <SelectTrigger aria-label="Source filter" className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sources</SelectItem>
              <SelectItem value="manchester-reference">Manchester reference</SelectItem>
              <SelectItem value="aprkb-patterns">AP-RKB patterns</SelectItem>
            </SelectContent>
          </Select>
          <SourceFilters
            taxonomy={taxonomy.data}
            sectionCode={sectionCode}
            intentCode={intentCode}
            onSectionChange={setSectionCode}
            onIntentChange={setIntentCode}
          />
          <Button onClick={() => setSearch((value) => value)}>Search</Button>
        </CardContent>
      </Card>
      {hasFilters && !query && source !== "aprkb-patterns" && manchester.data ? (
        <p role="status" className="text-sm text-muted-foreground">
          {unmapped} items have no mapping for this filter and are hidden.
        </p>
      ) : null}
      {query ? (
        <Card>
          <CardHeader>
            <CardTitle>Search results</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <p className="text-sm text-muted-foreground">
              Showing up to{" "}
              {source === "aprkb-patterns"
                ? "200 AP-RKB"
                : source === "manchester-reference"
                  ? "50 Manchester"
                  : "50 Manchester and 200 AP-RKB"}{" "}
              matching results.
            </p>
            {source !== "aprkb-patterns" ? (
              results.isPending ? (
                <DataState state="loading" loadingLabel="Loading reference results" />
              ) : disabled ? (
                <p role="status">Manchester reference is disabled. Enable the reference library to browse it.</p>
              ) : visibleResults.length === 0 ? (
                <DataState
                  state="empty"
                  emptyTitle="No Manchester reference results"
                  emptyDescription="Try another phrase or filter."
                />
              ) : (
                <section className="flex flex-col gap-3">
                  <h3 className="font-medium">Manchester reference</h3>
                  {groupBy(visibleResults, (item) => item.category_slug).map(([slug, items]) => (
                    <section key={slug} className="flex flex-col gap-2">
                      <h4 className="font-medium">{items[0]?.category_title}</h4>
                      {groupBy(items, (item) => String(item.entry.heading_position)).map(([position, group]) => (
                        <div key={position} className="flex flex-col gap-2">
                          <h5 className="text-sm text-muted-foreground">{group[0]?.heading}</h5>
                          {group.map((item) => (
                            <SearchResultEntry
                              key={item.entry.id}
                              entry={item.entry}
                              query={query}
                              slug={slug}
                              headingPosition={position}
                            />
                          ))}
                        </div>
                      ))}
                    </section>
                  ))}
                </section>
              )
            ) : null}
            {source !== "manchester-reference" ? (
              <section className="flex flex-col gap-3">
                <h3 className="font-medium">AP-RKB patterns</h3>
                {patternSearch.isPending ? (
                  <DataState state="loading" loadingLabel="Loading approved patterns" />
                ) : patternSearch.isError ? (
                  <DataState
                    state="error"
                    errorTitle="Could not load approved patterns"
                    errorDescription={patternSearch.error.message}
                    onRetry={() => void patternSearch.refetch()}
                  />
                ) : (
                  <PatternGroups patterns={patternMatches} />
                )}
              </section>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <>
          {source !== "aprkb-patterns" && disabled ? (
            <Alert role="status">
              <AlertDescription>
                The Manchester reference collection is switched off here, so only the bank&apos;s own patterns are
                listed below.
              </AlertDescription>
            </Alert>
          ) : null}
          {source !== "aprkb-patterns" && !disabled ? (
            <Card>
              <CardHeader>
                <CardTitle>Sections</CardTitle>
              </CardHeader>
              <CardContent>
                {disabled ? (
                  <p role="status">
                    Manchester reference is disabled. Enable the reference library to browse these categories.
                  </p>
                ) : manchester.isPending ? (
                  <DataState state="loading" loadingLabel="Loading sections" />
                ) : manchester.isError ? (
                  <DataState
                    state="error"
                    errorTitle="Could not load sections"
                    errorDescription={manchester.error.message}
                    onRetry={() => void manchester.refetch()}
                  />
                ) : (
                  <CategoryCards categories={visibleCategories} kind="section" />
                )}
              </CardContent>
            </Card>
          ) : null}
          {source !== "aprkb-patterns" && !disabled ? (
            <Card>
              <CardHeader>
                <CardTitle>General functions</CardTitle>
              </CardHeader>
              <CardContent>
                {disabled ? (
                  <DataState
                    state="empty"
                    emptyTitle="General functions unavailable"
                    emptyDescription="The reference library is disabled."
                  />
                ) : manchester.isPending ? (
                  <DataState state="loading" loadingLabel="Loading general functions" />
                ) : (
                  <CategoryCards categories={visibleCategories} kind="function" />
                )}
              </CardContent>
            </Card>
          ) : null}
          {source !== "manchester-reference" ? (
            <Card>
              <CardHeader>
                <CardTitle>
                  <Link
                    to="/phrasebank/$slug"
                    params={{ slug: "aprkb-patterns" }}
                    className="text-primary hover:underline"
                  >
                    AP-RKB patterns
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">Showing up to 200 matching patterns.</p>
                {patternSearch.isPending ? (
                  <DataState state="loading" loadingLabel="Loading approved patterns" />
                ) : patternSearch.isError ? (
                  <DataState
                    state="error"
                    errorTitle="Could not load approved patterns"
                    errorDescription={patternSearch.error.message}
                    onRetry={() => void patternSearch.refetch()}
                  />
                ) : (
                  <PatternGroups patterns={patternMatches} />
                )}
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
      <SourceCredit />
    </div>
  );
}

export function PhrasebankCategory({ slug }: { slug: string }) {
  const navigate = useNavigate();
  const locationHref = useRouterState({ select: (state) => state.location.href });
  const manchester = useQuery({
    queryKey: ["phrasebank-category", slug],
    queryFn: () => PHRASEBANK_SOURCES["manchester-reference"].getGroup(slug),
    enabled: slug !== "aprkb-patterns",
    retry: false,
  });
  const patterns = useQuery({
    queryKey: ["phrasebank-patterns"],
    queryFn: () => PHRASEBANK_SOURCES["aprkb-patterns"].getGroup("aprkb-patterns"),
    enabled: slug === "aprkb-patterns",
    retry: false,
  });
  const disabled = isReferenceDisabled(manchester.error);
  useEffect(() => {
    const hash = new URL(locationHref, window.location.origin).hash;
    if (!hash || (slug === "aprkb-patterns" && patterns.isPending)) return;
    const targetId = decodeURIComponent(hash.slice(1));
    window.setTimeout(() => scrollToHeading(targetId), 250);
  }, [locationHref, slug, manchester.data, patterns.data, patterns.isPending]);
  if (slug === "aprkb-patterns")
    return (
      <div className="flex flex-col gap-6">
        <Link to="/phrasebank" className="text-sm text-primary hover:underline">
          ← Phrasebank home
        </Link>
        <PageHeader
          title="Approved AP-RKB patterns"
          description="Patterns authored for this knowledge base, grouped by permitted section and intent."
        />
        {patterns.isPending ? (
          <DataState state="loading" loadingLabel="Loading approved patterns" />
        ) : patterns.isError ? (
          <DataState
            state="error"
            errorTitle="Could not load approved patterns"
            errorDescription={patterns.error.message}
            onRetry={() => void patterns.refetch()}
          />
        ) : (
          <PatternGroups patterns={patterns.data ?? []} />
        )}
        <SourceCredit />
      </div>
    );
  if (disabled)
    return (
      <div className="flex flex-col gap-6">
        <Link to="/phrasebank" className="text-sm text-primary hover:underline">
          ← Phrasebank home
        </Link>
        <PageHeader title="Phrasebank category" description="The reference library is currently unavailable." />
        <DataState
          state="empty"
          emptyTitle="Reference library is disabled"
          emptyDescription="Enable the reference library to browse this category."
        />
        <SourceCredit />
      </div>
    );
  if (manchester.isPending)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Phrasebank category" description="Loading the selected category." />
        <DataState state="loading" loadingLabel="Loading phrasebank category" />
        <SourceCredit />
      </div>
    );
  if (manchester.isError)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Phrasebank category" description="The selected category could not be loaded." />
        <DataState
          state="error"
          errorTitle="Could not load category"
          errorDescription={
            manchester.error instanceof ApiError && manchester.error.status === 404
              ? "Category not found or reference data has not been imported."
              : manchester.error.message
          }
          onRetry={() => void manchester.refetch()}
        />
        <SourceCredit />
      </div>
    );
  const category = manchester.data;
  if (!category)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Phrasebank category" description="The selected category is unavailable." />
        <DataState
          state="empty"
          emptyTitle="Category not found"
          emptyDescription="The requested phrasebank category is unavailable."
        />
      </div>
    );
  const intro = category.headings[0];
  const sections = category.headings.slice(1);
  return (
    <div className="flex flex-col gap-6">
      <Link to="/phrasebank" className="text-sm text-primary hover:underline">
        ← Phrasebank home
      </Link>
      <PageHeader
        title={category.category.title}
        description={
          "Reference phrases are shown in their original table order. Use the heading index to move through the " +
          "category."
        }
      />
      {intro?.entries.some((entry) => entry.kind === "phrase") ? (
        <section id={`heading-${category.category.slug}-${intro.heading_position}`}>
          <EntryList entries={intro.entries} />
        </section>
      ) : null}
      <nav aria-label="In-page headings" className="flex flex-col gap-2 border-y border-border py-4">
        <strong>On this page</strong>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {sections.map((item) => {
            const targetId = `heading-${category.category.slug}-${item.heading_position}`;
            return (
              <Link
                key={item.heading_position}
                to="/phrasebank/$slug"
                params={{ slug: category.category.slug }}
                hash={targetId}
                onClick={(event) => {
                  event.preventDefault();
                  void navigate({
                    to: "/phrasebank/$slug",
                    params: { slug: category.category.slug },
                    hash: targetId,
                  }).then(() => scrollAfterNavigation(targetId));
                }}
                className="text-sm text-primary hover:underline"
              >
                {item.heading}
              </Link>
            );
          })}
        </div>
      </nav>
      {sections.map((item) => (
        <section
          className="flex flex-col gap-3"
          id={`heading-${category.category.slug}-${item.heading_position}`}
          key={item.heading_position}
        >
          <h2 className="font-serif text-2xl">{item.heading}</h2>
          <EntryList entries={item.entries} />
        </section>
      ))}
      <SourceCredit />
    </div>
  );
}

function scrollToHeading(id: string) {
  document.getElementById(id)?.scrollIntoView({ block: "start", behavior: "instant" });
}
function scrollAfterNavigation(id: string) {
  let attempts = 0;
  const tryScroll = () => {
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start", behavior: "instant" });
    else if (attempts++ < 40) window.setTimeout(tryScroll, 50);
  };
  window.setTimeout(tryScroll, 0);
}

function DetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[12rem_1fr] gap-3 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function PhrasebankPatternDetail({ id }: { id: string }) {
  const pattern = useQuery({
    queryKey: ["phrasebank-pattern", id],
    queryFn: () => phrasebankSources.pattern(id),
    retry: false,
  });
  if (pattern.isPending) return <DataState state="loading" loadingLabel="Loading pattern" />;
  if (pattern.isError || !pattern.data)
    return (
      <DataState
        state="error"
        errorTitle="Pattern detail is unavailable"
        errorDescription={pattern.error?.message ?? "The pattern could not be found."}
        onRetry={() => void pattern.refetch()}
      />
    );
  const item = pattern.data;
  const list = (values: string[]) => (values.length ? values.join(", ") : "—");
  const slots = Object.entries(item.slots ?? {});
  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/phrasebank/$slug"
        params={{ slug: "aprkb-patterns" }}
        className="text-sm text-primary hover:underline"
      >
        ← AP-RKB patterns
      </Link>
      <PageHeader title={item.intent_name || item.intent_code} description={`Version ${item.version_no}`} />
      <Card>
        <CardHeader>
          <CardTitle>Frame</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-4">
          <p className="font-serif text-lg">{item.canonical_frame}</p>
          <Button asChild variant="outline" size="sm">
            <Link to="/writer">Use in writer</Link>
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Slots</CardTitle>
        </CardHeader>
        <CardContent>
          {slots.length ? (
            <dl className="flex flex-col gap-2">
              {slots.map(([name, slot]) => {
                const metadata =
                  typeof slot === "string"
                    ? { type: slot, label: null, instruction: null, example: null, required: true }
                    : slot;
                return (
                  <DetailField key={name} label={name}>
                    Type: {metadata.type}; Label: {metadata.label ?? "—"}; Instruction: {metadata.instruction ?? "—"};
                    Example: {metadata.example ?? "—"}; Required: {metadata.required ? "Yes" : "No"}
                  </DetailField>
                );
              })}
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">—</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Variants</CardTitle>
        </CardHeader>
        <CardContent>
          {item.variants.length ? (
            <ul className="flex flex-col gap-1">
              {item.variants.map((variant, index) => (
                <li key={`${index}-${variant.text}`}>
                  {variant.text}{" "}
                  {variant.register ? (
                    <span className="text-sm text-muted-foreground">({variant.register})</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">—</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col gap-2">
            <DetailField label="Minimum evidence">{item.evidence_min ?? "—"}</DetailField>
            <DetailField label="Forbidden contexts">{list(item.forbidden_contexts)}</DetailField>
            <DetailField label="Allowed sections">{list(item.allowed_sections)}</DetailField>
            <DetailField label="Allowed genres">{list(item.allowed_genres)}</DetailField>
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col gap-2">
            <DetailField label="Strength">{item.epistemic_strength ?? "Not labelled"}</DetailField>
            <DetailField label="Claim type">{item.claim_type ?? "Not labelled"}</DetailField>
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Provenance</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col gap-2">
            <DetailField label="Source type">{item.source_type}</DetailField>
            <DetailField label="License">
              {item.license_name ?? "—"}
              {item.license_code ? ` (${item.license_code})` : ""}
            </DetailField>
            <DetailField label="Allows display">{item.license_allows_display ? "Yes" : "No"}</DetailField>
            <DetailField label="Internal use">{item.license_flag ? "Yes" : "No"}</DetailField>
            <DetailField label="Article reference">{item.source_reference ?? "—"}</DetailField>
            <DetailField label="Article ID">{item.article_id ?? "—"}</DetailField>
            <DetailField label="Source sentences">{item.source_sentence_count}</DetailField>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
