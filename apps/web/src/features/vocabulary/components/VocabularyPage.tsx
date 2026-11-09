import { getRouteApi, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { useFamilies, useLemmas, useLetters, useVocabularyFilterOptions } from "../api/client";
import { VocabularyImportCard } from "./VocabularyImportCard";

const route = getRouteApi("/shell/guarded/vocabulary");
const alphabet = [..."abcdefghijklmnopqrstuvwxyz", "#"];
const noLemmaFilters = {
  letter: undefined,
  pos: undefined,
  status: undefined,
  bandMin: undefined,
  bandMax: undefined,
  domain: undefined,
  sort: undefined,
};
const sortOptions = {
  alpha: "A–Z",
  rank: "Academic rank",
  academic_frequency: "Most frequent in academic texts",
};

function statusVariant(status: string | null): "success" | "warning" | "secondary" | "default" {
  if (status === "y") return "success";
  if (status === "r") return "warning";
  if (status === "x") return "secondary";
  return "default";
}

function VocabularySelect({
  label,
  value,
  options,
  allLabel,
  onChange,
}: {
  label: string;
  value?: string;
  options: Record<string, string>;
  allLabel?: string;
  onChange: (value: string | undefined) => void;
}) {
  const id = `vocabulary-${label.toLowerCase().replaceAll(" ", "-")}`;
  const selectedLabel = value ? options[value] : allLabel;
  return (
    <Field className="min-w-0">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Select value={value ?? "all"} onValueChange={(next) => onChange(next === "all" ? undefined : next)}>
        <SelectTrigger id={id} className="w-full *:data-[slot=select-value]:min-w-0" title={selectedLabel}>
          <SelectValue>
            <span className="truncate">{selectedLabel === "unknown" ? `Unknown (${value})` : selectedLabel}</span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {allLabel ? <SelectItem value="all">{allLabel}</SelectItem> : null}
          {Object.entries(options).map(([code, name]) => (
            <SelectItem key={code} value={code}>
              {name === "unknown" ? `Unknown (${code})` : name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

function QueryState({
  pending,
  error,
  empty,
  onRetry,
  emptyTitle,
  emptyDescription,
  emptyAction,
}: {
  pending: boolean;
  error: Error | null;
  empty: boolean;
  onRetry: () => void;
  emptyTitle: string;
  emptyDescription: string;
  emptyAction?: ReactNode;
}) {
  if (pending)
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading vocabulary">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  if (error)
    return (
      <DataState
        state="error"
        errorTitle="Could not load vocabulary"
        errorDescription={error.message}
        onRetry={onRetry}
      />
    );
  if (empty)
    return (
      <DataState state="empty" emptyTitle={emptyTitle} emptyDescription={emptyDescription} emptyAction={emptyAction} />
    );
  return null;
}

function VocabularyPagination({
  total,
  offset,
  limit,
  onPageChange,
}: {
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
}) {
  if (total === 0) return null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  const hasPrevious = offset > 0;
  const hasNext = last < total;
  return (
    <Pagination>
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            href="#"
            aria-disabled={!hasPrevious}
            className={!hasPrevious ? "pointer-events-none opacity-50" : undefined}
            onClick={(event) => {
              event.preventDefault();
              if (hasPrevious) onPageChange(Math.max(0, offset - limit));
            }}
          />
        </PaginationItem>
        <PaginationItem>
          <span className="px-3 text-sm text-muted-foreground">
            {first <= last ? `${first.toLocaleString()}–${last.toLocaleString()} of ` : ""}
            {total.toLocaleString()}
          </span>
        </PaginationItem>
        <PaginationItem>
          <PaginationNext
            href="#"
            aria-disabled={!hasNext}
            className={!hasNext ? "pointer-events-none opacity-50" : undefined}
            onClick={(event) => {
              event.preventDefault();
              if (hasNext) onPageChange(offset + limit);
            }}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}

export function VocabularyPage() {
  const { client: authClient } = useAuth();
  const search = route.useSearch();
  const navigate = useNavigate({ from: "/vocabulary" });
  const [query, setQuery] = useState(search.q ?? "");
  const [minBand, setMinBand] = useState(search.bandMin?.toString() ?? "");
  const [maxBand, setMaxBand] = useState(search.bandMax?.toString() ?? "");
  const [showImport, setShowImport] = useState(false);
  const view = search.view ?? "lemmas";
  const sort = search.sort ?? "alpha";
  const offset = search.offset ?? 0;
  const limit = 50;
  const isCurator = authClient?.role === "curator" || authClient?.role === "admin";
  const filterOptions = useVocabularyFilterOptions();
  const lemmaFilters = {
    pos: search.pos,
    status: search.status,
    band_min: search.bandMin,
    band_max: search.bandMax,
    domain: search.domain,
  };
  const letters = useLetters(lemmaFilters);
  const lemmas = useLemmas({
    ...lemmaFilters,
    q: search.q,
    letter: search.letter,
    sort,
    limit,
    offset,
  });
  const families = useFamilies({ q: search.q, limit, offset });
  // Unfiltered totals for the summary strip.
  const allLetters = useLetters();
  const coreLetters = useLetters({ core_only: true });
  const familyTotal = useFamilies({ limit: 1, offset: 0 });
  const sumLetters = (data?: { count: number }[]) => data?.reduce((sum, item) => sum + item.count, 0);
  const lemmaCount = sumLetters(allLetters.data);
  const coreCount = sumLetters(coreLetters.data);
  const maxLetter = Math.max(1, ...(letters.data ?? []).map((item) => item.count));

  useEffect(() => {
    const nextQuery = query.trim() || undefined;
    if (nextQuery === search.q) return;
    const timer = window.setTimeout(() => {
      void navigate({
        search: (previous) => ({
          ...previous,
          q: nextQuery,
          letter: nextQuery ? undefined : previous.letter,
          offset: 0,
        }),
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [navigate, query, search.q]);
  useEffect(() => {
    setQuery(search.q ?? "");
  }, [search.q]);
  useEffect(() => {
    setMinBand(search.bandMin?.toString() ?? "");
    setMaxBand(search.bandMax?.toString() ?? "");
  }, [search.bandMin, search.bandMax]);

  const counts = useMemo(() => new Map((letters.data ?? []).map((item) => [item.letter, item.count])), [letters.data]);
  const totalLettersCount = useMemo(
    () => (letters.data ?? []).reduce((sum, item) => sum + item.count, 0),
    [letters.data],
  );
  const hasActiveFilters = Boolean(
    search.q || search.letter || Object.values(lemmaFilters).some((value) => value !== undefined) || sort !== "alpha",
  );
  const bandMin = minBand === "" ? undefined : Number(minBand);
  const bandMax = maxBand === "" ? undefined : Number(maxBand);
  const reversedBand = bandMin !== undefined && bandMax !== undefined && bandMin > bandMax;
  const updateSearch = (patch: Partial<typeof search>) =>
    void navigate({ search: (previous) => ({ ...previous, ...patch }) });
  const clearFilters = () => {
    setQuery("");
    setMinBand("");
    setMaxBand("");
    updateSearch({ ...noLemmaFilters, q: undefined, offset: 0 });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Academic vocabulary"
        description="Browse and inspect the academic lexicon by lemma, rank, and word family."
        actions={
          isCurator ? (
            <Button variant={showImport ? "outline" : "default"} onClick={() => setShowImport((open) => !open)}>
              {showImport ? "Close import" : "Import vocabulary"}
            </Button>
          ) : undefined
        }
      />
      {showImport && isCurator ? <VocabularyImportCard onClose={() => setShowImport(false)} /> : null}
      <section aria-label="Lexicon summary" className="grid grid-cols-3 gap-6">
        {[
          { value: lemmaCount, label: "Lemmas", note: "Every lemma and part of speech" },
          {
            value: coreCount,
            label: "Core academic lemmas",
            note:
              lemmaCount && coreCount !== undefined
                ? `${Math.round((coreCount / lemmaCount) * 100)}% of all lemmas`
                : undefined,
          },
          { value: familyTotal.data?.total, label: "Word families", note: "Grouped by headword" },
        ].map((figure) => (
          <div key={figure.label} className="flex flex-col gap-1 py-1">
            <span className="text-3xl font-semibold tabular-nums">{figure.value?.toLocaleString() ?? "—"}</span>
            <span className="text-sm">{figure.label}</span>
            {figure.note ? <span className="text-sm text-muted-foreground">{figure.note}</span> : null}
          </div>
        ))}
      </section>
      <Tabs
        value={view}
        onValueChange={(nextView) =>
          updateSearch({
            view: nextView as "lemmas" | "families",
            offset: 0,
            ...(nextView === "families" ? noLemmaFilters : {}),
          })
        }
        className="flex flex-col gap-4"
      >
        <TabsList aria-label="Vocabulary view">
          <TabsTrigger value="lemmas">
            Lemmas{lemmas.data ? ` (${lemmas.data.total.toLocaleString()})` : ""}
          </TabsTrigger>
          <TabsTrigger value="families">
            Word families{families.data ? ` (${families.data.total.toLocaleString()})` : ""}
          </TabsTrigger>
        </TabsList>
        <Card>
          <CardContent className="flex flex-col gap-4 pt-4">
            <div className="flex items-end gap-4">
              <Field className="max-w-xl">
                <FieldLabel htmlFor="vocabulary-search">Search vocabulary</FieldLabel>
                <Input
                  id="vocabulary-search"
                  type="search"
                  placeholder={view === "families" ? "Search word families by headword" : "Search lemmas by prefix"}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </Field>
              {query ? (
                <Button variant="ghost" onClick={() => setQuery("")}>
                  Clear
                </Button>
              ) : null}
            </div>
            <TabsContent value="lemmas" className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {filterOptions.data ? (
                  <>
                    <VocabularySelect
                      label="Part of speech"
                      allLabel="All parts of speech"
                      value={search.pos}
                      options={filterOptions.data.pos}
                      onChange={(pos) => updateSearch({ pos, offset: 0 })}
                    />
                    <VocabularySelect
                      label="Status"
                      allLabel="All statuses"
                      value={search.status}
                      options={filterOptions.data.status}
                      onChange={(status) => updateSearch({ status, offset: 0 })}
                    />
                    <VocabularySelect
                      label="Discipline"
                      allLabel="All disciplines"
                      value={search.domain}
                      options={filterOptions.data.domains}
                      onChange={(domain) => updateSearch({ domain, offset: 0 })}
                    />
                  </>
                ) : null}
                <VocabularySelect
                  label="Sort order"
                  value={sort}
                  options={sortOptions}
                  onChange={(value) => updateSearch({ sort: value as keyof typeof sortOptions, offset: 0 })}
                />
              </div>
              {filterOptions.isError ? (
                <p role="alert" className="text-sm text-muted-foreground">Could not load vocabulary filter options.</p>
              ) : null}
              {search.domain ? (
                <p className="text-sm text-muted-foreground">
                  Showing lemmas used more often than expected in this discipline.
                </p>
              ) : null}
              <form
                className="flex flex-wrap items-end gap-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!reversedBand) updateSearch({ bandMin, bandMax, offset: 0 });
                }}
              >
                <Field className="w-28">
                  <FieldLabel htmlFor="vocabulary-min-band">Min band</FieldLabel>
                  <Input
                    id="vocabulary-min-band"
                    type="number"
                    min={1}
                    max={2147483647}
                    value={minBand}
                    onChange={(event) => setMinBand(event.target.value)}
                    aria-invalid={reversedBand}
                  />
                </Field>
                <Field className="w-28">
                  <FieldLabel htmlFor="vocabulary-max-band">Max band</FieldLabel>
                  <Input
                    id="vocabulary-max-band"
                    type="number"
                    min={1}
                    max={2147483647}
                    value={maxBand}
                    onChange={(event) => setMaxBand(event.target.value)}
                    aria-invalid={reversedBand}
                  />
                </Field>
                <Button type="submit" variant="outline" disabled={reversedBand}>Apply band</Button>
                {hasActiveFilters || minBand || maxBand ? (
                  <Button type="button" variant="ghost" onClick={clearFilters}>
                    Reset filters
                  </Button>
                ) : null}
              </form>
              {reversedBand ? (
                <p role="alert" className="text-sm text-destructive">Min band must be less than or equal to max band.</p>
              ) : null}
              <ToggleGroup
                type="single"
                value={search.letter ?? "all"}
                onValueChange={(value) => {
                  if (!value) return;
                  setQuery("");
                  updateSearch({ letter: value === "all" ? undefined : value, q: undefined, offset: 0 });
                }}
                aria-label="Filter vocabulary by initial letter"
                className="flex w-full flex-nowrap justify-between gap-0.5"
              >
                <ToggleGroupItem
                  value="all"
                  aria-label="All letters"
                  className="h-14 min-w-9 flex-col justify-end gap-0 px-1"
                >
                  <span aria-hidden className="mb-1 block w-full bg-foreground/30" style={{ height: "4px" }} />
                  <span>All</span>
                  <small className="tabular-nums text-muted-foreground">{totalLettersCount}</small>
                </ToggleGroupItem>
                {alphabet.map((letter) => {
                  const count = counts.get(letter) ?? 0;
                  return (
                    <ToggleGroupItem
                      key={letter}
                      value={letter}
                      disabled={!letters.isPending && count === 0}
                      aria-label={`${letter.toUpperCase()} ${count} lemmas`}
                      className="h-14 min-w-8 flex-col justify-end gap-0 px-1"
                    >
                      <span
                        aria-hidden
                        className="mb-1 block w-full bg-foreground/30"
                        style={{ height: `${Math.max(2, Math.round((count / maxLetter) * 22))}px` }}
                      />
                      <span>{letter.toUpperCase()}</span>
                      <small className="tabular-nums text-muted-foreground">{count}</small>
                    </ToggleGroupItem>
                  );
                })}
              </ToggleGroup>
            </TabsContent>
          </CardContent>
        </Card>
        <TabsContent value="lemmas" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>Academic lemmas</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <QueryState
                pending={lemmas.isPending}
                error={lemmas.isError ? lemmas.error : null}
                empty={!lemmas.isPending && !lemmas.isError && lemmas.data.items.length === 0}
                onRetry={() => void lemmas.refetch()}
                emptyTitle={hasActiveFilters ? "No lemmas match these filters" : "No academic lemmas loaded"}
                emptyDescription={
                  hasActiveFilters
                    ? "Try another search or adjust the filters."
                    : "The lexicon has not been imported yet."
                }
                emptyAction={
                  hasActiveFilters ? (
                    <Button variant="outline" onClick={clearFilters}>
                      Reset filters
                    </Button>
                  ) : isCurator ? (
                    <Button variant="outline" onClick={() => setShowImport(true)}>
                      Open import tool
                    </Button>
                  ) : undefined
                }
              />
              {!lemmas.isPending && !lemmas.isError && lemmas.data.items.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Lemma</TableHead>
                      <TableHead>Part of speech</TableHead>
                      <TableHead numeric>Rank</TableHead>
                      <TableHead numeric>Band</TableHead>
                      {sort === "academic_frequency" ? <TableHead numeric>Academic frequency</TableHead> : null}
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lemmas.data.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Link
                            className="font-medium text-primary hover:underline"
                            to="/vocabulary/$lemmaId"
                            params={{ lemmaId: item.id }}
                            search={search}
                          >
                            {item.word}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.pos_label}</Badge>
                        </TableCell>
                        <TableCell numeric>{item.rank !== null ? `#${item.rank}` : "—"}</TableCell>
                        <TableCell numeric>{item.band !== null ? `Band ${item.band}` : "—"}</TableCell>
                        {sort === "academic_frequency" ? (
                          <TableCell numeric>{item.coca_acad?.toLocaleString() ?? "—"}</TableCell>
                        ) : null}
                        <TableCell>
                          <Badge variant={statusVariant(item.status)}>{item.status_label || "Unknown"}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
              <VocabularyPagination
                total={lemmas.data?.total ?? 0}
                offset={offset}
                limit={limit}
                onPageChange={(nextOffset) => updateSearch({ offset: nextOffset })}
              />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="families" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>Academic word families</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <QueryState
                pending={families.isPending}
                error={families.isError ? families.error : null}
                empty={!families.isPending && !families.isError && families.data.items.length === 0}
                onRetry={() => void families.refetch()}
                emptyTitle={query ? "No word families match this search" : "No word families recorded"}
                emptyDescription="Try a different search or import a vocabulary spreadsheet."
                emptyAction={
                  query ? (
                    <Button variant="outline" onClick={() => setQuery("")}>
                      Clear search
                    </Button>
                  ) : undefined
                }
              />
              {!families.isPending && !families.isError && families.data.items.length > 0 ? (
                <div className="flex flex-col gap-3">
                  {families.data.items.map((family) => (
                    <details key={family.id} className="rounded-[var(--radius)] border border-border">
                      <summary
                        className={
                          "flex cursor-pointer items-center justify-between gap-4 px-4 py-3 " + "hover:bg-muted/50"
                        }
                      >
                        <span className="flex items-center gap-3">
                          <strong>{family.headword}</strong>
                          <Badge variant="outline">{family.members.length} members</Badge>
                        </span>
                        <span className="text-sm text-muted-foreground">
                          Rank {family.rank} · {family.family_freq.toLocaleString()} frequency
                        </span>
                      </summary>
                      <div className="border-t border-border p-2">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Word form</TableHead>
                              <TableHead>Part of speech</TableHead>
                              <TableHead numeric>Frequency</TableHead>
                              <TableHead>Category</TableHead>
                              <TableHead>Domains</TableHead>
                              <TableHead>Action</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {family.members.map((member) => (
                              <TableRow key={`${family.id}-${member.lemma_id}`}>
                                <TableCell>
                                  <Link
                                    className="font-medium text-primary hover:underline"
                                    to="/vocabulary/$lemmaId"
                                    params={{ lemmaId: member.lemma_id }}
                                    search={search}
                                  >
                                    {member.word}
                                  </Link>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline">{member.pos_label}</Badge>
                                </TableCell>
                                <TableCell numeric>{member.freq.toLocaleString()}</TableCell>
                                <TableCell>
                                  <Badge>{member.category_label}</Badge>
                                </TableCell>
                                <TableCell>{member.domains.join(", ") || "—"}</TableCell>
                                <TableCell>
                                  <Button asChild variant="outline" size="sm">
                                    <Link
                                      to="/vocabulary/$lemmaId"
                                      params={{ lemmaId: member.lemma_id }}
                                      search={search}
                                    >
                                      Inspect
                                    </Link>
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </details>
                  ))}
                </div>
              ) : null}
              <VocabularyPagination
                total={families.data?.total ?? 0}
                offset={offset}
                limit={limit}
                onPageChange={(nextOffset) => updateSearch({ offset: nextOffset })}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
