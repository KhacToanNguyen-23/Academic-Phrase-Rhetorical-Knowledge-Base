import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Fragment, useMemo, useState } from "react";

import { api, type ApiClient, type RequestLog, type Submission } from "@/shared/api";
import { pct } from "@/shared/lib";
import { Badge, Card, Empty, JsonBlock, Loading, PageHeader, SeverityBadge, Stat, StatusBadge, Tabs, fmtTime } from "@/shared/ui";

type Tab = "clients" | "log" | "out" | "in";

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("clients");
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });
  const logs = useQuery({ queryKey: ["logs"], queryFn: api.logs });
  const subs = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions() });

  if (clients.isPending || logs.isPending || subs.isPending) return <Loading />;
  const L = logs.data ?? [];
  const C = clients.data ?? [];
  const S = subs.data ?? [];
  const name = (id: string) => C.find((c) => c.client_id === id)?.name ?? id;

  const errors = L.filter((l) => l.status >= 400).length;
  const served = L.reduce((n, l) => n + l.returned_ids.length, 0);
  const recs = L.filter((l) => l.fallback_tier);
  const fallbackRate = recs.length ? recs.filter((l) => l.fallback_tier !== "journal_genre").length / recs.length : 0;
  const p95 = [...L].map((l) => l.latency_ms).sort((a, b) => a - b)[Math.floor(L.length * 0.95)] ?? 0;

  return (
    <>
      <PageHeader
        code="Administration · WB-09"
        title="Administration"
        lead="Who is calling the API, what each request asked for, which entries left the bank and which data arrived from outside. Every state change is audited."
      />
      <div className="stat-row">
        <Stat label="Requests (last 11 h)" value={L.length} note={`${C.filter((c) => c.status === "active").length} active clients`} />
        <Stat label="Entries served" value={served} note="data out" />
        <Stat label="Submissions received" value={S.length} note={`${S.filter((s) => s.status === "pending").length} awaiting review`} />
        <Stat label="Error rate" value={pct(errors / Math.max(L.length, 1))} note={`${errors} failed · p95 ${p95} ms`} tone={errors ? "warn" : "ok"} />
        <Stat label="Fallback rate" value={pct(fallbackRate)} note="below journal + genre" tone={fallbackRate > 0.3 ? "warn" : undefined} />
      </div>

      <Tabs label="Admin views" value={tab} onChange={setTab} items={[
        { id: "clients", label: "API clients", count: C.length },
        { id: "log", label: "Request log", count: L.length },
        { id: "out", label: "Data out" },
        { id: "in", label: "Data in", count: S.length },
      ]} />

      <div key={tab} className="tab-panel">
        {tab === "clients" && <Clients clients={C} logs={L} subs={S} />}
        {tab === "log" && <Log logs={L} clients={C} name={name} />}
        {tab === "out" && <DataOut logs={L} clients={C} />}
        {tab === "in" && <DataIn subs={S} name={name} />}
      </div>
    </>
  );
}

function Clients({ clients, logs, subs }: { clients: ApiClient[]; logs: RequestLog[]; subs: Submission[] }) {
  return (
    <Card title="Registered clients" aside={<span className="caption" style={{ margin: 0 }}>Service accounts with scoped API keys</span>}>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th scope="col">Client</th><th scope="col">Owner</th><th scope="col">Scopes</th><th scope="col">Requests</th><th scope="col">Errors</th><th scope="col">Served / received</th><th scope="col">Last seen</th><th scope="col">Status</th></tr></thead>
          <tbody>
            {clients.map((c) => {
              const mine = logs.filter((l) => l.client_id === c.client_id);
              return (
                <tr key={c.client_id}>
                  <td><strong className="cell-title">{c.name}</strong><br /><code className="small muted">{c.client_id}</code></td>
                  <td>{c.owner}</td>
                  <td><div className="tags" style={{ margin: 0 }}>{c.scopes.map((s) => <Badge key={s}>{s}</Badge>)}</div></td>
                  <td className="num">{mine.length}</td>
                  <td className="num">{mine.filter((l) => l.status >= 400).length}</td>
                  <td className="num">{mine.reduce((n, l) => n + l.returned_ids.length, 0)} / {subs.filter((s) => s.client_id === c.client_id).length}</td>
                  <td className="small">{fmtTime(c.last_seen)}</td>
                  <td><StatusBadge status={c.status} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Log({ logs, clients, name }: { logs: RequestLog[]; clients: ApiClient[]; name: (id: string) => string }) {
  const [client, setClient] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [open, setOpen] = useState<string>();
  const rows = logs.filter((l) => (!client || l.client_id === client) && (!endpoint || l.endpoint === endpoint));
  const endpoints = [...new Set(logs.map((l) => l.endpoint))];

  return (
    <Card title="Request log" aside={
      <div className="filter-row">
        <select aria-label="Client" value={client} onChange={(e) => setClient(e.target.value)}>
          <option value="">All clients</option>
          {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.name}</option>)}
        </select>
        <select aria-label="Endpoint" value={endpoint} onChange={(e) => setEndpoint(e.target.value)}>
          <option value="">All endpoints</option>
          {endpoints.map((e) => <option key={e}>{e}</option>)}
        </select>
      </div>
    }>
      {rows.length === 0 ? <Empty>No requests match.</Empty> : (
        <div className="table-wrap">
          <table className="table log-table">
            <thead><tr><th scope="col">Time</th><th scope="col">Client</th><th scope="col">Endpoint</th><th scope="col">Status</th><th scope="col">claim_id</th><th scope="col">Result</th><th scope="col">Latency</th></tr></thead>
            <tbody>
              {rows.map((l) => (
                <Fragment key={l.request_id}>
                  <tr className="log-row" aria-expanded={open === l.request_id} tabIndex={0}
                    onClick={() => setOpen(open === l.request_id ? undefined : l.request_id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(open === l.request_id ? undefined : l.request_id); } }}>
                    <td className="small">{fmtTime(l.at)}</td>
                    <td>{name(l.client_id)}</td>
                    <td><code className="endpoint">{l.endpoint}</code></td>
                    <td><Badge tone={l.status >= 400 ? "bad" : "ok"}>{l.status}</Badge></td>
                    <td><code className="small">{l.claim_id ?? "—"}</code></td>
                    <td className="small">
                      {l.verdict && <SeverityBadge value={l.verdict} />}
                      {l.returned_ids.length > 0 && <>↗ {l.returned_ids.join(", ")}</>}
                      {l.received_ids.length > 0 && <>↙ {l.received_ids.join(", ")}</>}
                      {l.fallback_tier && <span className="muted"> · {l.fallback_tier.replace("_", " + ")}</span>}
                    </td>
                    <td className="num small">{l.latency_ms} ms</td>
                  </tr>
                  {open === l.request_id && (
                    <tr className="log-detail">
                      <td colSpan={7}>
                        <p className="caption" style={{ marginTop: 0 }}>Request <code>{l.request_id}</code> from <code>{l.client_id}</code></p>
                        <div className="json-pair"><JsonBlock title="Request" value={l.request} /><JsonBlock title="Response" value={l.response} /></div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="caption">↗ entries served to the client · ↙ submissions received from the client. Select a row for the full payload.</p>
    </Card>
  );
}

function DataOut({ logs, clients }: { logs: RequestLog[]; clients: ApiClient[] }) {
  const rows = useMemo(() => {
    const m = new Map<string, { total: number; by: Record<string, number>; last: string }>();
    for (const l of logs) for (const id of l.returned_ids) {
      const r = m.get(id) ?? { total: 0, by: {}, last: l.at };
      r.total++;
      r.by[l.client_id] = (r.by[l.client_id] ?? 0) + 1;
      if (l.at > r.last) r.last = l.at;
      m.set(id, r);
    }
    return [...m.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [logs]);
  const max = rows[0]?.[1].total ?? 1;

  return (
    <Card title="Entries served through the API" aside={<span className="caption" style={{ margin: 0 }}>Only approved, licence-compliant entries can appear here</span>}>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th scope="col">Entry</th><th scope="col">Times served</th>{clients.filter((c) => rows.some(([, r]) => r.by[c.client_id])).map((c) => <th key={c.client_id} scope="col">{c.name}</th>)}<th scope="col">Last served</th></tr></thead>
          <tbody>
            {rows.map(([id, r]) => (
              <tr key={id}>
                <td><Link to="/library" search={{ p: id.replace(/-v\d+$/, "") }}><code>{id}</code></Link></td>
                <td><div className="inline-bar"><span style={{ width: `${(r.total / max) * 100}%` }} /><b>{r.total}</b></div></td>
                {clients.filter((c) => rows.some(([, x]) => x.by[c.client_id])).map((c) => <td key={c.client_id} className="num">{r.by[c.client_id] ?? "—"}</td>)}
                <td className="small">{fmtTime(r.last)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DataIn({ subs, name }: { subs: Submission[]; name: (id: string) => string }) {
  return (
    <Card title="Data received from clients" aside={<Link className="btn btn-ghost" to="/inbox">Open Inbox <span className="arrow">→</span></Link>}>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th scope="col">Received</th><th scope="col">Client</th><th scope="col">Submission</th><th scope="col">Kind</th><th scope="col">Licence</th><th scope="col">Opt-in</th><th scope="col">Status</th></tr></thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td className="small">{fmtTime(s.received_at)}</td>
                <td>{name(s.client_id)}</td>
                <td><code className="small">{s.id}</code><br /><span className="small muted">{s.text.length > 70 ? `${s.text.slice(0, 70)}…` : s.text}</span></td>
                <td><Badge tone="info">{s.kind}</Badge></td>
                <td><Badge tone={s.license_status === "own_authored" || s.license_status === "allowed" ? "ok" : "bad"}>{s.license_status}</Badge></td>
                <td><Badge tone={s.user_opt_in ? "ok" : "bad"}>{s.user_opt_in ? "yes" : "no"}</Badge></td>
                <td><StatusBadge status={s.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption">Raw manuscripts are not retained (STORE_MANUSCRIPT_RAW=false); only submitted sentences and frames are kept, subject to author opt-in.</p>
    </Card>
  );
}
