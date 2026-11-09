import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { BarList, DataState, PageHeader, SeverityBadge } from "@/components/domain";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { api, type PatternStatus, type Section, type Submission } from "@/shared/api";
import { relativeTime } from "@/shared/lib";

const ROW_LIMIT = 5;
const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const STATUS_LABEL: Record<PatternStatus, string> = {
  approved: "Approved",
  in_review: "In review",
  draft: "Draft",
  retired: "Retired",
};

type Destination = "/phrasebank" | "/inbox" | "/admin";

const isQuarantined = (s: Submission) =>
  s.license_status === "unknown" || s.license_status === "restricted" || !s.user_opt_in;

function Figure({
  value,
  label,
  note,
  to,
  failed,
}: {
  value?: number;
  label: string;
  note?: string;
  to: Destination;
  failed?: boolean;
}) {
  return (
    <Link to={to} className="flex flex-col gap-1 py-2 text-foreground hover:no-underline">
      <span className="text-3xl font-semibold tabular-nums">{value ?? "—"}</span>
      <span className="text-sm">{failed ? `${label} (could not be loaded)` : label}</span>
      {note ? <span className="text-sm text-muted-foreground">{note}</span> : null}
    </Link>
  );
}

function Panel({
  title,
  description,
  to,
  linkLabel,
  children,
}: {
  title: string;
  description?: string;
  to?: Destination;
  linkLabel?: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
        {to ? (
          <CardAction>
            <Button asChild variant="ghost" size="sm">
              <Link to={to}>{linkLabel}</Link>
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function OverviewPage() {
  const patterns = useQuery({ queryKey: ["patterns", {}], queryFn: () => api.patterns({}) });
  const subs = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions() });
  const logs = useQuery({ queryKey: ["logs"], queryFn: api.logs });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });

  const all = patterns.data ?? [];
  const approved = patterns.data?.filter((p) => p.status === "approved").length;
  const inReview = patterns.data?.filter((p) => p.status === "in_review").length;
  const pending = subs.data?.filter((s) => s.status === "pending");
  const quarantined = pending?.filter(isQuarantined).length;
  const clientName = (id: string) => clients.data?.find((c) => c.client_id === id)?.name ?? id;
  const active = clients.data?.filter((c) => c.status === "active").length;
  const oldest = pending?.length
    ? [...pending].sort((a, b) => a.received_at.localeCompare(b.received_at))[0]
    : undefined;

  const byStatus = (Object.keys(STATUS_LABEL) as PatternStatus[]).map((status) => ({
    label: STATUS_LABEL[status],
    value: all.filter((p) => p.status === status).length,
    emphasis: status === "approved",
  }));
  const bySection = SECTIONS.map((section) => ({
    label: section,
    value: all.filter((p) => p.status === "approved" && p.section_scope.includes(section)).length,
  }));

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Workspace"
        description="What needs review, how big the bank is, and who has been calling the API."
      />

      <section aria-label="At a glance" className="grid grid-cols-4 gap-6">
        <Figure
          value={pending?.length}
          label="Submissions awaiting review"
          note={oldest ? `Oldest ${relativeTime(oldest.received_at)}` : "Queue is clear"}
          to="/inbox"
          failed={subs.isError}
        />
        <Figure
          value={approved}
          label="Approved patterns"
          note={patterns.data ? `of ${all.length} in the bank` : undefined}
          to="/phrasebank"
          failed={patterns.isError}
        />
        <Figure value={logs.data?.length} label="API requests today" to="/admin" failed={logs.isError} />
        <Figure value={active} label="Active API clients" to="/admin" failed={clients.isError} />
      </section>

      <div className="grid grid-cols-12 items-start gap-6">
        <div className="col-span-7">
          <Panel
            title="Needs attention"
            description="The next things an editor can act on."
            to="/inbox"
            linkLabel="Open inbox"
          >
            {subs.isPending ? (
              <DataState state="loading" loadingLabel="Loading submissions" />
            ) : subs.isError ? (
              <DataState
                state="error"
                errorTitle="Submissions could not be loaded"
                errorDescription="Check the connection and try again."
                onRetry={() => void subs.refetch()}
              />
            ) : !pending?.length ? (
              <DataState
                state="empty"
                emptyTitle="Nothing is waiting"
                emptyDescription="New submissions from the Writing Engine appear here."
              />
            ) : (
              <div className="flex flex-col gap-4">
                <Table>
                  <TableBody>
                    {pending.slice(0, ROW_LIMIT).map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="whitespace-normal">
                          <span className="line-clamp-2">{s.text}</span>
                          <span className="text-sm text-muted-foreground">
                            {s.kind === "frame" ? "Frame" : "Sentence"} · {relativeTime(s.received_at)}
                          </span>
                        </TableCell>
                        <TableCell className="w-32 text-right">
                          {isQuarantined(s) ? <Badge variant="warning">Quarantined</Badge> : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="text-sm text-muted-foreground">
                  {pending.length > ROW_LIMIT ? `${pending.length - ROW_LIMIT} more in the inbox. ` : ""}
                  {quarantined ? `${quarantined} quarantined for an unknown or restricted licence. ` : ""}
                  {inReview
                    ? `${inReview} ${inReview === 1 ? "pattern is" : "patterns are"} in review in phrasebank.`
                    : ""}
                </p>
              </div>
            )}
          </Panel>
        </div>

        <div className="col-span-5">
          <Panel title="The bank" description="Patterns by status, and approved patterns by manuscript section.">
            {patterns.isPending ? (
              <DataState state="loading" loadingLabel="Loading patterns" />
            ) : patterns.isError ? (
              <DataState
                state="error"
                errorTitle="Patterns could not be loaded"
                errorDescription="Check the connection and try again."
                onRetry={() => void patterns.refetch()}
              />
            ) : (
              <div className="flex flex-col gap-6">
                <BarList label="Patterns by status" items={byStatus} />
                <BarList label="Approved patterns by section" items={bySection} />
              </div>
            )}
          </Panel>
        </div>
      </div>

      <Panel title="Latest API requests" to="/admin" linkLabel="Open admin">
        {logs.isPending ? (
          <DataState state="loading" loadingLabel="Loading requests" />
        ) : logs.isError ? (
          <DataState
            state="error"
            errorTitle="Requests could not be loaded"
            errorDescription="Check the connection and try again."
            onRetry={() => void logs.refetch()}
          />
        ) : !logs.data?.length ? (
          <DataState
            state="empty"
            emptyTitle="No requests yet"
            emptyDescription="Calls from API clients appear here."
          />
        ) : (
          <Table>
            <TableBody>
              {logs.data.slice(0, ROW_LIMIT + 1).map((l) => (
                <TableRow key={l.request_id}>
                  <TableCell>
                    <code className="text-sm">{l.endpoint}</code>
                  </TableCell>
                  <TableCell>{clientName(l.client_id)}</TableCell>
                  <TableCell>
                    {l.verdict ? (
                      <SeverityBadge value={l.verdict} />
                    ) : (
                      <Badge variant={l.status >= 400 ? "destructive" : "success"}>{l.status}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{l.latency_ms} ms</TableCell>
                  <TableCell className="text-right text-muted-foreground">{relativeTime(l.at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </div>
  );
}
