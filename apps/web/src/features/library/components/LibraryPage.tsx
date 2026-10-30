import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { api, type PatternQuery, type PatternStatus, type PhrasePattern, type Section } from "@/shared/api";
import { Badge, Card, Empty, EvidenceLabel, Frame, Loading, PageHeader, ProvenanceTag, StatusBadge } from "@/shared/ui";

const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const STATUSES: PatternStatus[] = ["approved", "in_review", "draft", "retired"];

export function LibraryPage({ selectedId }: { selectedId?: string }) {
  const [f, setF] = useState<PatternQuery>({});
  const navigate = useNavigate();
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const list = useQuery({ queryKey: ["patterns", f], queryFn: () => api.patterns(f), placeholderData: (p) => p });

  const activeId = selectedId ?? list.data?.[0]?.id;
  const intentName = (id: string) => intents.data?.find((i) => i.intent_id === id)?.name ?? id;

  return (
    <>
      <PageHeader
        code="Pattern bank · WB-01 / WB-02"
        title="Library"
        lead="The bank of rhetorical patterns served to the Writing Engine. Only approved, licence-compliant entries are ever returned through the API."
      />
      <div className="library">
        <div className="library-list">
          <div className="library-filters" role="search">
            <input type="search" aria-label="Search patterns" placeholder="Search frames or IDs…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value || undefined })} />
            <div className="filter-row">
              <select aria-label="Section" value={f.section ?? ""} onChange={(e) => setF({ ...f, section: (e.target.value || undefined) as Section })}>
                <option value="">All sections</option>
                {SECTIONS.map((s) => <option key={s}>{s}</option>)}
              </select>
              <select aria-label="Status" value={f.status ?? ""} onChange={(e) => setF({ ...f, status: (e.target.value || undefined) as PatternStatus })}>
                <option value="">All statuses</option>
                {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
            <p className="caption" style={{ margin: 0 }}>{list.data?.length ?? 0} entries</p>
          </div>
          {list.isPending ? <Loading /> : (
            <ul className="entry-list">
              {list.data?.map((p, i) => (
                <li key={p.id} style={{ animationDelay: `${i * 0.04}s` }}>
                  <button type="button" className="entry" aria-current={p.id === activeId} onClick={() => navigate({ to: "/library", search: { p: p.id } })}>
                    <span className="entry-head"><code>{p.id}</code><StatusBadge status={p.status} /></span>
                    <span className="entry-frame"><Frame frame={p.canonical_frame} /></span>
                    <span className="entry-meta">{intentName(p.intent_id)} · {p.section_scope.join(", ")}</span>
                  </button>
                </li>
              ))}
              {list.data?.length === 0 && <Empty>No entries match.</Empty>}
            </ul>
          )}
        </div>
        <div className="library-detail" key={activeId}>
          {activeId ? <Detail id={activeId} intentName={intentName} /> : <Empty>Select an entry.</Empty>}
        </div>
      </div>
    </>
  );
}

function Detail({ id, intentName }: { id: string; intentName: (id: string) => string }) {
  const { data: p, isPending } = useQuery({ queryKey: ["pattern", id], queryFn: () => api.pattern(id) });
  if (isPending) return <Loading />;
  if (!p) return <Empty>Pattern {id} could not be found.</Empty>;
  const servable = p.status === "approved" && (p.license_status === "own_authored" || p.license_status === "allowed");

  return (
    <div className="stack">
      <Card
        title={<>{intentName(p.intent_id)}</>}
        aside={<span className="caption" style={{ margin: 0 }}>{p.id} · v{p.version}</span>}
        confirm={servable && <Link className="btn btn-primary" to="/playground" search={{ pattern: p.id }}>Try in Playground <span className="arrow">→</span></Link>}
      >
        <p className="frame-xl"><Frame frame={p.canonical_frame} /></p>
        <div className="tags">
          <StatusBadge status={p.status} />
          <Badge>{p.claim_type}</Badge>
          <Badge>{p.epistemic_strength} strength</Badge>
          {p.section_scope.map((s) => <Badge key={s}>{s}</Badge>)}
          {p.article_genres.map((g) => <Badge key={g} tone="info">{g}</Badge>)}
        </div>
        <p className={`notice ${servable ? "notice-ok" : "notice-warn"}`}>
          {servable ? "Servable via API — passes approval and licence gates." : `Not servable via API — ${p.status !== "approved" ? `status is ${p.status}` : `licence is ${p.license_status}`}.`}
        </p>
      </Card>

      <div className="grid-2">
        <Card title="Slots">
          <SlotTable p={p} />
        </Card>
        <Card title="Usage contract" aside={<Badge tone="warn">FR-02.4</Badge>}>
          <dl className="kv">
            <dt>Minimum evidence</dt><dd>{p.constraint.evidence_min}</dd>
            <dt>Do not use when</dt>
            <dd>{p.constraint.forbidden_contexts.length ? <ul>{p.constraint.forbidden_contexts.map((x) => <li key={x}>{x}</li>)}</ul> : "—"}</dd>
            <dt>Note</dt><dd>{p.constraint.guidance || "—"}</dd>
          </dl>
        </Card>
      </div>

      {p.variants.length > 0 && (
        <Card title="Variants">
          <ul className="variant-list">
            {p.variants.map((v) => (
              <li key={v.variant_id}>
                <Frame frame={v.phrase_text} />
                <div className="tags">
                  <span className="caption" style={{ margin: 0 }}>{v.transformation}</span>
                  <Badge tone={v.semantic_status === "equivalent" ? "ok" : "warn"}>{v.semantic_status === "equivalent" ? "Equivalence approved" : "Pending semantic review"}</Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid-2">
        <Card title="Provenance" aside={<ProvenanceTag value={p.provenance} />}>
          <dl className="kv">
            <dt>Source</dt><dd>{p.provenance_note}</dd>
            <dt>Licence</dt><dd><Badge tone={p.license_status === "restricted" || p.license_status === "unknown" ? "bad" : "ok"}>{p.license_status}</Badge></dd>
          </dl>
        </Card>
        <Card title="Corpus evidence" aside={<EvidenceLabel kind="observed" />}>
          {p.corpus_support ? (
            <p className="prose">
              Observed <strong>{p.corpus_support.occurrences}</strong> times across <strong>{p.corpus_support.documents}</strong> articles ({p.corpus_support.window}).
              <span className="caption" style={{ display: "block" }}>A descriptive observation, not a journal requirement.</span>
            </p>
          ) : <Empty>No corpus statistics.</Empty>}
        </Card>
      </div>
    </div>
  );
}

function SlotTable({ p }: { p: PhrasePattern }) {
  return (
    <table className="table">
      <thead><tr><th scope="col">Slot</th><th scope="col">Type</th><th scope="col">Guidance</th></tr></thead>
      <tbody>
        {p.slots_schema.map((s) => (
          <tr key={s.name}>
            <td><code>{`{${s.name}}`}</code>{s.required && <span className="req" title="required"> *</span>}</td>
            <td>{s.type}</td>
            <td>{s.guidance}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
