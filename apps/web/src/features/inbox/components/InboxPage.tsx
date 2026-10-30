import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { api, type Submission, type SubmissionStatus } from "@/shared/api";
import { pct } from "@/shared/lib";
import { Badge, Card, Empty, Frame, Loading, PageHeader, StatusBadge, Tabs, fmtTime } from "@/shared/ui";

type Filter = SubmissionStatus | "all";

export function InboxPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const all = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions() });
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });

  const count = (s: Filter) => all.data?.filter((x) => s === "all" || x.status === s).length ?? 0;
  const items = all.data?.filter((x) => filter === "all" || x.status === filter) ?? [];

  return (
    <>
      <PageHeader
        code="Incoming data · WB-07"
        title="Inbox"
        lead="Sentences and frames received from the Writing Engine. Nothing enters the bank until an editor approves it; quarantined licences can never be published."
      />
      <Tabs label="Submission status" value={filter} onChange={setFilter} items={[
        { id: "pending", label: "Awaiting review", count: count("pending") },
        { id: "approved", label: "Approved", count: count("approved") },
        { id: "revision", label: "Revision requested", count: count("revision") },
        { id: "rejected", label: "Rejected", count: count("rejected") },
        { id: "all", label: "All", count: count("all") },
      ]} />
      {all.isPending ? <Loading /> : items.length === 0 ? <Empty>Nothing here.</Empty> : (
        <ol className="candidate-list" key={filter}>
          {items.map((s) => (
            <li key={s.id}>
              <SubmissionItem s={s}
                intent={intents.data?.find((i) => i.intent_id === s.context.intent_id)?.name ?? s.context.intent_id}
                client={clients.data?.find((c) => c.client_id === s.client_id)?.name ?? s.client_id} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function SubmissionItem({ s, intent, client }: { s: Submission; intent: string; client: string }) {
  const qc = useQueryClient();
  const decide = useMutation({
    mutationFn: (status: Exclude<SubmissionStatus, "pending">) => api.decide(s.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["submissions"] }),
  });
  // BR-10: licence unknown/restricted bị cách ly; FR-09.6: không dùng câu của user khi chưa opt-in.
  const blocked = s.license_status === "unknown" || s.license_status === "restricted" || !s.user_opt_in;

  return (
    <Card
      title={<><code>{s.id}</code> <Badge tone="info">{s.kind}</Badge></>}
      aside={<StatusBadge status={s.status} />}
      confirm={s.status === "pending" && (
        <>
          <button type="button" className="btn btn-ghost" onClick={() => decide.mutate("rejected")} disabled={decide.isPending}>Reject</button>
          <button type="button" className="btn btn-ghost" onClick={() => decide.mutate("revision")} disabled={decide.isPending}>Request revision</button>
          <button type="button" className="btn btn-primary" onClick={() => decide.mutate("approved")} disabled={decide.isPending || blocked}
            title={blocked ? "Quarantined: licence or opt-in missing" : undefined}>
            Approve into bank <span className="arrow">→</span>
          </button>
        </>
      )}
    >
      <p className="frame-lg"><Frame frame={s.text} /></p>
      <dl className="kv kv-inline">
        <dt>From</dt><dd>{client} · {fmtTime(s.received_at)}</dd>
        <dt>Context</dt><dd>{intent} · {s.context.section}{s.context.genre ? ` · ${s.context.genre}` : ""}{s.context.field ? ` · ${s.context.field}` : ""}</dd>
        {s.claim_id && <><dt>claim_id</dt><dd><code>{s.claim_id}</code></dd></>}
        <dt>Licence</dt>
        <dd>
          <Badge tone={blocked ? "bad" : "ok"}>{s.license_status}</Badge>{" "}
          <Badge tone={s.user_opt_in ? "ok" : "bad"}>{s.user_opt_in ? "author opted in" : "no opt-in"}</Badge>
        </dd>
        {s.decided_by && <><dt>Decided by</dt><dd>{s.decided_by}</dd></>}
      </dl>
      {s.near_duplicate && (
        <p className="notice notice-warn">
          Near-duplicate of <Link to="/library" search={{ p: s.near_duplicate.pattern_id }}>{s.near_duplicate.pattern_id}</Link> ({pct(s.near_duplicate.similarity)} similar).
          Consider adding it as a variant instead of a new pattern.
        </p>
      )}
      {blocked && s.status === "pending" && <p className="notice notice-warn">Quarantined — cannot be approved until licence and author opt-in are confirmed (BR-10, FR-09.6).</p>}
    </Card>
  );
}
