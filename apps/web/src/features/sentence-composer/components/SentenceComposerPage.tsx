import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { api, type EpistemicStrength, type ValidationResult } from "@/shared/api";
import { renderFrame } from "@/shared/lib";
import { Badge, Card, Empty, Field, Frame, Loading, PageHeader } from "@/shared/ui";

export function SentenceComposerPage({ patternId }: { patternId?: string }) {
  const { data: p, isPending } = useQuery({ queryKey: ["pattern", patternId], queryFn: () => api.pattern(patternId!), enabled: !!patternId });
  const journals = useQuery({ queryKey: ["journals"], queryFn: api.journals });

  const [slots, setSlots] = useState<Record<string, string>>({});
  const [frameId, setFrameId] = useState<string>("canonical");
  const [evidenceLevel, setEvidenceLevel] = useState<EpistemicStrength>("moderate");
  const [evidenceIds, setEvidenceIds] = useState("");
  const [claim, setClaim] = useState("");
  const [journalId, setJournalId] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => { setSlots({}); setFrameId("canonical"); }, [patternId]);

  const frames = useMemo(
    () => (p ? [{ id: "canonical", text: p.canonical_frame, note: "Canonical frame" }, ...p.variants.filter((v) => v.semantic_status === "equivalent").map((v) => ({ id: v.variant_id, text: v.phrase_text, note: v.transformation }))] : []),
    [p],
  );
  const frame = frames.find((f) => f.id === frameId) ?? frames[0];
  const sentence = frame ? renderFrame(frame.text, slots) : "";

  const check = useMutation({
    mutationFn: () => api.validate({
      text: sentence, section: p?.section_scope[0], claim_type: p?.claim_type, evidence_level: evidenceLevel,
      evidence_ids: evidenceIds.split(",").map((s) => s.trim()).filter(Boolean), journal_id: journalId || undefined,
    }),
  });
  // Kết quả kiểm tra cũ không còn đúng khi câu hoặc ngữ cảnh đổi.
  const { reset } = check;
  useEffect(() => { reset(); }, [reset, sentence, evidenceLevel, evidenceIds, journalId]);

  if (!patternId) {
    return (
      <>
        <PageHeader code="Section II · WB-03" title="Sentence Composer" lead="Select a pattern in the Pattern Search to begin composing." />
        <Empty>No pattern selected. <Link to="/">Return to Pattern Search →</Link></Empty>
      </>
    );
  }
  if (isPending) return <Loading />;
  if (!p) return <Empty>Pattern {patternId} could not be found.</Empty>;

  const missing = p.slots_schema.filter((s) => s.required && !slots[s.name]?.trim());
  const copy = async () => {
    await navigator.clipboard.writeText(sentence);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <>
      <PageHeader
        code={`Section II · Pattern ${p.id} v${p.version} · WB-03`}
        title="Sentence Composer"
        lead="Fill each slot with your own content. The system never generates citations, figures or research gaps on your behalf."
        actions={<Link className="btn btn-ghost" to="/patterns/$patternId" params={{ patternId: p.id }}>View pattern</Link>}
      />
      <div className="layout-split">
        <div className="stack">
          <Card title="Claim context">
            <Field label="Claim (optional)" hint="A short summary of what you intend to assert. Not stored by default.">
              <textarea rows={2} value={claim} onChange={(e) => setClaim(e.target.value)} />
            </Field>
            <Field label="Strength of available evidence">
              <select value={evidenceLevel} onChange={(e) => setEvidenceLevel(e.target.value as EpistemicStrength)}>
                <option value="low">Low — preliminary indication</option>
                <option value="moderate">Moderate — several consistent studies</option>
                <option value="high">High — strong, replicated evidence</option>
              </select>
            </Field>
            <Field label="Evidence references" hint="Comma-separated IDs of real evidence (e.g. A3-E12, doi:…).">
              <input value={evidenceIds} onChange={(e) => setEvidenceIds(e.target.value)} />
            </Field>
            <Field label="Target journal">
              <select value={journalId} onChange={(e) => setJournalId(e.target.value)}>
                <option value="">Unspecified</option>
                {journals.data?.map((j) => <option key={j.journal_id} value={j.journal_id}>{j.title}</option>)}
              </select>
            </Field>
          </Card>

          <Card title="Slots">
            {p.slots_schema.map((s) => (
              <Field key={s.name} label={`{${s.name}}${s.required ? " *" : ""}`} hint={s.guidance}>
                <input value={slots[s.name] ?? ""} onChange={(e) => setSlots((v) => ({ ...v, [s.name]: e.target.value }))} />
              </Field>
            ))}
            <p className="caption">Constraint: {p.constraint.evidence_min}.</p>
          </Card>
        </div>

        <div className="stack">
          <Card title="Compare frames" aside={<Badge>{frames.length} options</Badge>}>
            <div className="choice-list" role="radiogroup" aria-label="Choose a frame">
              {frames.map((f) => (
                <label key={f.id} className={`choice ${f.id === frame?.id ? "is-active" : ""}`}>
                  <input type="radio" name="frame" checked={f.id === frame?.id} onChange={() => setFrameId(f.id)} />
                  <span><Frame frame={f.text} values={slots} /><small className="caption" style={{ margin: 0 }}>{f.note}</small></span>
                </label>
              ))}
            </div>
          </Card>

          <Card
            title="Rendered sentence"
            aside={check.data && <span className={`verdict verdict-${check.data.verdict}`}>{check.data.verdict}</span>}
            confirm={
              <>
                <Link className="btn btn-ghost" to="/validate" search={{ text: sentence }}>Open in Validation</Link>
                <button className="btn btn-ghost" type="button" onClick={copy} disabled={missing.length > 0 || check.data?.verdict === "block"}
                  title={check.data?.verdict === "block" ? "Blocked sentences cannot be copied" : undefined}>
                  {copied ? "Copied" : "Copy"}
                </button>
                <button className="btn btn-primary" type="button" onClick={() => check.mutate()} disabled={check.isPending}>
                  {check.isPending ? "Checking…" : "Confirm & validate"} <span className="arrow">→</span>
                </button>
              </>
            }
          >
            <p className="sentence-preview">{frame && <Frame frame={frame.text} values={slots} />}</p>
            {missing.length > 0 && <p className="caption">Unfilled: {missing.map((m) => `{${m.name}}`).join(", ")}.</p>}
            {check.data && <InlineReport result={check.data} />}
          </Card>
        </div>
      </div>
    </>
  );
}

function InlineReport({ result }: { result: ValidationResult }) {
  if (result.violations.length === 0) return <p className="notice notice-ok">No issues detected across checks V01–V08.</p>;
  return (
    <ul className="violation-list compact">
      {result.violations.map((v, i) => (
        <li key={i} className={`violation sev-${v.severity}`}>
          <span className="code">{v.code}</span> {v.message} <span className="muted">→ {v.recommended_action}</span>
        </li>
      ))}
    </ul>
  );
}
