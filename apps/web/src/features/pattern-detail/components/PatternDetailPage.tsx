import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { api } from "@/shared/api";
import { Badge, Card, Empty, EvidenceLabel, Frame, Loading, PageHeader, ProvenanceTag } from "@/shared/ui";

export function PatternDetailPage({ patternId }: { patternId: string }) {
  const { data: p, isPending } = useQuery({ queryKey: ["pattern", patternId], queryFn: () => api.pattern(patternId) });
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });

  if (isPending) return <Loading />;
  if (!p) return <Empty>Pattern {patternId} could not be found.</Empty>;

  const intent = intents.data?.find((i) => i.intent_id === p.intent_id);
  const usable = p.status === "approved" && (p.license_status === "own_authored" || p.license_status === "allowed");

  return (
    <>
      <PageHeader
        code={`Pattern ${p.id} · Version ${p.version} · WB-02`}
        title={intent?.name ?? p.intent_id}
        lead={intent ? `Move: ${intent.move}. Licensed for ${p.section_scope.join(" and ")} sections of ${p.article_genres.join(", ")} articles.` : undefined}
        actions={usable
          ? <Link className="btn btn-primary" to="/compose" search={{ pattern: p.id }}>Compose with this pattern <span className="arrow">→</span></Link>
          : <Badge tone="bad">Unavailable — {p.status}, {p.license_status}</Badge>}
      />

      <div className="stack">
        <Card title="Canonical frame">
          <p className="frame-xl"><Frame frame={p.canonical_frame} /></p>
          <div className="tags">
            <Badge>{p.claim_type}</Badge>
            <Badge>{p.epistemic_strength} strength</Badge>
            {p.section_scope.map((s) => <Badge key={s}>{s}</Badge>)}
            {p.article_genres.map((g) => <Badge key={g} tone="info">{g}</Badge>)}
          </div>
        </Card>

        <div className="grid-2">
          <Card title="Slots">
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
            <p className="caption">* Required. Slots must be filled with the author’s own content.</p>
          </Card>

          <Card title="Usage contract" aside={<Badge tone="warn">FR-02.4</Badge>}>
            <dl className="kv">
              <dt>Minimum evidence</dt><dd>{p.constraint.evidence_min}</dd>
              <dt>Do not use when</dt>
              <dd>{p.constraint.forbidden_contexts.length ? <ul>{p.constraint.forbidden_contexts.map((f) => <li key={f}>{f}</li>)}</ul> : "—"}</dd>
              <dt>Note</dt><dd>{p.constraint.guidance || "—"}</dd>
            </dl>
          </Card>
        </div>

        <Card title="Variants">
          {p.variants.length === 0 ? <Empty>No variants have been recorded.</Empty> : (
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
          )}
        </Card>

        <div className="grid-2">
          <Card title="Provenance" aside={<ProvenanceTag value={p.provenance} />}>
            <dl className="kv">
              <dt>Source</dt><dd>{p.provenance_note}</dd>
              <dt>Licence</dt><dd><Badge tone={p.license_status === "restricted" || p.license_status === "unknown" ? "bad" : "ok"}>{p.license_status}</Badge></dd>
              <dt>Status</dt><dd>{p.status}, v{p.version}</dd>
            </dl>
          </Card>
          <Card title="Corpus evidence" aside={<EvidenceLabel kind="observed" />}>
            {p.corpus_support ? (
              <p style={{ margin: 0, fontFamily: "var(--serif)", fontSize: "1.05rem" }}>
                Observed <strong>{p.corpus_support.occurrences}</strong> times across <strong>{p.corpus_support.documents}</strong> articles
                ({p.corpus_support.window}).
                <span className="caption" style={{ display: "block" }}>This is a descriptive observation, not a journal requirement.</span>
              </p>
            ) : <Empty>No corpus statistics are available for this pattern.</Empty>}
          </Card>
        </div>
      </div>
    </>
  );
}
