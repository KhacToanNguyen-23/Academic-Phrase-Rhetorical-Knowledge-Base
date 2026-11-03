import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, slrImportClient, unwrap } from "@/features/slr-import/api/client";
import { ArticleCard } from "./ArticleCard";
import { PhraseCard } from "./PhraseCard";
import {
  NO_BATCH,
  PAGE_SIZE,
  batchToken,
  toScope,
  type ArticleRow,
  type Batch,
  type PhrasePage,
  type PhraseStatus,
} from "./types";

type Notice = { tone: "ok" | "bad"; text: string };

const MINING_IN_PROGRESS = ["queued", "processing"];

function formatImportedAt(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function errorText(error: unknown) {
  return error instanceof ApiError || error instanceof Error ? error.message : "The request failed.";
}

export function ExtractPage({ initialBatch }: { initialBatch?: string }) {
  const api = slrImportClient();
  const queryClient = useQueryClient();
  const auth = useAuth();
  const canMine = auth.client?.role === "curator" || auth.client?.role === "admin";
  const [picked, setPicked] = useState<string[] | null>(initialBatch ? initialBatch.split(",").filter(Boolean) : null);
  const [status, setStatus] = useState<PhraseStatus>("pending");
  const [articleFilter, setArticleFilter] = useState<string>();
  const [articleSearch, setArticleSearch] = useState("");
  const [miningFilter, setMiningFilter] = useState("all");
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [offset, setOffset] = useState(0);
  const [notice, setNotice] = useState<Notice>();

  const batches = useQuery({
    queryKey: ["extract-batches"],
    queryFn: async (): Promise<Batch[]> => (unwrap(await api.GET("/v1/admin/corpus/batches")) ?? []) as Batch[],
  });
  const selected = picked ?? (batches.data?.[0] ? [batchToken(batches.data[0])] : []);
  const scope = toScope(selected);
  const articles = useQuery({
    queryKey: ["extract-articles", selected],
    enabled: selected.length > 0,
    refetchInterval: (query) =>
      query.state.data?.some((article) => MINING_IN_PROGRESS.includes(article.mining_status)) ? 3000 : false,
    queryFn: async (): Promise<ArticleRow[]> =>
      (unwrap(await api.GET("/v1/admin/corpus/articles", { params: { query: scope } })) ?? []) as ArticleRow[],
  });
  const inProgress = articles.data?.some((article) => MINING_IN_PROGRESS.includes(article.mining_status)) ?? false;
  const phraseScope = articleFilter ? { article_id: [articleFilter], batch_id: [], unbatched: false } : scope;
  const phrases = useQuery({
    queryKey: ["extract-phrases", status, selected, articleFilter, offset],
    enabled: selected.length > 0,
    refetchInterval: inProgress ? 4000 : false,
    queryFn: async (): Promise<PhrasePage> =>
      unwrap(
        await api.GET("/v1/admin/extraction/phrases", {
          params: { query: { status, limit: PAGE_SIZE, offset, ...phraseScope } },
        }),
      ) as PhrasePage,
  });

  const refresh = () => {
    for (const key of ["extract-batches", "extract-articles", "extract-phrases"]) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
  const wasInProgress = useRef(false);

  useEffect(() => {
    if (wasInProgress.current && !inProgress) {
      void queryClient.invalidateQueries({ queryKey: ["extract-batches"] });
      void queryClient.invalidateQueries({ queryKey: ["extract-phrases"] });
    }
    wasInProgress.current = inProgress;
  }, [inProgress, queryClient]);

  const mine = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/v1/admin/corpus/mine", {
          body: { article_ids: [], batch_ids: scope.batch_id, unbatched: scope.unbatched },
        }),
      ),
    onSuccess: (result) => {
      setNotice({
        tone: "ok",
        text: `Queued ${result?.job_ids.length ?? 0} article(s) for extraction${
          result?.skipped_not_ready ? `; skipped ${result.skipped_not_ready} not ready` : ""
        }.`,
      });
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });
  const decide = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "accept" | "reject" }) =>
      unwrap(
        await api.POST("/v1/admin/extraction/phrases/{candidate_id}/decision", {
          params: { path: { candidate_id: id } },
          body: { decision },
        }),
      ),
    onSuccess: (_, { decision }) => {
      setNotice({
        tone: "ok",
        text: decision === "accept" ? "Phrase accepted and saved." : "Phrase rejected.",
      });
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });
  const decideMany = useMutation({
    mutationFn: async (decision: "accept" | "reject") =>
      unwrap(
        await api.POST("/v1/admin/extraction/phrases/decisions", {
          body: { candidate_ids: [...checked], decision },
        }),
      ),
    onSuccess: (result) => {
      const failed = result?.failed.length ?? 0;
      setNotice({
        tone: failed ? "bad" : "ok",
        text: `${result?.results.length ?? 0} phrase(s) processed${
          failed ? `; ${failed} failed: ${result.failed[0].reason}` : ""
        }.`,
      });
      setChecked(new Set());
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });

  const chosenBatches = batches.data?.filter((batch) => selected.includes(batchToken(batch))) ?? [];
  const sum = (pick: (batch: Batch) => number) => chosenBatches.reduce((total, batch) => total + pick(batch), 0);
  const counts = {
    pending: sum((batch) => batch.phrases.pending),
    accepted: sum((batch) => batch.phrases.accepted),
    rejected: sum((batch) => batch.phrases.rejected),
  };
  const ready = articles.data?.filter((article) => article.ingest_status === "ready") ?? [];
  const mineable = ready.filter(
    (article) => article.mining_status === "not_started" || article.mining_status === "failed",
  ).length;
  const phrasesFirst = ready.length > 0 && ready.every((article) => article.mining_status === "succeeded");
  const items = phrases.data?.items ?? [];
  const total = phrases.data?.total ?? 0;
  const sourceSentenceIds = new Set(items.flatMap((phrase) => phrase.sources.map((source) => source.sentence_id)));
  const busy = decide.isPending || decideMany.isPending;
  const filteredArticles = useMemo(() => {
    if (!articles.data) return [];
    return articles.data.filter((article) => {
      const query = articleSearch.trim().toLowerCase();
      const title = (article.title ?? "").toLowerCase();
      const doi = (article.doi ?? "").toLowerCase();
      if (query && !title.includes(query) && !doi.includes(query)) return false;
      if (miningFilter === "not_started" && article.mining_status !== "not_started") return false;
      if (miningFilter === "running" && !MINING_IN_PROGRESS.includes(article.mining_status)) return false;
      if (miningFilter === "succeeded" && article.mining_status !== "succeeded") return false;
      if (miningFilter === "failed" && article.mining_status !== "failed") return false;
      return true;
    });
  }, [articles.data, articleSearch, miningFilter]);
  const changeScope = (next: string[]) => {
    setPicked(next);
    setArticleFilter(undefined);
    setArticleSearch("");
    setMiningFilter("all");
    setChecked(new Set());
    setOffset(0);
  };
  const toggleBatch = (token: string) => {
    changeScope(selected.includes(token) ? selected.filter((value) => value !== token) : [...selected, token]);
  };
  const toggle = (set: Set<string>, id: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(id);
    else next.delete(id);
    return next;
  };
  const changeStatus = (next: PhraseStatus) => {
    setStatus(next);
    setChecked(new Set());
    setOffset(0);
  };
  const allChecked = items.length > 0 && items.every((phrase) => checked.has(phrase.id));
  const checkState = checked.size > 0 && !allChecked ? "indeterminate" : allChecked;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Phrase extraction"
        description={
          "Choose imported batches, extract candidate phrases, and review their source evidence before " + "saving."
        }
      />
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Imported batches</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Select one or more batches for the next mining job.</p>
          </div>
          <Button
            variant="outline"
            disabled={!canMine || mine.isPending || mineable === 0}
            title={canMine ? undefined : "Curator access is required to extract phrases"}
            onClick={() => mine.mutate()}
          >
            {mine.isPending ? "Queueing extraction..." : `Extract ${mineable} article(s)`}
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {batches.isPending ? (
            <DataState state="loading" loadingLabel="Loading imported batches" />
          ) : batches.isError ? (
            <DataState
              state="error"
              errorTitle="Could not load imported batches"
              errorDescription={batches.error.message}
              onRetry={() => void batches.refetch()}
            />
          ) : batches.data.length === 0 ? (
            <DataState
              state="empty"
              emptyTitle="No imported batches"
              emptyDescription="Import articles before starting phrase extraction."
            />
          ) : (
            <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0">
              {batches.data.map((batch) => {
                const token = batchToken(batch);
                return (
                  <li key={token}>
                    <Label
                      htmlFor={`batch-${token}`}
                      className={
                        "flex h-full items-start gap-3 rounded-[var(--radius)] border border-border p-3 " +
                        "hover:bg-muted/50"
                      }
                    >
                      <Checkbox
                        id={`batch-${token}`}
                        checked={selected.includes(token)}
                        onCheckedChange={() => toggleBatch(token)}
                      />
                      <span className="flex min-w-0 flex-col gap-1">
                        <strong className="font-medium">
                          {batch.batch_id === null
                            ? "Unbatched articles"
                            : `Imported ${formatImportedAt(batch.imported_at)}`}
                        </strong>
                        <span className="text-sm text-muted-foreground">
                          {batch.articles} articles · {batch.ready} ready · {batch.mined} extracted ·{" "}
                          {batch.phrases.pending} pending phrases
                        </span>
                      </span>
                    </Label>
                  </li>
                );
              })}
            </ul>
          )}
          {notice ? (
            <Alert variant={notice.tone === "bad" ? "destructive" : undefined}>
              <AlertTitle>{notice.tone === "bad" ? "Extraction needs attention" : "Extraction updated"}</AlertTitle>
              <AlertDescription>{notice.text}</AlertDescription>
            </Alert>
          ) : null}
          {inProgress ? (
            <p className="text-sm text-muted-foreground">
              Extraction is running. Phrases will appear when the worker finishes the queued articles.
            </p>
          ) : null}
          {selected.includes(NO_BATCH) ? (
            <p className="text-sm text-muted-foreground">
              Unbatched articles were uploaded manually or imported before batch tracking was available.
            </p>
          ) : null}
        </CardContent>
      </Card>

      {selected.length > 0 ? (
        <>
          <div className="grid grid-cols-4 divide-x divide-border rounded-[var(--radius)] border border-border bg-card">
            <Metric
              label="Articles selected"
              value={sum((batch) => batch.articles)}
              note={`${sum((batch) => batch.ready)} ready`}
            />
            <Metric label="Articles extracted" value={sum((batch) => batch.mined)} note="Completed mining" />
            <Metric label="Phrases pending" value={counts.pending} note="Awaiting review" />
            <Metric label="Phrases accepted" value={counts.accepted} note="Saved decisions" />
          </div>
          <div
            className={`grid min-w-0 items-start gap-6 ${
              phrasesFirst ? "grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" : "grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]"
            }`}
          >
            <Card className={phrasesFirst ? "order-last min-w-0" : "min-w-0"}>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle>Articles</CardTitle>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {filteredArticles.length} shown · {ready.length} ready
                    </p>
                  </div>
                  {articleFilter ? (
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">One article filtered</Badge>
                      <Button variant="ghost" size="sm" onClick={() => setArticleFilter(undefined)}>
                        Show all articles
                      </Button>
                    </div>
                  ) : null}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Input
                    type="search"
                    placeholder="Search title or DOI"
                    value={articleSearch}
                    onChange={(event) => setArticleSearch(event.target.value)}
                    aria-label="Search articles"
                  />
                  <Select value={miningFilter} onValueChange={setMiningFilter}>
                    <SelectTrigger className="w-40" aria-label="Filter mining status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="all">All mining states</SelectItem>
                        <SelectItem value="not_started">Not started</SelectItem>
                        <SelectItem value="running">Running</SelectItem>
                        <SelectItem value="succeeded">Succeeded</SelectItem>
                        <SelectItem value="failed">Failed</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {articles.isPending ? (
                  <DataState state="loading" loadingLabel="Loading articles" />
                ) : articles.isError ? (
                  <DataState
                    state="error"
                    errorTitle="Could not load articles"
                    errorDescription={articles.error.message}
                    onRetry={() => void articles.refetch()}
                  />
                ) : articles.data.length === 0 ? (
                  <DataState
                    state="empty"
                    emptyTitle="No articles in this scope"
                    emptyDescription="Choose another batch to inspect its article queue."
                  />
                ) : filteredArticles.length === 0 ? (
                  <DataState
                    state="empty"
                    emptyTitle="No articles match"
                    emptyDescription="Try a different title, DOI, or mining status."
                  />
                ) : (
                  filteredArticles.map((article) => (
                    <ArticleCard
                      key={article.id}
                      article={article}
                      open={openIds.has(article.id)}
                      filtered={articleFilter === article.id}
                      sourceSentenceIds={sourceSentenceIds}
                      onToggle={() => setOpenIds((old) => toggle(old, article.id, !old.has(article.id)))}
                      onFilter={() => {
                        setArticleFilter(articleFilter === article.id ? undefined : article.id);
                        setChecked(new Set());
                        setOffset(0);
                      }}
                    />
                  ))
                )}
              </CardContent>
            </Card>

            <Card className={phrasesFirst ? "order-first min-w-0" : "min-w-0"}>
              <CardHeader>
                <CardTitle>Phrase candidates</CardTitle>
                <Tabs value={status} onValueChange={(value) => changeStatus(value as PhraseStatus)}>
                  <TabsList className="mt-3">
                    <TabsTrigger value="pending">
                      Pending <Badge variant="secondary">{counts.pending}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="accepted">
                      Accepted <Badge variant="secondary">{counts.accepted}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="rejected">
                      Rejected <Badge variant="secondary">{counts.rejected}</Badge>
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value={status} className="pt-3">
                    {status === "pending" && items.length > 0 ? (
                      <div
                        className={
                          "flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border " +
                          "border-border bg-muted/30 p-3"
                        }
                      >
                        <div className="flex items-center gap-3">
                          <Checkbox
                            id="select-all-phrases"
                            checked={checkState}
                            onCheckedChange={(value) =>
                              setChecked(value === true ? new Set(items.map((phrase) => phrase.id)) : new Set())
                            }
                          />
                          <Label htmlFor="select-all-phrases">Select all {items.length} on this page</Label>
                          {checked.size > 0 ? (
                            <Button variant="link" size="sm" onClick={() => setChecked(new Set())}>
                              Clear selection
                            </Button>
                          ) : null}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy || checked.size === 0}
                            onClick={() => decideMany.mutate("reject")}
                          >
                            Reject {checked.size ? `(${checked.size})` : ""}
                          </Button>
                          <Button
                            size="sm"
                            disabled={busy || checked.size === 0}
                            onClick={() => decideMany.mutate("accept")}
                          >
                            Accept {checked.size ? `(${checked.size})` : ""}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        {items.length === 0 ? "No phrases in this view." : `Showing ${items.length} ${status} phrases.`}
                      </p>
                    )}
                  </TabsContent>
                </Tabs>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {phrases.isPending ? (
                  <DataState state="loading" loadingLabel="Loading phrase candidates" />
                ) : phrases.isError ? (
                  <DataState
                    state="error"
                    errorTitle="Could not load phrase candidates"
                    errorDescription={phrases.error.message}
                    onRetry={() => void phrases.refetch()}
                  />
                ) : items.length === 0 ? (
                  <DataState
                    state="empty"
                    emptyTitle={inProgress ? "Extraction is still running" : "No phrase candidates"}
                    emptyDescription={
                      inProgress
                        ? "Candidates will appear when the worker finishes."
                        : "Try another batch or phrase status."
                    }
                  />
                ) : (
                  items.map((phrase) => (
                    <PhraseCard
                      key={phrase.id}
                      phrase={phrase}
                      checked={checked.has(phrase.id)}
                      busy={busy}
                      onCheck={(on) => setChecked((old) => toggle(old, phrase.id, on))}
                      onDecide={(decision) => decide.mutate({ id: phrase.id, decision })}
                    />
                  ))
                )}
                {total > PAGE_SIZE ? (
                  <div className="flex items-center justify-between gap-3 border-t border-border pt-3 text-sm">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    >
                      Previous page
                    </Button>
                    <span className="tabular-nums text-muted-foreground">
                      {offset + 1}–{offset + items.length} of {total}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset + PAGE_SIZE >= total}
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                    >
                      Next page
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Metric({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <div className="flex min-h-24 flex-col justify-center gap-1 px-4 py-3 first:pl-5 last:pr-5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <strong className="text-2xl font-medium tabular-nums">{value}</strong>
      <span className="text-xs text-muted-foreground">{note}</span>
    </div>
  );
}
