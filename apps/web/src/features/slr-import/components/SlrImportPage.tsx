import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { cn } from "@/lib/utils";
import { ApiError, slrImportClient, unwrap } from "../api/client";

const kinds = ["FULLTEXT_MARKDOWN", "FETCHER_FULLTEXT_MARKDOWN", "SOURCE_PDF"] as const;
type Kind = (typeof kinds)[number];
type Profile = {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  artifact_kinds: string[];
  batch_limit: number;
  is_active: boolean;
};
type JobResult = {
  listed?: number;
  imported?: number;
  skipped_license?: number;
  skipped_duplicate?: number;
  skipped_format?: number;
  skipped_invalid_content?: number;
  continuation_job_id?: string | null;
  batch_id?: string | null;
};
type TaxonomyPage = { items: { id: string; label: string }[]; nextCursor: string | null };

const taxonFields = { domain: "domainId", field: "fieldId", subfield: "subfieldId", topic: "topicId" } as const;
const taxonomyLabels = { domain: "Domain", field: "Field", subfield: "Subfield", topic: "Topic" } as const;
const jobLabels: Record<string, string> = {
  queued: "Queued: waiting for a worker",
  running: "Running: articles are being fetched and checked",
  processing: "Processing: imported articles are being prepared",
  done: "Complete: the import finished",
  succeeded: "Complete: the import finished",
  failed: "Failed: the import stopped with an error",
};

function taxonomyQuery(api: ReturnType<typeof slrImportClient>, level: string, parentId?: string, enabled = true) {
  return {
    queryKey: ["slr-taxonomy", level, parentId],
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }: { pageParam: string | undefined }): Promise<TaxonomyPage> => {
      const data = unwrap(
        await api.GET("/v1/admin/corpus/sources/slr/taxonomy", {
          params: { query: { level, parentId, cursor: pageParam, limit: 100 } },
        }),
      );
      if (!data) throw new Error("SLR taxonomy returned an empty response.");
      return data as unknown as TaxonomyPage;
    },
    getNextPageParam: (lastPage: TaxonomyPage | undefined) => lastPage?.nextCursor ?? undefined,
  };
}

export function SlrImportPage() {
  const api = slrImportClient();
  const queryClient = useQueryClient();
  const [key, setKey] = useState(sessionStorage.getItem("aprkb-api-key") ?? "");
  const [hasSavedKey, setHasSavedKey] = useState(Boolean(sessionStorage.getItem("aprkb-api-key")));
  const [selected, setSelected] = useState<string>();
  const [name, setName] = useState("");
  const [filters, setFilters] = useState<Record<string, string | boolean>>({ hasFullText: true });
  const [artifactKinds, setArtifactKinds] = useState<Kind[]>([...kinds]);
  const [batchLimit, setBatchLimit] = useState(25);
  const [jobId, setJobId] = useState<string>();
  const [startError, setStartError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState("");

  const profiles = useQuery({
    queryKey: ["slr-import-profiles"],
    queryFn: async () => {
      const data = unwrap(await api.GET("/v1/admin/corpus/import-profiles"));
      return (data ?? []) as Profile[];
    },
  });
  const profile = profiles.data?.find((item) => item.id === selected);
  const taxonomyLevels = Object.keys(taxonFields) as (keyof typeof taxonFields)[];
  const taxonomyQueries = [
    useInfiniteQuery(taxonomyQuery(api, "domain")),
    useInfiniteQuery(
      taxonomyQuery(api, "field", String(filters.domainId ?? "") || undefined, Boolean(filters.domainId)),
    ),
    useInfiniteQuery(
      taxonomyQuery(api, "subfield", String(filters.fieldId ?? "") || undefined, Boolean(filters.fieldId)),
    ),
    useInfiniteQuery(
      taxonomyQuery(api, "topic", String(filters.subfieldId ?? "") || undefined, Boolean(filters.subfieldId)),
    ),
  ];

  const handleSaveKey = () => {
    sessionStorage.setItem("aprkb-api-key", key);
    setHasSavedKey(Boolean(key));
    void queryClient.invalidateQueries();
  };

  const handleClearKey = () => {
    sessionStorage.removeItem("aprkb-api-key");
    setKey("");
    setHasSavedKey(false);
    void queryClient.invalidateQueries();
  };

  const handleSelectProfile = (item: Profile) => {
    setSelected(item.id);
    setName(item.name);
    setFilters((item.filters as Record<string, string | boolean>) ?? { hasFullText: true });
    setArtifactKinds((item.artifact_kinds as Kind[]) ?? [...kinds]);
    setBatchLimit(item.batch_limit ?? 25);
    setFieldErrors({});
    setSaveMessage("");
  };

  const handleCreateNew = () => {
    setSelected(undefined);
    setName("");
    setFilters({ hasFullText: true });
    setArtifactKinds([...kinds]);
    setBatchLimit(25);
    setFieldErrors({});
    setSaveMessage("");
  };

  const save = useMutation({
    mutationFn: async () => {
      const filterBody: Record<string, unknown> = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value !== ""),
      );
      for (const yearKey of ["yearFrom", "yearTo"]) {
        if (typeof filterBody[yearKey] === "string") filterBody[yearKey] = Number(filterBody[yearKey]);
      }
      filterBody.hasFullText = filters.hasFullText !== false;
      const body = {
        name,
        source: "slr" as const,
        is_active: true,
        filters: filterBody,
        artifact_kinds: artifactKinds,
        batch_limit: batchLimit,
      };
      const response = selected
        ? await api.PATCH("/v1/admin/corpus/import-profiles/{profile_id}", {
            params: { path: { profile_id: selected } },
            body: { name, filters: filterBody, artifact_kinds: artifactKinds, batch_limit: batchLimit } as never,
          })
        : await api.POST("/v1/admin/corpus/import-profiles", { body: body as never });
      return unwrap(response);
    },
    onSuccess: (created) => {
      setFieldErrors({});
      setSaveMessage("Import profile saved.");
      if (!selected && created?.id) setSelected(created.id);
      void queryClient.invalidateQueries({ queryKey: ["slr-import-profiles"] });
    },
    onError: (error) => {
      const details = error instanceof ApiError ? error.body?.error?.details?.errors : undefined;
      const mapped: Record<string, string> = {};
      for (const item of details ?? []) mapped[String(item.loc.at(-1) ?? "form")] = item.msg;
      setFieldErrors(mapped);
      setSaveMessage(details ? "Check the fields marked below." : error.message);
    },
  });

  const start = useMutation({
    mutationFn: async () => {
      const response = await api.POST("/v1/admin/corpus/imports", { body: { profile_id: selected } });
      return unwrap(response)?.job_id;
    },
    onSuccess: (id) => {
      setStartError("");
      if (id) setJobId(id);
    },
    onError: (error) => {
      setStartError(error.message || "The import job could not be started. Try again.");
    },
  });

  const job = useQuery({
    queryKey: ["slr-job", jobId],
    enabled: Boolean(jobId),
    refetchInterval: (query) =>
      ["done", "failed", "succeeded"].includes(query.state.data?.status ?? "") ? false : 2500,
    queryFn: async () => {
      const data = unwrap(await api.GET("/v1/admin/jobs/{job_id}", { params: { path: { job_id: jobId! } } }));
      return data as { status: string; error?: string; result?: JobResult };
    },
  });

  const setFilter = (fieldName: string, value: string | boolean) =>
    setFilters((old) => {
      const next = { ...old, [fieldName]: value };
      if (fieldName === "domainId") {
        delete next.fieldId;
        delete next.subfieldId;
        delete next.topicId;
      }
      if (fieldName === "fieldId") {
        delete next.subfieldId;
        delete next.topicId;
      }
      if (fieldName === "subfieldId") delete next.topicId;
      return next;
    });

  const moveKind = (index: number, by: number) =>
    setArtifactKinds((old) => {
      const next = [...old];
      const target = index + by;
      if (target < 0 || target >= next.length) return old;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });

  const pdfFirst = artifactKinds[0] === "SOURCE_PDF" && artifactKinds.some((kind) => kind.includes("MARKDOWN"));
  const result = job.data?.result;
  const jobStatus = job.data?.status ?? "queued";
  const listed = result?.listed ?? 0;
  const imported = result?.imported ?? 0;
  const skipped =
    (result?.skipped_license ?? 0) +
    (result?.skipped_duplicate ?? 0) +
    (result?.skipped_format ?? 0) +
    (result?.skipped_invalid_content ?? 0);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="SLR import"
        description="Configure source filters, save a profile, and monitor each import job to completion."
      />
      <div
        className={cn(
          "mx-auto grid w-full max-w-[1152px]",
          "grid-cols-[minmax(0,450px)_minmax(0,700px)] items-start gap-x-8 gap-y-8",
        )}
      >
        <SettingsLabel
          title="API access"
          description={
            "The corpus endpoints use the key stored for this browser session. " + "It is never rendered back as text."
          }
        />
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Corpus API key</CardTitle>
            <CardDescription>Use a curator or admin key for SLR profiles and import jobs.</CardDescription>
          </CardHeader>
          <CardContent>
            <Field>
              <FieldLabel htmlFor="slr-api-key">X-API-Key</FieldLabel>
              <Input
                id="slr-api-key"
                type="password"
                value={key}
                onChange={(event) => setKey(event.target.value)}
                autoComplete="off"
                placeholder="Paste a curator or admin key"
              />
              <FieldDescription>
                {hasSavedKey ? "A key is stored for this session." : "No key is stored for this session."}
              </FieldDescription>
            </Field>
          </CardContent>
          <CardFooter className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={handleSaveKey} disabled={!key.trim()}>
              Save session key
            </Button>
            {hasSavedKey ? (
              <Button type="button" variant="ghost" onClick={handleClearKey}>
                Clear key
              </Button>
            ) : null}
          </CardFooter>
        </Card>

        <Separator className="col-span-2" />

        <SettingsLabel
          title="Import profile"
          description={
            "Choose a saved SLR profile or start a new one. " +
            "The profile name and batch limit stay visible beside the editor."
          }
        />
        <Card className="shadow-none">
          <CardHeader className="flex-row items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <CardTitle>Saved profiles</CardTitle>
              <CardDescription>{profiles.data?.length ?? 0} profiles available</CardDescription>
            </div>
            <Button type="button" variant="outline" onClick={handleCreateNew}>
              New profile
            </Button>
          </CardHeader>
          <CardContent>
            {profiles.isPending ? (
              <DataState state="loading" loadingLabel="Loading import profiles" />
            ) : profiles.isError ? (
              <DataState
                state="error"
                errorTitle="Profiles unavailable"
                errorDescription={profiles.error.message}
                onRetry={() => void profiles.refetch()}
              />
            ) : profiles.data.length === 0 ? (
              <DataState
                state="empty"
                emptyTitle="No import profiles yet"
                emptyDescription="Create a profile to save its source filters and artifact order."
                emptyAction={
                  <Button type="button" variant="outline" onClick={handleCreateNew}>
                    Create profile
                  </Button>
                }
              />
            ) : (
              <div className="flex flex-col gap-2">
                {profiles.data.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={cn(
                      "flex w-full flex-col gap-1 rounded-[var(--radius)] border p-3 text-left",
                      "transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-foreground",
                      selected === item.id ? "border-foreground bg-muted" : "border-border",
                    )}
                    aria-pressed={selected === item.id}
                    onClick={() => handleSelectProfile(item)}
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className="font-medium">{item.name}</span>
                      <StatusBadge status={item.is_active ? "active" : "inactive"} />
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {item.batch_limit} articles per run · {item.artifact_kinds?.length ?? 0} formats
                    </span>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Separator className="col-span-2" />

        <SettingsLabel
          title={selected ? "Edit profile" : "Create profile"}
          description={
            "The profile defines which articles can enter the corpus and " +
            "in which artifact formats they are stored."
          }
        />
        <form
          className="min-w-0"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{selected ? `Edit ${name || "unnamed profile"}` : "New import profile"}</CardTitle>
              {selected ? <CardDescription>ID {selected.slice(0, 8)}</CardDescription> : null}
            </CardHeader>
            <CardContent>
              <FieldGroup>
                <Field data-invalid={Boolean(fieldErrors.name)}>
                  <FieldLabel htmlFor="profile-name">Profile name</FieldLabel>
                  <Input
                    id="profile-name"
                    required
                    value={name}
                    placeholder="Methods review 2020–2026"
                    aria-invalid={Boolean(fieldErrors.name)}
                    onChange={(event) => setName(event.target.value)}
                  />
                  <FieldError>{fieldErrors.name}</FieldError>
                </Field>
                <FieldGroup>
                  <div className="flex flex-col gap-1">
                    <h2 className="text-base font-medium">SLR taxonomy</h2>
                    <p className="text-sm text-muted-foreground">
                      Child selectors become available after their parent is chosen.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {taxonomyLevels.map((level, index) => {
                      const fieldName = taxonFields[level];
                      const query = taxonomyQueries[index];
                      const items = query.data?.pages.flatMap((page) => page.items) ?? [];
                      const parent = index > 0 ? taxonFields[taxonomyLevels[index - 1]] : undefined;
                      const disabled = Boolean(parent && !filters[parent]);
                      return (
                        <Field key={level} data-disabled={disabled}>
                          <FieldLabel htmlFor={`taxonomy-${level}`}>{taxonomyLabels[level]}</FieldLabel>
                          <Select
                            value={String(filters[fieldName] ?? "") || "all"}
                            onValueChange={(value) => setFilter(fieldName, value === "all" ? "" : value)}
                            disabled={disabled}
                          >
                            <SelectTrigger id={`taxonomy-${level}`}>
                              <SelectValue placeholder={`All ${level}s`} />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectGroup>
                                <SelectItem value="all">All {level}s</SelectItem>
                                {items.map((item) => (
                                  <SelectItem key={item.id} value={item.id}>
                                    {item.label}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                          {query.hasNextPage ? (
                            <Button
                              type="button"
                              variant="link"
                              size="sm"
                              className="w-fit px-0"
                              disabled={query.isFetchingNextPage}
                              onClick={() => void query.fetchNextPage()}
                            >
                              {query.isFetchingNextPage ? "Loading more…" : `Load more ${level}s`}
                            </Button>
                          ) : null}
                        </Field>
                      );
                    })}
                  </div>
                </FieldGroup>
                <FieldGroup>
                  <div className="flex flex-col gap-1">
                    <h2 className="text-base font-medium">Article filters</h2>
                    <p className="text-sm text-muted-foreground">Keep the source query explicit for auditability.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field data-invalid={Boolean(fieldErrors.yearFrom)}>
                      <FieldLabel htmlFor="year-from">Published from</FieldLabel>
                      <Input
                        id="year-from"
                        type="number"
                        placeholder="2020"
                        value={String(filters.yearFrom ?? "")}
                        aria-invalid={Boolean(fieldErrors.yearFrom)}
                        onChange={(event) => setFilter("yearFrom", event.target.value)}
                      />
                      <FieldError>{fieldErrors.yearFrom}</FieldError>
                    </Field>
                    <Field data-invalid={Boolean(fieldErrors.yearTo)}>
                      <FieldLabel htmlFor="year-to">Published to</FieldLabel>
                      <Input
                        id="year-to"
                        type="number"
                        placeholder="2026"
                        value={String(filters.yearTo ?? "")}
                        aria-invalid={Boolean(fieldErrors.yearTo)}
                        onChange={(event) => setFilter("yearTo", event.target.value)}
                      />
                      <FieldError>{fieldErrors.yearTo}</FieldError>
                    </Field>
                    <Field data-invalid={Boolean(fieldErrors.language)}>
                      <FieldLabel htmlFor="language">Language</FieldLabel>
                      <Input
                        id="language"
                        placeholder="en"
                        value={String(filters.language ?? "")}
                        aria-invalid={Boolean(fieldErrors.language)}
                        onChange={(event) => setFilter("language", event.target.value)}
                      />
                      <FieldDescription>ISO code, such as en or vi.</FieldDescription>
                      <FieldError>{fieldErrors.language}</FieldError>
                    </Field>
                    <Field data-invalid={Boolean(fieldErrors.publicationType)}>
                      <FieldLabel htmlFor="publication-type">Publication type</FieldLabel>
                      <Input
                        id="publication-type"
                        placeholder="journal-article"
                        value={String(filters.publicationType ?? "")}
                        aria-invalid={Boolean(fieldErrors.publicationType)}
                        onChange={(event) => setFilter("publicationType", event.target.value)}
                      />
                      <FieldError>{fieldErrors.publicationType}</FieldError>
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field>
                      <FieldLabel htmlFor="batch-limit">Articles per run</FieldLabel>
                      <Input
                        id="batch-limit"
                        type="number"
                        min={1}
                        max={100}
                        value={batchLimit}
                        onChange={(event) => setBatchLimit(Number(event.target.value))}
                      />
                      <FieldDescription>Between 1 and 100 articles.</FieldDescription>
                    </Field>
                    <Field orientation="horizontal" className="items-start pt-7">
                      <Checkbox
                        id="has-full-text"
                        checked={filters.hasFullText !== false}
                        onCheckedChange={(checked) => setFilter("hasFullText", checked === true)}
                      />
                      <div className="flex flex-col gap-1">
                        <FieldLabel htmlFor="has-full-text">Full text required</FieldLabel>
                        <FieldDescription>Skip records that contain only abstracts or metadata.</FieldDescription>
                      </div>
                    </Field>
                  </div>
                </FieldGroup>
                <FieldGroup>
                  <div className="flex flex-col gap-1">
                    <h2 className="text-base font-medium">Artifact order</h2>
                    <p className="text-sm text-muted-foreground">The first enabled format has the highest priority.</p>
                  </div>
                  <div className="flex flex-col gap-2">
                    {artifactKinds.map((kind, index) => (
                      <ArtifactKindRow
                        key={kind}
                        kind={kind}
                        index={index}
                        total={artifactKinds.length}
                        enabled
                        onToggle={() => setArtifactKinds((old) => old.filter((item) => item !== kind))}
                        onMove={(by) => moveKind(index, by)}
                      />
                    ))}
                    {kinds
                      .filter((kind) => !artifactKinds.includes(kind))
                      .map((kind) => (
                        <ArtifactKindRow
                          key={kind}
                          kind={kind}
                          index={0}
                          total={1}
                          enabled={false}
                          onToggle={() => setArtifactKinds((old) => [...old, kind])}
                          onMove={() => undefined}
                        />
                      ))}
                  </div>
                </FieldGroup>
              </FieldGroup>
              {pdfFirst ? (
                <Alert className="mt-6">
                  <AlertTitle>PDF parser limitation</AlertTitle>
                  <AlertDescription>
                    PDF records can be stored, but mining waits until a parser is available. Put Markdown first when
                    possible.
                  </AlertDescription>
                </Alert>
              ) : null}
              {saveMessage ? (
                <p
                  className={`mt-4 text-sm ${save.isError ? "text-destructive" : "text-muted-foreground"}`}
                  role="status"
                >
                  {saveMessage}
                </p>
              ) : null}
            </CardContent>
            <CardFooter className="flex flex-wrap gap-2">
              <Button type="submit" variant="outline" disabled={save.isPending || !name.trim()}>
                {save.isPending ? "Saving profile…" : selected ? "Update profile" : "Save profile"}
              </Button>
              {selected ? (
                <Button type="button" variant="ghost" onClick={handleCreateNew}>
                  Create another
                </Button>
              ) : null}
            </CardFooter>
          </Card>
        </form>

        <Separator className="col-span-2" />

        <SettingsLabel
          title="Import progress"
          description={
            "A job reports its state, counts, and skip reasons in words and numbers. " +
            "There is no indefinite spinner."
          }
        />
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Run an import</CardTitle>
            <CardDescription>{selected ? (profile?.name ?? name) : "Choose a profile to begin."}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {!selected ? (
              <DataState
                state="empty"
                emptyTitle="No profile selected"
                emptyDescription="Choose a saved profile or create one above before starting an import."
              />
            ) : (
              <>
                <div
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-3",
                    "rounded-[var(--radius)] bg-muted/50 p-4",
                  )}
                >
                  <div className="flex flex-col gap-1">
                    <span className="font-medium">{profile?.name ?? name}</span>
                    <span className="text-sm text-muted-foreground">
                      {batchLimit} articles per run · {artifactKinds.length} enabled formats
                    </span>
                  </div>
                  <StatusBadge status={profile?.is_active ? "active" : "inactive"} />
                </div>
                <Button
                  type="button"
                  className="w-fit"
                  disabled={!profile?.is_active || start.isPending}
                  onClick={() => start.mutate()}
                >
                  {start.isPending ? "Starting import…" : "Start import"}
                </Button>
                {!profile?.is_active ? (
                  <p className="text-sm text-muted-foreground">This profile is inactive and cannot start a job.</p>
                ) : null}
              </>
            )}
            {startError ? (
              <Alert variant="destructive">
                <AlertTitle>Import could not start</AlertTitle>
                <AlertDescription>{startError}</AlertDescription>
              </Alert>
            ) : null}
            {jobId ? (
              <JobProgress
                job={job}
                jobStatus={jobStatus}
                listed={listed}
                imported={imported}
                skipped={skipped}
                result={result}
                setJobId={setJobId}
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SettingsLabel({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col gap-2 pt-2">
      <h2 className="text-base font-medium">{title}</h2>
      <p className="max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}

function ArtifactKindRow({
  kind,
  index,
  total,
  enabled,
  onToggle,
  onMove,
}: {
  kind: Kind;
  index: number;
  total: number;
  enabled: boolean;
  onToggle: () => void;
  onMove: (by: number) => void;
}) {
  const label = kind.replaceAll("_", " ");
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius)] border border-border p-3">
      <div className="flex min-w-0 items-center gap-3">
        <Checkbox
          checked={enabled}
          onCheckedChange={onToggle}
          aria-label={`${enabled ? "Disable" : "Enable"} ${label}`}
        />
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate font-medium">{label}</span>
          <span className="text-sm text-muted-foreground">{enabled ? `Priority ${index + 1}` : "Disabled"}</span>
        </div>
      </div>
      {enabled ? (
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Move ${label} up`}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            ↑
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Move ${label} down`}
            disabled={index === total - 1}
            onClick={() => onMove(1)}
          >
            ↓
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function JobProgress({
  job,
  jobStatus,
  listed,
  imported,
  skipped,
  result,
  setJobId,
}: {
  job: ReturnType<typeof useQuery<{ status: string; error?: string; result?: JobResult }>>;
  jobStatus: string;
  listed: number;
  imported: number;
  skipped: number;
  result: JobResult | undefined;
  setJobId: (id: string) => void;
}) {
  return (
    <div className="flex flex-col gap-5 border-t border-border pt-5" aria-live="polite">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="font-medium">Import job</span>
          <span className="text-xs text-muted-foreground">
            {job.data ? "Job status received" : "Waiting for first status update"}
          </span>
        </div>
        <StatusBadge status={jobStatus} />
      </div>
      <p className="text-sm text-muted-foreground">{jobLabels[jobStatus] ?? `Status: ${jobStatus}`}</p>
      {job.isPending ? <DataState state="loading" loadingLabel="Checking import progress" /> : null}
      {job.isError ? (
        <DataState
          state="error"
          errorTitle="Progress unavailable"
          errorDescription={job.error.message}
          onRetry={() => void job.refetch()}
        />
      ) : null}
      {job.data?.error ? (
        <Alert variant="destructive">
          <AlertTitle>Import stopped</AlertTitle>
          <AlertDescription>{job.data.error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="grid grid-cols-3 divide-x divide-border rounded-[var(--radius)] border border-border">
        <Metric label="Listed" value={listed} />
        <Metric label="Imported" value={imported} />
        <Metric label="Skipped" value={skipped} />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Skip reason</TableHead>
            <TableHead numeric>Articles</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Licence</TableCell>
            <TableCell numeric>{result?.skipped_license ?? 0}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Duplicate</TableCell>
            <TableCell numeric>{result?.skipped_duplicate ?? 0}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Format</TableCell>
            <TableCell numeric>{result?.skipped_format ?? 0}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Invalid content</TableCell>
            <TableCell numeric>{result?.skipped_invalid_content ?? 0}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      {result?.batch_id && imported > 0 && ["done", "succeeded"].includes(jobStatus) ? (
        <Button asChild variant="outline" className="w-fit">
          <Link to="/extract" search={{ batch: result.batch_id }}>
            Review phrases from this batch
          </Link>
        </Button>
      ) : null}
      {result?.continuation_job_id ? (
        <Button type="button" variant="outline" className="w-fit" onClick={() => setJobId(result.continuation_job_id!)}>
          Follow continuation job
        </Button>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex min-h-20 flex-col justify-center gap-1 px-4 py-3 first:pl-5 last:pr-5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <strong className="text-2xl font-medium tabular-nums">{value}</strong>
    </div>
  );
}
