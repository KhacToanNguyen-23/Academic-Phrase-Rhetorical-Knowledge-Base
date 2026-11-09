import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { DataState } from "@/components/domain/DataState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/features/slr-import/api/client";
import type { APBFilterState } from "./AcademicPhraseBank";
import {
  PHRASEBANK_SOURCES,
  SOURCE_REGISTRY,
  phrasebankSources,
  type AcademicPhrase,
  type ManchesterCategory,
  type ManchesterSearchResult,
  type PatternDetail,
  type SourceId,
  type TaxonomyTree,
} from "./source-registry";

const SOURCE_CREDIT = "Source: University of Manchester Academic Phrasebank.";
const PAGE_SIZE = 20;

export function isReferenceDisabled(error: unknown) {
  return (
    error instanceof ApiError && error.status === 404 && error.body?.error?.message === "Reference library is disabled"
  );
}

export function taxonomyIntents(taxonomy?: TaxonomyTree) {
  return (taxonomy?.sections ?? []).flatMap((section) =>
    section.moves.flatMap((move) => move.steps.flatMap((step) => step.intents)),
  );
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

function sourceLabel(id: SourceId) {
  return SOURCE_REGISTRY.find((source) => source.id === id)?.label ?? id;
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const terms = [...new Set(query.trim().split(/\s+/).filter(Boolean))];
  if (!terms.length) return <>{text}</>;
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

type Row = {
  key: string;
  source: SourceId;
  /** Short group / function name, shown in the "Name" column. */
  name: string;
  /** Phrase text or a one-line description. */
  detail: ReactNode;
  /** Section / intent context. */
  context: string[];
  action: ReactNode;
};

function stringField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function patternRow(pattern: PatternDetail): Row {
  return {
    key: `pattern-${pattern.id}`,
    source: "aprkb-patterns",
    name: pattern.intent_name || pattern.intent_code,
    detail: <span className="font-serif text-base">{pattern.canonical_frame}</span>,
    context: [...pattern.allowed_sections],
    action: (
      <Button asChild variant="outline" size="sm">
        <Link to="/phrasebank/pattern/$id" params={{ id: pattern.id }}>View</Link>
      </Button>
    ),
  };
}

function academicRow(item: AcademicPhrase): Row {
  const functions = (item.communicative_functions ?? []).flatMap((record) => {
    const label = stringField(record, "label");
    return label ? [label] : [];
  });
  const sections = [
    ...new Set([
      ...(item.allowed_sections ?? []),
      ...(item.usage_profiles ?? []).flatMap((profile) => (profile.section_code ? [profile.section_code] : [])),
    ]),
  ];
  return {
    key: `apb-${item.id}`,
    source: "academic-phrase-bank",
    name: functions.join(", ") || item.intent_name || "Unmapped function",
    detail: <span className="font-serif text-base">{item.canonical_frame ?? "Phrase frame unavailable"}</span>,
    context: sections,
    action: (
      <Button asChild variant="outline" size="sm">
        <Link to="/phrasebank/apb/$id" params={{ id: item.id }}>View</Link>
      </Button>
    ),
  };
}

function categoryRow(category: ManchesterCategory): Row {
  return {
    key: `category-${category.slug}`,
    source: "manchester-reference",
    name: category.title,
    detail: (
      <span className="text-muted-foreground">
        {category.kind === "section" ? "Section" : "General function"} · {category.entry_count} entries
      </span>
    ),
    context: category.section_code ? [category.section_code] : [],
    action: (
      <Button asChild variant="outline" size="sm">
        <Link to="/phrasebank/$slug" params={{ slug: category.slug }}>Open</Link>
      </Button>
    ),
  };
}

function ReferenceAction({ item }: { item: ManchesterSearchResult }) {
  const navigate = useNavigate();
  const targetId = `heading-${item.category_slug}-${item.entry.heading_position}`;
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() =>
        void navigate({ to: "/phrasebank/$slug", params: { slug: item.category_slug }, hash: targetId }).then(() =>
          scrollAfterNavigation(targetId),
        )
      }
    >
      Open heading
    </Button>
  );
}

function referenceSearchRow(item: ManchesterSearchResult, query: string): Row | null {
  if (item.entry.kind !== "phrase" || !item.entry.cells?.length) return null;
  const text = item.entry.cells.map((alternatives) => alternatives.join(" / ")).join(" ");
  return {
    key: `reference-${item.entry.id}`,
    source: "manchester-reference",
    name: item.category_title,
    detail: (
      <span className="font-serif text-base">
        <HighlightedText text={text} query={query} />
      </span>
    ),
    context: item.section_code ? [item.section_code] : [],
    action: <ReferenceAction item={item} />,
  };
}

type Props = {
  source: "all" | SourceId;
  query: string;
  sectionCode: string;
  intentCode: string;
  hasSlots?: boolean;
  apbFilters: APBFilterState;
  taxonomy?: TaxonomyTree;
};

export function UnifiedResults({ source, query, sectionCode, intentCode, hasSlots, apbFilters, taxonomy }: Props) {
  const [page, setPage] = useState(1);
  // APB facets (function / stance / register / domain) exist only on APB entries, so an
  // active facet narrows the table to that source instead of silently ignoring it.
  const facetActive = Object.values(apbFilters).some(Boolean);
  const includes = (id: SourceId) => (source === "all" || source === id) && (!facetActive || id === "academic-phrase-bank");
  const showReference = includes("manchester-reference");
  const showPatterns = includes("aprkb-patterns");
  const showAcademic = includes("academic-phrase-bank");
  const filters = { sectionCode: sectionCode || undefined, intentCode: intentCode || undefined, hasSlots };
  const reference = PHRASEBANK_SOURCES["manchester-reference"];

  const categories = useQuery({
    queryKey: ["phrasebank-categories"],
    queryFn: reference.listGroups,
    enabled: showReference && !query,
    retry: false,
  });
  const referenceSearch = useQuery({
    queryKey: ["phrasebank-search", query, sectionCode, intentCode],
    queryFn: () => reference.search(query, filters),
    enabled: showReference && Boolean(query),
    retry: false,
  });
  const patterns = useQuery({
    queryKey: ["phrasebank-pattern-search", query, sectionCode, intentCode, hasSlots],
    queryFn: () => PHRASEBANK_SOURCES["aprkb-patterns"].search(query, filters),
    enabled: showPatterns,
    retry: false,
  });
  const academic = useQuery({
    queryKey: ["academic-phrase-search", query, sectionCode, intentCode, apbFilters],
    queryFn: () =>
      phrasebankSources.academicPhrases({
        q: query || undefined,
        sectionCode: sectionCode || undefined,
        intentCode: intentCode || undefined,
        functionCode: apbFilters.function?.code,
        functionVersion: apbFilters.function?.version,
        stanceCode: apbFilters.stance?.code,
        stanceVersion: apbFilters.stance?.version,
        registerCode: apbFilters.register?.code,
        registerVersion: apbFilters.register?.version,
        domainCode: apbFilters.domain?.code,
        limit: 200,
        offset: 0,
      }),
    enabled: showAcademic,
    retry: false,
  });

  const referenceDisabled = isReferenceDisabled(query ? referenceSearch.error : categories.error);
  const referenceQuery = query ? referenceSearch : categories;
  const referencePending = showReference && referenceQuery.isPending && !referenceDisabled;

  const rows: Row[] = [];
  if (showReference && !referenceDisabled) {
    if (query) {
      for (const item of referenceSearch.data ?? []) {
        const row = referenceSearchRow(item, query);
        if (row) rows.push(row);
      }
    } else {
      for (const category of categories.data ?? []) {
        if (sectionCode && !(taxonomy && reference.filterBySection(category, sectionCode, taxonomy))) continue;
        if (intentCode && !reference.filterByIntent(category, intentCode)) continue;
        rows.push(categoryRow(category));
      }
    }
  }
  if (showPatterns) for (const pattern of patterns.data ?? []) rows.push(patternRow(pattern));
  if (showAcademic) {
    for (const item of academic.data?.items ?? []) {
      rows.push(academicRow(item));
    }
  }

  const errors = [
    showPatterns && patterns.isError ? { label: "AP-RKB patterns", message: patterns.error.message, retry: patterns.refetch } : null,
    showAcademic && academic.isError ? { label: "Academic Phrase Bank", message: academic.error.message, retry: academic.refetch } : null,
    showReference && referenceQuery.isError && !referenceDisabled
      ? { label: "Manchester reference", message: referenceQuery.error.message, retry: referenceQuery.refetch }
      : null,
  ].filter((entry) => entry !== null);
  const pending = referencePending || (showPatterns && patterns.isPending) || (showAcademic && academic.isPending);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const firstIndex = (currentPage - 1) * PAGE_SIZE;
  const shown = rows.slice(firstIndex, firstIndex + PAGE_SIZE);
  const filterKey = [source, query, sectionCode, intentCode, hasSlots, JSON.stringify(apbFilters)].join("|");
  useEffect(() => setPage(1), [filterKey]);
  const title = source === "all" ? "All Phrasebank" : sourceLabel(source);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {showReference && referenceDisabled ? (
          <p role="status" className="text-sm text-muted-foreground">
            Manchester reference phrases are unavailable. Other sources are still shown.
          </p>
        ) : null}
        {facetActive && source !== "academic-phrase-bank" ? (
          <p role="status" className="text-sm text-muted-foreground">
            Function, stance, register and domain filters only apply to Academic Phrase Bank, so other sources are hidden.
          </p>
        ) : null}
        {errors.map((entry) => (
          <DataState
            key={entry.label}
            state="error"
            errorTitle={`Could not load ${entry.label}`}
            errorDescription={entry.message}
            onRetry={() => void entry.retry()}
          />
        ))}
        {pending && rows.length === 0 ? (
          <DataState state="loading" loadingLabel="Loading phrases" />
        ) : rows.length === 0 && errors.length === 0 ? (
          <DataState
            state="empty"
            emptyTitle="No phrases match"
            emptyDescription="Try another phrase, source or filter."
          />
        ) : rows.length > 0 ? (
          <>
            <p className="text-sm text-muted-foreground" role="status">
              Showing {firstIndex + 1}–{firstIndex + shown.length} of {rows.length} results.
            </p>
            <Table aria-label="Phrasebank results">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">#</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Phrase / description</TableHead>
                  <TableHead>Section</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="w-28" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((row, index) => (
                  <TableRow key={row.key}>
                    <TableCell className="align-top text-muted-foreground">{firstIndex + index + 1}</TableCell>
                    <TableCell className="whitespace-normal align-top font-medium">{row.name}</TableCell>
                    <TableCell className="whitespace-normal align-top leading-7">{row.detail}</TableCell>
                    <TableCell className="whitespace-normal align-top">
                      <div className="flex flex-wrap gap-1.5">
                        {row.context.map((value) => (
                          <Badge key={value} variant="secondary">{value}</Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="align-top">
                      <Badge variant="outline">{sourceLabel(row.source)}</Badge>
                    </TableCell>
                    <TableCell className="align-top">{row.action}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {pageCount > 1 ? (
              <nav aria-label="Results pagination" className="flex items-center justify-center gap-3">
                <Button variant="outline" size="sm" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)} aria-label="Previous page">
                  <ChevronLeft aria-hidden="true" className="size-4" /> Previous
                </Button>
                <span className="text-sm text-muted-foreground" aria-live="polite">
                  Page {currentPage} of {pageCount}
                </span>
                <Button variant="outline" size="sm" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)} aria-label="Next page">
                  Next <ChevronRight aria-hidden="true" className="size-4" />
                </Button>
              </nav>
            ) : null}
          </>
        ) : null}
        {showReference && !referenceDisabled && rows.some((row) => row.source === "manchester-reference") ? (
          <p className="text-sm text-muted-foreground">{SOURCE_CREDIT}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
