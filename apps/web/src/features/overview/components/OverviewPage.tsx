import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { api } from "@/shared/api";
import { EvidenceLabel, Frame, SeverityBadge, StatusBadge, fmtTime } from "@/shared/ui";

const SECTIONS = [
  { to: "/library", title: "Library", text: "Browse every rhetorical pattern, its slots, usage contract, variants and provenance.", tag: "WB-01 / 02" },
  { to: "/playground", title: "Playground", text: "Replay a Writing Engine call — recommend, render, validate — with the exact JSON.", tag: "WB-03 / 08" },
  { to: "/inbox", title: "Inbox", text: "Review sentences and frames sent by the Writing Engine before they enter the bank.", tag: "WB-07" },
  { to: "/journals", title: "Journals", text: "Verified author guidelines kept apart from stylistic trends observed in the corpus.", tag: "WB-04" },
  { to: "/admin", title: "Admin", text: "API clients, the request log, and every entry that left or arrived in the bank.", tag: "WB-09" },
] as const;

const FLOW_OUT = [
  ["Context", "Writing sends section, intent, genre, claim and evidence level."],
  ["Hard gates", "Unapproved, unlicensed or over-claiming patterns are removed."],
  ["Ranking", "Candidates are scored with a visible breakdown and fallback tier."],
  ["Validation", "The rendered sentence is checked against V01–V08 before use."],
];
const FLOW_IN = [
  ["Submission", "Writing proposes a sentence or frame with its context."],
  ["Quarantine", "Licence and author opt-in are verified; unknown rights stay locked."],
  ["Editor review", "Near-duplicates are flagged; an editor approves, rejects or asks for revision."],
  ["Bank", "Approved entries become immutable, versioned patterns."],
];

export function OverviewPage() {
  const patterns = useQuery({ queryKey: ["patterns", {}], queryFn: () => api.patterns({}) });
  const subs = useQuery({ queryKey: ["submissions"], queryFn: () => api.submissions() });
  const logs = useQuery({ queryKey: ["logs"], queryFn: api.logs });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });

  const approved = patterns.data?.filter((p) => p.status === "approved").length;
  const pending = subs.data?.filter((s) => s.status === "pending");
  const name = (id: string) => clients.data?.find((c) => c.client_id === id)?.name ?? id;

  return (
    <div className="overview">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Rhetorical pattern bank</p>
          <h1 className="hero-title">The right phrasing for <span>every claim.</span></h1>
          <p className="lead">
            Academic Wordbank supplies the Writing Engine with approved, licence-compliant sentence patterns — matched to the
            section, rhetorical intent and strength of evidence — and never invents citations, figures or research gaps.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary btn-lg" to="/library">Explore the library <span className="arrow">→</span></Link>
            <Link className="btn btn-lg" to="/playground">Try the API <span className="arrow">↗</span></Link>
          </div>
          <ul className="hero-points">
            <li><Check /> Evidence-aware validation</li>
            <li><Check /> Traceable provenance</li>
            <li><Check /> Works with OpenAlex disabled</li>
          </ul>
        </div>

        <div className="hero-visual" aria-hidden>
          <div className="hv-card hv-main">
            <div className="hv-head"><span>Pattern GAP-014</span><span>Introduction · Gap</span></div>
            <p className="hv-frame"><Frame frame="Although {research_focus} has been examined, its behavior under {specific_condition} remains insufficiently characterized." /></p>
            <div className="hv-quote">
              <span className="hv-label">Usage contract</span>
              Requires a literature synthesis showing limited work under this condition.
            </div>
            <div className="hv-foot"><EvidenceLabel kind="observed" /><span className="hv-meta">42 uses · 31 articles</span></div>
          </div>
          <div className="hv-card hv-float">
            <span className="hv-label">Validation</span>
            <strong>pass</strong>
            <small>V01–V08 · moderate evidence</small>
          </div>
        </div>
      </section>

      <section className="kpis" aria-label="At a glance">
        <Kpi value={approved} label="Approved patterns" to="/library" />
        <Kpi value={pending?.length} label="Awaiting review" to="/inbox" tone={pending?.length ? "warn" : undefined} />
        <Kpi value={logs.data?.length} label="API requests today" to="/admin" />
        <Kpi value={clients.data?.filter((c) => c.status === "active").length} label="Active API clients" to="/admin" />
      </section>

      <section className="ov-section">
        <div className="ov-head">
          <h2>Two flows, one bank.</h2>
          <p className="lead">Data leaves the bank only through hard gates, and enters it only through editorial review.</p>
        </div>
        <div className="flows">
          <Flow title="Data out" sub="Writing Engine asks for phrasing" steps={FLOW_OUT} />
          <Flow title="Data in" sub="Writing Engine contributes phrasing" steps={FLOW_IN} />
        </div>
      </section>

      <section className="ov-section">
        <div className="ov-head"><h2>Explore the workspace.</h2></div>
        <div className="explore-grid">
          {SECTIONS.map((s) => (
            <Link key={s.to} to={s.to} className="explore-card">
              <span className="explore-tag">{s.tag}</span>
              <strong>{s.title}</strong>
              <span className="explore-text">{s.text}</span>
              <span className="explore-go">Open <span className="arrow">→</span></span>
            </Link>
          ))}
        </div>
      </section>

      <section className="ov-section">
        <div className="ov-head"><h2>Recent activity.</h2></div>
        <div className="grid-2">
          <div className="card">
            <div className="card-head"><h2>Latest API requests</h2><Link to="/admin">View log →</Link></div>
            <ul className="activity">
              {logs.data?.slice(0, 5).map((l) => (
                <li key={l.request_id}>
                  <code className="endpoint">{l.endpoint}</code>
                  <span className="activity-main">{name(l.client_id)}</span>
                  <span className="activity-side">
                    {l.verdict ? <SeverityBadge value={l.verdict} /> : l.status >= 400 ? <span className="badge badge-bad">{l.status}</span> : <span className="badge badge-ok">{l.status}</span>}
                    <small>{fmtTime(l.at)}</small>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <div className="card-head"><h2>Awaiting review</h2><Link to="/inbox">Open inbox →</Link></div>
            <ul className="activity">
              {pending?.slice(0, 5).map((s) => (
                <li key={s.id}>
                  <code className="endpoint">{s.id}</code>
                  <span className="activity-main activity-text">{s.text}</span>
                  <span className="activity-side">
                    {s.license_status === "unknown" || s.license_status === "restricted" || !s.user_opt_in
                      ? <span className="badge badge-bad">quarantined</span>
                      : <StatusBadge status={s.status} />}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

function Kpi({ value, label, to, tone }: { value?: number; label: string; to: "/library" | "/inbox" | "/admin"; tone?: "warn" }) {
  return (
    <Link to={to} className={`kpi ${tone ? `kpi-${tone}` : ""}`}>
      <span className="kpi-value">{value ?? "—"}</span>
      <span className="kpi-label">{label}</span>
    </Link>
  );
}

function Flow({ title, sub, steps }: { title: string; sub: string; steps: string[][] }) {
  return (
    <div className="flow">
      <div className="flow-head"><strong>{title}</strong><span>{sub}</span></div>
      <ol className="flow-steps">
        {steps.map(([h, t], i) => (
          <li key={h} style={{ animationDelay: `${i * 0.06}s` }}>
            <span className="flow-num">{i + 1}</span>
            <div><strong>{h}</strong><p>{t}</p></div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
