import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { DataState, PageHeader, SeverityBadge, StatusBadge } from "@/components/domain";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { api } from "@/shared/api";

const ROW_LIMIT = 5;

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

type Destination = "/library" | "/inbox" | "/admin";

function Figure({
  value,
  label,
  to,
  failed,
}: {
  value?: number;
  label: string;
  to: Destination;
  failed?: boolean;
}) {
  return (
    <Link to={to} className="flex flex-col gap-1 py-2">
      <span className="text-3xl font-semibold tabular-nums">{value ?? "—"}</span>
      <span className="text-sm text-muted-foreground">{failed ? `${label} (could not be loaded)` : label}</span>
    </Link>
  );
}

function RecentCard({
  title,
  to,
  linkLabel,
  children,
}: {
  title: string;
  to: Destination;
  linkLabel: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardAction>
          <Button asChild variant="ghost" size="sm">
            <Link to={to}>{linkLabel}</Link>
          </Button>
        </CardAction>
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

  const approved = patterns.data?.filter((p) => p.status === "approved").length;
  const pending = subs.data?.filter((s) => s.status === "pending");
  const clientName = (id: string) => clients.data?.find((c) => c.client_id === id)?.name ?? id;
  const active = clients.data?.filter((c) => c.status === "active").length;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Workspace"
        description="What needs review, how big the bank is, and who has been calling the API."
      />

      <section aria-label="At a glance" className="grid grid-cols-4 gap-6">
        <Figure value={pending?.length} label="Submissions awaiting review" to="/inbox" />
        <Figure value={approved} label="Approved patterns" to="/library" failed={patterns.isError} />
        <Figure value={logs.data?.length} label="API requests today" to="/admin" />
        <Figure value={active} label="Active API clients" to="/admin" failed={clients.isError} />
      </section>

      <div className="grid grid-cols-2 gap-6">
        <RecentCard title="Awaiting review" to="/inbox" linkLabel="Open inbox">
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
              emptyTitle="Nothing waiting"
              emptyDescription="New submissions from the Writing Engine appear here."
            />
          ) : (
            <Table>
              <TableBody>
                {pending.slice(0, ROW_LIMIT).map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="w-full max-w-0 truncate">{s.text}</TableCell>
                    <TableCell className="text-right">
                      {s.license_status === "unknown" || s.license_status === "restricted" || !s.user_opt_in ? (
                        <Badge variant="warning">Quarantined</Badge>
                      ) : (
                        <StatusBadge status={s.status} />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </RecentCard>

        <RecentCard title="Latest API requests" to="/admin" linkLabel="Open admin">
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
                {logs.data.slice(0, ROW_LIMIT).map((l) => (
                  <TableRow key={l.request_id}>
                    <TableCell>
                      <code className="text-sm">{l.endpoint}</code>
                      <span className="block text-sm text-muted-foreground">{clientName(l.client_id)}</span>
                    </TableCell>
                    <TableCell className="text-right">
                      {l.verdict ? (
                        <SeverityBadge value={l.verdict} />
                      ) : (
                        <Badge variant={l.status >= 400 ? "destructive" : "success"}>{l.status}</Badge>
                      )}
                      <span className="block text-sm text-muted-foreground">{fmtTime(l.at)}</span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </RecentCard>
      </div>
    </div>
  );
}
