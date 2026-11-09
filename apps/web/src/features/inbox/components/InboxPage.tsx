import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { PhraseFrame } from "@/components/domain/PhraseFrame";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { api, type Submission, type SubmissionStatus } from "@/shared/api";
import { pct } from "@/shared/lib";

type Filter = SubmissionStatus | "all";

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "pending", label: "Awaiting review" },
  { id: "approved", label: "Approved" },
  { id: "revision", label: "Revision requested" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];

function formatReceivedAt(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function InboxPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [selectedId, setSelectedId] = useState<string>();
  const [query, setQuery] = useState("");
  const all = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions() });
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });

  if (all.isPending || intents.isPending || clients.isPending) {
    return <DataState state="loading" loadingLabel="Loading inbox" />;
  }

  if (all.isError || intents.isError || clients.isError) {
    return (
      <DataState
        state="error"
        errorTitle="Could not load the inbox"
        errorDescription="We couldn't reach the submission, intent, or client data. Try again."
        onRetry={() => void Promise.all([all.refetch(), intents.refetch(), clients.refetch()])}
      />
    );
  }

  const count = (status: Filter) =>
    all.data.filter((submission) => status === "all" || submission.status === status).length;
  const needle = query.trim().toLowerCase();
  const items = all.data.filter(
    (submission) =>
      (filter === "all" || submission.status === filter) &&
      (!needle || `${submission.id} ${submission.text}`.toLowerCase().includes(needle)),
  );
  const selected = items.find((submission) => submission.id === selectedId) ?? items[0];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Inbox"
        description="Review submissions before an editor-approved frame or sentence enters the phrase bank."
      />
      <Tabs
        value={filter}
        onValueChange={(value) => {
          setFilter(value as Filter);
          setSelectedId(undefined);
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <TabsList aria-label="Submission status" className="max-w-full flex-wrap justify-start group-data-horizontal/tabs:h-auto">
            {FILTERS.map((item) => (
              <TabsTrigger key={item.id} value={item.id}>
                {item.label}
                <Badge variant="secondary">{count(item.id)}</Badge>
              </TabsTrigger>
            ))}
          </TabsList>
          <Input
            type="search"
            aria-label="Search submissions"
            placeholder="Search text or ID"
            className="w-64"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelectedId(undefined);
            }}
          />
        </div>
        <TabsContent value={filter} className="pt-4">
          {items.length === 0 ? (
            <DataState
              state="empty"
              emptyTitle={needle ? "No submissions match this search" : "Nothing needs attention here"}
              emptyDescription={
                needle
                  ? "Try another word or clear the search."
                  : "Submissions will appear when the Writing Engine sends them."
              }
            />
          ) : (
            <div className="grid min-w-0 grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] [&>*]:min-w-0">
              <Card>
                <CardHeader>
                  <CardTitle>Submissions</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {items.length} {items.length === 1 ? "submission" : "submissions"} in this view
                  </p>
                </CardHeader>
                <CardContent className="p-0">
                  <ol className="m-0 flex list-none flex-col gap-px p-0">
                    {items.map((submission) => (
                      <SubmissionRow
                        key={submission.id}
                        submission={submission}
                        selected={submission.id === selected?.id}
                        onSelect={() => setSelectedId(submission.id)}
                      />
                    ))}
                  </ol>
                </CardContent>
              </Card>
              {selected ? (
                <SubmissionDetail
                  submission={selected}
                  intent={
                    intents.data.find((item) => item.intent_id === selected.context.intent_id)?.name ??
                    selected.context.intent_id
                  }
                  client={
                    clients.data.find((item) => item.client_id === selected.client_id)?.name ?? selected.client_id
                  }
                />
              ) : null}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SubmissionRow({
  submission,
  selected,
  onSelect,
}: {
  submission: Submission;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        className={
          "flex w-full min-w-0 flex-col gap-2 border-b border-border px-4 py-3 text-left outline-none " +
          "transition-colors last:border-0 hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring/50 " +
          "data-[selected=true]:bg-muted"
        }
        data-selected={selected}
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
      >
        <span className="flex min-w-0 items-center justify-between gap-3">
          <code className="truncate text-xs text-muted-foreground">{submission.id}</code>
          <StatusBadge status={submission.status} />
        </span>
        <span className="truncate text-sm font-medium text-foreground">{submission.kind} submission</span>
        <span className="text-xs text-muted-foreground">{formatReceivedAt(submission.received_at)}</span>
      </button>
    </li>
  );
}

function SubmissionDetail({ submission, intent, client }: { submission: Submission; intent: string; client: string }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string>();
  const decide = useMutation({
    mutationFn: (status: Exclude<SubmissionStatus, "pending">) => api.decide(submission.id, status),
    onSuccess: (_, status) => {
      const text = status === "approved" ? "Submission approved into the phrase bank." : "Submission decision saved.";
      setMessage(text);
      toast.success(text);
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
    },
    onError: (error: Error) => {
      const text = error.message || "The decision could not be saved. Try again.";
      setMessage(text);
      toast.error(text);
    },
  });
  const blocked =
    submission.license_status === "unknown" || submission.license_status === "restricted" || !submission.user_opt_in;
  const isPending = submission.status === "pending";

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="min-w-0">
          <CardTitle>Submission detail</CardTitle>
          <p className="mt-1 truncate text-sm text-muted-foreground">{submission.id}</p>
        </div>
        <StatusBadge status={submission.status} />
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <PhraseFrame frame={submission.text} className="text-xl" />
        <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
          <dt className="text-muted-foreground">From</dt>
          <dd>
            {client} · {formatReceivedAt(submission.received_at)}
          </dd>
          <dt className="text-muted-foreground">Context</dt>
          <dd>
            {intent} · {submission.context.section}
            {submission.context.genre ? ` · ${submission.context.genre}` : ""}
            {submission.context.field ? ` · ${submission.context.field}` : ""}
          </dd>
          {submission.claim_id ? (
            <>
              <dt className="text-muted-foreground">Claim ID</dt>
              <dd>
                <code>{submission.claim_id}</code>
              </dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Licence</dt>
          <dd className="flex flex-wrap gap-2">
            <Badge variant={blocked ? "destructive" : "success"}>{submission.license_status}</Badge>
            <Badge variant={submission.user_opt_in ? "success" : "destructive"}>
              {submission.user_opt_in ? "Author opted in" : "No author opt-in"}
            </Badge>
          </dd>
        </dl>
        {submission.near_duplicate ? (
          <Alert>
            <AlertTitle>Similar pattern found</AlertTitle>
            <AlertDescription>
              <Link to="/phrasebank/pattern/$id" params={{ id: submission.near_duplicate.pattern_id }}>
                {submission.near_duplicate.pattern_id}
              </Link>{" "}
              is {pct(submission.near_duplicate.similarity)} similar. Consider adding a variant instead.
            </AlertDescription>
          </Alert>
        ) : null}
        {blocked && isPending ? (
          <Alert variant="destructive">
            <AlertTitle>Approval is locked</AlertTitle>
            <AlertDescription>
              Licence clearance and author opt-in are required before this submission can enter the bank.
            </AlertDescription>
          </Alert>
        ) : null}
        {message ? (
          <p className="text-sm text-muted-foreground" role="status">
            {message}
          </p>
        ) : null}
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={decide.isPending || blocked}
              title={blocked ? "Licence clearance or author opt-in is missing" : undefined}
              onClick={() => decide.mutate("approved")}
            >
              Approve into bank
            </Button>
            <Button variant="outline" disabled={decide.isPending} onClick={() => decide.mutate("revision")}>
              Request revision
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" disabled={decide.isPending}>
                  Reject
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reject this submission?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The submission will leave the pending review queue. You can still see the decision in the rejected
                    view.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Keep submission</AlertDialogCancel>
                  <AlertDialogAction variant="destructive" onClick={() => decide.mutate("rejected")}>
                    Reject submission
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
