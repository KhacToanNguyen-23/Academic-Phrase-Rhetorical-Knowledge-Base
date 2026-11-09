import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { MeasurementSlotSuggestions } from "@/features/measurement";
import { ApiError } from "@/features/slr-import/api/client";
import {
  PHRASEBANK_SOURCES,
  phrasebankSources,
  type ManchesterCategory,
  type PatternDetail,
  type PatternFilter,
  type SourceId,
  type TaxonomyTree,
} from "./source-registry";

const SOURCE_CREDIT = "Source: University of Manchester Academic Phrasebank.";
const PATTERN_PAGE_SIZE = 50;

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
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
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
      <Table aria-label={`Phrases under ${entry.heading}`}>
        <TableBody>
          <TableRow>
            {entry.cells.map((alternatives, index) => (
              <TableCell key={index} className="whitespace-normal px-4 py-3 align-top leading-7">
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
        <TableCell key={index} className="whitespace-normal px-4 py-3 align-top leading-7">
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
  const intents = taxonomyIntents(taxonomy);
  const selectedIntent = intents.find((intent) => intent.code === intentCode);

  return (
    <>
      <div className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted-foreground">
        <span>Section</span>
        <Select value={sectionCode || "all"} onValueChange={(value) => onSectionChange(value === "all" ? "" : value)}>
          <SelectTrigger aria-label="Section filter" className="w-full text-foreground">
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
      <div className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted-foreground">
        <span>Intent</span>
        <Select value={intentCode || "all"} onValueChange={(value) => onIntentChange(value === "all" ? "" : value)}>
          <SelectTrigger
            aria-label="Intent filter"
            className="w-full text-foreground *:data-[slot=select-value]:min-w-0"
            title={selectedIntent?.name}
          >
            <SelectValue placeholder="All intents">
              <span className="truncate">{selectedIntent?.name ?? "All intents"}</span>
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="max-w-(--radix-select-content-available-width)">
            <SelectItem value="all">All intents</SelectItem>
            {intents.map((intent) => (
              <SelectItem key={intent.code} value={intent.code}>
                {intent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
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
        <Table key={block.id} aria-label={`Phrases under ${block.entries[0]?.heading ?? "this heading"}`}>
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
  const groups = new Map<string, { section: string; items: PatternDetail[] }>();
  for (const pattern of patterns)
    for (const section of pattern.allowed_sections) {
      const key = `${section} · ${pattern.intent_code}`;
      const group = groups.get(key) ?? { section, items: [] };
      group.items.push(pattern);
      groups.set(key, group);
    }
  return (
    <div className="flex flex-col gap-4">
      {[...groups.entries()].map(([key, { section, items }]) => (
        <details key={key} className="group border-b border-border py-2 last:border-0">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-2 [&::-webkit-details-marker]:hidden">
            <h3 className="text-lg font-semibold">
              {section} <span aria-hidden="true">·</span> {items[0]?.intent_name || items[0]?.intent_code}
            </h3>
            <ChevronDown aria-hidden="true" className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
          </summary>
          <ul className="flex flex-col gap-2 pt-2">
            {items.map((pattern) => (
              <li
                id={`pattern-${pattern.id}`}
                key={pattern.id}
                className="flex items-start justify-between gap-4 border-b border-border py-3 last:border-0"
              >
                <Link
                  to="/phrasebank/pattern/$id"
                  params={{ id: pattern.id }}
                  className="font-serif text-lg text-primary hover:underline"
                >
                  {pattern.canonical_frame}
                </Link>
                <Button asChild variant="outline" size="sm">
                  <Link to="/writer" search={{
                    intent: pattern.intent_code,
                    move: pattern.move_code ?? undefined,
                    section: pattern.allowed_sections.length === 1 ? pattern.allowed_sections[0] : undefined,
                    genre: pattern.allowed_genres.length === 1 ? pattern.allowed_genres[0] : undefined,
                  }}>Use in writer</Link>
                </Button>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}

function PaginatedPatterns({ query, filters }: { query: string; filters: PatternFilter }) {
  const [offset, setOffset] = useState(0);
  const patternSearch = useQuery({
    queryKey: ["phrasebank-pattern-search", query, filters, offset],
    queryFn: () =>
      phrasebankSources.patterns(query, filters, { offset, limit: PATTERN_PAGE_SIZE + 1 }),
    retry: false,
  });
  const patterns = patternSearch.data?.slice(0, PATTERN_PAGE_SIZE) ?? [];
  const hasPrevious = offset > 0;
  const hasNext = (patternSearch.data?.length ?? 0) > PATTERN_PAGE_SIZE;

  return (
    <>
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
        <PatternGroups patterns={patterns} />
      )}
      {hasPrevious || hasNext ? (
        <Pagination aria-label="AP-RKB pattern pages">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                href="#"
                aria-disabled={!hasPrevious}
                className={!hasPrevious ? "pointer-events-none opacity-50" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  if (hasPrevious) setOffset(offset - PATTERN_PAGE_SIZE);
                }}
              />
            </PaginationItem>
            <PaginationItem>
              <span className="px-3 text-sm text-muted-foreground">
                Page {offset / PATTERN_PAGE_SIZE + 1}
              </span>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                href="#"
                aria-disabled={!hasNext}
                className={!hasNext ? "pointer-events-none opacity-50" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  if (hasNext) setOffset(offset + PATTERN_PAGE_SIZE);
                }}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      ) : null}
    </>
  );
}

export function PhrasebankHome() {
  const [source, setSource] = useState<"all" | SourceId>("all");
  const [search, setSearch] = useState("");
  const [sectionCode, setSectionCode] = useState("");
  const [intentCode, setIntentCode] = useState("");
  const [slotFilter, setSlotFilter] = useState("all");
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
  const patternFilters = { ...filters, hasSlots: slotFilter === "all" ? undefined : slotFilter === "with" };
  const patternPageKey = JSON.stringify([source, query, sectionCode, intentCode, slotFilter]);
  const referenceSource = PHRASEBANK_SOURCES["manchester-reference"];
  const visibleCategories = (manchester.data ?? []).filter(
    (category) =>
      (!sectionCode ||
        Boolean(taxonomy.data && referenceSource.filterBySection(category, sectionCode, taxonomy.data))) &&
      (!intentCode || referenceSource.filterByIntent(category, intentCode)),
  );
  const visibleResults = results.data ?? [];
  const hasSlotFilter = source !== "manchester-reference" && slotFilter !== "all";
  const hasFilters = Boolean(sectionCode || intentCode || hasSlotFilter);
  const selectedSection = taxonomy.data?.sections.find((section) => section.code === sectionCode);
  const selectedIntent = taxonomyIntents(taxonomy.data).find((intent) => intent.code === intentCode);
  const hasManchesterContent = query ? visibleResults.length > 0 : visibleCategories.length > 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={<span className="text-3xl">Phrasebank</span>}
        description="Browse reference categories and approved AP-RKB patterns by section, intent, and phrase."
      />
      <Card>
        <CardHeader>
          <CardTitle>Find a phrase</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <label className="flex min-w-0 max-w-xl flex-col gap-1 text-xs font-medium text-muted-foreground">
            Search phrases and categories
            <Input
              className="w-full"
              type="search"
              aria-label="Search phrasebanks"
              placeholder="Type a phrase or category"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_2fr_1fr]">
            <label className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted-foreground">
              Source
              <Select value={source} onValueChange={(value) => setSource(value as "all" | SourceId)}>
                <SelectTrigger aria-label="Source filter" className="w-full text-foreground">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  <SelectItem value="manchester-reference">Manchester reference</SelectItem>
                  <SelectItem value="aprkb-patterns">AP-RKB patterns</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <SourceFilters
              taxonomy={taxonomy.data}
              sectionCode={sectionCode}
              intentCode={intentCode}
              onSectionChange={setSectionCode}
              onIntentChange={setIntentCode}
            />
            {source !== "manchester-reference" ? (
              <div className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted-foreground">
                <span>Fill-in fields</span>
                <Select value={slotFilter} onValueChange={setSlotFilter}>
                  <SelectTrigger
                    aria-label="Fill-in fields"
                    aria-describedby={source === "all" ? "phrasebank-slot-filter-scope" : undefined}
                    className="w-full text-foreground"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All phrases</SelectItem>
                    <SelectItem value="with">Has fill-in fields</SelectItem>
                    <SelectItem value="without">No fill-in fields</SelectItem>
                  </SelectContent>
                </Select>
                {source === "all" ? (
                  <span id="phrasebank-slot-filter-scope" className="text-xs text-muted-foreground">
                    AP-RKB patterns only
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
          {hasFilters ? (
            <div className="flex flex-wrap items-center gap-2" role="status" aria-label="Active filters">
              <span className="text-sm font-medium">Active filters</span>
              {sectionCode ? <Badge variant="secondary">Section: {selectedSection?.name ?? sectionCode}</Badge> : null}
              {intentCode ? <Badge variant="secondary">Intent: {selectedIntent?.name ?? intentCode}</Badge> : null}
              {hasSlotFilter ? (
                <Badge variant="secondary">{slotFilter === "with" ? "Has fill-in fields" : "No fill-in fields"}</Badge>
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto"
                onClick={() => {
                  setSectionCode("");
                  setIntentCode("");
                  setSlotFilter("all");
                }}
              >
                Clear filters
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
      {query ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-xl font-semibold">Search results</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {source !== "aprkb-patterns" ? (
              results.isPending ? (
                <DataState state="loading" loadingLabel="Loading reference results" />
              ) : disabled ? (
                <p role="status" className="text-sm text-muted-foreground">Manchester phrases are unavailable.</p>
              ) : visibleResults.length === 0 ? (
                <DataState
                  state="empty"
                  emptyTitle="No Manchester reference results"
                  emptyDescription="Try another phrase or filter."
                />
              ) : (
                <section className="flex flex-col gap-3">
                  <h3 className="text-lg font-semibold">Manchester reference</h3>
                  {groupBy(visibleResults, (item) => item.category_slug).map(([slug, items]) => (
                    <section key={slug} className="flex flex-col gap-3 border-t border-border pt-3 first:border-0 first:pt-0">
                      <h4 className="text-base font-semibold">{items[0]?.category_title}</h4>
                      {groupBy(items, (item) => String(item.entry.heading_position)).map(([position, group]) => (
                        <div key={position} className="flex flex-col gap-3 border-l-2 border-border pl-4">
                          <h5 className="text-sm font-semibold">{group[0]?.heading}</h5>
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
              <section className="flex flex-col gap-3 border-t border-border pt-5">
                <h3 className="text-lg font-semibold">AP-RKB patterns</h3>
                <PaginatedPatterns key={patternPageKey} query={query} filters={patternFilters} />
              </section>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <>
          {source !== "aprkb-patterns" && disabled ? (
            <Alert role="status">
              <AlertDescription>
                Manchester reference phrases are unavailable. AP-RKB patterns are still available below.
              </AlertDescription>
            </Alert>
          ) : null}
          {source !== "aprkb-patterns" && !disabled ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-xl font-semibold">Sections</CardTitle>
              </CardHeader>
              <CardContent>
                {manchester.isPending ? (
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
                <CardTitle className="text-xl font-semibold">General functions</CardTitle>
              </CardHeader>
              <CardContent>
                {manchester.isPending ? (
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
                <CardTitle className="text-xl font-semibold">
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
                <PaginatedPatterns key={patternPageKey} query={query} filters={patternFilters} />
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
      {source !== "aprkb-patterns" && !disabled && hasManchesterContent ? <SourceCredit /> : null}
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
          title={<span className="text-3xl">Approved AP-RKB patterns</span>}
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
      </div>
    );
  if (disabled)
    return (
      <div className="flex flex-col gap-6">
        <Link to="/phrasebank" className="text-sm text-primary hover:underline">
          ← Phrasebank home
        </Link>
        <PageHeader title="Phrasebank category" description="Manchester phrases are currently unavailable." />
        <DataState state="empty" emptyTitle="Manchester phrases are unavailable." />
      </div>
    );
  if (manchester.isPending)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Phrasebank category" description="Loading the selected category." />
        <DataState state="loading" loadingLabel="Loading phrasebank category" />
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
        title={<span className="text-3xl">{category.category.title}</span>}
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
          <h2 className="font-serif text-3xl">{item.heading}</h2>
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
    <div className="grid grid-cols-[minmax(8rem,12rem)_minmax(0,1fr)] gap-x-5 gap-y-1 border-b border-border py-3 text-sm last:border-0">
      <dt className="font-medium text-foreground">{label}</dt>
      <dd className="flex min-w-0 flex-col gap-1">{children}</dd>
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
  const list = (values: string[]) => (values.length ? values.join(", ") : null);
  const slots = Object.entries(item.slots ?? {});
  const usage = [
    item.evidence_min ? { label: "Minimum evidence", value: item.evidence_min } : null,
    list(item.forbidden_contexts) ? { label: "Forbidden contexts", value: list(item.forbidden_contexts) } : null,
    list(item.allowed_sections) ? { label: "Allowed sections", value: list(item.allowed_sections) } : null,
    list(item.allowed_genres) ? { label: "Allowed genres", value: list(item.allowed_genres) } : null,
  ].filter((field): field is { label: string; value: string } => field !== null);
  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/phrasebank/$slug"
        params={{ slug: "aprkb-patterns" }}
        className="text-sm text-primary hover:underline"
      >
        ← AP-RKB patterns
      </Link>
      <PageHeader title={<span className="text-3xl">{item.intent_name || item.intent_code}</span>} description={`Version ${item.version_no}`} />
      <Card>
        <CardHeader>
          <CardTitle>Frame</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between gap-4">
          <p className="font-serif text-lg">{item.canonical_frame}</p>
          <Button asChild variant="outline" size="sm">
            <Link to="/writer" search={{
              intent: item.intent_code,
              move: item.move_code ?? undefined,
              section: item.allowed_sections.length === 1 ? item.allowed_sections[0] : undefined,
              genre: item.allowed_genres.length === 1 ? item.allowed_genres[0] : undefined,
            }}>Use in writer</Link>
          </Button>
        </CardContent>
      </Card>
      {slots.length ? <Card>
        <CardHeader>
          <CardTitle>Slots</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            {slots.map(([name, slot]) => {
              const metadata =
                typeof slot === "string"
                  ? { type: slot, label: null, instruction: null, example: null, required: true }
                  : slot;
              return (
                <DetailField key={name} label={name}>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                    <span><span className="text-muted-foreground">Type:</span> {metadata.type}</span>
                    <Badge variant="outline">{metadata.required ? "Required" : "Optional"}</Badge>
                  </div>
                  {metadata.label ? <p><span className="text-muted-foreground">Label:</span> {metadata.label}</p> : null}
                  {metadata.instruction ? <p><span className="text-muted-foreground">How to fill:</span> {metadata.instruction}</p> : null}
                  {metadata.example ? <p><span className="text-muted-foreground">Example:</span> {metadata.example}</p> : null}
                  <MeasurementSlotSuggestions patternId={id} slot={name} />
                </DetailField>
              );
            })}
          </dl>
        </CardContent>
      </Card> : null}
      {item.variants.length ? <Card>
        <CardHeader>
          <CardTitle>Variants</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-2">
            {item.variants.map((variant, index) => (
              <li key={`${index}-${variant.text}`} className="leading-7">
                {variant.text}{" "}
                {variant.register ? (
                  <span className="text-sm text-muted-foreground">({variant.register})</span>
                ) : null}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card> : null}
      {usage.length ? <Card>
        <CardHeader>
          <CardTitle>Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            {usage.map((field) => <DetailField key={field.label} label={field.label}>{field.value}</DetailField>)}
          </dl>
        </CardContent>
      </Card> : null}
      <Card>
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
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
          <dl className="flex flex-col">
            <DetailField label="Source type">{item.source_type}</DetailField>
            {item.license_name || item.license_code ? (
              <DetailField label="License">
                {item.license_name ?? item.license_code}
                {item.license_name && item.license_code ? ` (${item.license_code})` : ""}
              </DetailField>
            ) : null}
            <DetailField label="Allows display">{item.license_allows_display ? "Yes" : "No"}</DetailField>
            <DetailField label="Internal use">{item.license_flag ? "Yes" : "No"}</DetailField>
            {item.source_reference ? <DetailField label="Article reference">{item.source_reference}</DetailField> : null}
            {item.article_id ? <DetailField label="Article ID">{item.article_id}</DetailField> : null}
            {item.source_sentence_count > 0 ? <DetailField label="Source sentences">{item.source_sentence_count}</DetailField> : null}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
