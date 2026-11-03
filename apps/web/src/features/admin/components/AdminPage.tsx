import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { SeverityBadge } from "@/components/domain/SeverityBadge";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { cn } from "@/lib/utils";
import { api, type ApiClient, type RequestLog, type Submission } from "@/shared/api";
import { createBackendClient } from "@/shared/api/contract-client";
import { ApiError, unwrap } from "@/features/slr-import/api/client";

type ApiKeySummary = {
  id: string;
  is_active: boolean;
  key_prefix: string;
  name: string;
  role: string;
};

type ApiKeyCreated = ApiKeySummary & { api_key: string };

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function adminClient(apiKey: string | null) {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      if (apiKey) request.headers.set("X-API-Key", apiKey);
      return request;
    },
  });
  return client;
}

export function AdminPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [keyRole, setKeyRole] = useState("client");
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated>();
  const [copied, setCopied] = useState(false);
  const client = useMemo(() => adminClient(auth.apiKey), [auth.apiKey]);

  const clients = useQuery({ queryKey: ["admin-clients"], queryFn: api.clients });
  const logs = useQuery({ queryKey: ["admin-logs"], queryFn: api.logs });
  const submissions = useQuery({ queryKey: ["admin-submissions"], queryFn: () => api.submissions() });
  const keys = useQuery({
    queryKey: ["admin-api-keys"],
    enabled: auth.client?.role === "admin",
    queryFn: async () => unwrap(await client.GET("/v1/admin/api-keys")) as unknown as ApiKeySummary[],
  });
  const createKey = useMutation({
    mutationFn: async () => {
      const response = await client.POST("/v1/admin/api-keys", {
        body: { name: keyName.trim(), role: keyRole as "admin" | "curator" | "reviewer" | "client" },
      });
      return unwrap(response) as unknown as ApiKeyCreated;
    },
    onSuccess: (value) => {
      setCreatedKey(value);
      setCopied(false);
      setKeyName("");
      void queryClient.invalidateQueries({ queryKey: ["admin-api-keys"] });
    },
  });

  if (auth.client?.role !== "admin") {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-medium">Administration</h1>
        <Alert variant="destructive">
          <AlertTitle>Admin role required</AlertTitle>
          <AlertDescription>
            Sign in with an admin API key to view API clients, logs, and key management.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (clients.isPending || logs.isPending || submissions.isPending) {
    return <DataState state="loading" loadingLabel="Loading administration data" />;
  }

  if (clients.isError || logs.isError || submissions.isError) {
    return (
      <DataState
        state="error"
        errorTitle="Administration data unavailable"
        errorDescription="The client, log, or submission data could not be loaded."
        onRetry={() => {
          void Promise.all([clients.refetch(), logs.refetch(), submissions.refetch()]);
        }}
      />
    );
  }

  const clientRows = clients.data ?? [];
  const logRows = logs.data ?? [];
  const submissionRows = submissions.data ?? [];
  const errorCount = logRows.filter((item) => item.status >= 400).length;
  const served = logRows.reduce((total, item) => total + item.returned_ids.length, 0);
  const fallbackRows = logRows.filter((item) => item.fallback_tier);
  const fallbackRate = fallbackRows.length
    ? fallbackRows.filter((item) => item.fallback_tier !== "journal_genre").length / fallbackRows.length
    : 0;
  const p95 = [...logRows].map((item) => item.latency_ms).sort((a, b) => a - b)[Math.floor(logRows.length * 0.95)] ?? 0;

  const closeDialog = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      setCreatedKey(undefined);
      setCopied(false);
      setKeyName("");
      createKey.reset();
    }
  };

  const copyKey = async () => {
    if (!createdKey) return;
    await navigator.clipboard.writeText(createdKey.api_key);
    setCopied(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Administration"
        description="See which clients call the API, inspect redacted request activity, and manage scoped keys."
        actions={
          <Dialog open={dialogOpen} onOpenChange={closeDialog}>
            <DialogTrigger asChild>
              <Button>Create API key</Button>
            </DialogTrigger>
            <DialogContent>
              {createdKey ? (
                <>
                  <DialogHeader>
                    <DialogTitle>API key created</DialogTitle>
                    <DialogDescription>
                      Copy this key now. It will not be shown again after this dialog closes.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="flex flex-col gap-3">
                    <code className="break-all rounded-[var(--radius)] bg-muted p-3 font-mono text-xs">
                      {createdKey.api_key}
                    </code>
                    <p className="text-sm text-muted-foreground" aria-live="polite">
                      {createdKey.name} · {createdKey.role}
                    </p>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => void copyKey()}>
                      {copied ? "Copied" : "Copy key"}
                    </Button>
                    <DialogClose asChild>
                      <Button type="button" variant="outline">
                        Done
                      </Button>
                    </DialogClose>
                  </DialogFooter>
                </>
              ) : (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    createKey.mutate();
                  }}
                >
                  <DialogHeader>
                    <DialogTitle>Create an API key</DialogTitle>
                    <DialogDescription>
                      Name the integration and grant only the role it needs. The secret appears once after creation.
                    </DialogDescription>
                  </DialogHeader>
                  <FieldGroup className="py-4">
                    <Field>
                      <FieldLabel htmlFor="key-name">Key name</FieldLabel>
                      <Input
                        id="key-name"
                        required
                        value={keyName}
                        onChange={(event) => setKeyName(event.target.value)}
                        placeholder="Notebook reviewer"
                      />
                      <FieldDescription>Use a person, service, or environment name.</FieldDescription>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="key-role">Role</FieldLabel>
                      <Select value={keyRole} onValueChange={setKeyRole}>
                        <SelectTrigger id="key-role">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem value="client">Client</SelectItem>
                            <SelectItem value="reviewer">Reviewer</SelectItem>
                            <SelectItem value="curator">Curator</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                    {createKey.isError ? (
                      <p className="text-sm text-destructive" role="alert">
                        {createKey.error instanceof ApiError
                          ? createKey.error.message
                          : "The key could not be created."}
                      </p>
                    ) : null}
                  </FieldGroup>
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button type="button" variant="outline">
                        Keep editing
                      </Button>
                    </DialogClose>
                    <Button type="submit" disabled={createKey.isPending || !keyName.trim()}>
                      {createKey.isPending ? "Creating key…" : "Create key"}
                    </Button>
                  </DialogFooter>
                </form>
              )}
            </DialogContent>
          </Dialog>
        }
      />

      <div className="grid grid-cols-5 divide-x divide-border rounded-[var(--radius)] border border-border bg-card">
        <Metric
          label="Requests"
          value={logRows.length}
          note={`${clientRows.filter((item) => item.status === "active").length} active clients`}
        />
        <Metric label="Entries served" value={served} note="approved data out" />
        <Metric
          label="Submissions"
          value={submissionRows.length}
          note={`${submissionRows.filter((item) => item.status === "pending").length} awaiting review`}
        />
        <Metric
          label="Error rate"
          value={formatPercent(errorCount / Math.max(logRows.length, 1))}
          note={`${errorCount} failed · p95 ${p95} ms`}
        />
        <Metric label="Fallback rate" value={formatPercent(fallbackRate)} note="below journal + genre" />
      </div>

      {keys.isError ? (
        <Alert variant="destructive">
          <AlertTitle>API keys unavailable</AlertTitle>
          <AlertDescription>
            The admin key list could not be loaded. Existing clients and logs remain available.
          </AlertDescription>
        </Alert>
      ) : null}

      <Tabs defaultValue="clients" className="flex flex-col gap-5">
        <TabsList aria-label="Admin views">
          <TabsTrigger value="clients">API clients ({clientRows.length})</TabsTrigger>
          <TabsTrigger value="log">Request log ({logRows.length})</TabsTrigger>
          <TabsTrigger value="keys">API keys ({keys.data?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="out">Data out</TabsTrigger>
          <TabsTrigger value="in">Data in ({submissionRows.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="clients">
          <Clients clients={clientRows} logs={logRows} submissions={submissionRows} />
        </TabsContent>
        <TabsContent value="log">
          <Log logs={logRows} clients={clientRows} />
        </TabsContent>
        <TabsContent value="keys">
          <KeysState
            keys={keys.data ?? []}
            loading={keys.isPending}
            error={keys.error}
            onRetry={() => void keys.refetch()}
          />
        </TabsContent>
        <TabsContent value="out">
          <DataOut logs={logRows} clients={clientRows} />
        </TabsContent>
        <TabsContent value="in">
          <DataIn submissions={submissionRows} clients={clientRows} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Clients({
  clients,
  logs,
  submissions,
}: {
  clients: ApiClient[];
  logs: RequestLog[];
  submissions: Submission[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Registered clients</CardTitle>
        <CardDescription>Service accounts with scoped API keys and recent activity.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Client</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead>Scopes</TableHead>
              <TableHead numeric>Requests</TableHead>
              <TableHead numeric>Errors</TableHead>
              <TableHead numeric>Served / received</TableHead>
              <TableHead numeric>Last seen</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {clients.map((item) => {
              const mine = logs.filter((log) => log.client_id === item.client_id);
              return (
                <TableRow key={item.client_id}>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <strong>{item.name}</strong>
                      <code className="font-mono text-xs text-muted-foreground">{item.client_id}</code>
                    </div>
                  </TableCell>
                  <TableCell>{item.owner}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {item.scopes.map((scope) => (
                        <Badge key={scope} variant="secondary">
                          {scope}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell numeric>{mine.length}</TableCell>
                  <TableCell numeric>{mine.filter((log) => log.status >= 400).length}</TableCell>
                  <TableCell numeric>
                    {mine.reduce((total, log) => total + log.returned_ids.length, 0)} /{" "}
                    {submissions.filter((submission) => submission.client_id === item.client_id).length}
                  </TableCell>
                  <TableCell numeric>{formatTime(item.last_seen)}</TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Log({ logs, clients }: { logs: RequestLog[]; clients: ApiClient[] }) {
  const [clientId, setClientId] = useState("all");
  const [endpoint, setEndpoint] = useState("all");
  const [open, setOpen] = useState<string>();
  const endpoints = [...new Set(logs.map((item) => item.endpoint))];
  const rows = logs.filter(
    (item) => (clientId === "all" || item.client_id === clientId) && (endpoint === "all" || item.endpoint === endpoint),
  );
  const name = (id: string) => clients.find((item) => item.client_id === id)?.name ?? id;

  return (
    <Card>
      <CardHeader className="flex-row items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <CardTitle>Request log</CardTitle>
          <CardDescription>Payload details are redacted; API keys and article text never appear here.</CardDescription>
        </div>
        <div className="flex gap-2">
          <Select value={clientId} onValueChange={setClientId}>
            <SelectTrigger aria-label="Client" className="w-44">
              <SelectValue placeholder="All clients" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All clients</SelectItem>
                {clients.map((item) => (
                  <SelectItem key={item.client_id} value={item.client_id}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Select value={endpoint} onValueChange={setEndpoint}>
            <SelectTrigger aria-label="Endpoint" className="w-52">
              <SelectValue placeholder="All endpoints" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All endpoints</SelectItem>
                {endpoints.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <DataState
            state="empty"
            emptyTitle="No requests match"
            emptyDescription="Change the client or endpoint filters."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead numeric>Time</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Endpoint</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>Result</TableHead>
                <TableHead numeric>Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((item) => (
                <LogRows
                  key={item.request_id}
                  item={item}
                  clientName={name(item.client_id)}
                  open={open === item.request_id}
                  onToggle={() => setOpen(open === item.request_id ? undefined : item.request_id)}
                />
              ))}
            </TableBody>
          </Table>
        )}
        <p className="mt-4 text-sm text-muted-foreground">
          Select a row to see a redacted request and response summary.
        </p>
      </CardContent>
    </Card>
  );
}

function LogRows({
  item,
  clientName,
  open,
  onToggle,
}: {
  item: RequestLog;
  clientName: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <TableRow
        aria-expanded={open}
        tabIndex={0}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onToggle();
          }
        }}
      >
        <TableCell numeric>{formatTime(item.at)}</TableCell>
        <TableCell>{clientName}</TableCell>
        <TableCell>
          <code className="font-mono text-xs">{item.endpoint}</code>
        </TableCell>
        <TableCell>
          <Badge variant={item.status >= 400 ? "destructive" : "success"}>{item.status}</Badge>
        </TableCell>
        <TableCell>
          <code className="font-mono text-xs">{item.claim_id ?? "—"}</code>
        </TableCell>
        <TableCell>
          <div className="flex flex-wrap items-center gap-2">
            {item.verdict ? <SeverityBadge value={item.verdict} /> : null}
            {item.returned_ids.length > 0 ? <span>{item.returned_ids.join(", ")}</span> : null}
            {item.received_ids.length > 0 ? <span>{item.received_ids.join(", ")}</span> : null}
            {item.fallback_tier ? (
              <span className="text-muted-foreground">· {item.fallback_tier.replace("_", " + ")}</span>
            ) : null}
          </div>
        </TableCell>
        <TableCell numeric>{item.latency_ms} ms</TableCell>
      </TableRow>
      {open ? (
        <TableRow>
          <TableCell colSpan={7}>
            <div className="grid grid-cols-2 gap-4 rounded-[var(--radius)] bg-muted/50 p-4">
              <RedactedJson title="Request" value={item.request} />
              <RedactedJson title="Response" value={item.response} />
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

function KeysState({
  keys,
  loading,
  error,
  onRetry,
}: {
  keys: ApiKeySummary[];
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
}) {
  if (loading) return <DataState state="loading" loadingLabel="Loading API keys" />;
  if (error) {
    return (
      <DataState state="error" errorTitle="API keys unavailable" errorDescription={error.message} onRetry={onRetry} />
    );
  }
  if (keys.length === 0) {
    return (
      <DataState
        state="empty"
        emptyTitle="No API keys listed"
        emptyDescription="Create a scoped key from the page header."
      />
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scoped API keys</CardTitle>
        <CardDescription>Only key prefixes are retained after creation. The secret is never listed.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key name</TableHead>
              <TableHead>Prefix</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {keys.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.name}</TableCell>
                <TableCell>
                  <code className="font-mono text-xs">{item.key_prefix}</code>
                </TableCell>
                <TableCell>{item.role}</TableCell>
                <TableCell>
                  <StatusBadge status={item.is_active ? "active" : "suspended"} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function DataOut({ logs, clients }: { logs: RequestLog[]; clients: ApiClient[] }) {
  const rows = new Map<string, { total: number; by: Record<string, number>; last: string }>();
  for (const log of logs) {
    for (const id of log.returned_ids) {
      const row = rows.get(id) ?? { total: 0, by: {}, last: log.at };
      row.total += 1;
      row.by[log.client_id] = (row.by[log.client_id] ?? 0) + 1;
      if (log.at > row.last) row.last = log.at;
      rows.set(id, row);
    }
  }
  const entries = [...rows.entries()].sort((a, b) => b[1].total - a[1].total);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Entries served through the API</CardTitle>
        <CardDescription>Only approved, licence-compliant entry IDs appear here.</CardDescription>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <DataState
            state="empty"
            emptyTitle="No approved entries served"
            emptyDescription="Data out will appear after a client receives an entry."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entry ID</TableHead>
                <TableHead numeric>Times served</TableHead>
                <TableHead numeric>Last served</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map(([id, row]) => (
                <TableRow key={id}>
                  <TableCell>
                    <Button asChild variant="link" className="h-auto p-0 text-xs">
                      <Link to="/library" search={{ p: id.replace(/-v\d+$/, "") }}>
                        <code className="font-mono">{id}</code>
                      </Link>
                    </Button>
                  </TableCell>
                  <TableCell numeric>{row.total}</TableCell>
                  <TableCell numeric>{formatTime(row.last)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <p className="mt-4 text-sm text-muted-foreground">Tracked across {clients.length} registered clients.</p>
      </CardContent>
    </Card>
  );
}

function DataIn({ submissions, clients }: { submissions: Submission[]; clients: ApiClient[] }) {
  const name = (id: string) => clients.find((item) => item.client_id === id)?.name ?? id;
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <CardTitle>Data received from clients</CardTitle>
          <CardDescription>Submission metadata is shown without raw article text.</CardDescription>
        </div>
        <Button asChild variant="outline">
          <Link to="/inbox">Open Inbox</Link>
        </Button>
      </CardHeader>
      <CardContent>
        {submissions.length === 0 ? (
          <DataState
            state="empty"
            emptyTitle="No submissions received"
            emptyDescription="Incoming submissions will appear here."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead numeric>Received</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Submission ID</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Licence</TableHead>
                <TableHead>Opt-in</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {submissions.map((item) => (
                <TableRow key={item.id}>
                  <TableCell numeric>{formatTime(item.received_at)}</TableCell>
                  <TableCell>{name(item.client_id)}</TableCell>
                  <TableCell>
                    <code className="font-mono text-xs">{item.id}</code>
                  </TableCell>
                  <TableCell>{item.kind}</TableCell>
                  <TableCell>
                    <StatusBadge status={item.license_status} />
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.user_opt_in ? "success" : "destructive"}>
                      {item.user_opt_in ? "Yes" : "No"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function RedactedJson({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <h3 className="text-sm font-medium">{title}</h3>
      <pre
        className={cn(
          "max-h-56 overflow-auto whitespace-pre-wrap break-words",
          "rounded-[var(--radius)] bg-background p-3 font-mono text-xs",
        )}
      >
        {JSON.stringify(redact(value), null, 2)}
      </pre>
    </div>
  );
}

function redact(value: unknown): unknown {
  if (typeof value === "string") return "[redacted]";
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => {
      const normalized = key.toLowerCase();
      if (
        normalized === "api_key" ||
        normalized === "apikey" ||
        normalized === "text" ||
        normalized.includes("content")
      ) {
        return [key, "[redacted]"];
      }
      return [key, redact(child)];
    }),
  );
}

function Metric({ label, value, note }: { label: string; value: number | string; note: string }) {
  return (
    <div className="flex min-h-24 flex-col justify-center gap-1 px-4 py-3 first:pl-5 last:pr-5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <strong className="text-2xl font-medium tabular-nums">{value}</strong>
      <span className="text-xs text-muted-foreground">{note}</span>
    </div>
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatTime(value: string) {
  return dateFormat.format(new Date(value));
}
