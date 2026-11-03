import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/domain/DataState";
import { EvidenceLabel } from "@/components/domain/EvidenceLabel";
import { PageHeader } from "@/components/domain/PageHeader";
import { PhraseFrame } from "@/components/domain/PhraseFrame";
import { LicenceStatus, ProvenanceTag } from "@/components/domain/ProvenanceTag";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type PatternQuery, type PatternStatus, type PhrasePattern, type Section } from "@/shared/api";

const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const STATUSES: PatternStatus[] = ["approved", "in_review", "draft", "retired"];

export function LibraryPage({ selectedId }: { selectedId?: string }) {
  const [filters, setFilters] = useState<PatternQuery>({});
  const navigate = useNavigate();
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const list = useQuery({
    queryKey: ["patterns", filters],
    queryFn: () => api.patterns(filters),
    placeholderData: (previous) => previous,
  });
  const statusSummary = list.data?.length
    ? " · " +
      STATUSES.map((status) => [status, list.data.filter((p) => p.status === status).length] as const)
        .filter(([, count]) => count > 0)
        .map(([status, count]) => `${count} ${status.replace("_", " ")}`)
        .join(" · ")
    : "";
  const activeId = selectedId ?? list.data?.[0]?.id;
  const intentName = (id: string) => intents.data?.find((intent) => intent.intent_id === id)?.name ?? id;
  const retry = async () => {
    await Promise.all([intents.refetch(), list.refetch()]);
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Pattern library"
        description={
          "Approved rhetorical frames are separated from provenance, licence, and corpus evidence so every entry " +
          "remains auditable."
        }
      />
      {intents.isError || list.isError ? (
        <DataState
          state="error"
          errorTitle="Could not load the pattern library"
          errorDescription="The pattern list or intent taxonomy could not be loaded."
          onRetry={() => void retry()}
        />
      ) : (
        <div className="grid grid-cols-[22rem_1fr] items-start gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Find a pattern</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Input
                type="search"
                aria-label="Search patterns"
                placeholder="Search frames or IDs"
                value={filters.q ?? ""}
                onChange={(event) => setFilters((previous) => ({ ...previous, q: event.target.value || undefined }))}
              />
              <div className="grid grid-cols-2 gap-2">
                <Select
                  value={filters.section ?? "all"}
                  onValueChange={(value) =>
                    setFilters((previous) => ({
                      ...previous,
                      section: value === "all" ? undefined : (value as Section),
                    }))
                  }
                >
                  <SelectTrigger aria-label="Section">
                    <SelectValue placeholder="Section" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All sections</SelectItem>
                    {SECTIONS.map((section) => (
                      <SelectItem key={section} value={section}>
                        {section}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={filters.status ?? "all"}
                  onValueChange={(value) =>
                    setFilters((previous) => ({
                      ...previous,
                      status: value === "all" ? undefined : (value as PatternStatus),
                    }))
                  }
                >
                  <SelectTrigger aria-label="Status">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    {STATUSES.map((status) => (
                      <SelectItem key={status} value={status}>
                        {status.replace("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-sm text-muted-foreground">
                {list.data?.length ?? 0} entries
                {statusSummary}
              </p>
              {list.isPending ? (
                <div className="flex flex-col gap-2" aria-busy="true">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : list.data?.length ? (
                <ul className="flex flex-col gap-1">
                  {list.data.map((pattern) => (
                    <li key={pattern.id}>
                      <button
                        type="button"
                        className={
                          "flex w-full flex-col gap-2 rounded-[var(--radius)] border border-transparent px-3 py-3 " +
                          "text-left hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-2 " +
                          "focus-visible:ring-ring/50 data-[selected=true]:border-border data-[selected=true]:bg-muted"
                        }
                        data-selected={pattern.id === activeId}
                        aria-current={pattern.id === activeId ? "page" : undefined}
                        onClick={() => void navigate({ to: "/library", search: { p: pattern.id } })}
                      >
                        <span className="flex items-center justify-between gap-3">
                          <code>{pattern.id}</code>
                          <StatusBadge status={pattern.status} />
                        </span>
                        <PhraseFrame frame={pattern.canonical_frame} className="text-base" />
                        <span className="text-xs text-muted-foreground">
                          {intentName(pattern.intent_id)} · {pattern.section_scope.join(", ")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <DataState
                  state="empty"
                  emptyTitle="No patterns match"
                  emptyDescription="Try a different query, section, or status."
                />
              )}
            </CardContent>
          </Card>
          <div key={activeId}>
            {activeId ? (
              <Detail id={activeId} intentName={intentName} />
            ) : (
              <DataState
                state="empty"
                emptyTitle="Select a pattern"
                emptyDescription="Choose an entry from the list to inspect its contract."
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ id, intentName }: { id: string; intentName: (id: string) => string }) {
  const query = useQuery({ queryKey: ["pattern", id], queryFn: () => api.pattern(id) });
  if (query.isPending)
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  if (query.isError)
    return (
      <DataState
        state="error"
        errorTitle={`Pattern ${id} could not be loaded`}
        errorDescription={query.error.message}
        onRetry={() => void query.refetch()}
      />
    );
  if (!query.data)
    return (
      <DataState
        state="empty"
        emptyTitle={`Pattern ${id} not found`}
        emptyDescription="This entry is no longer available."
      />
    );
  const pattern = query.data;
  const servable =
    pattern.status === "approved" &&
    (pattern.license_status === "own_authored" || pattern.license_status === "allowed");
  const provenance =
    pattern.provenance === "authored"
      ? "authored"
      : pattern.provenance === "adapted_permission"
        ? "adapted"
        : "corpus-inferred";
  const licence =
    pattern.license_status === "own_authored" || pattern.license_status === "allowed"
      ? "cleared"
      : pattern.license_status === "unknown"
        ? "unknown"
        : "restricted";

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>{intentName(pattern.intent_id)}</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {pattern.id} · version {pattern.version}
              </p>
            </div>
            {servable ? (
              <Button asChild>
                <Link to="/playground" search={{ pattern: pattern.id }}>
                  Try in playground
                </Link>
              </Button>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <PhraseFrame frame={pattern.canonical_frame} className="text-xl" />
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={pattern.status} />
            <Badge>{pattern.claim_type}</Badge>
            <Badge>{pattern.epistemic_strength} strength</Badge>
            {pattern.section_scope.map((section) => (
              <Badge key={section} variant="outline">
                {section}
              </Badge>
            ))}
            {pattern.article_genres.map((genre) => (
              <Badge key={genre} variant="outline">
                {genre}
              </Badge>
            ))}
          </div>
          <p className="rounded-[var(--radius)] border border-border px-3 py-2 text-sm">
            {servable
              ? "Servable via API — approval and licence gates pass."
              : `Not servable via API — ${
                  pattern.status !== "approved" ? `status is ${pattern.status}` : `licence is ${pattern.license_status}`
                }.`}
          </p>
        </CardContent>
      </Card>
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Slots</CardTitle>
          </CardHeader>
          <CardContent>
            <SlotTable pattern={pattern} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Usage contract</CardTitle>
            <Badge variant="warning">FR-02.4</Badge>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-3 text-sm">
              <dt className="text-muted-foreground">Minimum evidence</dt>
              <dd>{pattern.constraint.evidence_min}</dd>
              <dt className="text-muted-foreground">Do not use when</dt>
              <dd>
                {pattern.constraint.forbidden_contexts.length ? (
                  <ul className="flex list-disc flex-col gap-1 pl-5">
                    {pattern.constraint.forbidden_contexts.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </dd>
              <dt className="text-muted-foreground">Note</dt>
              <dd>{pattern.constraint.guidance || "—"}</dd>
            </dl>
          </CardContent>
        </Card>
      </div>
      {pattern.variants.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Variants</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {pattern.variants.map((variant) => (
              <div
                key={variant.variant_id}
                className="flex items-center justify-between gap-4 rounded-[var(--radius)] border border-border p-3"
              >
                <PhraseFrame frame={variant.phrase_text} className="text-base" />
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">{variant.transformation}</span>
                  <Badge variant={variant.semantic_status === "equivalent" ? "success" : "warning"}>
                    {variant.semantic_status === "equivalent" ? "Equivalence approved" : "Pending semantic review"}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
      <div className="grid grid-cols-2 items-start gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Provenance</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <ProvenanceTag value={provenance} />
            <LicenceStatus status={licence} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Corpus evidence</CardTitle>
            <EvidenceLabel kind="observed" />
          </CardHeader>
          <CardContent>
            {pattern.corpus_support ? (
              // prettier-ignore
              <p className="text-sm">
                Observed{" "}
                <strong className="tabular-nums">
                  {pattern.corpus_support.occurrences}
                </strong>{" "}
                times across{" "}
                <strong className="tabular-nums">{pattern.corpus_support.documents}</strong> articles (
                {pattern.corpus_support.window}). This is descriptive evidence, not a journal requirement.
              </p>
            ) : (
              <DataState
                state="empty"
                emptyTitle="No corpus statistics"
                emptyDescription="No descriptive corpus support has been recorded."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SlotTable({ pattern }: { pattern: PhrasePattern }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Slot</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Guidance</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pattern.slots_schema.map((slot) => (
          <TableRow key={slot.name}>
            <TableCell>
              <code>{`{${slot.name}}`}</code>
              {slot.required ? " *" : ""}
            </TableCell>
            <TableCell>{slot.type}</TableCell>
            <TableCell className="whitespace-normal">{slot.guidance}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
