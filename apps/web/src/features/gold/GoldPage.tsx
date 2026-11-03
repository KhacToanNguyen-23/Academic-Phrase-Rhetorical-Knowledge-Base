import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { ApiError, unwrap } from "@/features/slr-import/api/client";
import { goldClient } from "./api";

type GoldItem = {
  id: string;
  sample_batch: string;
  split: string;
  section: string;
  status: string;
  ai_labels: Record<string, unknown> | null;
  final_labels: Record<string, unknown> | null;
};

type GoldDetail = GoldItem & {
  text: string;
  previous_text: string | null;
  next_text: string | null;
  section_heading: string | null;
};

type GoldStats = {
  total: number;
  by_status: Record<string, number>;
  by_split: Record<string, number>;
  field_edits: Record<string, number>;
};

const statusOptions = [
  { value: "draft", label: "AI draft" },
  { value: "pending_ai", label: "Pending AI" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "label_failed", label: "Label failed" },
];

export function GoldPage() {
  const client = goldClient();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("draft");
  const [split, setSplit] = useState("");
  const [section, setSection] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string>();
  const [labelsJson, setLabelsJson] = useState("");
  const [message, setMessage] = useState<string>();
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const items = useQuery({
    queryKey: ["gold-items", status, split, section, offset],
    refetchInterval: status === "pending_ai" ? 2500 : false,
    queryFn: async (): Promise<GoldItem[]> => {
      const data = unwrap(
        await client.GET("/v1/admin/gold/items", {
          params: {
            query: {
              status: status || undefined,
              split: split || undefined,
              section: section || undefined,
              offset,
              limit: 100,
            },
          },
        }),
      );
      return (data ?? []) as unknown as GoldItem[];
    },
  });
  const stats = useQuery({
    queryKey: ["gold-stats"],
    queryFn: async (): Promise<GoldStats> => unwrap(await client.GET("/v1/admin/gold/stats")) as unknown as GoldStats,
  });
  const detail = useQuery({
    queryKey: ["gold-item", selected],
    enabled: Boolean(selected),
    queryFn: async (): Promise<GoldDetail> =>
      unwrap(
        await client.GET("/v1/admin/gold/items/{item_id}", {
          params: { path: { item_id: selected! } },
        }),
      ) as unknown as GoldDetail,
  });
  const current = detail.data;

  useEffect(() => {
    setLabelsJson(current?.ai_labels ? JSON.stringify(current.ai_labels, null, 2) : "");
  }, [current]);

  const review = useMutation({
    mutationFn: async ({ decision, useAiDraft }: { decision: "approve" | "reject"; useAiDraft?: boolean }) => {
      let finalLabels: Record<string, unknown> | undefined;
      if (decision === "approve" && !useAiDraft && labelsJson.trim()) {
        const parsed: unknown = JSON.parse(labelsJson);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("Labels must be a JSON object.");
        }
        finalLabels = parsed as Record<string, unknown>;
      }
      return unwrap(
        await client.POST("/v1/admin/gold/items/{item_id}/review", {
          params: { path: { item_id: selected! } },
          body: { decision, final_labels: finalLabels } as never,
        }),
      );
    },
    onSuccess: () => {
      setMessage("Gold decision saved.");
      void queryClient.invalidateQueries({ queryKey: ["gold-items"] });
      void queryClient.invalidateQueries({ queryKey: ["gold-stats"] });
      setSelected(undefined);
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : error.message || "The decision could not be saved.");
    },
  });
  const labelBatch = useMutation({
    mutationFn: async (sampleBatch: string) =>
      unwrap(
        await client.POST("/v1/admin/gold/samples/{sample_batch}/label", {
          params: { path: { sample_batch: sampleBatch } },
        }),
      ),
    onSuccess: () => setMessage("AI labelling job queued for this sample batch."),
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : error.message || "The labelling job could not be queued.");
    },
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!current || current.status !== "draft" || review.isPending) return;
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key.toLowerCase() === "a") {
        event.preventDefault();
        review.mutate({ decision: "approve" });
      }
      if (event.key.toLowerCase() === "r") {
        event.preventDefault();
        setRejectDialogOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [current, review]);

  const editedFields = Object.values(stats.data?.field_edits ?? {}).reduce((total, value) => total + value, 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Gold review"
        description="Review AI labels against the source sentence before they enter the development gold set."
      />
      <div className="grid grid-cols-4 divide-x divide-border rounded-[var(--radius)] border border-border bg-card">
        <Metric label="Gold items" value={stats.data?.total ?? 0} note="All samples" />
        <Metric label="Awaiting review" value={stats.data?.by_status.draft ?? 0} note="AI drafts" />
        <Metric label="Test split" value={stats.data?.by_split.test ?? 0} note="Held from tuning" />
        <Metric label="Reviewed edits" value={editedFields} note="Changed fields" />
      </div>
      {stats.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Gold statistics unavailable</AlertTitle>
          <AlertDescription>The review queue is still usable, but its summary could not be loaded.</AlertDescription>
        </Alert>
      ) : null}
      <div className="grid min-w-0 grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)] items-start gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Review queue</CardTitle>
            <FieldGroup className="mt-3 gap-3">
              <Field>
                <FieldLabel htmlFor="gold-status">Status</FieldLabel>
                <Select
                  value={status}
                  onValueChange={(value) => {
                    setStatus(value);
                    setOffset(0);
                  }}
                >
                  <SelectTrigger id="gold-status" aria-label="Status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {statusOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field>
                  <FieldLabel htmlFor="gold-split">Split</FieldLabel>
                  <Select
                    value={split || "all"}
                    onValueChange={(value) => {
                      setSplit(value === "all" ? "" : value);
                      setOffset(0);
                    }}
                  >
                    <SelectTrigger id="gold-split" aria-label="Split">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="all">All splits</SelectItem>
                        <SelectItem value="dev">Dev</SelectItem>
                        <SelectItem value="test">Test</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="gold-section">Section</FieldLabel>
                  <Input
                    id="gold-section"
                    placeholder="All sections"
                    value={section}
                    onChange={(event) => {
                      setSection(event.target.value);
                      setOffset(0);
                    }}
                  />
                </Field>
              </div>
            </FieldGroup>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {items.isPending ? (
              <DataState state="loading" loadingLabel="Loading gold queue" />
            ) : items.isError ? (
              <DataState
                state="error"
                errorTitle="Could not load the gold queue"
                errorDescription={items.error.message}
                onRetry={() => void items.refetch()}
              />
            ) : items.data.length === 0 ? (
              <DataState
                state="empty"
                emptyTitle="No gold items match"
                emptyDescription="Try a different status, split, or section."
              />
            ) : (
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {items.data.map((item) => (
                  <li key={item.id}>
                    <Button
                      variant="ghost"
                      className={
                        "h-auto w-full justify-between gap-3 rounded-[var(--radius)] border " +
                        "border-transparent px-3 py-3 " +
                        "text-left data-[selected=true]:border-border data-[selected=true]:bg-muted"
                      }
                      data-selected={selected === item.id}
                      aria-pressed={selected === item.id}
                      onClick={() => {
                        setSelected(item.id);
                        setMessage(undefined);
                      }}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">
                          {item.section} · {item.split}
                        </span>
                        <code className="text-xs text-muted-foreground">{item.id.slice(0, 8)}</code>
                      </span>
                      <StatusBadge status={item.status} />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {!items.isPending && !items.isError && items.data.length > 0 ? (
              <div className="flex items-center justify-between gap-3 border-t border-border pt-3 text-sm">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 100))}
                >
                  Previous
                </Button>
                <span className="tabular-nums text-muted-foreground">
                  {offset + 1}–{offset + items.data.length}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={items.data.length < 100}
                  onClick={() => setOffset(offset + 100)}
                >
                  Next
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div className="min-w-0">
              <CardTitle>{current?.section_heading || "Review item"}</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {current ? `${current.section} · ${current.split}` : "Choose an item from the queue."}
              </p>
            </div>
            {current ? <StatusBadge status={current.status} /> : null}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!selected ? (
              <DataState
                state="empty"
                emptyTitle="Select a gold item"
                emptyDescription="The source sentence and its AI labels will appear here."
              />
            ) : detail.isPending ? (
              <DataState state="loading" loadingLabel="Loading gold item" />
            ) : detail.isError ? (
              <DataState
                state="error"
                errorTitle="Could not load this gold item"
                errorDescription={detail.error.message}
                onRetry={() => void detail.refetch()}
              />
            ) : current ? (
              <div className="flex flex-col gap-4">
                {current.previous_text ? (
                  <p className="text-sm text-muted-foreground">{current.previous_text}</p>
                ) : null}
                <blockquote className="border-l-2 border-border bg-muted/40 px-4 py-4 text-base leading-7">
                  {current.text}
                </blockquote>
                {current.next_text ? <p className="text-sm text-muted-foreground">{current.next_text}</p> : null}
                <Field>
                  <FieldLabel htmlFor="gold-labels">AI draft labels · edit JSON before approval</FieldLabel>
                  <Textarea
                    id="gold-labels"
                    className="min-h-64 font-mono text-xs"
                    value={labelsJson}
                    onChange={(event) => setLabelsJson(event.target.value)}
                    spellCheck={false}
                    disabled={current.status !== "draft"}
                  />
                </Field>
                {message ? (
                  <p className="text-sm text-muted-foreground" role="status">
                    {message}
                  </p>
                ) : null}
                {current.status === "pending_ai" ? (
                  <Button
                    variant="outline"
                    disabled={labelBatch.isPending}
                    onClick={() => labelBatch.mutate(current.sample_batch)}
                  >
                    Queue AI labelling for this batch
                  </Button>
                ) : null}
                {current.status === "draft" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button disabled={review.isPending} onClick={() => review.mutate({ decision: "approve" })}>
                      Approve and save edits
                    </Button>
                    <Button
                      variant="outline"
                      disabled={review.isPending}
                      onClick={() => review.mutate({ decision: "approve", useAiDraft: true })}
                    >
                      Approve AI labels
                    </Button>
                    <AlertDialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" disabled={review.isPending}>
                          Reject
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Reject this gold item?</AlertDialogTitle>
                          <AlertDialogDescription>
                            The item will be marked rejected and removed from the draft queue.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Keep item</AlertDialogCancel>
                          <AlertDialogAction
                            variant="destructive"
                            onClick={() => review.mutate({ decision: "reject" })}
                          >
                            Reject item
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                    <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                      <Kbd>A</Kbd> approve <Kbd>R</Kbd> reject
                    </span>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
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
