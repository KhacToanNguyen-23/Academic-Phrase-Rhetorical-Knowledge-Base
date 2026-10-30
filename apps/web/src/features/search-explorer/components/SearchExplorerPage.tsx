import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { api, type Candidate, type ClaimType, type Genre, type RecommendationRequest, type Section } from "@/shared/api";
import { pct } from "@/shared/lib";
import { Badge, Card, Empty, FallbackNotice, Field, Frame, Loading, Meter, PageHeader, ProvenanceTag } from "@/shared/ui";

const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const GENRES: Genre[] = ["Original Research", "SLR", "Review"];
const CLAIMS: ClaimType[] = ["background", "gap", "method", "result", "implication", "limitation"];

const BREAKDOWN_LABELS: Record<keyof Candidate["breakdown"], string> = {
  intent_section: "Intent & section fit",
  disciplinary_fit: "Disciplinary fit",
  journal_genre: "Journal & genre affinity",
  evidence_alignment: "Evidence–claim alignment",
  linguistic_quality: "Linguistic quality",
  provenance_confidence: "Provenance confidence",
};

export function SearchExplorerPage() {
  const [req, setReq] = useState<RecommendationRequest>({ section: "Introduction", intent_id: "INT-GAP" });
  const set = <K extends keyof RecommendationRequest>(k: K, v: string) => setReq((r) => ({ ...r, [k]: v || undefined }));

  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const fields = useQuery({ queryKey: ["fields"], queryFn: api.fields });
  const journals = useQuery({ queryKey: ["journals"], queryFn: api.journals });
  const result = useQuery({ queryKey: ["recommend", req], queryFn: () => api.recommend(req), placeholderData: (p) => p });

  const visibleIntents = intents.data?.filter((i) => !req.section || i.sections.includes(req.section));

  return (
    <>
      <PageHeader
        code="Section I · WB-01"
        title="Pattern Search"
        lead="Specify the rhetorical context of your sentence. Only approved, licence-compliant patterns are returned, ranked with a transparent score breakdown."
      />
      <div className="layout-split">
        <form className="filters" role="search" aria-label="Pattern filters" onSubmit={(e) => e.preventDefault()}>
          <div className="filters-title">Rhetorical context</div>
          <Field label="Keyword">
            <input type="search" placeholder="e.g. remains, few studies" value={req.query ?? ""} onChange={(e) => set("query", e.target.value)} />
          </Field>
          <Field label="Manuscript section">
            <select value={req.section ?? ""} onChange={(e) => setReq((r) => ({ ...r, section: (e.target.value || undefined) as Section, intent_id: undefined }))}>
              <option value="">Any section</option>
              {SECTIONS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Rhetorical intent">
            <select value={req.intent_id ?? ""} onChange={(e) => set("intent_id", e.target.value)}>
              <option value="">Any intent</option>
              {visibleIntents?.map((i) => <option key={i.intent_id} value={i.intent_id}>{i.name}</option>)}
            </select>
          </Field>
          <Field label="Claim type">
            <select value={req.claim_type ?? ""} onChange={(e) => set("claim_type", e.target.value)}>
              <option value="">Any claim type</option>
              {CLAIMS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Article genre">
            <select value={req.genre ?? ""} onChange={(e) => set("genre", e.target.value)}>
              <option value="">Unspecified</option>
              {GENRES.map((g) => <option key={g}>{g}</option>)}
            </select>
          </Field>
          <Field label="Field">
            <select value={req.field ?? ""} onChange={(e) => set("field", e.target.value)}>
              <option value="">Unspecified</option>
              {fields.data?.map((f) => <option key={f}>{f}</option>)}
            </select>
          </Field>
          <Field label="Target journal" hint="Optional. Missing profiles fall back transparently.">
            <select value={req.journal_id ?? ""} onChange={(e) => set("journal_id", e.target.value)}>
              <option value="">Unspecified</option>
              {journals.data?.map((j) => <option key={j.journal_id} value={j.journal_id}>{j.title}</option>)}
            </select>
          </Field>
          <button type="button" className="btn btn-ghost" onClick={() => setReq({})}>Reset filters</button>
        </form>

        <div aria-live="polite">
          {result.isPending ? <Loading /> : result.data && (
            <>
              <div className="results-meta">
                <FallbackNotice tier={result.data.fallback_tier} reason={result.data.fallback_reason} />
                <p className="caption">
                  {result.data.candidates.length} candidate{result.data.candidates.length === 1 ? "" : "s"} retained;{" "}
                  {result.data.gated_out} excluded by hard gates (approval, licence). Ranking rule {result.data.rule_version}.
                </p>
              </div>
              {result.data.candidates.length === 0 ? (
                <Empty>No approved pattern matches this context. Consider relaxing a filter.</Empty>
              ) : (
                <ol className="candidate-list">
                  {result.data.candidates.map((c) => <CandidateItem key={c.pattern.id} c={c} />)}
                </ol>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

function CandidateItem({ c }: { c: Candidate }) {
  const [open, setOpen] = useState(false);
  const p = c.pattern;
  return (
    <li>
      <Card
        title={<><span className="rank">{c.rank}.</span> <Link to="/patterns/$patternId" params={{ patternId: p.id }}>{p.id}</Link></>}
        aside={<span className="score" title="Overall soft-ranking score">{pct(c.score)}<small>score</small></span>}
        confirm={
          <>
            <Link className="btn btn-ghost" to="/patterns/$patternId" params={{ patternId: p.id }}>Read details</Link>
            <Link className="btn btn-primary" to="/compose" search={{ pattern: p.id }}>Use this pattern <span className="arrow">→</span></Link>
          </>
        }
      >
        <p className="frame-lg"><Frame frame={p.canonical_frame} /></p>
        <div className="tags">
          <Badge>{p.claim_type}</Badge>
          <Badge tone={p.epistemic_strength === "high" ? "warn" : "neutral"}>{p.epistemic_strength} strength</Badge>
          {p.section_scope.map((s) => <Badge key={s}>{s}</Badge>)}
          <ProvenanceTag value={p.provenance} />
          <Badge tone="ok">v{p.version}</Badge>
        </div>
        <p className="caption">{c.explanation}</p>
        <div className="card-actions">
          <button type="button" className="btn btn-link" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "Show"} score breakdown
          </button>
        </div>
        {open && (
          <dl className="breakdown">
            {Object.entries(c.breakdown).map(([k, v]) => (
              <div key={k}>
                <dt>{BREAKDOWN_LABELS[k as keyof Candidate["breakdown"]]}</dt>
                <dd><Meter value={v} label={k} /> <span>{pct(v)}</span></dd>
              </div>
            ))}
          </dl>
        )}
      </Card>
    </li>
  );
}
